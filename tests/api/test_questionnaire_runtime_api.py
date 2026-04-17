import os
import sys
import uuid

import pytest
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.security import hash_password
from app.models import AppUser, Role, UserRole, db
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


def _ensure_roles(role_names: list[str]):
    roles = {}
    for name in role_names:
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(name=name)
            db.session.add(role)
            db.session.flush()
        roles[name] = role
    return roles


def _create_user_with_token(app, *, username: str, email: str, user_type: str = "guardian", roles: list[str] | None = None):
    roles = roles or []
    with app.app_context():
        user = AppUser(
            username=username,
            email=email,
            password=hash_password("StrongPass123!"),
            full_name=username,
            user_type=user_type,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        if roles:
            role_rows = _ensure_roles(roles)
            for role_name in roles:
                db.session.add(UserRole(user_id=user.id, role_id=role_rows[role_name].id))

        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": roles})
        return user.id, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_questionnaire_runtime_user_flow_completed_and_results(client, app):
    _, token = _create_user_with_token(
        app,
        username=f"guardian_{uuid.uuid4().hex[:6]}",
        email=f"guardian_{uuid.uuid4().hex[:6]}@example.com",
        user_type="guardian",
    )
    headers = _auth_headers(token)

    active = client.get("/api/v1/questionnaire-runtime/questionnaire/active", headers=headers)
    assert active.status_code == 200
    sections = active.json["sections"]
    assert sections

    first_questions = []
    for section in sections:
        for q in section["questions"]:
            if q["response_type"] == "consent/info_only":
                continue
            first_questions.append(q)
            if len(first_questions) >= 4:
                break
        if len(first_questions) >= 4:
            break
    assert len(first_questions) >= 1

    draft_payload = {
        "respondent_type": "caregiver",
        "child_age_years": 9,
        "child_sex_assigned_at_birth": "Male",
        "consent_accepted": True,
    }
    draft = client.post("/api/v1/questionnaire-runtime/evaluations/draft", json=draft_payload, headers=headers)
    assert draft.status_code == 201
    evaluation_id = draft.json["evaluation_id"]

    answers = []
    for q in first_questions:
        if q["response_type"] in {"boolean", "single_choice"}:
            value = q.get("options", [{"value": "1"}])[0]["value"]
        elif q["response_type"] in {"integer", "likert_single", "numeric_range"}:
            value = q.get("min_value") if q.get("min_value") is not None else 1
        else:
            value = 1
        answers.append({"question_id": q["id"], "value": value})

    save = client.patch(
        f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/draft",
        json={"answers": answers, "consent_accepted": True},
        headers=headers,
    )
    assert save.status_code == 200

    submit = client.post(
        f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/submit",
        json={"wait_live_result": False},
        headers=headers,
    )
    assert submit.status_code in (200, 202)

    status = client.get(f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/status", headers=headers)
    assert status.status_code == 200
    assert status.json["status"] in {"processing", "completed"}

    results = client.get(f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/results", headers=headers)
    assert results.status_code == 200
    domains = results.json["results"]
    assert {d["domain"] for d in domains} == {"adhd", "conduct", "elimination", "anxiety", "depression"}
    elimination = [d for d in domains if d["domain"] == "elimination"][0]
    assert elimination["model_status"] == "experimental_line_more_useful_not_product_ready"

    notifications = client.get("/api/v1/questionnaire-runtime/notifications", headers=headers)
    assert notifications.status_code == 200
    assert notifications.json["count"] >= 1

    export = client.get(
        f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/export?mode=responses_and_results",
        headers=headers,
    )
    assert export.status_code == 200
    assert "metadata" in export.json


def test_questionnaire_runtime_professional_access_and_soft_delete(client, app):
    _, owner_token = _create_user_with_token(
        app,
        username=f"owner_{uuid.uuid4().hex[:6]}",
        email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
        user_type="guardian",
    )
    _, psych_token = _create_user_with_token(
        app,
        username=f"psy_{uuid.uuid4().hex[:6]}",
        email=f"psy_{uuid.uuid4().hex[:6]}@example.com",
        user_type="psychologist",
        roles=["PSYCHOLOGIST"],
    )

    owner_headers = _auth_headers(owner_token)
    psych_headers = _auth_headers(psych_token)

    active = client.get("/api/v1/questionnaire-runtime/questionnaire/active", headers=owner_headers)
    assert active.status_code == 200
    first_question = None
    for section in active.json["sections"]:
        if section["questions"]:
            first_question = section["questions"][0]
            break
    assert first_question is not None
    if first_question["response_type"] in {"boolean", "single_choice"}:
        sample_value = first_question.get("options", [{"value": "1"}])[0]["value"]
    else:
        sample_value = first_question.get("min_value") if first_question.get("min_value") is not None else 1

    draft = client.post(
        "/api/v1/questionnaire-runtime/evaluations/draft",
        json={
            "respondent_type": "caregiver",
            "child_age_years": 10,
            "child_sex_assigned_at_birth": "Female",
            "consent_accepted": True,
            "answers": [{"question_id": first_question["id"], "value": sample_value}],
        },
        headers=owner_headers,
    )
    assert draft.status_code == 201
    evaluation_id = draft.json["evaluation_id"]
    reference_id = draft.json["reference_id"]
    pin = draft.json["pin"]

    submit = client.post(
        f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/submit",
        json={"wait_live_result": False},
        headers=owner_headers,
    )
    assert submit.status_code in (200, 202)

    access = client.post(
        "/api/v1/questionnaire-runtime/professional/access",
        json={"reference_id": reference_id, "pin": pin},
        headers=psych_headers,
    )
    assert access.status_code == 200

    p_results = client.get(
        f"/api/v1/questionnaire-runtime/professional/evaluations/{evaluation_id}/results",
        headers=psych_headers,
    )
    assert p_results.status_code == 200
    assert "probability" in p_results.json["results"][0]

    set_tag = client.patch(
        f"/api/v1/questionnaire-runtime/professional/evaluations/{evaluation_id}/tag",
        json={"tag": "en revision"},
        headers=psych_headers,
    )
    assert set_tag.status_code == 200
    assert set_tag.json["review_tag"] == "en_revision"

    remove = client.delete(f"/api/v1/questionnaire-runtime/evaluations/{evaluation_id}", headers=owner_headers)
    assert remove.status_code == 200

    after_delete = client.get(
        f"/api/v1/questionnaire-runtime/professional/evaluations/{evaluation_id}/results",
        headers=psych_headers,
    )
    assert after_delete.status_code == 410


def test_questionnaire_runtime_admin_versioning_flow(client, app):
    _, admin_token = _create_user_with_token(
        app,
        username=f"admin_{uuid.uuid4().hex[:6]}",
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        user_type="guardian",
        roles=["ADMIN"],
    )
    headers = _auth_headers(admin_token)

    bootstrap = client.post("/api/v1/questionnaire-runtime/admin/bootstrap", headers=headers)
    assert bootstrap.status_code == 201

    create_tpl = client.post(
        "/api/v1/questionnaire-runtime/admin/templates",
        json={"slug": f"tpl-{uuid.uuid4().hex[:8]}", "name": "Template QA", "description": "test"},
        headers=headers,
    )
    assert create_tpl.status_code == 201
    template_id = create_tpl.json["id"]

    create_ver = client.post(
        f"/api/v1/questionnaire-runtime/admin/templates/{template_id}/versions",
        json={"version_label": "v2.0.0", "changelog": "new", "clone_from_active": True},
        headers=headers,
    )
    assert create_ver.status_code == 201
    version_id = create_ver.json["id"]

    disclosure = client.post(
        f"/api/v1/questionnaire-runtime/admin/versions/{version_id}/disclosures",
        json={
            "disclosure_type": "disclaimer_result",
            "version_label": "v2",
            "title": "Resultado",
            "content_markdown": "Texto actualizado",
        },
        headers=headers,
    )
    assert disclosure.status_code == 201

    set_active = client.post(
        f"/api/v1/questionnaire-runtime/admin/templates/{template_id}/active",
        json={"is_active": True},
        headers=headers,
    )
    assert set_active.status_code == 200
    assert set_active.json["is_active"] is True

    publish = client.post(
        f"/api/v1/questionnaire-runtime/admin/versions/{version_id}/publish",
        headers=headers,
    )
    assert publish.status_code == 200
    assert publish.json["is_published"] is True


def test_questionnaire_runtime_create_draft_validates_payload(client, app):
    _, token = _create_user_with_token(
        app,
        username=f"guardian_invalid_{uuid.uuid4().hex[:6]}",
        email=f"guardian_invalid_{uuid.uuid4().hex[:6]}@example.com",
        user_type="guardian",
    )
    headers = _auth_headers(token)

    invalid = client.post(
        "/api/v1/questionnaire-runtime/evaluations/draft",
        json={"respondent_type": "caregiver", "child_age_years": 3},
        headers=headers,
    )
    assert invalid.status_code == 400
    assert invalid.json["error"] == "validation_error"
