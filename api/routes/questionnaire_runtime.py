import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from api.decorators import roles_required
from api.security import log_audit
from api.schemas.questionnaire_runtime_schema import (
    RuntimeAdminDisclosureSchema,
    RuntimeAdminQuestionSchema,
    RuntimeAdminSectionSchema,
    RuntimeAdminTemplateActiveSchema,
    RuntimeAdminTemplateCreateSchema,
    RuntimeAdminVersionCreateSchema,
    RuntimeCreateDraftSchema,
    RuntimeProfessionalAccessSchema,
    RuntimeProfessionalTagSchema,
    RuntimeSaveDraftSchema,
    RuntimeSubmitSchema,
    RuntimeValidateSectionSchema,
)
from api.services import questionnaire_runtime_service as qr_service
from api.services import transport_crypto_service as transport_crypto
from app.models import AppUser, QRQuestionnaireVersion, db


questionnaire_runtime_bp = Blueprint(
    "questionnaire_runtime",
    __name__,
    url_prefix="/api/v1/questionnaire-runtime",
)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _error_response(message: str, error: str, code: int, details=None):
    payload = {"msg": message, "error": error}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), code


def _decode_sensitive_payload() -> tuple[dict, transport_crypto.TransportContext]:
    payload = request.get_json(silent=True) or {}
    return transport_crypto.decode_sensitive_request_payload(payload)


def _sensitive_json_response(payload: dict, status_code: int, context: transport_crypto.TransportContext):
    encoded_payload, headers = transport_crypto.encode_sensitive_response_payload(payload, context)
    response = jsonify(encoded_payload)
    response.status_code = status_code
    response.headers["Cache-Control"] = "no-store"
    for key, value in headers.items():
        response.headers[key] = value
    return response


def _legacy_plaintext_response(response, replacement: str):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-CognIA-Endpoint-Status"] = "legacy_plaintext"
    response.headers["X-CognIA-Replacement"] = replacement
    return response


def _current_user_uuid() -> tuple[uuid.UUID | None, AppUser | None]:
    identity = _parse_uuid(get_jwt_identity())
    if not identity:
        return None, None
    return identity, db.session.get(AppUser, identity)


def _require_professional_role(user: AppUser | None):
    claims = get_jwt() or {}
    roles = {str(r).upper() for r in claims.get("roles", [])}
    if "ADMIN" in roles or "PSYCHOLOGIST" in roles:
        return True
    if user and (user.user_type or "").lower() == "psychologist":
        return True
    return False


# -----------------------
# Public/User endpoints
# -----------------------


@questionnaire_runtime_bp.get("/questionnaire/active")
@jwt_required()
def get_active_questionnaire():
    payload = qr_service.get_active_questionnaire_payload()
    return jsonify(payload), 200


@questionnaire_runtime_bp.post("/evaluations/draft")
@jwt_required()
def create_draft_evaluation():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not user.is_active:
        return _error_response("Inactive account", "inactive_account", 403)

    schema = RuntimeCreateDraftSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        evaluation, pin = qr_service.create_evaluation_draft(user_id=user_id, payload=payload)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    log_audit(user_id, "QR_DRAFT_CREATED", "questionnaire_runtime", {"evaluation_id": str(evaluation.id)})
    return _sensitive_json_response(
        {
            "evaluation_id": str(evaluation.id),
            "reference_id": evaluation.reference_id,
            "pin": pin,
            "status": evaluation.status,
        },
        201,
        transport_context,
    )


