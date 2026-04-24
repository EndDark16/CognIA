# api/services/evaluation_service.py

import hashlib
import secrets
from datetime import datetime, timezone

from app.models import Evaluation, EvaluationResponse, Question
from api.security import hash_password

_INTEGER_TYPES = {
    "likert_0_4",
    "likert_1_5",
    "frequency_0_3",
    "intensity_0_10",
    "count",
    "ordinal",
}
_DEFAULT_RANGES = {
    "likert_0_4": (0, 4),
    "likert_1_5": (1, 5),
    "frequency_0_3": (0, 3),
    "intensity_0_10": (0, 10),
}


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


def get_template_questions_map(template_id):
    questions = Question.query.filter_by(questionnaire_id=template_id).all()
    return {str(q.id): q for q in questions}


def _coerce_numeric(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in ("true", "false"):
            return float(1 if raw == "true" else 0)
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _normalize_boolean(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and int(value) in (0, 1) and float(value).is_integer():
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in ("0", "1"):
            return int(raw)
        if raw in ("true", "false"):
            return 1 if raw == "true" else 0
    return None


def _normalize_options(options):
    numeric_options = []
    string_options = set()
    for opt in options:
        numeric = _coerce_numeric(opt)
        if numeric is not None:
            numeric_options.append(float(numeric))
        else:
            string_options.add(str(opt).strip())
    return numeric_options, string_options


def validate_response_value(question, value):
    response_type = question.response_type
    response_min = float(question.response_min) if question.response_min is not None else None
    response_max = float(question.response_max) if question.response_max is not None else None
    response_step = float(question.response_step) if question.response_step is not None else None
    response_options = question.response_options

    if response_type == "text_context":
        if value is None:
            return False, "missing_text_context", None
        return True, None, str(value)

    if response_type == "boolean":
        normalized = _normalize_boolean(value)
        if normalized is None:
            return False, "invalid_boolean", None
        if response_options:
            numeric_opts, string_opts = _normalize_options(response_options)
            if numeric_opts and not any(abs(normalized - opt) < 1e-6 for opt in numeric_opts):
                return False, "option_not_allowed", None
            if string_opts and str(normalized) not in string_opts:
                return False, "option_not_allowed", None
        return True, None, str(normalized)

    numeric_value = _coerce_numeric(value)
    if numeric_value is None:
        return False, "invalid_numeric", None

    if response_type in _INTEGER_TYPES:
        if response_step is None or float(response_step).is_integer():
            if not float(numeric_value).is_integer():
                return False, "expected_integer", None
        numeric_value = float(int(round(numeric_value)))

    min_value = response_min
    max_value = response_max
    if min_value is None and response_type in _DEFAULT_RANGES:
        min_value, max_value = _DEFAULT_RANGES[response_type]
    if response_type == "count" and min_value is None:
        min_value = 0

    if min_value is not None and numeric_value < float(min_value):
        return False, "below_min", None
    if max_value is not None and numeric_value > float(max_value):
        return False, "above_max", None

    if response_step is not None:
        base = min_value if min_value is not None else 0.0
        step = float(response_step)
        if step > 0:
            delta = (numeric_value - base) / step
            if abs(round(delta) - delta) > 1e-6:
                return False, "invalid_step", None

    if response_options:
        numeric_opts, string_opts = _normalize_options(response_options)
        if numeric_opts:
            if not any(abs(numeric_value - opt) < 1e-6 for opt in numeric_opts):
                return False, "option_not_allowed", None
        elif str(value).strip() not in string_opts:
            return False, "option_not_allowed", None

    return True, None, str(int(numeric_value)) if float(numeric_value).is_integer() else str(numeric_value)
