import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import pyotp
import pytest
from flask import jsonify

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.decorators import roles_required
from api.cache import roles_cache
from app.models import db, AppUser, Role, UserRole, MFALoginChallenge
from config.settings import TestingConfig


@pytest.fixture(autouse=True)
def mfa_key_env(monkeypatch):
    key = "MFA_ENCRYPTION_KEY"
    if not os.getenv(key):
        monkeypatch.setenv(key, "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY=")
    yield


@pytest.fixture
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _persist_cookies(client, set_cookie_headers):
    cookies = SimpleCookie()
    for header in set_cookie_headers:
        cookies.load(header)
    refresh_cookie_val = cookies.get("refresh_token").value if cookies.get("refresh_token") else None
    csrf_refresh = cookies.get("csrf_refresh_token").value if cookies.get("csrf_refresh_token") else None
    if refresh_cookie_val:
        client.set_cookie("refresh_token", refresh_cookie_val, path="/api/auth/refresh")
    if csrf_refresh:
        client.set_cookie("csrf_refresh_token", csrf_refresh, path="/")
    return refresh_cookie_val, csrf_refresh


def test_register_and_login(client):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
            "user_type": "guardian",
        },
    )

    assert resp_reg.status_code == 201
    assert "user_id" in resp_reg.json

    resp_login = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )

    assert resp_login.status_code == 200
    data = resp_login.json
    assert "access_token" in data
    assert "expires_in" in data

    set_cookie_headers = resp_login.headers.getlist("Set-Cookie")
    assert any("refresh_token=" in c for c in set_cookie_headers)
    access_token = data["access_token"]

    refresh_cookie_val, csrf_refresh = _persist_cookies(client, set_cookie_headers)
    assert csrf_refresh and refresh_cookie_val

    resp_refresh = client.post(
        "/api/auth/refresh",
        headers={
            "X-CSRF-Token": csrf_refresh,
        },
    )
    assert resp_refresh.status_code == 200
    assert "access_token" in resp_refresh.json

    cookies_refresh = SimpleCookie()
    for header in resp_refresh.headers.getlist("Set-Cookie"):
        cookies_refresh.load(header)
    new_csrf = cookies_refresh.get("csrf_refresh_token").value if cookies_refresh.get("csrf_refresh_token") else csrf_refresh
    if cookies_refresh.get("refresh_token"):
        client.set_cookie("refresh_token", cookies_refresh.get("refresh_token").value, path="/api/auth/refresh")
    if cookies_refresh.get("csrf_refresh_token"):
        client.set_cookie("csrf_refresh_token", new_csrf, path="/")

    resp_logout = client.post(
        "/api/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": new_csrf,
        },
    )
    assert resp_logout.status_code == 200
    logout_set_cookie = resp_logout.headers.get("Set-Cookie", "")
    assert "refresh_token=" in logout_set_cookie and ("Max-Age=0" in logout_set_cookie or "Expires=" in logout_set_cookie)

    client2 = create_app(TestingConfig).test_client()
    resp_no_cookie = client2.post(
        "/api/auth/refresh",
        headers={
            "X-CSRF-Token": new_csrf,
        },
    )
    assert resp_no_cookie.status_code == 401


def test_register_sends_welcome_email(client, monkeypatch):
    called = {}

    def _fake_send(to_email, full_name):
        called["to_email"] = to_email
        called["full_name"] = full_name

    monkeypatch.setattr("api.routes.auth.send_welcome_email", _fake_send)

    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
            "user_type": "guardian",
        },
    )

    assert resp_reg.status_code == 201
    assert called["to_email"] == email
    assert called["full_name"] == "Test User"


def test_register_psychologist_requires_card(client):
    username = f"psych_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_missing = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Psych User",
            "user_type": "psychologist",
        },
    )
    assert resp_missing.status_code == 400
    assert resp_missing.json.get("error") == "missing_professional_card"

    resp_ok = client.post(
        "/api/auth/register",
        json={
            "username": f"{username}2",
            "email": f"{username}2@example.com",
            "password": password,
            "full_name": "Psych User 2",
            "user_type": "psychologist",
            "professional_card_number": "COLPSIC-12345",
        },
    )
    assert resp_ok.status_code == 201


def test_psychologist_login_requires_colpsic_verification(client, app):
    username = f"psychlogin_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Psych User",
            "user_type": "psychologist",
            "professional_card_number": "COLPSIC-98765",
        },
    )
    assert resp_reg.status_code == 201

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 403
    assert resp_login.json.get("error") == "colpsic_pending"