@questionnaire_runtime_bp.patch("/evaluations/<evaluation_id>/draft")
@jwt_required()
def save_draft(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    schema = RuntimeSaveDraftSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    answers = payload.get("answers") or []

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        qr_service.save_draft_answers(
            evaluation,
            answers,
            consent_accepted=payload.get("consent_accepted"),
        )
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Evaluation not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    return _sensitive_json_response({"msg": "draft_saved", "evaluation_id": str(eval_uuid)}, 200, transport_context)


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/validate-section")
@jwt_required()
def validate_section(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    schema = RuntimeValidateSectionSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    section_key = payload["section_key"].strip()

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        result = qr_service.evaluate_section_completeness(evaluation, section_key)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/submit")
@jwt_required()
def submit_evaluation(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    schema = RuntimeSubmitSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    wait_live_result = bool(payload.get("wait_live_result", True))

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        status_payload = qr_service.submit_evaluation(evaluation, wait_live_result=wait_live_result)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    return _sensitive_json_response(status_payload, 202, transport_context)


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/heartbeat")
@jwt_required()
def heartbeat(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        qr_service.heartbeat_presence(evaluation)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return jsonify({"msg": "heartbeat_recorded", "evaluation_id": str(eval_uuid)}), 200


@questionnaire_runtime_bp.get("/evaluations/<evaluation_id>/status")
@jwt_required()
def evaluation_status(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return jsonify(qr_service._status_payload(evaluation)), 200


@questionnaire_runtime_bp.get("/evaluations/<evaluation_id>/responses")
@jwt_required()
def get_responses(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.get_responses_payload(evaluation)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/responses/secure",
    )


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/responses/secure")
@jwt_required()
def get_responses_secure(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.get_responses_payload(evaluation)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_runtime_bp.get("/evaluations/<evaluation_id>/results")
@jwt_required()
def get_results(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.get_results_payload(evaluation, audience="user")
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/results/secure",
    )


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/results/secure")
@jwt_required()
def get_results_secure(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.get_results_payload(evaluation, audience="user")
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_runtime_bp.get("/evaluations/history")
@jwt_required()
def list_history():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"
    items = qr_service.list_user_evaluations(user_id, include_deleted=include_deleted)
    response = jsonify({"items": items, "count": len(items)})
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/evaluations/history/secure",
    )


@questionnaire_runtime_bp.post("/evaluations/history/secure")
@jwt_required()
def list_history_secure():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    try:
        payload, transport_context = _decode_sensitive_payload()
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)

    include_deleted = bool(payload.get("include_deleted", False))
    items = qr_service.list_user_evaluations(user_id, include_deleted=include_deleted)
    return _sensitive_json_response({"items": items, "count": len(items)}, 200, transport_context)


@questionnaire_runtime_bp.delete("/evaluations/<evaluation_id>")
@jwt_required()
def delete_evaluation(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id, allow_deleted=True)
        qr_service.soft_delete_evaluation(evaluation)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return jsonify({"msg": "evaluation_soft_deleted", "evaluation_id": str(eval_uuid)}), 200


@questionnaire_runtime_bp.get("/evaluations/<evaluation_id>/export")
@jwt_required()
def export_evaluation(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    mode = request.args.get("mode", "responses_and_results")
    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.export_evaluation_payload(
            evaluation,
            requested_by_user_id=user_id,
            export_mode=mode,
            audience="user",
        )
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/evaluations/{evaluation_id}/export/secure",
    )


@questionnaire_runtime_bp.post("/evaluations/<evaluation_id>/export/secure")
@jwt_required()
def export_evaluation_secure(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        raw_payload, transport_context = _decode_sensitive_payload()
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    mode = (raw_payload.get("mode") or "responses_and_results")
    try:
        evaluation = qr_service.get_user_evaluation_or_404(eval_uuid, user_id)
        payload = qr_service.export_evaluation_payload(
            evaluation,
            requested_by_user_id=user_id,
            export_mode=mode,
            audience="user",
        )
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    return _sensitive_json_response(payload, 200, transport_context)


# -----------------------
# Professional endpoints
# -----------------------


@questionnaire_runtime_bp.post("/professional/access")
@jwt_required()
def professional_open_access():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)

    schema = RuntimeProfessionalAccessSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    reference_id = payload["reference_id"].strip()
    pin = payload["pin"].strip()

    try:
        evaluation = qr_service.professional_access(reference_id, pin, psychologist_user_id=user_id)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except FileNotFoundError as exc:
        return _error_response("Evaluation deleted by user", str(exc), 410)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(
        {"evaluation_id": str(evaluation.id), "reference_id": evaluation.reference_id},
        200,
        transport_context,
    )


@questionnaire_runtime_bp.get("/professional/evaluations/<evaluation_id>/responses")
@jwt_required()
def professional_responses(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)

    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        if evaluation.deleted_by_user:
            return _error_response("Evaluation deleted by user", "evaluation_deleted_by_user", 410)
        payload = qr_service.get_responses_payload(evaluation)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/professional/evaluations/{evaluation_id}/responses/secure",
    )


@questionnaire_runtime_bp.post("/professional/evaluations/<evaluation_id>/responses/secure")
@jwt_required()
def professional_responses_secure(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        if evaluation.deleted_by_user:
            return _error_response("Evaluation deleted by user", "evaluation_deleted_by_user", 410)
        payload = qr_service.get_responses_payload(evaluation)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_runtime_bp.get("/professional/evaluations/<evaluation_id>/results")
@jwt_required()
def professional_results(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)

    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        if evaluation.deleted_by_user:
            return _error_response("Evaluation deleted by user", "evaluation_deleted_by_user", 410)
        payload = qr_service.get_results_payload(evaluation, audience="professional")
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/professional/evaluations/{evaluation_id}/results/secure",
    )


@questionnaire_runtime_bp.post("/professional/evaluations/<evaluation_id>/results/secure")
@jwt_required()
def professional_results_secure(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        if evaluation.deleted_by_user:
            return _error_response("Evaluation deleted by user", "evaluation_deleted_by_user", 410)
        payload = qr_service.get_results_payload(evaluation, audience="professional")
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_runtime_bp.patch("/professional/evaluations/<evaluation_id>/tag")
@jwt_required()
def professional_tag(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)

    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)
    schema = RuntimeProfessionalTagSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    tag = payload["tag"]

    try:
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        updated = qr_service.set_professional_tag(evaluation, str(tag))
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)

    return _sensitive_json_response(
        {"evaluation_id": str(updated.id), "review_tag": updated.review_tag},
        200,
        transport_context,
    )


@questionnaire_runtime_bp.delete("/professional/evaluations/<evaluation_id>/access")
@jwt_required()
def professional_release_access(evaluation_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    if not _require_professional_role(user):
        return _error_response("Forbidden", "professional_role_required", 403)

    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)

    try:
        evaluation = qr_service.professional_guard(eval_uuid, user_id)
        qr_service.release_professional_access(evaluation, user_id)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return jsonify({"msg": "professional_access_released", "evaluation_id": str(eval_uuid)}), 200


# -----------------------
# Notifications
# -----------------------


@questionnaire_runtime_bp.get("/notifications")
@jwt_required()
def list_notifications():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    items = qr_service.list_notifications(user_id, unread_only=unread_only)
    response = jsonify({"items": items, "count": len(items)})
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v1/questionnaire-runtime/notifications/secure",
    )


@questionnaire_runtime_bp.post("/notifications/secure")
@jwt_required()
def list_notifications_secure():
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    try:
        payload, transport_context = _decode_sensitive_payload()
    except transport_crypto.TransportCryptoError as exc:
        return _error_response(exc.message, exc.code, exc.status_code)

    unread_only = bool(payload.get("unread_only", False))
    items = qr_service.list_notifications(user_id, unread_only=unread_only)
    return _sensitive_json_response({"items": items, "count": len(items)}, 200, transport_context)


@questionnaire_runtime_bp.patch("/notifications/<notification_id>/read")
@jwt_required()
def mark_notification_read(notification_id):
    user_id, user = _current_user_uuid()
    if not user_id or not user:
        return _error_response("Invalid user", "invalid_user", 401)
    notif_uuid = _parse_uuid(notification_id)
    if not notif_uuid:
        return _error_response("Invalid notification_id", "invalid_notification_id", 400)
    try:
        row = qr_service.mark_notification_read(notif_uuid, user_id)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except PermissionError as exc:
        return _error_response("Forbidden", str(exc), 403)

    return jsonify({"id": str(row.id), "is_read": row.is_read, "read_at": row.read_at.isoformat()}), 200


# -----------------------
# Admin endpoints
# -----------------------


@questionnaire_runtime_bp.post("/admin/bootstrap")
@roles_required("ADMIN")
def admin_bootstrap():
    user_id, _ = _current_user_uuid()
    version = qr_service.ensure_runtime_bootstrap(created_by=user_id)
    return jsonify({"version_id": str(version.id), "version_label": version.version_label}), 201


@questionnaire_runtime_bp.post("/admin/templates")
@roles_required("ADMIN")
def admin_create_template():
    user_id, _ = _current_user_uuid()
    schema = RuntimeAdminTemplateCreateSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        template = qr_service.create_template(payload, created_by=user_id)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(template.id), "slug": template.slug, "name": template.name}), 201


