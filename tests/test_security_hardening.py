import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


class ProdLikeConfig(TestingConfig):
    TESTING = False
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTH_CROSS_SITE_COOKIES = True
    JWT_COOKIE_SAMESITE = None
    JWT_COOKIE_SECURE = None
    SECURITY_HEADERS_ENABLED = True
    TRUST_PROXY_HEADERS = False
    RATELIMIT_ENABLED = False


def test_cookie_defaults_for_cross_site_prod():
    app = create_app(ProdLikeConfig)
    assert app.config["JWT_COOKIE_SAMESITE"] == "None"
    assert app.config["JWT_COOKIE_SECURE"] is True


def test_security_headers_present_when_enabled():
    app = create_app(ProdLikeConfig)
    client = app.test_client()

    resp = client.get("/healthz", headers={"X-Forwarded-Proto": "https"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "max-age=" in (resp.headers.get("Strict-Transport-Security") or "")


def test_missing_jwt_message_is_sanitized():
    app = create_app(ProdLikeConfig)
    client = app.test_client()

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json["error"] == "unauthorized"
    assert resp.json["msg"] == "Unauthorized"
