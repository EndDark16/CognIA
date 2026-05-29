import uuid

from flask import Blueprint, current_app, g, jsonify, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from api.decorators import roles_required
from api.extensions import limiter
from api.schemas.questionnaire_v2_schema import (
    ColombiaCitiesQuerySchema,
    CaseCreateSchema,
    CaseListQuerySchema,
    CaseUpdateSchema,
    DashboardQuerySchema,
    GuardianDashboardQuerySchema,
    NotificationsQuerySchema,
    ProfessionalReviewCreateSchema,
    ProfessionalReviewUpdateSchema,
    PsychologistDashboardQuerySchema,
    PsychologistSearchQuerySchema,
    ReportRequestSchema,
    ShareRequestDecisionSchema,
    ShareRequestListQuerySchema,
    SessionAnswersPatchSchema,
    SessionCreateSchema,
    SessionFilterSchema,
    SessionPageQuerySchema,
    SessionSubmitSchema,
    ShareCreateSchema,
    SharedAccessSchema,
    TagAssignSchema,
)
from api.services import colombia_locations
from api.services import questionnaire_v2_loader_service as loader_service
from api.services import questionnaire_v2_service as service
from api.services import transport_crypto_service as transport_crypto
from app.models import AppUser, db


questionnaire_v2_bp = Blueprint("questionnaire_v2", __name__, url_prefix="/api/v2")


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except Exception:
        return None


def _error(message: str, error: str, code: int, details=None):
    request_id = getattr(g, "request_id", None)
    payload = {
        "msg": message,
        "error": error,
        "request_id": request_id,
        "error_detail": {
            "code": error,
            "message": message,
            "details": details or {},
            "request_id": request_id,
            "retryable": code in {429, 500, 503},
        },
    }
    if details is not None:
        payload["details"] = details
    return jsonify(payload), code


def _server_error(message: str, error: str = "server_error"):
    current_app.logger.error("questionnaire_v2_error error=%s message=%s", error, message, exc_info=True)
    return _error(message, error, 500)


def _handle_backend_failure(exc: Exception, fallback_message: str, fallback_error: str = "server_error"):
    db.session.rollback()
    if isinstance(exc, service.RuntimeArtifactResolutionError):
        error_text = str(exc)
        if error_text.startswith("feature_coverage_below_minimum:"):
            current_app.logger.warning("questionnaire_v2_feature_coverage_blocked: %s", error_text)
            return _error("validation_error", "validation_error", 400, {"runtime": error_text})
        current_app.logger.error("questionnaire_v2_runtime_artifact_error: %s", exc, exc_info=True)
        return _error("Runtime model artifact unavailable", "runtime_artifact_unavailable", 503)
    if isinstance(exc, FileNotFoundError):
        current_app.logger.error("questionnaire_v2_dependency_unavailable: %s", exc, exc_info=True)
        return _error("Service unavailable", "runtime_assets_unavailable", 503)
    if isinstance(exc, (OperationalError, DBAPIError)):
        current_app.logger.error("questionnaire_v2_db_unavailable: %s", exc, exc_info=True)
        return _error("Service unavailable", "db_unavailable", 503)
    if isinstance(exc, SQLAlchemyError):
        current_app.logger.error("questionnaire_v2_db_error: %s", exc, exc_info=True)
        return _error("Database error", "db_error", 500)
    return _server_error(fallback_message, fallback_error)


def _current_user() -> tuple[uuid.UUID | None, AppUser | None]:
    user_id = _parse_uuid(get_jwt_identity())
    if not user_id:
        return None, None
    return user_id, db.session.get(AppUser, user_id)


def _has_admin_role_from_jwt() -> bool:
    claims = get_jwt() or {}
    roles = claims.get("roles") or []
    return any(str(role).strip().upper() == "ADMIN" for role in roles)