def test_mfa_setup_and_login_flow(client, app):
    username = f"mfauser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "MFA User", "user_type": "guardian"},
    )

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    access_token = resp_login.json["access_token"]

    set_cookie_headers = resp_login.headers.getlist("Set-Cookie")
    _persist_cookies(client, set_cookie_headers)

    resp_setup = client.post(
        "/api/mfa/setup",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp_setup.status_code == 200
    secret = resp_setup.json["secret"]

    totp = pyotp.TOTP(secret)
    code = totp.now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"code": code},
    )
    assert resp_confirm.status_code == 200
    assert "recovery_codes" in resp_confirm.json

    resp_login_2 = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login_2.status_code == 200
    assert resp_login_2.json.get("mfa_required") is True
    challenge_id = resp_login_2.json["challenge_id"]
    assert not any("refresh_token=" in c for c in resp_login_2.headers.getlist("Set-Cookie"))

    code2 = totp.now()
    resp_login_mfa = client.post(
        "/api/auth/login/mfa",
        json={"challenge_id": challenge_id, "code": code2},
    )
    assert resp_login_mfa.status_code == 200
    assert "access_token" in resp_login_mfa.json
    set_cookie_headers = resp_login_mfa.headers.getlist("Set-Cookie")
    assert any("refresh_token=" in c for c in set_cookie_headers)

    refresh_cookie_val, csrf_refresh_new = _persist_cookies(client, set_cookie_headers)
    assert refresh_cookie_val and csrf_refresh_new

    resp_refresh = client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": csrf_refresh_new},
    )
    assert resp_refresh.status_code == 200


def test_refresh_requires_csrf_header(client):
    username = f"csrfuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "CSRF User", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    # Sin header CSRF, debe fallar con 403
    resp_refresh_no_csrf = client.post("/api/auth/refresh")
    assert resp_refresh_no_csrf.status_code == 403
    assert resp_refresh_no_csrf.json.get("error") == "csrf_failed"


def test_login_requires_mfa_enrollment_for_admin(client, app):
    username = f"admin_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    with app.app_context():
        admin_role = Role(name="ADMIN")
        db.session.add(admin_role)
        db.session.commit()

    resp_reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Admin User", "user_type": "guardian"},
    )
    assert resp_reg.status_code == 201
    user_id = uuid.UUID(resp_reg.json["user_id"])
    with app.app_context():
        role = Role.query.filter_by(name="ADMIN").first()
        user = AppUser.query.filter_by(id=user_id).first()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    assert resp_login.json.get("mfa_enrollment_required") is True
    assert "enrollment_token" in resp_login.json
    assert not any("refresh_token=" in c for c in resp_login.headers.getlist("Set-Cookie"))

    enrollment_token = resp_login.json["enrollment_token"]
    resp_setup = client.post(
        "/api/mfa/setup",
        headers={"Authorization": f"Bearer {enrollment_token}"},
    )
    assert resp_setup.status_code == 200
    secret = resp_setup.json["secret"]

    totp = pyotp.TOTP(secret)
    code = totp.now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {enrollment_token}"},
        json={"code": code},
    )
    assert resp_confirm.status_code == 200


def test_refresh_rotation_revokes_old_token(client):
    username = f"rotuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Rot User", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200

    set_cookie_headers = resp_login.headers.getlist("Set-Cookie")
    old_refresh, old_csrf = _persist_cookies(client, set_cookie_headers)

    resp_refresh = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert resp_refresh.status_code == 200

    # Fuerza el uso del refresh anterior (debe estar revocado)
    client.set_cookie("refresh_token", old_refresh, path="/api/auth/refresh")
    client.set_cookie("csrf_refresh_token", old_csrf, path="/")
    resp_old = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert resp_old.status_code == 401


def test_logout_revokes_refresh(client):
    username = f"logout_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Logout User", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    access_token = resp_login.json["access_token"]
    old_refresh, old_csrf = _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    resp_logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}", "X-CSRF-Token": old_csrf},
    )
    assert resp_logout.status_code == 200

    # Intentar refresh con el cookie anterior debe fallar
    client.set_cookie("refresh_token", old_refresh, path="/api/auth/refresh")
    client.set_cookie("csrf_refresh_token", old_csrf, path="/")
    resp_refresh = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert resp_refresh.status_code == 401


def test_refresh_rejects_invalid_csrf(client):
    username = f"csrfbad_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "CSRF Bad", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    resp_refresh = client.post("/api/auth/refresh", headers={"X-CSRF-Token": "bad-token"})
    assert resp_refresh.status_code == 403
    assert resp_refresh.json.get("error") == "csrf_failed"


def test_inactive_user_blocked_login(client, app):
    username = f"inactive_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Inactive User", "user_type": "guardian"},
    )
    assert resp_reg.status_code == 201
    user_id = uuid.UUID(resp_reg.json["user_id"])

    with app.app_context():
        user = db.session.get(AppUser, user_id)
        user.is_active = False
        db.session.commit()

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 403


def test_login_lockout_after_failed_attempts(client, app):
    app.config["MAX_LOGIN_ATTEMPTS"] = 2
    app.config["LOGIN_LOCKOUT_MINUTES"] = 1

    username = f"lock_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Lock User",
            "user_type": "guardian",
        },
    )
    assert resp_reg.status_code == 201

    for _ in range(2):
        resp_fail = client.post("/api/auth/login", json={"username": username, "password": "badpass"})
        assert resp_fail.status_code == 401

    resp_locked = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_locked.status_code == 423


