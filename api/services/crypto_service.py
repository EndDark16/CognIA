from __future__ import annotations

import base64
import hashlib
import json
import os
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app

FIELD_ENVELOPE_VERSION = "field_encryption_v1"
FIELD_ENVELOPE_MARKER = "__cognia_field_encrypted__"
FIELD_ENVELOPE_ALGORITHM = "AES-256-GCM"


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_field_encryption_enabled() -> bool:
    try:
        enabled = current_app.config.get("COGNIA_ENABLE_FIELD_ENCRYPTION")
    except RuntimeError:
        enabled = None
    if enabled is not None:
        return bool(enabled)
    return _bool_env("COGNIA_ENABLE_FIELD_ENCRYPTION", False)


@lru_cache(maxsize=1)
def _load_field_key_bytes() -> bytes:
    raw = os.getenv("COGNIA_FIELD_ENCRYPTION_KEY", "").strip()
    if raw:
        # Preferred format: base64url-encoded 32-byte key.
        try:
            key = _b64url_decode(raw)
            if len(key) == 32:
                return key
        except Exception:
            pass

        # Fallback: raw literal with exactly 32 bytes.
        key_bytes = raw.encode("utf-8")
        if len(key_bytes) == 32:
            return key_bytes

    testing_mode = False
    try:
        testing_mode = bool(current_app.config.get("TESTING"))
    except RuntimeError:
        testing_mode = _bool_env("COGNIA_TESTING", False)

    if testing_mode:
        # Deterministic test-only key to avoid leaking secrets into tests.
        return hashlib.sha256(b"cognia-testing-field-encryption").digest()

    raise RuntimeError("COGNIA_FIELD_ENCRYPTION_KEY missing or invalid for field encryption")


def _field_key_id() -> str:
    return os.getenv("COGNIA_FIELD_ENCRYPTION_KEY_ID", "field-key-v1")


def _build_aad(purpose: str, key_id: str) -> bytes:
    return f"{FIELD_ENVELOPE_VERSION}|{FIELD_ENVELOPE_ALGORITHM}|{key_id}|{purpose}".encode("utf-8")


def _encrypt_bytes(payload: bytes, purpose: str) -> dict[str, Any]:
    key = _load_field_key_bytes()
    key_id = _field_key_id()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    aad = _build_aad(purpose=purpose, key_id=key_id)
    ciphertext = aesgcm.encrypt(nonce, payload, aad)
    return {
        FIELD_ENVELOPE_MARKER: True,
        "version": FIELD_ENVELOPE_VERSION,
        "algorithm": FIELD_ENVELOPE_ALGORITHM,
        "key_id": key_id,
        "purpose": purpose,
        "nonce": _b64url_encode(nonce),
        "ciphertext": _b64url_encode(ciphertext),
    }


def _decrypt_bytes(envelope: dict[str, Any], purpose: str | None = None) -> bytes:
    key = _load_field_key_bytes()
    key_id = str(envelope.get("key_id") or "")
    nonce = _b64url_decode(str(envelope.get("nonce") or ""))
    ciphertext = _b64url_decode(str(envelope.get("ciphertext") or ""))
    envelope_purpose = str(envelope.get("purpose") or purpose or "generic")
    aad = _build_aad(purpose=envelope_purpose, key_id=key_id)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)


def is_encrypted(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get(FIELD_ENVELOPE_MARKER))
    if isinstance(value, str):
        text = value.strip()
        if not text or not text.startswith("{"):
            return False
        try:
            payload = json.loads(text)
        except Exception:
            return False
        return bool(isinstance(payload, dict) and payload.get(FIELD_ENVELOPE_MARKER))
    return False


def encrypt_json(value: Any, purpose: str) -> Any:
    if value is None:
        return None
    if not is_field_encryption_enabled():
        return value
    if is_encrypted(value):
        return value

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _encrypt_bytes(serialized, purpose=purpose)


def decrypt_json(value: Any, purpose: str) -> Any:
    if value is None:
        return None
    envelope: dict[str, Any] | None = None
    if isinstance(value, dict) and value.get(FIELD_ENVELOPE_MARKER):
        envelope = value
    elif isinstance(value, str):
        text = value.strip()
        if text.startswith("{"):
            try:
                payload = json.loads(text)
            except Exception:
                return value
            if isinstance(payload, dict) and payload.get(FIELD_ENVELOPE_MARKER):
                envelope = payload
            else:
                return value
        else:
            return value
    else:
        return value

    raw = _decrypt_bytes(envelope, purpose=purpose)
    return json.loads(raw.decode("utf-8"))


def encrypt_text(value: str | None, purpose: str) -> str | None:
    if value is None:
        return None
    if not is_field_encryption_enabled():
        return value
    if is_encrypted(value):
        return value
    envelope = _encrypt_bytes(str(value).encode("utf-8"), purpose=purpose)
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def decrypt_text(value: str | None, purpose: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    text = value.strip()
    if not text.startswith("{"):
        return value
    try:
        payload = json.loads(text)
    except Exception:
        return value
    if not isinstance(payload, dict) or not payload.get(FIELD_ENVELOPE_MARKER):
        return value
    raw = _decrypt_bytes(payload, purpose=purpose)
    return raw.decode("utf-8")


def mask_for_logs(value: Any) -> str:
    if value is None:
        return "<null>"
    if is_encrypted(value):
        return "<encrypted>"
    return "<redacted>"
