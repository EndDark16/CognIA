import os
import sys
import uuid

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import crypto_service
from api.services import questionnaire_runtime_service as qr_service
from app.models import AppUser, QRDomainResult, QREvaluation, QREvaluationResponse, QRNotification, db
from config.settings import TestingConfig


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("COGNIA_FIELD_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")

    class RuntimeEncryptionConfig(TestingConfig):
        COGNIA_ENABLE_FIELD_ENCRYPTION = True
        QR_PROCESS_ASYNC = False

    app = create_app(RuntimeEncryptionConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_runtime_sensitive_fields_are_encrypted_at_rest_and_decrypted_on_read(app):
    with app.app_context():
        user = AppUser(
            username=f"runtime_enc_{uuid.uuid4().hex[:8]}",
            email=f"runtime_enc_{uuid.uuid4().hex[:8]}@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        active = qr_service.get_active_questionnaire_payload()
        candidate = None
        for section in active.get("sections", []):
            for question in section.get("questions", []):
                if question.get("response_type") != "consent/info_only":
                    candidate = question
                    break
            if candidate is not None:
                break
        assert candidate is not None

        if candidate["response_type"] in {"single_choice", "boolean"}:
            options = candidate.get("options") or [{"value": "1"}]
            answer_value = options[0]["value"]
        else:
            answer_value = candidate.get("min_value") if candidate.get("min_value") is not None else 1

        evaluation, _pin = qr_service.create_evaluation_draft(
            user_id=user.id,
            payload={
                "respondent_type": "guardian",
                "child_age_years": 9,
                "child_sex_assigned_at_birth": "Male",
                "consent_accepted": True,
                "answers": [{"question_id": candidate["id"], "value": answer_value}],
            },
        )

        response_row = QREvaluationResponse.query.filter_by(evaluation_id=evaluation.id).first()
        assert response_row is not None
        assert crypto_service.is_encrypted(response_row.answer_raw)
        assert crypto_service.is_encrypted(response_row.answer_normalized)

        qr_service.submit_evaluation(evaluation, wait_live_result=False)
        evaluation = db.session.get(QREvaluation, evaluation.id)
        assert evaluation is not None
        assert evaluation.status in {"submitted", "processing", "completed"}
        if evaluation.status != "completed":
            qr_service.process_evaluation_sync(evaluation.id)
            evaluation = db.session.get(QREvaluation, evaluation.id)

        result_row = QRDomainResult.query.filter_by(evaluation_id=evaluation.id).first()
        assert result_row is not None
        assert crypto_service.is_encrypted(result_row.recommendation_text)
        assert crypto_service.is_encrypted(result_row.explanation_short)
        assert crypto_service.is_encrypted(result_row.contributors_json)
        assert crypto_service.is_encrypted(result_row.caveats_json)

        notification_row = QRNotification.query.filter_by(evaluation_id=evaluation.id).first()
        assert notification_row is not None
        assert crypto_service.is_encrypted(notification_row.title)
        assert crypto_service.is_encrypted(notification_row.body)
        assert crypto_service.is_encrypted(notification_row.payload_json)

        responses_payload = qr_service.get_responses_payload(evaluation)
        assert responses_payload["answers"]
        assert "value" in responses_payload["answers"][0]

        results_payload = qr_service.get_results_payload(evaluation, audience="professional")
        assert results_payload["results"]
        assert "contributors" in results_payload["results"][0]

        notifications_payload = qr_service.list_notifications(user.id)
        assert notifications_payload
        assert notifications_payload[0]["title"]
