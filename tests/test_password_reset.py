import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.security import check_password
from app.models import db, AppUser, RefreshToken, PasswordResetToken
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config["FRONTEND_URL"] = "https://example.com"
    app.config["PASSWORD_RESET_PATH"] = "/reset-password"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _register_user(client, username, email, password):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
            "user_type": "guardian",
        },
    )


def test_forgot_returns_200_for_unknown_email(client):
    resp = client.post("/api/auth/password/forgot", json={"email": "missing@example.com"})
    assert resp.status_code == 200


def test_forgot_stores_hashed_token_only(client, app, monkeypatch):
    username = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    _register_user(client, username, email, password)

    captured = {}

    def _capture(to_email, reset_link, full_name):
        captured["link"] = reset_link

    monkeypatch.setattr("api.routes.auth.send_password_reset", _capture)

    resp = client.post("/api/auth/password/forgot", json={"email": email})
    assert resp.status_code == 200
    token = captured["link"].split("token=")[-1]

    with app.app_context():
        entry = PasswordResetToken.query.filter_by(user_id=AppUser.query.filter_by(email=email).first().id).first()
        assert entry is not None
        from api.services.password_reset_service import hash_reset_token
        assert entry.token_hash != token
        assert entry.token_hash == hash_reset_token(token)


def test_reset_rejects_expired_token(client, app):
    username = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    _register_user(client, username, email, password)

    token = "expiredtoken"
    from api.services.password_reset_service import hash_reset_token
    token_hash = hash_reset_token(token)
    with app.app_context():
        user = AppUser.query.filter_by(email=email).first()
        entry = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.session.add(entry)
        db.session.commit()

    resp = client.post(
        "/api/auth/password/reset",
        json={
            "token": token,
            "newPassword": "NewPassword123!",
            "confirmNewPassword": "NewPassword123!",
        },
    )
    assert resp.status_code == 400


def test_reset_updates_password_and_marks_used(client, app):
    username = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    _register_user(client, username, email, password)

    token = "validtoken123"
    from api.services.password_reset_service import hash_reset_token
    token_hash = hash_reset_token(token)

    with app.app_context():
        user = AppUser.query.filter_by(email=email).first()
        entry = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.session.add(entry)
        db.session.commit()

    resp = client.post(
        "/api/auth/password/reset",
        json={
            "token": token,
            "newPassword": "NewPassword123!",
            "confirmNewPassword": "NewPassword123!",
        },
    )
    assert resp.status_code == 200

    with app.app_context():
        user = AppUser.query.filter_by(email=email).first()
        assert check_password("NewPassword123!", user.password)
        entry = PasswordResetToken.query.filter_by(user_id=user.id).first()
        assert entry.used_at is not None


def test_change_password_revokes_refresh_tokens(client, app):
    username = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    _register_user(client, username, email, password)

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]

    resp_change = client.post(
        "/api/auth/password/change",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "currentPassword": password,
            "newPassword": "NewPassword123!",
            "confirmNewPassword": "NewPassword123!",
        },
    )
    assert resp_change.status_code == 200

    with app.app_context():
        user = AppUser.query.filter_by(username=username).first()
        revoked = RefreshToken.query.filter_by(user_id=user.id, revoked=True).count()
        assert revoked >= 1


def test_rate_limit_basic_for_forgot(client, app):
    class RateConfig(TestingConfig):
        RATELIMIT_ENABLED = True
        PASSWORD_FORGOT_RATE_LIMIT = "1 per minute"

    rate_app = create_app(RateConfig)
    with rate_app.app_context():
        db.create_all()
    rate_client = rate_app.test_client()
    resp1 = rate_client.post("/api/auth/password/forgot", json={"email": "test@example.com"})
    resp2 = rate_client.post("/api/auth/password/forgot", json={"email": "test@example.com"})
    assert resp1.status_code == 200
    assert resp2.status_code == 429


def test_verify_reset_token_valid_and_invalid(client, app):
    username = f"user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    _register_user(client, username, email, password)

    from api.services.password_reset_service import create_reset_token
    with app.app_context():
        user = AppUser.query.filter_by(email=email).first()
        token = create_reset_token(user_id=user.id, request_ip=None, user_agent=None)

    resp_ok = client.get(f"/api/auth/password/reset/verify?token={token}")
    assert resp_ok.status_code == 200
    assert resp_ok.json.get("valid") is True

    resp_bad = client.get("/api/auth/password/reset/verify?token=badtoken")
    assert resp_bad.status_code == 400
    assert resp_bad.json.get("valid") is False