@questionnaire_runtime_bp.post("/admin/templates/<template_id>/versions")
@roles_required("ADMIN")
def admin_create_version(template_id):
    user_id, _ = _current_user_uuid()
    tpl_uuid = _parse_uuid(template_id)
    if not tpl_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    schema = RuntimeAdminVersionCreateSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        version = qr_service.create_template_version(tpl_uuid, payload, created_by=user_id)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(version.id), "version_label": version.version_label, "status": version.status}), 201


@questionnaire_runtime_bp.post("/admin/templates/<template_id>/active")
@roles_required("ADMIN")
def admin_set_template_active(template_id):
    tpl_uuid = _parse_uuid(template_id)
    if not tpl_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    schema = RuntimeAdminTemplateActiveSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    is_active = bool(payload.get("is_active", True))
    try:
        template = qr_service.set_template_active(tpl_uuid, is_active=is_active)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    return jsonify({"id": str(template.id), "is_active": template.is_active}), 200


@questionnaire_runtime_bp.get("/admin/templates/<template_id>/versions")
@roles_required("ADMIN")
def admin_list_versions(template_id):
    tpl_uuid = _parse_uuid(template_id)
    if not tpl_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    items = qr_service.list_template_versions(tpl_uuid)
    return jsonify({"items": items, "count": len(items)}), 200


