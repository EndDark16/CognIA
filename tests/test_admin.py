import os
import sys
import uuid
from datetime import date, datetime, timezone

import pytest
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.security import hash_password
from app.models import (
    AppUser,
    AuditLog,
    EmailUnsubscribe,
    Evaluation,
    PasswordResetToken,
    Question,
    QuestionnaireTemplate,
    RecoveryCode,
    Role,
    UserMFA,
    UserRole,
    db,
)
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


def _admin_token(app, admin_id):
    with app.app_context():
        return create_access_token(identity=str(admin_id), additional_claims={"roles": ["ADMIN"]})


def _create_admin(app) -> uuid.UUID:
    with app.app_context():
        admin = AppUser(
            username=f"admin_{uuid.uuid4().hex[:6]}",
            email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
            password=hash_password("AdminPass123!"),
            user_type="guardian",
            is_active=True,
        )
        role = Role.query.filter_by(name="ADMIN").first()
        if not role:
            role = Role(name="ADMIN")
            db.session.add(role)
            db.session.flush()
        db.session.add(admin)
        db.session.flush()
        if not UserRole.query.filter_by(user_id=admin.id, role_id=role.id).first():
            db.session.add(UserRole(user_id=admin.id, role_id=role.id))
        db.session.commit()
        return admin.id


def _create_guardian(app, *, roles: list[str] | None = None) -> uuid.UUID:
    with app.app_context():
        user = AppUser(
            username=f"guardian_{uuid.uuid4().hex[:6]}",
            email=f"guardian_{uuid.uuid4().hex[:6]}@example.com",
            password=hash_password("GuardianPass123!"),
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        base_role = Role.query.filter_by(name="GUARDIAN").first()
        if not base_role:
            base_role = Role(name="GUARDIAN")
            db.session.add(base_role)
            db.session.flush()
        if not UserRole.query.filter_by(user_id=user.id, role_id=base_role.id).first():
            db.session.add(UserRole(user_id=user.id, role_id=base_role.id))
        for role_name in roles or []:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)
                db.session.flush()
            if not UserRole.query.filter_by(user_id=user.id, role_id=role.id).first():
                db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()
        return user.id


def _create_psychologist(app, *, verified: bool = False) -> uuid.UUID:
    with app.app_context():
        user = AppUser(
            username=f"psych_{uuid.uuid4().hex[:6]}",
            email=f"psych_{uuid.uuid4().hex[:6]}@example.com",
            password=hash_password("PsychPass123!"),
            user_type="psychologist",
            professional_card_number=f"COLPSIC-{uuid.uuid4().hex[:6]}",
            is_active=True,
            colpsic_verified=verified,
        )
        role = Role.query.filter_by(name="PSYCHOLOGIST").first()
        if not role:
            role = Role(name="PSYCHOLOGIST")
            db.session.add(role)
            db.session.flush()
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()
        return user.id


def _create_questionnaire(app, *, name: str, version: str) -> uuid.UUID:
    with app.app_context():
        template = QuestionnaireTemplate(
            name=name,
            version=version,
            description="test template",
            is_active=False,
        )
        db.session.add(template)
        db.session.commit()
        return template.id


def _add_question(app, *, template_id: uuid.UUID, code: str = "Q1"):
    with app.app_context():
        question = Question(
            questionnaire_id=template_id,
            code=code,
            text="Texto de prueba",
            response_type="text",
        )
        db.session.add(question)
        db.session.commit()


