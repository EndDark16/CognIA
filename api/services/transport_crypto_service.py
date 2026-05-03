from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app, request

TRANSPORT_ENVELOPE_VERSION = "transport_envelope_v1"
TRANSPORT_ALGORITHM = "RSA-OAEP-256+AES-256-GCM"


class TransportCryptoError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class TransportContext:
    request_encrypted: bool = False
    symmetric_key: bytes | None = None
    key_id: str | None = None


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def transport_payload_encryption_enabled() -> bool:
    try:
        configured = current_app.config.get("COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION")
    except RuntimeError:
        configured = None
    if configured is not None:
        return bool(configured)
    return _bool_env("COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION", False)


def _allow_plaintext_in_dev() -> bool:
    try:
        configured = current_app.config.get("COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV")
    except RuntimeError:
        configured = None
    if configured is not None:
        return bool(configured)
    return _bool_env("COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV", True)


def _require_prod_encryption() -> bool:
    try:
        configured = current_app.config.get("COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD")
    except RuntimeError:
        configured = None
    if configured is not None:
        return bool(configured)
    return _bool_env("COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD", True)


def _is_production_runtime() -> bool:
    try:
        return not bool(current_app.debug) and not bool(current_app.testing)
    except RuntimeError:
        return False


def should_require_encrypted_payload() -> bool:
    if not transport_payload_encryption_enabled():
        return False
    if _is_production_runtime() and _require_prod_encryption():
        return True
    return not _allow_plaintext_in_dev()


def _transport_key_id() -> str:
    try:
        configured = current_app.config.get("COGNIA_TRANSPORT_KEY_ID")
    except RuntimeError:
        configured = None
    return str(configured or os.getenv("COGNIA_TRANSPORT_KEY_ID", "transport-key-v1"))


def _transport_key_ttl_seconds() -> int:
    try:
        configured = current_app.config.get("COGNIA_TRANSPORT_KEY_TTL_SECONDS")
    except RuntimeError:
        configured = None
    raw = configured if configured is not None else os.getenv("COGNIA_TRANSPORT_KEY_TTL_SECONDS", "3600")
    try:
        return max(60, int(raw))
    except Exception:
        return 3600


def _normalize_pem(raw: str) -> str:
    return raw.replace("\\n", "\n").strip()


@lru_cache(maxsize=1)
def _load_or_generate_private_key():
    pem = os.getenv("COGNIA_TRANSPORT_PRIVATE_KEY_PEM", "").strip()
    if pem:
        key = serialization.load_pem_private_key(_normalize_pem(pem).encode("utf-8"), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise RuntimeError("COGNIA_TRANSPORT_PRIVATE_KEY_PEM must be an RSA private key")
        return key

    if _is_production_runtime() and transport_payload_encryption_enabled():
        raise RuntimeError("COGNIA_TRANSPORT_PRIVATE_KEY_PEM is required in production when transport encryption is enabled")

    # Development/testing fallback: ephemeral in-memory key.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public_key_to_jwk(public_key: rsa.RSAPublicKey) -> dict[str, str]:
    numbers = public_key.public_numbers()
    n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "alg": "RSA-OAEP-256",
        "use": "enc",
        "n": _b64url_encode(n),
        "e": _b64url_encode(e),
    }


def transport_key_payload() -> dict[str, Any]:
    private_key = _load_or_generate_private_key()
    public_key = private_key.public_key()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=_transport_key_ttl_seconds())
    return {
        "key_id": _transport_key_id(),
        "algorithm": TRANSPORT_ALGORITHM,
        "public_key_jwk": _public_key_to_jwk(public_key),
        "expires_at": expires_at.isoformat(),
        "version": TRANSPORT_ENVELOPE_VERSION,
    }


def _validate_envelope(envelope: dict[str, Any]) -> None:
    required = {"encrypted", "version", "key_id", "encrypted_key", "iv", "ciphertext", "alg"}
    missing = [field for field in sorted(required) if field not in envelope]
    if missing:
        raise TransportCryptoError("encrypted_payload_invalid", f"missing_fields:{','.join(missing)}", 400)
    if not bool(envelope.get("encrypted")):
        raise TransportCryptoError("encrypted_payload_invalid", "encrypted_flag_required", 400)
    if str(envelope.get("version")) != TRANSPORT_ENVELOPE_VERSION:
        raise TransportCryptoError("encrypted_payload_invalid", "unsupported_crypto_version", 400)
    if str(envelope.get("key_id")) != _transport_key_id():
        raise TransportCryptoError("encrypted_payload_invalid", "key_id_mismatch", 400)
    algorithm = str(envelope.get("alg") or "").upper()
    if "AES-256-GCM" not in algorithm:
        raise TransportCryptoError("encrypted_payload_invalid", "unsupported_algorithm", 400)


