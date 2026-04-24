import os
import sys
import uuid

import pytest
import pyotp

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db, AppUser, Role, UserRole, QuestionnaireTemplate
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
        json={"username": username, "email": email, "password": password, "full_name": "Admin", "user_type": "guardian"},
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


def test_activate_template_disables_others(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp_a = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template A", "version": "v1", "description": "A"},
        headers=headers,
    )
    resp_b = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template B", "version": "v1", "description": "B"},
        headers=headers,
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201

    template_a = resp_a.json["id"]
    template_b = resp_b.json["id"]

    payload = [{"code": "Q1", "text": "Question 1", "response_type": "likert_0_4", "position": 1}]
    client.post(
        f"/api/v1/questionnaires/{template_a}/questions",
        json=payload,
        headers=headers,
    )
    client.post(
        f"/api/v1/questionnaires/{template_b}/questions",
        json=payload,
        headers=headers,
    )

    resp_activate_a = client.post(
        f"/api/v1/questionnaires/{template_a}/activate",
        headers=headers,
    )
    assert resp_activate_a.status_code == 200

    resp_activate_b = client.post(
        f"/api/v1/questionnaires/{template_b}/activate",
        headers=headers,
    )
    assert resp_activate_b.status_code == 200

    with app.app_context():
        active_count = QuestionnaireTemplate.query.filter_by(is_active=True).count()
        active = QuestionnaireTemplate.query.filter_by(id=uuid.UUID(template_b)).first()
        assert active_count == 1
        assert active and active.is_active is True


def test_get_active_returns_sorted_questions(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template Order", "version": "v1", "description": None},
        headers=headers,
    )
    template_id = resp.json["id"]

    payload = [
        {"code": "Q2", "text": "Second", "response_type": "likert_0_4", "position": 2},
        {"code": "Q3", "text": "No position", "response_type": "boolean", "position": None},
        {"code": "Q1", "text": "First", "response_type": "likert_0_4", "position": 1},
    ]
    resp_questions = client.post(
        f"/api/v1/questionnaires/{template_id}/questions",
        json=payload,
        headers=headers,
    )
    assert resp_questions.status_code == 201

    resp_activate = client.post(
        f"/api/v1/questionnaires/{template_id}/activate",
        headers=headers,
    )
    assert resp_activate.status_code == 200

    resp_active = client.get("/api/v1/questionnaires/active")
    assert resp_active.status_code == 200
    codes = [q["code"] for q in resp_active.json["questions"]]
    assert codes == ["Q1", "Q2", "Q3"]


def test_activate_without_questions_rejected(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template Empty", "version": "v1", "description": None},
        headers=headers,
    )
    template_id = resp.json["id"]

    resp_activate = client.post(
        f"/api/v1/questionnaires/{template_id}/activate",
        headers=headers,
    )
    assert resp_activate.status_code == 409


def test_clone_active_template_creates_draft(client, app):
    token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template Clone", "version": "v1", "description": "base"},
        headers=headers,
    )
    template_id = resp.json["id"]

    payload = [
        {"code": "Q1", "text": "Question 1", "response_type": "likert_0_4", "position": 1},
        {"code": "Q2", "text": "Question 2", "response_type": "boolean", "position": 2},
    ]
    resp_questions = client.post(
        f"/api/v1/questionnaires/{template_id}/questions",
        json=payload,
        headers=headers,
    )
    assert resp_questions.status_code == 201

    resp_activate = client.post(
        f"/api/v1/questionnaires/{template_id}/activate",
        headers=headers,
    )
    assert resp_activate.status_code == 200

    resp_clone = client.post(
        "/api/v1/questionnaires/active/clone",
        json={"version": "v2"},
        headers=headers,
    )
    assert resp_clone.status_code == 201
    assert resp_clone.json["is_active"] is False
    assert resp_clone.json["question_count"] == 2
