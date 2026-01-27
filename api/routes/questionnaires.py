# api/routes/questionnaires.py

import uuid

from flask import Blueprint, jsonify, request
from marshmallow import ValidationError

from api.decorators import roles_required
from api.schemas.questionnaire_schema import (
    QuestionnaireCreateSchema,
    QuestionnaireCloneSchema,
    QuestionCreateSchema,
)
from api.security import log_audit
from api.services.questionnaire_service import (
    activate_template,
    clone_template,
    deactivate_all_templates,
    get_active_template,
    get_template_questions,
)
from app.models import db, QuestionnaireTemplate, Question, Disorder


questionnaires_bp = Blueprint("questionnaires", __name__, url_prefix="/api/v1/questionnaires")


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


def _validate_question_constraints(item):
    response_type = item.get("response_type")
    response_min = item.get("response_min")
    response_max = item.get("response_max")
    response_step = item.get("response_step")
    response_options = item.get("response_options")

    if response_type == "text_context":
        if any(
            value is not None
            for value in (response_min, response_max, response_step, response_options)
        ):
            return "text_context_no_constraints"
        return None

    if response_min is not None and response_max is not None and response_min > response_max:
        return "response_min_gt_max"
    if response_step is not None and response_step <= 0:
        return "response_step_invalid"
    if response_options is not None and not isinstance(response_options, list):
        return "response_options_invalid"
    if response_options is not None and isinstance(response_options, list) and len(response_options) == 0:
        return "response_options_empty"
    if response_type == "ordinal" and not response_options:
        return "response_options_required_for_ordinal"
    return None


def _normalize_disorder_ids(item):
    disorder_ids = []
    if item.get("disorder_id"):
        disorder_ids.append(item["disorder_id"])
    if item.get("disorder_ids"):
        disorder_ids.extend(item["disorder_ids"])
    unique = []
    seen = set()
    for entry in disorder_ids:
        key = str(entry)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


@questionnaires_bp.get("/active")
def get_active_questionnaire():
    template = get_active_template()
    if not template:
        return _error_response("No active questionnaire template", "no_active_template", 404)

    questions = get_template_questions(template.id)
    return (
        jsonify(
            {
                "questionnaire_template": {
                    "id": str(template.id),
                    "name": template.name,
                    "version": template.version,
                    "description": template.description,
                    "is_active": template.is_active,
                },
                "questions": [
                    {
                        "id": str(q.id),
                        "code": q.code,
                        "text": q.text,
                        "response_type": q.response_type,
                        "disorder_id": str(q.disorder_id) if q.disorder_id else None,
                        "disorder_ids": [str(d.id) for d in q.disorders] or (
                            [str(q.disorder_id)] if q.disorder_id else []
                        ),
                        "position": q.position,
                        "response_min": float(q.response_min) if q.response_min is not None else None,
                        "response_max": float(q.response_max) if q.response_max is not None else None,
                        "response_step": float(q.response_step) if q.response_step is not None else None,
                        "response_options": q.response_options,
                    }
                    for q in questions
                ],
            }
        ),
        200,
    )


@questionnaires_bp.post("")
@roles_required("ADMIN")
def create_questionnaire():
    schema = QuestionnaireCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    name = data["name"].strip()
    version = data["version"].strip()
    description = data.get("description")

    existing = QuestionnaireTemplate.query.filter_by(name=name, version=version).first()
    if existing:
        return _error_response("Template already exists", "template_exists", 409)

    template = QuestionnaireTemplate(
        name=name,
        version=version,
        description=description,
        is_active=False,
    )

    try:
        db.session.add(template)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error_response("Database error", "db_error", 500)

    log_audit(None, "QUESTIONNAIRE_CREATED", "questionnaires", {"template_id": str(template.id)})
    return jsonify({"id": str(template.id), "name": template.name, "version": template.version}), 201


