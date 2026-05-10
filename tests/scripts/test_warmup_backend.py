import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.warmup_backend import (
    build_api_url,
    build_config,
    default_api_prefix_from_base,
    normalize_api_prefix,
)


def test_default_api_prefix_from_base_handles_api_base_path():
    assert default_api_prefix_from_base("https://www.cognia.lat/api") == ""
    assert default_api_prefix_from_base("https://www.cognia.lat") == "/api"


def test_normalize_api_prefix_avoids_duplicate_api():
    base_url = "https://www.cognia.lat/api"
    assert normalize_api_prefix(base_url, "/api") == ""
    assert normalize_api_prefix(base_url, "api") == ""


def test_build_api_url_without_duplicate_prefix():
    url = build_api_url("https://www.cognia.lat", "/api", "/auth/login")
    assert url == "https://www.cognia.lat/api/auth/login"


def test_build_config_uses_empty_prefix_when_base_already_has_api(monkeypatch):
    monkeypatch.delenv("API_PREFIX", raising=False)
    monkeypatch.setenv("BASE_URL", "https://www.cognia.lat/api")
    monkeypatch.setenv("USERNAME", "perf_user")
    monkeypatch.setenv("PASSWORD", "perf_password")

    args = argparse.Namespace(
        base_url=None,
        api_prefix=None,
        username=None,
        password=None,
        timeout_seconds=None,
        warmup_modes=None,
        warmup_roles=None,
        safe_mode=None,
    )
    cfg = build_config(args)
    assert cfg.base_url == "https://www.cognia.lat/api"
    assert cfg.api_prefix == ""
