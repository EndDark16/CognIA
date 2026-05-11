import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from api.decorators import roles_required
from api.schemas.problem_report_schema import (
    ProblemReportCreateSchema,
    ProblemReportListQuerySchema,
    ProblemReportUpdateSchema,
)
from api.extensions import limiter
from api.services import problem_report_service as service
from app.models import AppUser, db


problem_reports_bp = Blueprint("problem_reports", __name__, url_prefix="/api")


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except Exception:
        return None


def _error(message: str, error: str, status_code: int, details=None):
    payload = {"msg": message, "error": error}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def _server_error(message: str, error: str):
    current_app.logger.error("problem_reports_error error=%s message=%s", error, message, exc_info=True)
    return _error(message, error, 500)


def _handle_backend_failure(exc: Exception, fallback_message: str, fallback_error: str):
    db.session.rollback()
    if isinstance(exc, (OperationalError, DBAPIError)):
        current_app.logger.error("problem_reports_db_unavailable: %s", exc, exc_info=True)
        return _error("Service unavailable", "db_unavailable", 503)
    if isinstance(exc, SQLAlchemyError):
        current_app.logger.error("problem_reports_db_error: %s", exc, exc_info=True)
        return _error("Database error", "db_error", 500)
    return _server_error(fallback_message, fallback_error)


def _current_user() -> tuple[uuid.UUID | None, AppUser | None]:
    user_id = _parse_uuid(get_jwt_identity())
    if not user_id:
        return None, None
    return user_id, db.session.get(AppUser, user_id)


def _jwt_roles() -> list[str]:
    claims = get_jwt() or {}
    roles = claims.get("roles") or []
    return [str(role) for role in roles]


@problem_reports_bp.post("/problem-reports")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("PROBLEM_REPORT_CREATE_RATE_LIMIT", "20 per 10 minutes"))
def create_problem_report():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("Invalid user", "invalid_user", 401)
    if not user.is_active:
        return _error("Inactive account", "inactive_account", 403)

    schema = ProblemReportCreateSchema()
    payload_raw = request.get_json(silent=True) or {}
    attachment = None
    if request.content_type and "multipart/form-data" in request.content_type.lower():
        payload_raw = request.form.to_dict(flat=True)
        attachment = request.files.get("attachment")

    try:
        payload = schema.load(payload_raw)
    except ValidationError as exc:
        return _error("Validation error", "validation_error", 400, exc.messages)

    try:
        row = service.create_problem_report(
            reporter=user,
            roles=_jwt_roles(),
            payload=payload,
            attachment=attachment,
        )
    except ValueError as exc:
        return _error("Validation error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "problem_report_create_failed", "problem_report_create_failed")

    return jsonify({"report": service.serialize_problem_report(row, include_private=False)}), 201


@problem_reports_bp.get("/problem-reports/mine")
@jwt_required()
def list_my_problem_reports():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("Invalid user", "invalid_user", 401)

    schema = ProblemReportListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("Validation error", "validation_error", 400, exc.messages)

    rows, pagination = service.list_my_problem_reports(
        user_id=user_id,
        page=params["page"],
        page_size=params["page_size"],
    )
    attachments_map = service.preload_attachments_by_report_ids([row.id for row in rows])
    return jsonify(
        {
            "items": [
                service.serialize_problem_report(
                    item,
                    include_private=False,
                    attachments=attachments_map.get(item.id, []),
                )
                for item in rows
            ],
            "pagination": pagination,
        }
    ), 200


@problem_reports_bp.get("/admin/problem-reports")
@roles_required("ADMIN")
def list_problem_reports_admin():
    schema = ProblemReportListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("Validation error", "validation_error", 400, exc.messages)

    rows, pagination = service.list_problem_reports(params)
    attachments_map = service.preload_attachments_by_report_ids([row.id for row in rows])
    return jsonify(
        {
            "items": [
                service.serialize_problem_report(
                    item,
                    include_private=True,
                    attachments=attachments_map.get(item.id, []),
                )
                for item in rows
            ],
            "pagination": pagination,
        }
    ), 200


@problem_reports_bp.get("/admin/problem-reports/<report_id>")
@roles_required("ADMIN")
def get_problem_report_admin(report_id: str):
    rid = _parse_uuid(report_id)
    if not rid:
        return _error("Invalid report_id", "invalid_report_id", 400)
    try:
        row = service.get_problem_report_or_404(rid)
    except LookupError as exc:
        return _error("Not found", str(exc), 404)
    return jsonify({"report": service.serialize_problem_report(row, include_private=True)}), 200


@problem_reports_bp.patch("/admin/problem-reports/<report_id>")
@roles_required("ADMIN")
def update_problem_report_admin(report_id: str):
    rid = _parse_uuid(report_id)
    if not rid:
        return _error("Invalid report_id", "invalid_report_id", 400)
    schema = ProblemReportUpdateSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("Validation error", "validation_error", 400, exc.messages)

    actor_id, _ = _current_user()
    if not actor_id:
        return _error("Invalid user", "invalid_user", 401)

    try:
        row = service.get_problem_report_or_404(rid)
        row = service.admin_update_problem_report(report=row, actor_user_id=actor_id, payload=payload)
    except LookupError as exc:
        return _error("Not found", str(exc), 404)
    except ValueError as exc:
        return _error("Validation error", str(exc), 400)
    except Exception as exc:
        return _handle_backend_failure(exc, "problem_report_update_failed", "problem_report_update_failed")

    return jsonify({"report": service.serialize_problem_report(row, include_private=True)}), 200
