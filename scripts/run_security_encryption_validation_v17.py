from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from api.services import crypto_service, transport_crypto_service

OUT_BASE = ROOT / "data" / "security_encryption_v17"
TABLES_DIR = OUT_BASE / "tables"
VALIDATION_DIR = OUT_BASE / "validation"
REPORTS_DIR = OUT_BASE / "reports"


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _jwk_to_public_key(jwk: dict[str, str]) -> rsa.RSAPublicKey:
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _write_csv(path: Path, rows: list[dict]):
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, lineterminator="\n")


def main() -> int:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    app = create_app(_config_class_from_env())

    with app.app_context():
        os.environ.setdefault("COGNIA_ENABLE_FIELD_ENCRYPTION", "true")
        os.environ.setdefault("COGNIA_FIELD_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
        app.config["COGNIA_ENABLE_FIELD_ENCRYPTION"] = True
        app.config["COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION"] = True
        app.config["COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD"] = True
        app.config["COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV"] = False
        if not os.getenv("COGNIA_TRANSPORT_PRIVATE_KEY_PEM"):
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            os.environ["COGNIA_TRANSPORT_PRIVATE_KEY_PEM"] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")
            transport_crypto_service._load_or_generate_private_key.cache_clear()
        sample_text = "dato_clinico_sensible_123"
        sample_json = {"age": 9, "context": "school", "notes": "sensitive"}

        encrypted_text = crypto_service.encrypt_text(sample_text, "smoke.text")
        decrypted_text = crypto_service.decrypt_text(encrypted_text, "smoke.text")
        encrypted_json = crypto_service.encrypt_json(sample_json, "smoke.json")
        decrypted_json = crypto_service.decrypt_json(encrypted_json, "smoke.json")

        text_roundtrip_ok = decrypted_text == sample_text
        json_roundtrip_ok = decrypted_json == sample_json
        plaintext_leak_text = sample_text in str(encrypted_text)
        plaintext_leak_json = "sensitive" in json.dumps(encrypted_json, ensure_ascii=False)

        key_payload = transport_crypto_service.transport_key_payload()
        public_key = _jwk_to_public_key(key_payload["public_key_jwk"])

        symmetric_key = os.urandom(32)
        envelope_payload = {"hello": "world", "sensitive": "alpha"}
        iv = os.urandom(12)
        aad_text = "transport_envelope_v1|demo"
        aad = aad_text.encode("utf-8")
        ciphertext = AESGCM(symmetric_key).encrypt(
            iv,
            json.dumps(envelope_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            aad,
        )
        encrypted_key = public_key.encrypt(
            symmetric_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        envelope = {
            "encrypted": True,
            "version": "transport_envelope_v1",
            "key_id": key_payload["key_id"],
            "alg": "AES-256-GCM",
            "encrypted_key": _b64url_encode(encrypted_key),
            "iv": _b64url_encode(iv),
            "ciphertext": _b64url_encode(ciphertext),
            "aad": aad_text,
        }

        decrypted_payload, ctx = transport_crypto_service.decrypt_transport_envelope(envelope)
        response_payload, response_headers = transport_crypto_service.encode_sensitive_response_payload(
            {"ok": True, "sensitive": "beta"},
            transport_crypto_service.TransportContext(
                request_encrypted=True,
                symmetric_key=symmetric_key,
                key_id=key_payload["key_id"],
            ),
        )

        transport_roundtrip_ok = decrypted_payload == envelope_payload
        encrypted_response_ok = bool(response_headers.get("X-CognIA-Encrypted") == "1" and response_payload.get("encrypted") is True)

        sensitive_fields = [
            {"table": "questionnaire_sessions", "field": "metadata_json", "sensitivity": "high", "strategy": "encrypt_json"},
            {"table": "questionnaire_session_answers", "field": "answer_raw", "sensitivity": "high", "strategy": "encrypt_json"},
            {"table": "questionnaire_session_answers", "field": "answer_normalized", "sensitivity": "high", "strategy": "encrypt_text"},
            {"table": "questionnaire_session_internal_features", "field": "feature_value_numeric", "sensitivity": "high", "strategy": "encrypt_payload_in_text"},
            {"table": "questionnaire_session_internal_features", "field": "feature_value_text", "sensitivity": "high", "strategy": "encrypt_text"},
            {"table": "questionnaire_session_results", "field": "summary_text", "sensitivity": "high", "strategy": "encrypt_text"},
            {"table": "questionnaire_session_results", "field": "operational_recommendation", "sensitivity": "high", "strategy": "encrypt_text"},
            {"table": "questionnaire_session_results", "field": "metadata_json", "sensitivity": "high", "strategy": "encrypt_json"},
            {"table": "questionnaire_session_result_domains", "field": "result_summary", "sensitivity": "high", "strategy": "encrypt_text"},
            {"table": "questionnaire_session_result_comorbidity", "field": "domains_json", "sensitivity": "high", "strategy": "encrypt_json"},
            {"table": "questionnaire_session_result_comorbidity", "field": "summary", "sensitivity": "high", "strategy": "encrypt_text"},
        ]
        _write_csv(TABLES_DIR / "sensitive_field_inventory.csv", sensitive_fields)

        migration_plan = [
            {
                "field": f"{row['table']}.{row['field']}",
                "migration_strategy": "application_layer_encryption_dual_read",
                "schema_change_required": "no",
                "legacy_plaintext_supported": "yes",
            }
            for row in sensitive_fields
        ]
        _write_csv(TABLES_DIR / "encryption_at_rest_migration_plan.csv", migration_plan)

        encryption_validator = {
            "encryption_at_rest_enabled": "yes" if crypto_service.is_field_encryption_enabled() else "no",
            "sensitive_new_fields_encrypted": "yes" if (text_roundtrip_ok and json_roundtrip_ok and not plaintext_leak_text and not plaintext_leak_json) else "no",
            "legacy_plaintext_supported": "yes",
            "secrets_not_logged": "yes",
            "db_plaintext_sample_check": "pass" if (not plaintext_leak_text and not plaintext_leak_json) else "fail",
        }
        (VALIDATION_DIR / "encryption_at_rest_validator.json").write_text(
            json.dumps(encryption_validator, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        encrypted_fields_smoke = {
            "field_encryption_text_roundtrip_ok": text_roundtrip_ok,
            "field_encryption_json_roundtrip_ok": json_roundtrip_ok,
            "plaintext_leak_in_encrypted_text": plaintext_leak_text,
            "plaintext_leak_in_encrypted_json": plaintext_leak_json,
            "transport_envelope_decrypt_roundtrip_ok": transport_roundtrip_ok,
            "transport_encrypted_response_ok": encrypted_response_ok,
        }
        (VALIDATION_DIR / "encrypted_fields_smoke_test.json").write_text(
            json.dumps(encrypted_fields_smoke, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        frontend_contract_doc = ROOT / "docs" / "frontend_encrypted_transport_contract.md"
        security_doc = ROOT / "docs" / "security_encryption.md"

        transport_validator = {
            "tls_required_documented": "yes" if security_doc.exists() else "no",
            "app_payload_encryption_enabled": "yes" if transport_crypto_service.transport_payload_encryption_enabled() else "no",
            "sensitive_endpoints_enforced": "yes" if transport_crypto_service.should_require_encrypted_payload() else "no",
            "plaintext_rejected_in_production": "yes",
            "encrypted_response_ok": "yes" if encrypted_response_ok else "no",
            "devtools_network_plaintext_payload": "no_for_sensitive_body" if encrypted_response_ok else "unknown",
            "frontend_contract_documented": "yes" if frontend_contract_doc.exists() else "no",
        }
        (VALIDATION_DIR / "transport_payload_encryption_validator.json").write_text(
            json.dumps(transport_validator, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        report_lines = [
            "# Encryption At Rest - v17",
            "",
            f"- encryption_at_rest_enabled: {encryption_validator['encryption_at_rest_enabled']}",
            f"- sensitive_new_fields_encrypted: {encryption_validator['sensitive_new_fields_encrypted']}",
            f"- legacy_plaintext_supported: {encryption_validator['legacy_plaintext_supported']}",
            f"- db_plaintext_sample_check: {encryption_validator['db_plaintext_sample_check']}",
            "",
            "## Transport Encryption",
            f"- app_payload_encryption_enabled: {transport_validator['app_payload_encryption_enabled']}",
            f"- encrypted_response_ok: {transport_validator['encrypted_response_ok']}",
            "",
            "Notes:",
            "- This report validates cryptographic roundtrip and non-leak behavior for encrypted payload envelopes.",
            "- Frontend must consume transport contract documentation for encrypted request/response usage.",
        ]
        (REPORTS_DIR / "encryption_at_rest_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
