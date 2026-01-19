import os
import sys
import uuid
from http.cookies import SimpleCookie

import pyotp
import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db, AppUser, Role, UserRole
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


def test_mfa_setup_and_login_flow(client, app):
    username = f"mfauser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "MFA User"},
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
        json={"username": username, "email": email, "password": password, "full_name": "CSRF User"},
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
        json={"username": username, "email": email, "password": password, "full_name": "Admin User"},
    )
    assert resp_reg.status_code == 201
    user_id = uuid.UUID(resp_reg.json["user_id"])
    with app.app_context():
        role = Role.query.filter_by(name="ADMIN").first()
        user = AppUser.query.filter_by(id=user_id).first()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()

    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp_login.status_code == 403
    assert resp_login.json.get("mfa_enrollment_required") is True
    assert not any("refresh_token=" in c for c in resp_login.headers.getlist("Set-Cookie"))
