import base64
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services import crypto_service


def test_field_key_bytes_loader_uses_lru_cache(monkeypatch):
    key_material = b"0123456789abcdef0123456789abcdef"
    key_b64 = base64.urlsafe_b64encode(key_material).decode("utf-8").rstrip("=")
    monkeypatch.setenv("COGNIA_FIELD_ENCRYPTION_KEY", key_b64)

    crypto_service._load_field_key_bytes.cache_clear()
    info_before = crypto_service._load_field_key_bytes.cache_info()

    first = crypto_service._load_field_key_bytes()
    second = crypto_service._load_field_key_bytes()

    assert first == second == key_material
    info_after = crypto_service._load_field_key_bytes.cache_info()
    assert info_after.hits >= info_before.hits + 1