def test_refresh_denied_for_inactive_user(client, app):
    username = f"inact_ref_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    resp_reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Inactive Refresh", "user_type": "guardian"},
    )
    assert resp_reg.status_code == 201
    user_id = uuid.UUID(resp_reg.json["user_id"])

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 200
    old_refresh, old_csrf = _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    with app.app_context():
        user = db.session.get(AppUser, user_id)
        user.is_active = False
        db.session.commit()

    client.set_cookie("refresh_token", old_refresh, path="/api/auth/refresh")
    client.set_cookie("csrf_refresh_token", old_csrf, path="/")
    resp_refresh = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert resp_refresh.status_code == 401


def test_mfa_challenge_reuse_rejected(client):
    username = f"mfareuse_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "MFA Reuse", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]
    _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    resp_setup = client.post("/api/mfa/setup", headers={"Authorization": f"Bearer {access_token}"})
    secret = resp_setup.json["secret"]
    code = pyotp.TOTP(secret).now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"code": code},
    )
    assert resp_confirm.status_code == 200

    resp_login_2 = client.post("/api/auth/login", json={"username": username, "password": password})
    challenge_id = resp_login_2.json["challenge_id"]
    code2 = pyotp.TOTP(secret).now()
    resp_mfa = client.post("/api/auth/login/mfa", json={"challenge_id": challenge_id, "code": code2})
    assert resp_mfa.status_code == 200

    # Reusar el mismo challenge debe fallar
    resp_mfa_reuse = client.post("/api/auth/login/mfa", json={"challenge_id": challenge_id, "code": code2})
    assert resp_mfa_reuse.status_code == 401


def test_mfa_challenge_expired_rejected(client, app):
    username = f"mfaexp_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "MFA Exp", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]
    _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    resp_setup = client.post("/api/mfa/setup", headers={"Authorization": f"Bearer {access_token}"})
    secret = resp_setup.json["secret"]
    code = pyotp.TOTP(secret).now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"code": code},
    )
    assert resp_confirm.status_code == 200

    with app.app_context():
        user = AppUser.query.filter_by(username=username).first()
        expired = MFALoginChallenge(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        db.session.add(expired)
        db.session.commit()
        challenge_id = str(expired.id)

    resp_mfa = client.post(
        "/api/auth/login/mfa",
        json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
    )
    assert resp_mfa.status_code == 401


def test_recovery_code_cannot_be_reused(client):
    username = f"mfarec_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "MFA Rec", "user_type": "guardian"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]
    _persist_cookies(client, resp_login.headers.getlist("Set-Cookie"))

    resp_setup = client.post("/api/mfa/setup", headers={"Authorization": f"Bearer {access_token}"})
    secret = resp_setup.json["secret"]
    code = pyotp.TOTP(secret).now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"code": code},
    )
    recovery_code = resp_confirm.json["recovery_codes"][0]

    resp_login_2 = client.post("/api/auth/login", json={"username": username, "password": password})
    challenge_id = resp_login_2.json["challenge_id"]
    resp_mfa = client.post(
        "/api/auth/login/mfa",
        json={"challenge_id": challenge_id, "recovery_code": recovery_code},
    )
    assert resp_mfa.status_code == 200

    # Nuevo challenge, mismo recovery code debe fallar
    resp_login_3 = client.post("/api/auth/login", json={"username": username, "password": password})
    challenge_id_2 = resp_login_3.json["challenge_id"]
    resp_mfa_2 = client.post(
        "/api/auth/login/mfa",
        json={"challenge_id": challenge_id_2, "recovery_code": recovery_code},
    )
    assert resp_mfa_2.status_code == 401


def test_roles_required_enforces_claims(client, app):
    roles_cache.clear()

    def _admin_only():
        return jsonify({"ok": True}), 200

    app.add_url_rule(
        "/api/admin-only",
        "admin_only",
        roles_required("TESTER")(_admin_only),
        methods=["GET"],
    )

    username = f"role_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    resp_reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Role User", "user_type": "guardian"},
    )
    user_id = uuid.UUID(resp_reg.json["user_id"])

    with app.app_context():
        role = Role(name="TESTER")
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=user_id, role_id=role.id))
        db.session.commit()

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]
    resp_ok = client.get("/api/admin-only", headers={"Authorization": f"Bearer {access_token}"})
    assert resp_ok.status_code == 200

    username2 = f"norole_{uuid.uuid4().hex[:8]}"
    email2 = f"{username2}@example.com"
    client.post(
        "/api/auth/register",
        json={"username": username2, "email": email2, "password": password, "full_name": "No Role", "user_type": "guardian"},
    )
    resp_login2 = client.post("/api/auth/login", json={"username": username2, "password": password})
    access_token2 = resp_login2.json["access_token"]
    resp_forbidden = client.get(
        "/api/admin-only", headers={"Authorization": f"Bearer {access_token2}"}
    )
    assert resp_forbidden.status_code == 403


def test_auth_me_returns_profile(client):
    username = f"profile_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    resp_reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Profile User", "user_type": "guardian"},
    )
    assert resp_reg.status_code == 201

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    access_token = resp_login.json["access_token"]

    resp_me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp_me.status_code == 200
    assert resp_me.json["username"] == username
    assert resp_me.json["email"] == email