def test_admin_approve_and_reject_psychologist(client, app, monkeypatch):
    admin_id = _create_admin(app)
    psych_id = _create_psychologist(app, verified=False)
    token = _admin_token(app, admin_id)

    resp_approve = client.post(
        f"/api/admin/psychologists/{psych_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_approve.status_code == 200

    with app.app_context():
        updated = db.session.get(AppUser, psych_id)
        assert updated.colpsic_verified is True
        assert updated.is_active is True
        assert updated.colpsic_rejected_at is None

    sent = {}

    def _fake_send(**kwargs):
        sent["called"] = True
        sent["reason"] = kwargs.get("reject_reason")

    monkeypatch.setattr("api.services.admin_service.send_psychologist_rejected_email", _fake_send)

    resp_reject = client.post(
        f"/api/admin/psychologists/{psych_id}/reject",
        json={"reason": "Documento incompleto"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_reject.status_code == 200
    assert resp_reject.json.get("email_sent") is True
    assert sent["called"] is True

    with app.app_context():
        updated = db.session.get(AppUser, psych_id)
        assert updated.colpsic_verified is False
        assert updated.is_active is False
        assert updated.colpsic_reject_reason == "Documento incompleto"
        assert updated.sessions_revoked_at is not None


def test_admin_reapprove_overrides_previous_reject(client, app, monkeypatch):
    admin_id = _create_admin(app)
    psych_id = _create_psychologist(app, verified=False)
    token = _admin_token(app, admin_id)

    monkeypatch.setattr(
        "api.services.admin_service.send_psychologist_rejected_email",
        lambda **kwargs: None,
    )

    resp_reject = client.post(
        f"/api/admin/psychologists/{psych_id}/reject",
        json={"reason": "COLPSIC no legible"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_reject.status_code == 200

    resp_approve = client.post(
        f"/api/admin/psychologists/{psych_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_approve.status_code == 200

    with app.app_context():
        updated = db.session.get(AppUser, psych_id)
        assert updated.colpsic_verified is True
        assert updated.is_active is True
        assert updated.colpsic_rejected_at is None
        assert updated.colpsic_rejected_by is None
        assert updated.colpsic_reject_reason is None


def test_admin_password_reset_creates_token(client, app, monkeypatch):
    admin_id = _create_admin(app)
    user_id = _create_psychologist(app, verified=True)
    token = _admin_token(app, admin_id)

    called = {}

    def _fake_send(*, to_email, reset_link, full_name):
        called["to_email"] = to_email
        called["reset_link"] = reset_link

    monkeypatch.setattr("api.services.admin_service.send_password_reset", _fake_send)

    resp = client.post(
        f"/api/admin/users/{user_id}/password-reset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    with app.app_context():
        entry = PasswordResetToken.query.filter_by(user_id=user_id).first()
        assert entry is not None
        refreshed = db.session.get(AppUser, user_id)
        assert refreshed.sessions_revoked_at is not None


def test_admin_mfa_reset(client, app):
    admin_id = _create_admin(app)
    user_id = _create_psychologist(app, verified=True)
    token = _admin_token(app, admin_id)

    with app.app_context():
        user = db.session.get(AppUser, user_id)
        user.mfa_enabled = True
        db.session.add(user)
        db.session.add(UserMFA(user_id=user_id, secret_encrypted="test"))
        db.session.add(RecoveryCode(user_id=user_id, code_hash="hash"))
        db.session.commit()

    resp = client.post(
        f"/api/admin/users/{user_id}/mfa/reset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    with app.app_context():
        refreshed = db.session.get(AppUser, user_id)
        assert refreshed.mfa_enabled is False
        assert UserMFA.query.filter_by(user_id=user_id).first() is None
        assert RecoveryCode.query.filter_by(user_id=user_id).first() is None


def test_admin_list_users_with_role_filter(client, app):
    admin_id = _create_admin(app)
    psych_id = _create_psychologist(app, verified=False)
    _create_guardian(app)
    token = _admin_token(app, admin_id)

    resp = client.get(
        "/api/admin/users?role=PSYCHOLOGIST",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json.get("items") or []
    assert len(items) == 1
    assert items[0]["id"] == str(psych_id)


def test_admin_patch_user_updates_user_type_and_roles(client, app):
    admin_id = _create_admin(app)
    user_id = _create_guardian(app)
    token = _admin_token(app, admin_id)

    resp = client.patch(
        f"/api/admin/users/{user_id}",
        json={"user_type": "psychologist", "professional_card_number": "COLPSIC-9999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    with app.app_context():
        updated = db.session.get(AppUser, user_id)
        assert updated.user_type == "psychologist"
        assert updated.colpsic_verified is False
        assert updated.sessions_revoked_at is not None
        roles = [r.name for r in updated.roles]
        assert "PSYCHOLOGIST" in roles


def test_admin_questionnaire_publish_archive_clone(client, app):
    admin_id = _create_admin(app)
    token = _admin_token(app, admin_id)
    template_id = _create_questionnaire(app, name="QTest", version="v1")

    resp_empty = client.post(
        f"/api/admin/questionnaires/{template_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_empty.status_code == 409

    _add_question(app, template_id=template_id, code="Q1")

    resp_publish = client.post(
        f"/api/admin/questionnaires/{template_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_publish.status_code == 200

    resp_archive = client.post(
        f"/api/admin/questionnaires/{template_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_archive.status_code == 200

    with app.app_context():
        template = db.session.get(QuestionnaireTemplate, template_id)
        assert template.is_archived is True
        assert template.is_active is False

    resp_clone = client.post(
        f"/api/admin/questionnaires/{template_id}/clone",
        json={"name": "QTest Clone", "version": "v2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_clone.status_code == 201
    assert resp_clone.json.get("question_count") == 1


def test_admin_audit_logs_list(client, app):
    admin_id = _create_admin(app)
    token = _admin_token(app, admin_id)
    with app.app_context():
        entry = AuditLog(user_id=admin_id, action="TEST_ACTION", section="admin", details={"ok": True})
        db.session.add(entry)
        db.session.commit()

    resp = client.get(
        "/api/admin/audit-logs?section=admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    actions = [item["action"] for item in resp.json.get("items", [])]
    assert "TEST_ACTION" in actions


def test_admin_roles_create_and_assign(client, app):
    admin_id = _create_admin(app)
    user_id = _create_guardian(app)
    token = _admin_token(app, admin_id)

    resp_role = client.post(
        "/api/admin/roles",
        json={"name": "ANALYST", "description": "QA"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_role.status_code == 201

    resp_assign = client.post(
        f"/api/admin/users/{user_id}/roles",
        json={"roles": ["ANALYST"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_assign.status_code == 200

    with app.app_context():
        user = db.session.get(AppUser, user_id)
        assert "ANALYST" in [r.name for r in user.roles]


def test_admin_email_unsubscribes_flow(client, app):
    admin_id = _create_admin(app)
    token = _admin_token(app, admin_id)
    with app.app_context():
        entry = EmailUnsubscribe(email="unsub@example.com", reason="test", source="manual")
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    resp_list = client.get(
        "/api/admin/email/unsubscribes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_list.status_code == 200
    emails = [item["email"] for item in resp_list.json.get("items", [])]
    assert "unsub@example.com" in emails

    resp_remove = client.post(
        f"/api/admin/email/unsubscribes/{entry_id}/remove",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_remove.status_code == 200

    with app.app_context():
        assert db.session.get(EmailUnsubscribe, entry_id) is None


def test_admin_evaluations_list_and_update_status(client, app):
    admin_id = _create_admin(app)
    requester_id = _create_guardian(app)
    token = _admin_token(app, admin_id)
    template_id = _create_questionnaire(app, name="EvalQ", version="v1")

    with app.app_context():
        evaluation = Evaluation(
            requested_by_user_id=requester_id,
            questionnaire_template_id=template_id,
            age_at_evaluation=8,
            evaluation_date=date.today(),
            status="draft",
            registration_number="REG-1",
            access_key_hash="hash",
            access_key_created_at=datetime.now(timezone.utc),
        )
        db.session.add(evaluation)
        db.session.commit()
        evaluation_id = evaluation.id

    resp_list = client.get(
        "/api/admin/evaluations?status=draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_list.status_code == 200
    items = resp_list.json.get("items", [])
    assert any(item["id"] == str(evaluation_id) for item in items)

    resp_update = client.patch(
        f"/api/admin/evaluations/{evaluation_id}/status",
        json={"status": "submitted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_update.status_code == 200

    with app.app_context():
        updated = db.session.get(Evaluation, evaluation_id)
        assert updated.status == "submitted"


def test_admin_email_health_metrics_and_impersonate(client, app):
    admin_id = _create_admin(app)
    user_id = _create_guardian(app)
    token = _admin_token(app, admin_id)

    resp_health = client.get(
        "/api/admin/email/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_health.status_code == 200
    assert "email_enabled" in resp_health.json

    resp_metrics = client.get(
        "/api/admin/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_metrics.status_code == 200
    assert "requests_total" in resp_metrics.json

    resp_impersonate = client.post(
        f"/api/admin/impersonate/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_impersonate.status_code == 200
    assert resp_impersonate.json.get("access_token")
