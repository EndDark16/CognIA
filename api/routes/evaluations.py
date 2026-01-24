# api/routes/evaluations.py

import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from api.schemas.evaluation_schema import EvaluationCreateSchema
from api.security import log_audit
from api.services.evaluation_service import (
    attach_access_key,
    build_evaluation_payload,
    build_evaluation_responses,
    generate_access_key,
    get_template_question_ids,
)
from api.services.questionnaire_service import get_active_template
from app.models import db, Subject


evaluations_bp = Blueprint("evaluations", __name__, url_prefix="/api/v1/evaluations")


def _parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _error_response(message: str, error_code: str, status_code: int, details=None):
    payload = {"msg": message, "error": error_code}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


@evaluations_bp.post("")
@jwt_required()
def create_evaluation():
    identity = _parse_uuid(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)

    schema = EvaluationCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    template = get_active_template()
    if not template:
        return _error_response("No active questionnaire template", "no_active_template", 409)

    responses = data.get("responses") or []
    if not responses:
        return _error_response("Missing responses", "missing_responses", 400)

    question_ids = [resp.get("question_id") for resp in responses]
    if any(qid is None for qid in question_ids):
        return _error_response("Missing question_id", "missing_question_id", 400)

    if len(set(map(str, question_ids))) != len(question_ids):
        return _error_response("Duplicate question_id in responses", "duplicate_question_id", 400)

    valid_ids = get_template_question_ids(template.id)
    if not valid_ids:
        return _error_response("Template has no questions", "template_empty", 409)

    invalid = [qid for qid in question_ids if str(qid) not in valid_ids]
    if invalid:
        return _error_response(
            "Invalid question_id for template",
            "invalid_question_id",
            400,
            {"question_ids": invalid},
        )

    subject_id = data.get("subject_id")
    if subject_id:
        subject_uuid = _parse_uuid(subject_id)
        if not subject_uuid:
            return _error_response("Invalid subject_id", "invalid_subject_id", 400)
        subject = Subject.query.filter_by(id=subject_uuid).first()
        if not subject:
            return _error_response("Subject not found", "subject_not_found", 404)
    else:
        subject_uuid = None

    is_anonymous = data.get("is_anonymous")
    if is_anonymous is None:
        is_anonymous = subject_uuid is None

    access_key = data.get("access_key")
    if access_key:
        access_key = str(access_key).strip()
        if len(access_key) < 6 or len(access_key) > 64:
            return _error_response("Invalid access_key length", "invalid_access_key", 400)
    else:
        access_key = generate_access_key()

    evaluation_id = uuid.uuid4()
    evaluation = build_evaluation_payload(
        evaluation_id=evaluation_id,
        requested_by_user_id=identity,
        questionnaire_template_id=template.id,
        age_at_evaluation=data["age_at_evaluation"],
        evaluation_date=data["evaluation_date"],
        status=data["status"],
        subject_id=subject_uuid,
        psychologist_id=None,
        context=data.get("context"),
        raw_symptoms=data.get("raw_symptoms"),
        processed_features=data.get("processed_features"),
        is_anonymous=is_anonymous,
    )

    attach_access_key(evaluation, access_key)
    evaluation_responses = build_evaluation_responses(evaluation_id, responses)

    try:
        db.session.add(evaluation)
        db.session.add_all(evaluation_responses)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error_response("Database error", "db_error", 500)

    log_audit(
        identity,
        "EVALUATION_CREATED",
        "evaluations",
        {"evaluation_id": str(evaluation.id), "template_id": str(template.id)},
    )

    return (
        jsonify(
            {
                "evaluation_id": str(evaluation.id),
                "registration_number": evaluation.registration_number,
                "questionnaire_template_id": str(template.id),
                "access_key": access_key,
            }
        ),
        201,
    )