@questionnaires_bp.post("/<template_id>/questions")
@roles_required("ADMIN")
def add_questions(template_id):
    template_uuid = _parse_uuid(template_id)
    if not template_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)

    template = QuestionnaireTemplate.query.filter_by(id=template_uuid).first()
    if not template:
        return _error_response("Template not found", "template_not_found", 404)
    if template.is_active:
        return _error_response("Template is active", "template_active", 409)

    payload = request.get_json(silent=True)
    if payload is None:
        return _error_response("Missing payload", "missing_payload", 400)

    if isinstance(payload, list):
        schema = QuestionCreateSchema(many=True)
        try:
            items = schema.load(payload)
        except ValidationError as exc:
            return _error_response("Validation error", "validation_error", 400, exc.messages)
    else:
        schema = QuestionCreateSchema()
        try:
            items = [schema.load(payload)]
        except ValidationError as exc:
            return _error_response("Validation error", "validation_error", 400, exc.messages)

    codes = [item["code"].strip() for item in items]
    if len(set(codes)) != len(codes):
        return _error_response("Duplicate question codes in payload", "duplicate_codes", 400)

    existing_codes = {
        q.code
        for q in Question.query.filter_by(questionnaire_id=template.id)
        .filter(Question.code.in_(codes))
        .all()
    }
    if existing_codes:
        return _error_response(
            "Question code already exists",
            "code_exists",
            409,
            {"codes": sorted(existing_codes)},
        )

    constraint_errors = {}
    for item in items:
        constraint_error = _validate_question_constraints(item)
        if constraint_error:
            constraint_errors[item["code"]] = constraint_error
    if constraint_errors:
        return _error_response(
            "Invalid question constraints",
            "invalid_question_constraints",
            400,
            constraint_errors,
        )

    disorder_ids_by_code = {}
    for item in items:
        disorder_ids = _normalize_disorder_ids(item)
        if disorder_ids:
            found = Disorder.query.filter(Disorder.id.in_(disorder_ids)).all()
            if len(found) != len(disorder_ids):
                return _error_response(
                    "Disorder not found",
                    "disorder_not_found",
                    404,
                    {"code": item["code"], "disorder_ids": [str(d) for d in disorder_ids]},
                )
            disorder_ids_by_code[item["code"]] = found

    questions = []
    for item in items:
        disorder_ids = _normalize_disorder_ids(item)
        questions.append(
            Question(
                questionnaire_id=template.id,
                code=item["code"].strip(),
                text=item["text"].strip(),
                response_type=item["response_type"],
                disorder_id=disorder_ids[0] if disorder_ids else None,
                position=item.get("position"),
                response_min=item.get("response_min"),
                response_max=item.get("response_max"),
                response_step=item.get("response_step"),
                response_options=item.get("response_options"),
            )
        )

    try:
        db.session.add_all(questions)
        for question in questions:
            disorders = disorder_ids_by_code.get(question.code)
            if disorders:
                question.disorders = disorders
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error_response("Database error", "db_error", 500)

    log_audit(
        None,
        "QUESTIONS_ADDED",
        "questionnaires",
        {"template_id": str(template.id), "count": len(questions)},
    )
    return (
        jsonify({"template_id": str(template.id), "created": len(questions)}),
        201,
    )


@questionnaires_bp.post("/<template_id>/activate")
@roles_required("ADMIN")
def activate_questionnaire(template_id):
    template_uuid = _parse_uuid(template_id)
    if not template_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)

    template = QuestionnaireTemplate.query.filter_by(id=template_uuid).first()
    if not template:
        return _error_response("Template not found", "template_not_found", 404)
    if Question.query.filter_by(questionnaire_id=template.id).count() == 0:
        return _error_response("Template has no questions", "template_empty", 409)

    try:
        deactivate_all_templates()
        activate_template(template)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error_response("Database error", "db_error", 500)

    log_audit(
        None,
        "QUESTIONNAIRE_ACTIVATED",
        "questionnaires",
        {"template_id": str(template.id)},
    )
    return jsonify({"msg": "template activated", "template_id": str(template.id)}), 200


@questionnaires_bp.post("/active/clone")
@roles_required("ADMIN")
def clone_active_questionnaire():
    template = get_active_template()
    if not template:
        return _error_response("No active questionnaire template", "no_active_template", 404)

    schema = QuestionnaireCloneSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    name = (data.get("name") or template.name).strip()
    version = data["version"].strip()
    description = data.get("description")
    if description is None:
        description = template.description

    existing = QuestionnaireTemplate.query.filter_by(name=name, version=version).first()
    if existing:
        return _error_response("Template already exists", "template_exists", 409)

    try:
        cloned, count = clone_template(
            template,
            name=name,
            version=version,
            description=description,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error_response("Database error", "db_error", 500)

    log_audit(
        None,
        "QUESTIONNAIRE_CLONED",
        "questionnaires",
        {"source_id": str(template.id), "new_id": str(cloned.id), "question_count": count},
    )
    return (
        jsonify(
            {
                "template_id": str(cloned.id),
                "name": cloned.name,
                "version": cloned.version,
                "is_active": cloned.is_active,
                "question_count": count,
            }
        ),
        201,
    )