def decrypt_transport_envelope(envelope: dict[str, Any]) -> tuple[dict[str, Any], TransportContext]:
    _validate_envelope(envelope)

    private_key = _load_or_generate_private_key()
    encrypted_key = _b64url_decode(str(envelope.get("encrypted_key")))
    iv = _b64url_decode(str(envelope.get("iv")))
    ciphertext = _b64url_decode(str(envelope.get("ciphertext")))
    aad_text = str(envelope.get("aad") or "")
    aad = aad_text.encode("utf-8") if aad_text else None

    try:
        symmetric_key = private_key.decrypt(
            encrypted_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        if len(symmetric_key) != 32:
            raise TransportCryptoError("encrypted_payload_invalid", "invalid_symmetric_key_length", 400)

        payload_bytes = AESGCM(symmetric_key).decrypt(iv, ciphertext, aad)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except TransportCryptoError:
        raise
    except Exception:
        raise TransportCryptoError("encrypted_payload_invalid", "decrypt_failed", 400)

    ctx = TransportContext(request_encrypted=True, symmetric_key=symmetric_key, key_id=str(envelope.get("key_id")))
    return payload, ctx


def encrypt_transport_payload(payload: dict[str, Any], context: TransportContext) -> dict[str, Any]:
    if context.symmetric_key is None:
        raise TransportCryptoError("encrypted_payload_invalid", "missing_transport_key", 500)
    iv = os.urandom(12)
    aad_text = f"{TRANSPORT_ENVELOPE_VERSION}|{context.key_id or _transport_key_id()}"
    aad = aad_text.encode("utf-8")
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(context.symmetric_key).encrypt(iv, plaintext, aad)
    return {
        "encrypted": True,
        "version": TRANSPORT_ENVELOPE_VERSION,
        "key_id": context.key_id or _transport_key_id(),
        "alg": "AES-256-GCM",
        "iv": _b64url_encode(iv),
        "ciphertext": _b64url_encode(ciphertext),
        "aad": aad_text,
    }


def decode_sensitive_request_payload(payload: dict[str, Any] | None) -> tuple[dict[str, Any], TransportContext]:
    payload = payload or {}
    encrypted_header = str(request.headers.get("X-CognIA-Encrypted", "")).strip()
    crypto_version_header = str(request.headers.get("X-CognIA-Crypto-Version", "")).strip()
    header_wants_encryption = encrypted_header == "1"
    payload_is_encrypted = bool(payload.get("encrypted"))

    if encrypted_header and encrypted_header != "1":
        raise TransportCryptoError("encrypted_payload_invalid", "invalid_encrypted_header", 400)

    if crypto_version_header and crypto_version_header != TRANSPORT_ENVELOPE_VERSION:
        raise TransportCryptoError("invalid_crypto_version", "invalid_crypto_version", 400)

    if payload_is_encrypted and not header_wants_encryption:
        raise TransportCryptoError("encrypted_payload_invalid", "missing_encrypted_header", 400)

    if header_wants_encryption and not crypto_version_header:
        raise TransportCryptoError("invalid_crypto_version", "missing_crypto_version_header", 400)

    if not transport_payload_encryption_enabled():
        return payload, TransportContext(request_encrypted=False)

    if header_wants_encryption or payload_is_encrypted:
        decrypted_payload, ctx = decrypt_transport_envelope(payload)
        return decrypted_payload, ctx

    if should_require_encrypted_payload():
        raise TransportCryptoError(
            "plaintext_not_allowed",
            "encrypted_transport_required_for_sensitive_endpoint",
            400,
        )

    return payload, TransportContext(request_encrypted=False)


def encode_sensitive_response_payload(payload: dict[str, Any], context: TransportContext) -> tuple[dict[str, Any], dict[str, str]]:
    if transport_payload_encryption_enabled() and context.request_encrypted:
        encrypted = encrypt_transport_payload(payload, context)
        headers = {
            "X-CognIA-Encrypted": "1",
            "X-CognIA-Crypto-Version": TRANSPORT_ENVELOPE_VERSION,
            "Cache-Control": "no-store",
        }
        return encrypted, headers

    return payload, {}
