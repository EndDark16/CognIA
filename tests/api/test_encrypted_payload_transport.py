import base64
import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import questionnaire_v2_loader_service as loader_service
from app.models import AppUser, db
from config.settings import TestingConfig


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding_str = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding_str).encode("utf-8"))


def _jwk_to_public_key(jwk: dict[str, str]) -> rsa.RSAPublicKey:
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _encrypt_envelope(payload: dict, key_payload: dict):
    public_key = _jwk_to_public_key(key_payload["public_key_jwk"])
    symmetric_key = os.urandom(32)
    iv = os.urandom(12)
    aad_text = "transport_envelope_v1|pytest"
    aad = aad_text.encode("utf-8")
    ciphertext = AESGCM(symmetric_key).encrypt(
        iv,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
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
    return envelope, symmetric_key


def _decrypt_encrypted_response(payload: dict, symmetric_key: bytes) -> dict:
    iv = _b64url_decode(payload["iv"])
    ciphertext = _b64url_decode(payload["ciphertext"])
    aad = str(payload.get("aad") or "").encode("utf-8")
    data = AESGCM(symmetric_key).decrypt(iv, ciphertext, aad)
    return json.loads(data.decode("utf-8"))


def _build_source(tmp_path: Path) -> Path:
    source = tmp_path / "cuestionario_v16.4"
    source.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "scale_id": "FREQ_0_3",
                "scale_name": "Frecuencia",
                "response_type": "single_choice",
                "response_options_json": '[{"value": 0, "label": "Nunca"}, {"value": 1, "label": "A veces"}, {"value": 2, "label": "Frecuente"}, {"value": 3, "label": "Muy frecuente"}]',
                "min_value": 0,
                "max_value": 3,
                "unit": "",
                "scale_guidance": "",
            }
        ]
    ).to_csv(source / "questionnaire_v16_4_scales_excel_utf8.csv", index=False)

    rows = []
    for idx, domain in enumerate(["adhd", "conduct", "elimination", "anxiety", "depression"], start=1):
        rows.append(
            {
                "questionnaire_item_id": f"Q{idx:03d}",
                "feature": f"{domain}_symptom_01",
                "question_text_primary": f"Pregunta {domain}",
                "caregiver_question": f"Pregunta {domain}",
                "psychologist_question": f"Pregunta {domain}",
                "section_name": "General",
                "subsection_name": "Base",
                "questionnaire_section_suggested": "General",
                "questionnaire_subsection_suggested": "Base",
                "layer": "dsm5",
                "domain": domain,
                "domains_final": domain,
                "module": "core",
                "criterion_ref": "A1",
                "instrument_or_source": "dsm5",
                "feature_type": "symptom",
                "feature_role": "model_input",
                "respondent_expected": "caregiver_or_psychologist",
                "administered_by": "caregiver_or_psychologist",
                "response_type": "single_choice",
                "scale_id": "FREQ_0_3",
                "response_options_json": '[{"value": 0, "label": "Nunca"}, {"value": 1, "label": "A veces"}, {"value": 2, "label": "Frecuente"}, {"value": 3, "label": "Muy frecuente"}]',
                "min_value": 0,
                "max_value": 3,
                "unit": "",
                "visible_question_yes_no": "yes",
                "generated_input_yes_no": "no",
                "show_in_questionnaire_yes_no": "yes",
                "is_transparent_derived": "no",
                "requires_internal_scoring": "no",
                "requires_exact_item_wording": "no",
                "requires_clinician_administration": "no",
                "requires_child_self_report": "no",
                "include_caregiver_1_3": "yes",
                "include_caregiver_2_3": "yes",
                "include_caregiver_full": "yes",
                "include_psychologist_1_3": "yes",
                "include_psychologist_2_3": "yes",
                "include_psychologist_full": "yes",
                "caregiver_rank": idx,
                "psychologist_rank": idx,
                "caregiver_priority_bucket": "alta",
                "psychologist_priority_bucket": "alta",
                "derived_from_features": "",
                "internal_scoring_formula_summary": "",
                "help_text": "",
                "notes": "",
                "canonical_question_id": "",
                "reuse_answer_from_question_id": "",
                "question_audit_status": "audited_v16_4",
            }
        )

    frame = pd.DataFrame(rows)
    frame.to_csv(source / "questionnaire_v16_4_master_excel_utf8.csv", index=False)
    frame.to_csv(source / "questionnaire_v16_4_visible_questions_excel_utf8.csv", index=False)
    (source / "questionnaire_v16_4_preview.md").write_text("preview", encoding="utf-8")
    (source / "questionnaire_v16_4_audit_summary.md").write_text("audit", encoding="utf-8")
    (source / "cuestionario_v16_4.pdf").write_bytes(b"%PDF-1.4\n%EOF")
    return source