@questionnaire_runtime_bp.post("/admin/versions/<version_id>/publish")
@roles_required("ADMIN")
def admin_publish_version(version_id):
    ver_uuid = _parse_uuid(version_id)
    if not ver_uuid:
        return _error_response("Invalid version_id", "invalid_version_id", 400)
    try:
        version = qr_service.publish_template_version(ver_uuid)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(version.id), "status": version.status, "is_published": version.is_published}), 200


@questionnaire_runtime_bp.post("/admin/versions/<version_id>/disclosures")
@roles_required("ADMIN")
def admin_upsert_disclosure(version_id):
    user_id, _ = _current_user_uuid()
    ver_uuid = _parse_uuid(version_id)
    if not ver_uuid:
        return _error_response("Invalid version_id", "invalid_version_id", 400)
    schema = RuntimeAdminDisclosureSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        row = qr_service.create_or_update_disclosure(ver_uuid, payload, created_by=user_id)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(row.id), "type": row.disclosure_type, "version_label": row.version_label}), 201


@questionnaire_runtime_bp.post("/admin/versions/<version_id>/sections")
@roles_required("ADMIN")
def admin_create_section(version_id):
    ver_uuid = _parse_uuid(version_id)
    if not ver_uuid:
        return _error_response("Invalid version_id", "invalid_version_id", 400)
    schema = RuntimeAdminSectionSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        section = qr_service.create_section(ver_uuid, payload)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(section.id), "key": section.key, "title": section.title}), 201


@questionnaire_runtime_bp.post("/admin/sections/<section_id>/questions")
@roles_required("ADMIN")
def admin_create_question(section_id):
    sec_uuid = _parse_uuid(section_id)
    if not sec_uuid:
        return _error_response("Invalid section_id", "invalid_section_id", 400)
    schema = RuntimeAdminQuestionSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    try:
        question = qr_service.create_question(sec_uuid, payload)
    except LookupError as exc:
        return _error_response("Not found", str(exc), 404)
    except ValueError as exc:
        return _error_response("Validation error", str(exc), 400)
    return jsonify({"id": str(question.id), "key": question.key, "feature_key": question.feature_key}), 201


@questionnaire_runtime_bp.get("/admin/versions/<version_id>")
@roles_required("ADMIN")
def admin_get_version_detail(version_id):
    ver_uuid = _parse_uuid(version_id)
    if not ver_uuid:
        return _error_response("Invalid version_id", "invalid_version_id", 400)
    version = db.session.get(QRQuestionnaireVersion, ver_uuid)
    if not version:
        return _error_response("Not found", "version_not_found", 404)
    return jsonify(qr_service.serialize_questionnaire(version)), 200