def _decode_sensitive_payload(*, allow_legacy_plaintext: bool = False) -> tuple[dict, transport_crypto.TransportContext]:
    raw_payload = request.get_json(silent=True) or {}
    try:
        return transport_crypto.decode_sensitive_request_payload(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        if allow_legacy_plaintext and exc.code == "plaintext_not_allowed":
            return raw_payload, transport_crypto.TransportContext(request_encrypted=False)
        raise


def _sensitive_json_response(payload: dict, status_code: int, context: transport_crypto.TransportContext):
    encoded_payload, headers = transport_crypto.encode_sensitive_response_payload(payload, context)
    response = jsonify(encoded_payload)
    response.status_code = status_code
    # Sensitive payloads must never be cached, even when response is plaintext in dev.
    response.headers["Cache-Control"] = "no-store"
    for key, value in headers.items():
        response.headers[key] = value
    return response


def _legacy_plaintext_response(response, replacement: str):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-CognIA-Endpoint-Status"] = "legacy_plaintext"
    response.headers["X-CognIA-Replacement"] = replacement
    return response


def _load_session_for_user(session_id: uuid.UUID, user_id: uuid.UUID):
    session = service.get_session_or_404(session_id)
    service.ensure_view_access(session, user_id)
    return session


@questionnaire_v2_bp.post("/questionnaires/admin/bootstrap")
@roles_required("ADMIN")
def bootstrap_questionnaire_v2():
    user_id, _ = _current_user()
    try:
        result = loader_service.bootstrap_questionnaire_backend_v2(created_by=user_id)
    except Exception as exc:
        return _handle_backend_failure(exc, "bootstrap_failed", "bootstrap_failed")
    return jsonify(result), 201


@questionnaire_v2_bp.get("/questionnaires/active")
@jwt_required()
def get_active_questionnaire():
    mode = (request.args.get("mode") or "short").strip().lower()
    role = (request.args.get("role") or "guardian").strip().lower()
    include_full = request.args.get("include_full", "false").lower() == "true"

    schema = SessionPageQuerySchema()
    try:
        paging = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        payload = service.get_active_questionnaire_payload(
            mode=mode,
            role=role,
            include_full=include_full,
            page=paging["page"],
            page_size=paging["page_size"],
        )
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "internal_error")

    return jsonify(payload), 200


@questionnaire_v2_bp.get("/security/transport-key")
@limiter.limit(lambda: current_app.config.get("QV2_TRANSPORT_KEY_RATE_LIMIT", "60 per minute"))
def get_transport_key():
    try:
        payload = transport_crypto.transport_key_payload()
    except Exception as exc:
        return _handle_backend_failure(exc, "transport_key_failed", "transport_key_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/sessions")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_SESSION_CREATE_RATE_LIMIT", "60 per minute"))
def create_session():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = SessionCreateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.create_session(owner_user_id=user_id, payload=payload)
    except LookupError as exc:
        db.session.rollback()
        if str(exc) == "session_case_not_found":
            return _error("session_case_not_found", "session_case_not_found", 404)
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        db.session.rollback()
        if str(exc) == "session_case_forbidden":
            return _error("session_case_forbidden", "session_case_forbidden", 403)
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        if str(exc) == "session_case_validation_error":
            return _error("session_case_validation_error", "session_case_validation_error", 400)
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "session_create_failed")

    return _sensitive_json_response(
        {"session": service.get_session_payload(session, viewer_user_id=user_id)},
        201,
        transport_context,
    )


@questionnaire_v2_bp.post("/questionnaires/cases")
@questionnaire_v2_bp.post("/cases")
@jwt_required()
def create_case():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if str(getattr(user, "user_type", "") or "").lower() != "guardian":
        return _error("case_create_forbidden", "case_create_forbidden", 403)
    schema = CaseCreateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("case_validation_error", "case_validation_error", 400, exc.messages)
    try:
        result = service.create_case(owner_user_id=user_id, payload=payload)
    except ValueError as exc:
        return _error(str(exc), str(exc), 400)
    except RuntimeError as exc:
        if str(exc) == "case_public_id_conflict":
            return _error("case_public_id_conflict", "case_public_id_conflict", 409)
        return _handle_backend_failure(exc, "case_create_failed", "case_create_failed")
    except Exception as exc:
        return _handle_backend_failure(exc, "case_create_failed", "case_create_failed")
    return _sensitive_json_response(result, 201, transport_context)