@pytest.fixture
def app(tmp_path, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    monkeypatch.setenv("COGNIA_TRANSPORT_PRIVATE_KEY_PEM", private_pem)
    monkeypatch.setenv("COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION", "true")
    monkeypatch.setenv("COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD", "true")
    monkeypatch.setenv("COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV", "false")
    monkeypatch.setenv("COGNIA_FIELD_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")

    class StrictTransportConfig(TestingConfig):
        TESTING = False
        COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION = True
        COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD = True
        COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV = False
        COGNIA_ENABLE_FIELD_ENCRYPTION = True

    app = create_app(StrictTransportConfig)
    with app.app_context():
        db.create_all()
        source = _build_source(tmp_path)
        loader_service.sync_questionnaire_catalog(source_dir=source)
        loader_service.sync_active_models()
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _user_headers(app):
    with app.app_context():
        user = AppUser(
            username=f"user_{uuid.uuid4().hex[:8]}",
            email=f"user_{uuid.uuid4().hex[:8]}@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": []})
    return {"Authorization": f"Bearer {token}"}


def _get_transport_key(client, headers):
    resp = client.get("/api/v2/security/transport-key", headers=headers)
    assert resp.status_code == 200
    return resp.get_json()


def test_encrypted_payload_roundtrip(client, app):
    headers = _user_headers(app)
    key_payload = _get_transport_key(client, headers)

    envelope, symmetric_key = _encrypt_envelope(
        {
            "mode": "short",
            "role": "guardian",
            "child_age_years": 9,
            "child_sex_assigned_at_birth": "male",
        },
        key_payload,
    )

    req_headers = {**headers, "X-CognIA-Encrypted": "1", "X-CognIA-Crypto-Version": "transport_envelope_v1"}
    resp = client.post("/api/v2/questionnaires/sessions", json=envelope, headers=req_headers)
    assert resp.status_code == 201
    assert resp.headers.get("X-CognIA-Encrypted") == "1"

    decrypted = _decrypt_encrypted_response(resp.get_json(), symmetric_key)
    assert "session" in decrypted
    assert "session_id" in decrypted["session"]


def test_plaintext_sensitive_payload_rejected_in_production(client, app):
    headers = _user_headers(app)
    resp = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "plaintext_not_allowed"


def test_encrypted_response_for_sensitive_endpoint(client, app):
    headers = _user_headers(app)
    key_payload = _get_transport_key(client, headers)
    req_headers = {**headers, "X-CognIA-Encrypted": "1", "X-CognIA-Crypto-Version": "transport_envelope_v1"}

    # create session encrypted
    create_envelope, create_key = _encrypt_envelope(
        {
            "mode": "short",
            "role": "guardian",
            "child_age_years": 9,
            "child_sex_assigned_at_birth": "male",
        },
        key_payload,
    )
    created = client.post("/api/v2/questionnaires/sessions", json=create_envelope, headers=req_headers)
    assert created.status_code == 201
    created_payload = _decrypt_encrypted_response(created.get_json(), create_key)
    session_id = created_payload["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=100", headers=headers)
    questions = []
    for block in page.get_json()["pages"]:
        questions.extend(block["questions"])

    answers = [{"question_id": q["question_id"], "answer": 3} for q in questions]

    answers_envelope, answers_key = _encrypt_envelope({"answers": answers, "mark_final": True}, key_payload)
    saved = client.patch(f"/api/v2/questionnaires/sessions/{session_id}/answers", json=answers_envelope, headers=req_headers)
    assert saved.status_code == 200
    assert saved.headers.get("X-CognIA-Encrypted") == "1"
    decrypted_saved = _decrypt_encrypted_response(saved.get_json(), answers_key)
    assert "saved_answers" in decrypted_saved
