import os
import sys
import uuid

import pyotp
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db, AppUser, Role, UserRole
from config.settings import TestingConfig


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


def _admin_token(client, app):
    username = f"admin_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Admin",
            "user_type": "guardian",
        },
    )
    with app.app_context():
        role = Role(name="ADMIN")
        db.session.add(role)
        db.session.commit()
        user = AppUser.query.filter_by(username=username).first()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    enrollment_token = resp_login.json["enrollment_token"]

    resp_setup = client.post(
        "/api/mfa/setup",
        headers={"Authorization": f"Bearer {enrollment_token}"},
    )
    secret = resp_setup.json["secret"]
    code = pyotp.TOTP(secret).now()
    resp_confirm = client.post(
        "/api/mfa/confirm",
        headers={"Authorization": f"Bearer {enrollment_token}"},
        json={"code": code},
    )
    assert resp_confirm.status_code == 200

    resp_login_2 = client.post("/api/auth/login", json={"username": username, "password": password})
    challenge_id = resp_login_2.json["challenge_id"]
    code2 = pyotp.TOTP(secret).now()
    resp_login_mfa = client.post(
        "/api/auth/login/mfa",
        json={"challenge_id": challenge_id, "code": code2},
    )
    return resp_login_mfa.json["access_token"]


def test_admin_can_create_and_list_users(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp_create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": f"user_{uuid.uuid4().hex[:6]}",
            "email": f"user_{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPassword123!",
            "full_name": "User One",
            "user_type": "guardian",
            "roles": ["GUARDIAN"],
        },
    )
    assert resp_create.status_code == 201

    resp_list = client.get("/api/v1/users", headers=headers)
    assert resp_list.status_code == 200
    assert resp_list.json["total"] >= 1


def test_users_list_rejects_invalid_pagination(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/users?page=0&page_size=500", headers=headers)
    assert resp.status_code == 400
    assert resp.json.get("error") == "validation_error"


def test_users_patch_requires_at_least_one_field(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp_create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": f"user_{uuid.uuid4().hex[:6]}",
            "email": f"user_{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPassword123!",
            "full_name": "User To Patch",
            "user_type": "guardian",
        },
    )
    assert resp_create.status_code == 201
    user_id = resp_create.json["id"]

    resp_patch = client.patch(f"/api/v1/users/{user_id}", headers=headers, json={})
    assert resp_patch.status_code == 400
    assert resp_patch.json.get("error") == "validation_error"
