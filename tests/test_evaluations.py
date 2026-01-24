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
from app.models import db, AppUser, Role, UserRole, Evaluation, EvaluationResponse
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
        json={"username": username, "email": email, "password": password, "full_name": "Admin"},
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


def _user_token(client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "StrongPassword123!"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "User"},
    )
    resp_login = client.post("/api/auth/login", json={"username": username, "password": password})
    return resp_login.json["access_token"]


def _create_active_template(client, app):
    admin_token = _admin_token(client, app)
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.post(
        "/api/v1/questionnaires",
        json={"name": "Template Eval", "version": "v1", "description": None},
        headers=headers,
    )
    template_id = resp.json["id"]

    questions_payload = [
        {"code": "Q1", "text": "Question 1", "response_type": "likert", "position": 1},
        {"code": "Q2", "text": "Question 2", "response_type": "boolean", "position": 2},
    ]
    resp_questions = client.post(
        f"/api/v1/questionnaires/{template_id}/questions",
        json=questions_payload,
        headers=headers,
    )
    assert resp_questions.status_code == 201
    resp_activate = client.post(
        f"/api/v1/questionnaires/{template_id}/activate",
        headers=headers,
    )
    assert resp_activate.status_code == 200
    return template_id


def test_create_evaluation_links_template(client, app):
    _create_active_template(client, app)
    token = _user_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp_active = client.get("/api/v1/questionnaires/active")
    question_ids = [q["id"] for q in resp_active.json["questions"]]

    resp_eval = client.post(
        "/api/v1/evaluations",
        json={
            "age_at_evaluation": 9,
            "evaluation_date": "2025-01-01",
            "status": "submitted",
            "responses": [
                {"question_id": question_ids[0], "value": "3"},
                {"question_id": question_ids[1], "value": "true"},
            ],
        },
        headers=headers,
    )
    assert resp_eval.status_code == 201
    evaluation_id = resp_eval.json["evaluation_id"]

    with app.app_context():
        evaluation = Evaluation.query.filter_by(id=uuid.UUID(evaluation_id)).first()
        responses = EvaluationResponse.query.filter_by(
            evaluation_id=uuid.UUID(evaluation_id)
        ).all()
        assert evaluation is not None
        assert evaluation.questionnaire_template_id is not None
        assert len(responses) == 2


def test_create_evaluation_rejects_invalid_question(client, app):
    _create_active_template(client, app)
    token = _user_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    bad_question_id = str(uuid.uuid4())
    resp_eval = client.post(
        "/api/v1/evaluations",
        json={
            "age_at_evaluation": 10,
            "evaluation_date": "2025-01-02",
            "status": "submitted",
            "responses": [{"question_id": bad_question_id, "value": "1"}],
        },
        headers=headers,
    )
    assert resp_eval.status_code == 400