@questionnaire_v2_bp.get("/questionnaires/cases")
@questionnaire_v2_bp.get("/cases")
@jwt_required()
def list_cases():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = CaseListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    try:
        payload = service.list_cases(
            owner_user_id=user_id,
            status=params.get("status"),
            q=params.get("q"),
            label=params.get("label"),
            case_public_id=params.get("case_public_id"),
            has_sessions=params.get("has_sessions"),
            latest_alert_level=params.get("latest_alert_level"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            page=params["page"],
            page_size=params["page_size"],
        )
    except Exception as exc:
        return _handle_backend_failure(exc, "cases_list_failed", "cases_list_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.get("/questionnaires/cases/<case_id>")
@questionnaire_v2_bp.get("/cases/<case_id>")
@jwt_required()
def get_case_detail(case_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    cid = _parse_uuid(case_id)
    if not cid:
        return _error("invalid_case_id", "invalid_case_id", 400)
    try:
        case = service.get_case_or_404(cid)
        payload = service.get_case_detail(case, owner_user_id=user_id)
    except LookupError:
        return _error("case_not_found", "case_not_found", 404)
    except PermissionError:
        return _error("case_forbidden", "case_forbidden", 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "case_detail_failed", "case_detail_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.patch("/questionnaires/cases/<case_id>")
@questionnaire_v2_bp.patch("/cases/<case_id>")
@jwt_required()
def patch_case(case_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    cid = _parse_uuid(case_id)
    if not cid:
        return _error("invalid_case_id", "invalid_case_id", 400)
    schema = CaseUpdateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("case_update_validation_error", "case_update_validation_error", 400, exc.messages)

    try:
        case = service.get_case_or_404(cid)
        result = service.update_case(case, owner_user_id=user_id, payload=payload)
    except LookupError:
        return _error("case_not_found", "case_not_found", 404)
    except PermissionError:
        return _error("case_forbidden", "case_forbidden", 403)
    except ValueError:
        return _error("case_update_validation_error", "case_update_validation_error", 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "case_update_failed", "case_update_failed")
    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/sessions/<session_id>")
@jwt_required()
def get_session(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        session = _load_session_for_user(sid, user_id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    payload = service.get_session_payload(session, include_answers=True, viewer_user_id=user_id)
    payload["tags"] = service.list_session_tags(session.id)
    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/sessions/{session_id}/secure",
    )


@questionnaire_v2_bp.post("/questionnaires/sessions/<session_id>/secure")
@jwt_required()
def get_session_secure(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        session = _load_session_for_user(sid, user_id)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    payload = service.get_session_payload(session, include_answers=True, viewer_user_id=user_id)
    payload["tags"] = service.list_session_tags(session.id)
    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/sessions/<session_id>/page")
@jwt_required()
def get_session_page(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionPageQuerySchema()
    try:
        query = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        payload = service.get_session_page_payload(session, page=query["page"], page_size=query["page_size"])
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/sessions/{session_id}/page-secure",
    )


@questionnaire_v2_bp.post("/questionnaires/sessions/<session_id>/page-secure")
@jwt_required()
def get_session_page_secure(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionPageQuerySchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        query = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        payload = service.get_session_page_payload(session, page=query["page"], page_size=query["page_size"])
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.patch("/questionnaires/sessions/<session_id>/answers")
@questionnaire_v2_bp.patch("/questionnaires/sessions/<session_id>/answers/bulk")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_SAVE_ANSWERS_RATE_LIMIT", "120 per minute"))
def patch_answers(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionAnswersPatchSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        result = service.save_answers(
            session=session,
            user_id=user_id,
            answers=payload["answers"],
            mark_final=payload.get("mark_final", False),
            include_answers=payload.get("include_answers", False),
        )
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        if str(exc).startswith("clinical_consistency_error:"):
            return _error(str(exc), "clinical_consistency_error", 422)
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "save_failed")

    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/guardian/dashboard")
@jwt_required()
def guardian_dashboard():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = GuardianDashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("guardian_dashboard_invalid_period", "guardian_dashboard_invalid_period", 400, exc.messages)
    try:
        payload = service.guardian_dashboard(
            owner_user_id=user_id,
            months=params.get("months", 3),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            case_id=params.get("case_id"),
            case_public_id=params.get("case_public_id"),
            case_label=params.get("case_label"),
            q=params.get("q"),
            domain=params.get("domain"),
            alert_level=params.get("alert_level"),
        )
    except LookupError:
        return _error("guardian_dashboard_case_not_found", "guardian_dashboard_case_not_found", 404)
    except PermissionError:
        return _error("guardian_dashboard_forbidden", "guardian_dashboard_forbidden", 403)
    except ValueError:
        return _error("guardian_dashboard_invalid_period", "guardian_dashboard_invalid_period", 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "guardian_dashboard_failed", "guardian_dashboard_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.get("/questionnaires/psychologist/dashboard")
@jwt_required()
def psychologist_dashboard():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if str(user.user_type or "").strip().lower() != "psychologist":
        return _error(
            "psychologist_dashboard_requires_psychologist",
            "psychologist_dashboard_requires_psychologist",
            403,
        )
    schema = PsychologistDashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("psychologist_dashboard_invalid_filter", "psychologist_dashboard_invalid_filter", 400, exc.messages)
    try:
        payload = service.psychologist_dashboard(
            psychologist_user_id=user_id,
            q=params.get("q"),
            case_public_id=params.get("case_public_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            domain=params.get("domain"),
            alert_level=params.get("alert_level"),
            review_status=params.get("review_status"),
            page=params["page"],
            page_size=params["page_size"],
        )
    except ValueError:
        return _error("psychologist_dashboard_invalid_filter", "psychologist_dashboard_invalid_filter", 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "psychologist_dashboard_failed", "psychologist_dashboard_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.get("/questionnaires/psychologist/share-requests")
@jwt_required()
def psychologist_share_requests():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if str(user.user_type or "").strip().lower() != "psychologist":
        return _error(
            "psychologist_share_requests_requires_psychologist",
            "psychologist_share_requests_requires_psychologist",
            403,
        )
    schema = ShareRequestListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("psychologist_share_requests_invalid_filter", "psychologist_share_requests_invalid_filter", 400, exc.messages)
    try:
        payload = service.list_psychologist_share_requests(
            psychologist_user_id=user_id,
            status=params["status"],
            page=params["page"],
            page_size=params["page_size"],
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            q=params.get("q"),
        )
    except ValueError:
        return _error("psychologist_share_requests_invalid_filter", "psychologist_share_requests_invalid_filter", 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "psychologist_share_requests_failed", "psychologist_share_requests_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/psychologist/share-requests/<grant_id>/accept")
@jwt_required()
def accept_share_request(grant_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if str(user.user_type or "").strip().lower() != "psychologist":
        return _error("share_request_requires_psychologist", "share_request_requires_psychologist", 403)
    gid = _parse_uuid(grant_id)
    if not gid:
        return _error("invalid_grant_id", "invalid_grant_id", 400)
    schema = ShareRequestDecisionSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("share_request_validation_error", "share_request_validation_error", 400, exc.messages)
    try:
        result = service.accept_share_request(gid, user_id, message=payload.get("message"))
    except LookupError:
        return _error("share_request_not_found", "share_request_not_found", 404)
    except PermissionError as exc:
        if str(exc) == "share_request_requires_psychologist":
            return _error("share_request_requires_psychologist", "share_request_requires_psychologist", 403)
        return _error("share_request_forbidden", "share_request_forbidden", 403)
    except ValueError as exc:
        return _error(str(exc), str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "share_request_accept_failed", "share_request_accept_failed")
    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_v2_bp.post("/questionnaires/psychologist/share-requests/<grant_id>/reject")
@jwt_required()
def reject_share_request(grant_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if str(user.user_type or "").strip().lower() != "psychologist":
        return _error("share_request_requires_psychologist", "share_request_requires_psychologist", 403)
    gid = _parse_uuid(grant_id)
    if not gid:
        return _error("invalid_grant_id", "invalid_grant_id", 400)
    schema = ShareRequestDecisionSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("share_request_validation_error", "share_request_validation_error", 400, exc.messages)
    try:
        result = service.reject_share_request(gid, user_id, message=payload.get("message"))
    except LookupError:
        return _error("share_request_not_found", "share_request_not_found", 404)
    except PermissionError as exc:
        if str(exc) == "share_request_requires_psychologist":
            return _error("share_request_requires_psychologist", "share_request_requires_psychologist", 403)
        return _error("share_request_forbidden", "share_request_forbidden", 403)
    except ValueError as exc:
        return _error(str(exc), str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "share_request_reject_failed", "share_request_reject_failed")
    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_v2_bp.get("/psychologists/search")
@jwt_required()
def search_psychologists():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = PsychologistSearchQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("psychologist_search_invalid_query", "psychologist_search_invalid_query", 400, exc.messages)
    try:
        payload = service.search_psychologists(
            q=params.get("q"),
            requester_user=user,
            department=params.get("department"),
            city=params.get("city"),
            same_location=params.get("same_location", False),
            location=params.get("location"),
            page=params["page"],
            page_size=params["page_size"],
        )
    except Exception as exc:
        return _handle_backend_failure(exc, "psychologist_search_failed", "psychologist_search_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.get("/locations/colombia")
def list_colombia_locations():
    return jsonify(colombia_locations.catalog_payload()), 200


@questionnaire_v2_bp.get("/locations/colombia/cities")
def list_colombia_cities():
    schema = ColombiaCitiesQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("location_invalid_query", "location_invalid_query", 400, exc.messages)
    cities = colombia_locations.cities_for_department(params.get("department"))
    if cities is None:
        return _error("location_department_not_found", "location_department_not_found", 404)
    return jsonify({"department": colombia_locations.canonical_department(params["department"]), "cities": cities}), 200


@questionnaire_v2_bp.get("/notifications")
@jwt_required()
def list_notifications():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = NotificationsQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("notifications_validation_error", "notifications_validation_error", 400, exc.messages)
    try:
        payload = service.list_notifications(
            user_id=user_id,
            unread_only=params.get("unread_only", False),
            notification_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
        )
    except Exception as exc:
        return _handle_backend_failure(exc, "notifications_list_failed", "notifications_list_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.patch("/notifications/<notification_id>/read")
@jwt_required()
def mark_notification_read(notification_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    nid = _parse_uuid(notification_id)
    if not nid:
        return _error("invalid_notification_id", "invalid_notification_id", 400)
    try:
        payload = service.mark_notification_read(notification_id=nid, user_id=user_id)
    except LookupError:
        return _error("notification_not_found", "notification_not_found", 404)
    except PermissionError:
        return _error("notification_forbidden", "notification_forbidden", 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "notification_update_failed", "notification_update_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/sessions/<session_id>/submit")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_SUBMIT_RATE_LIMIT", "20 per minute"))
def submit_session(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionSubmitSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        result = service.submit_session(session, user_id=user_id, force_reprocess=payload["force_reprocess"])
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        if str(exc).startswith("clinical_consistency_error:"):
            return _error(str(exc), "clinical_consistency_error", 422)
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "submit_failed")

    return _sensitive_json_response(result, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/history")
@jwt_required()
def history():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)

    schema = SessionFilterSchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    payload = service.list_history(
        user_id=user_id,
        status=params.get("status"),
        case_id=params.get("case_id"),
        case_public_id=params.get("case_public_id"),
        case_label=params.get("case_label"),
        tag=params.get("tag"),
        q=params.get("q"),
        date_from=params.get("date_from"),
        date_to=params.get("date_to"),
        domain=params.get("domain"),
        alert_level=params.get("alert_level"),
        needs_professional_review=params.get("needs_professional_review"),
        page=params["page"],
        page_size=params["page_size"],
    )
    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/history/secure",
    )


@questionnaire_v2_bp.post("/questionnaires/history/secure")
@jwt_required()
def history_secure():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)

    schema = SessionFilterSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        params = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    payload = service.list_history(
        user_id=user_id,
        status=params.get("status"),
        case_id=params.get("case_id"),
        case_public_id=params.get("case_public_id"),
        case_label=params.get("case_label"),
        tag=params.get("tag"),
        q=params.get("q"),
        date_from=params.get("date_from"),
        date_to=params.get("date_to"),
        domain=params.get("domain"),
        alert_level=params.get("alert_level"),
        needs_professional_review=params.get("needs_professional_review"),
        page=params["page"],
        page_size=params["page_size"],
    )
    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>")
@jwt_required()
def history_item(session_id: str):
    return get_session(session_id)


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>/results")
@jwt_required()
def history_results(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    try:
        session = _load_session_for_user(sid, user_id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    response = jsonify(service.get_results_payload(session, viewer_user_id=user_id))
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/history/{session_id}/results-secure",
    )


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/results-secure")
@jwt_required()
def history_results_secure(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        session = _load_session_for_user(sid, user_id)
        payload = service.get_results_payload(session, viewer_user_id=user_id)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/clinical-summary")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_CLINICAL_SUMMARY_RATE_LIMIT", "30 per minute"))
def history_clinical_summary(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        session = _load_session_for_user(sid, user_id)
        payload = service.get_clinical_summary_payload(session)
        service.persist_clinical_summary_payload(session, payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "clinical_summary_failed", "clinical_summary_failed")

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/tags")
@jwt_required()
def add_tag(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    schema = TagAssignSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        service.ensure_tag_access(session, user_id)
        tags = service.upsert_tag(
            session=session,
            user_id=user_id,
            tag=payload["tag"],
            color=payload.get("color"),
            visibility=payload.get("visibility"),
        )
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)

    return _sensitive_json_response({"tags": tags}, 200, transport_context)


@questionnaire_v2_bp.delete("/questionnaires/history/<session_id>/tags/<tag_id>")
@jwt_required()
def remove_tag(session_id: str, tag_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    tid = _parse_uuid(tag_id)
    if not sid or not tid:
        return _error("invalid_id", "invalid_id", 400)

    try:
        session = _load_session_for_user(sid, user_id)
        service.ensure_tag_access(session, user_id)
        service.remove_tag(sid, tid, user_id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    return jsonify({"msg": "tag_removed"}), 200


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/share")
@jwt_required()
def share(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = ShareCreateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.get_session_or_404(sid)
        if session.owner_user_id != user_id:
            return _error("share_owner_required", "share_owner_required", 403)
        result = service.create_share(session=session, user_id=user_id, payload=payload)
    except LookupError as exc:
        if str(exc) == "share_grantee_not_found":
            return _error("share_grantee_not_found", "share_grantee_not_found", 404)
        return _error("not_found", str(exc), 404)
    except ValueError as exc:
        if str(exc) in {
            "share_target_not_psychologist",
            "share_grantee_inactive",
            "share_request_already_pending",
            "share_request_already_accepted",
        }:
            return _error(str(exc), str(exc), 400)
        return _error("share_validation_error", "share_validation_error", 400, {"reason": str(exc)})
    except Exception as exc:
        return _handle_backend_failure(exc, "share_failed")

    return _sensitive_json_response(result, 201, transport_context)


@questionnaire_v2_bp.get("/questionnaires/shared/<questionnaire_id>/<share_code>")
@limiter.limit(lambda: current_app.config.get("QV2_SHARED_ACCESS_RATE_LIMIT", "30 per minute"))
def shared_access(questionnaire_id: str, share_code: str):
    schema = SharedAccessSchema()
    try:
        params = schema.load({"questionnaire_id": questionnaire_id, "share_code": share_code})
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.get_shared_session(
            questionnaire_id=params["questionnaire_id"],
            share_code=params["share_code"],
        )
        payload = service.get_results_payload(session)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    response = jsonify(payload)
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/shared/access-secure",
    )


@questionnaire_v2_bp.post("/questionnaires/shared/access-secure")
@limiter.limit(lambda: current_app.config.get("QV2_SHARED_ACCESS_RATE_LIMIT", "30 per minute"))
def shared_access_secure():
    schema = SharedAccessSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload()
        params = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.get_shared_session(
            questionnaire_id=params["questionnaire_id"],
            share_code=params["share_code"],
        )
        payload = service.get_results_payload(session)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/pdf/generate")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_PDF_RATE_LIMIT", "8 per minute"))
def pdf_generate(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        session = _load_session_for_user(sid, user_id)
        service.ensure_pdf_access(session, user_id)
        export = service.generate_pdf(session, user_id)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)

    return _sensitive_json_response(
        {"pdf_id": str(export.id), "file_name": export.file_name},
        201,
        transport_context,
    )


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>/pdf")
@jwt_required()
def pdf_metadata(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        session = _load_session_for_user(sid, user_id)
        service.ensure_pdf_access(session, user_id)
        export = service.latest_pdf(session.id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    if not export:
        return _error("not_found", "pdf_not_found", 404)

    response = jsonify(
        {
            "pdf_id": str(export.id),
            "file_name": export.file_name,
            "download_url": f"/api/v2/questionnaires/history/{session_id}/pdf/download",
            "created_at": export.created_at.isoformat() if export.created_at else None,
        }
    )
    response.status_code = 200
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/history/{session_id}/pdf/secure",
    )


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/pdf/secure")
@jwt_required()
def pdf_metadata_secure(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        _, transport_context = _decode_sensitive_payload()
        session = _load_session_for_user(sid, user_id)
        service.ensure_pdf_access(session, user_id)
        export = service.latest_pdf(session.id)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    if not export:
        return _error("not_found", "pdf_not_found", 404)

    return _sensitive_json_response(
        {
            "pdf_id": str(export.id),
            "file_name": export.file_name,
            "download_url": f"/api/v2/questionnaires/history/{session_id}/pdf/download",
            "created_at": export.created_at.isoformat() if export.created_at else None,
        },
        200,
        transport_context,
    )


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>/pdf/download")
@jwt_required()
def pdf_download(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        session = _load_session_for_user(sid, user_id)
        service.ensure_pdf_access(session, user_id)
        export = service.latest_pdf(session.id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)

    if not export:
        return _error("not_found", "pdf_not_found", 404)

    path = service.resolve_download_path(export.file_path)
    if path is None or not path.exists():
        return _error("not_found", "pdf_file_missing", 404)
    response = send_file(path, as_attachment=True, download_name=export.file_name)
    return _legacy_plaintext_response(
        response,
        "/api/v2/questionnaires/history/{session_id}/pdf/secure",
    )


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>/professional-reviews")
@jwt_required()
def professional_reviews(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    try:
        session = _load_session_for_user(sid, user_id)
        items = service.list_professional_reviews(session, user_id=user_id)
        payload = {
            "items": items,
            "permissions": {"can_view_professional_reviews": True},
            "empty_state": None
            if items
            else {
                "title": "Sin revision profesional visible",
                "message": "Aun no hay comentarios profesionales compartidos para este cuestionario.",
            },
        }
    except LookupError:
        return _error("professional_reviews_session_not_found", "professional_reviews_session_not_found", 404)
    except PermissionError:
        return _error("professional_reviews_forbidden", "professional_reviews_forbidden", 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "professional_reviews_failed", "professional_reviews_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/professional-reviews")
@jwt_required()
def create_professional_review(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    schema = ProfessionalReviewCreateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error("professional_review_validation_error", "professional_review_validation_error", 400, exc.messages)
    try:
        session = service.get_session_or_404(sid)
        review = service.upsert_professional_review(session, psychologist_user_id=user_id, payload=payload)
    except LookupError:
        return _error("professional_review_session_not_found", "professional_review_session_not_found", 404)
    except PermissionError as exc:
        code = str(exc)
        if code == "professional_review_requires_psychologist":
            return _error("professional_review_requires_psychologist", "professional_review_requires_psychologist", 403)
        return _error("professional_review_forbidden", "professional_review_forbidden", 403)
    except ValueError as exc:
        return _error(str(exc), str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "professional_review_failed", "professional_review_failed")
    return _sensitive_json_response({"review": review}, 201, transport_context)


@questionnaire_v2_bp.patch("/questionnaires/history/<session_id>/professional-reviews/<review_id>")
@jwt_required()
def patch_professional_review(session_id: str, review_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    rid = _parse_uuid(review_id)
    if not sid or not rid:
        return _error("invalid_id", "invalid_id", 400)
    schema = ProfessionalReviewUpdateSchema()
    try:
        raw_payload, transport_context = _decode_sensitive_payload(allow_legacy_plaintext=True)
        payload = schema.load(raw_payload or {})
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except ValidationError as exc:
        return _error(
            "professional_review_update_validation_error",
            "professional_review_update_validation_error",
            400,
            exc.messages,
        )
    try:
        session = service.get_session_or_404(sid)
        review = service.update_professional_review(
            session=session,
            review_id=rid,
            psychologist_user_id=user_id,
            payload=payload,
        )
    except LookupError:
        return _error("professional_review_not_found", "professional_review_not_found", 404)
    except PermissionError as exc:
        if str(exc) == "professional_review_requires_psychologist":
            return _error("professional_review_requires_psychologist", "professional_review_requires_psychologist", 403)
        return _error("professional_review_forbidden", "professional_review_forbidden", 403)
    except ValueError as exc:
        return _error(str(exc), str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "professional_review_update_failed", "professional_review_update_failed")
    return _sensitive_json_response({"review": review}, 200, transport_context)


@questionnaire_v2_bp.get("/questionnaires/history/<session_id>/report-preview")
@jwt_required()
def report_preview(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    try:
        session = _load_session_for_user(sid, user_id)
        payload = service.get_report_preview_payload(session, viewer_user_id=user_id)
    except LookupError:
        return _error("report_preview_session_not_found", "report_preview_session_not_found", 404)
    except PermissionError:
        return _error("report_preview_forbidden", "report_preview_forbidden", 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "report_preview_failed", "report_preview_failed")
    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/report-preview/secure")
@jwt_required()
def report_preview_secure(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)
    try:
        _, transport_context = _decode_sensitive_payload()
        session = _load_session_for_user(sid, user_id)
        payload = service.get_report_preview_payload(session, viewer_user_id=user_id)
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)
    except LookupError:
        return _error("report_preview_session_not_found", "report_preview_session_not_found", 404)
    except PermissionError:
        return _error("report_preview_forbidden", "report_preview_forbidden", 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "report_preview_failed", "report_preview_failed")
    return _sensitive_json_response(payload, 200, transport_context)


@questionnaire_v2_bp.get("/dashboard/adoption-history")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_adoption_history():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/questionnaire-volume")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_questionnaire_volume():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/user-growth")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_user_growth():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_user_growth(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/funnel")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_funnel():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/retention")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_retention():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/productivity")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_productivity():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/questionnaire-quality")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_questionnaire_quality():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/data-quality")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_data_quality():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/api-health")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_api_health():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/model-monitoring")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_model_monitoring():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/drift")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_drift():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/equity")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_equity():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/human-review")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_human_review():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/executive-summary")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_DASHBOARD_RATE_LIMIT", "90 per minute"))
def dashboard_executive_summary():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.post("/reports/jobs")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_REPORT_RATE_LIMIT", "20 per minute"))
def create_report_job():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    if not _has_admin_role_from_jwt():
        return _error("forbidden", "admin_required", 403)

    schema = ReportRequestSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        result = service.build_report(
            report_type=payload["report_type"],
            months=payload["months"],
            requested_by_user_id=user_id,
            date_from=payload.get("date_from"),
            date_to=payload.get("date_to"),
            granularity=payload.get("granularity", "month"),
            file_format=payload.get("format", "pdf"),
            filters=payload.get("filters") or {},
        )
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "report_failed")

    return jsonify(result), 201


@questionnaire_v2_bp.get("/reports/jobs/<report_job_id>")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_REPORT_RATE_LIMIT", "20 per minute"))
def get_report_job(report_job_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    rid = _parse_uuid(report_job_id)
    if not rid:
        return _error("invalid_report_job_id", "invalid_report_job_id", 400)
    if not _has_admin_role_from_jwt():
        return _error("forbidden", "admin_required", 403)

    try:
        report_job = service.get_report_job_or_404(rid)
        service.ensure_report_access(report_job, user_id, is_admin=_has_admin_role_from_jwt())
        generated = service.latest_generated_report_for_job(report_job.id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "report_metadata_failed")

    return jsonify(service.report_job_payload(report_job, generated)), 200


@questionnaire_v2_bp.get("/reports/jobs/<report_job_id>/download")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("QV2_REPORT_RATE_LIMIT", "20 per minute"))
def download_report_job(report_job_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    rid = _parse_uuid(report_job_id)
    if not rid:
        return _error("invalid_report_job_id", "invalid_report_job_id", 400)
    if not _has_admin_role_from_jwt():
        return _error("forbidden", "admin_required", 403)

    try:
        report_job = service.get_report_job_or_404(rid)
        service.ensure_report_access(report_job, user_id, is_admin=_has_admin_role_from_jwt())
        generated = service.latest_generated_report_for_job(report_job.id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except Exception as exc:
        return _handle_backend_failure(exc, "report_download_failed")

    if not generated:
        return _error("not_found", "report_file_not_found", 404)
    path = service.resolve_download_path(generated.file_path)
    if path is None or not path.exists():
        return _error("not_found", "report_file_missing", 404)
    return send_file(path, as_attachment=True, download_name=path.name)
