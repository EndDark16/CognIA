# api/services/evaluation_service.py

import hashlib
import secrets
from datetime import datetime, timezone

from app.models import Evaluation, EvaluationResponse, Question
from app.models import db
from api.security import hash_password


def generate_access_key() -> str:
    # Short, URL-safe token for sharing.
    return secrets.token_urlsafe(8)


def _hash_access_key(access_key: str) -> str:
    return hash_password(access_key)


def _generate_registration_number(evaluation_id, created_at: datetime) -> str:
    date_part = created_at.strftime("%Y%m%d")
    hash_part = hashlib.md5(str(evaluation_id).encode("utf-8")).hexdigest()[:8]
    return f"EV-{date_part}-{hash_part}"


def build_evaluation_payload(
    *,
    evaluation_id,
    requested_by_user_id,
    questionnaire_template_id,
    age_at_evaluation,
    evaluation_date,
    status,
    subject_id=None,
    psychologist_id=None,
    context=None,
    raw_symptoms=None,
    processed_features=None,
    is_anonymous=True,
):
    created_at = datetime.now(timezone.utc)
    registration_number = _generate_registration_number(evaluation_id, created_at)
    return Evaluation(
        id=evaluation_id,
        subject_id=subject_id,
        requested_by_user_id=requested_by_user_id,
        psychologist_id=psychologist_id,
        age_at_evaluation=age_at_evaluation,
        context=context,
        raw_symptoms=raw_symptoms,
        processed_features=processed_features,
        evaluation_date=evaluation_date,
        status=status,
        is_anonymous=is_anonymous,
        created_at=created_at,
        questionnaire_template_id=questionnaire_template_id,
        registration_number=registration_number,
    )


def attach_access_key(evaluation: Evaluation, access_key: str) -> None:
    evaluation.access_key_hash = _hash_access_key(access_key)
    evaluation.access_key_created_at = datetime.now(timezone.utc)
    evaluation.access_key_failed_attempts = 0
    evaluation.access_key_locked_until = None
    evaluation.requires_access_key_reset = False


def build_evaluation_responses(evaluation_id, responses):
    return [
        EvaluationResponse(
            evaluation_id=evaluation_id,
            question_id=resp["question_id"],
            value=str(resp["value"]),
        )
        for resp in responses
    ]


def get_template_question_ids(template_id):
    return {
        str(q.id)
        for q in Question.query.filter_by(questionnaire_id=template_id).all()
    }
