import uuid

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from api.decorators import roles_required
from api.extensions import limiter
from api.schemas.questionnaire_v2_schema import (
    DashboardQuerySchema,
    ReportRequestSchema,
    SessionAnswersPatchSchema,
    SessionCreateSchema,
    SessionFilterSchema,
    SessionPageQuerySchema,
    SessionSubmitSchema,
    ShareCreateSchema,
    SharedAccessSchema,
    TagAssignSchema,
)
from api.services import questionnaire_v2_loader_service as loader_service
from api.services import questionnaire_v2_service as service
from app.models import AppUser, db


questionnaire_v2_bp = Blueprint("questionnaire_v2", __name__, url_prefix="/api/v2")


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except Exception:
        return None


def _error(message: str, error: str, code: int, details=None):
    payload = {"msg": message, "error": error}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), code


def _server_error(message: str, error: str = "server_error"):
    current_app.logger.error("questionnaire_v2_error error=%s message=%s", error, message, exc_info=True)
    return _error(message, error, 500)


def _current_user() -> tuple[uuid.UUID | None, AppUser | None]:
    user_id = _parse_uuid(get_jwt_identity())
    if not user_id:
        return None, None
    return user_id, db.session.get(AppUser, user_id)


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
    except Exception:
        db.session.rollback()
        return _server_error("bootstrap_failed", "bootstrap_failed")
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
    except Exception:
        return _server_error("internal_error")

    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/sessions")
@jwt_required()
def create_session():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    schema = SessionCreateSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.create_session(owner_user_id=user_id, payload=payload)
    except ValueError as exc:
        db.session.rollback()
        return _error("validation_error", str(exc), 400)
    except Exception:
        db.session.rollback()
        return _server_error("session_create_failed")

    return jsonify({"session": service.get_session_payload(session)}), 201


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

    payload = service.get_session_payload(session)
    payload["tags"] = service.list_session_tags(session.id)
    return jsonify(payload), 200


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

    return jsonify(payload), 200


@questionnaire_v2_bp.patch("/questionnaires/sessions/<session_id>/answers")
@jwt_required()
def patch_answers(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionAnswersPatchSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = _load_session_for_user(sid, user_id)
        result = service.save_answers(
            session=session,
            user_id=user_id,
            answers=payload["answers"],
            mark_final=payload.get("mark_final", False),
        )
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception:
        db.session.rollback()
        return _server_error("save_failed")

    return jsonify(result), 200


@questionnaire_v2_bp.post("/questionnaires/sessions/<session_id>/submit")
@jwt_required()
def submit_session(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    schema = SessionSubmitSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
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
        return _error("validation_error", str(exc), 400)
    except Exception:
        db.session.rollback()
        return _server_error("submit_failed")

    return jsonify(result), 200


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
        page=params["page"],
        page_size=params["page_size"],
    )
    return jsonify(payload), 200


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

    return jsonify(service.get_results_payload(session)), 200


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
        payload = schema.load(request.get_json(silent=True) or {})
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

    return jsonify({"tags": tags}), 200


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
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)

    try:
        session = service.get_session_or_404(sid)
        if session.owner_user_id != user_id:
            return _error("forbidden", "owner_required", 403)
        result = service.create_share(session=session, user_id=user_id, payload=payload)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception:
        db.session.rollback()
        return _server_error("share_failed")

    return jsonify(result), 201


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

    return jsonify(payload), 200


@questionnaire_v2_bp.post("/questionnaires/history/<session_id>/pdf/generate")
@jwt_required()
def pdf_generate(session_id: str):
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)
    sid = _parse_uuid(session_id)
    if not sid:
        return _error("invalid_session_id", "invalid_session_id", 400)

    try:
        session = _load_session_for_user(sid, user_id)
        service.ensure_pdf_access(session, user_id)
        export = service.generate_pdf(session, user_id)
    except LookupError as exc:
        return _error("not_found", str(exc), 404)
    except PermissionError as exc:
        return _error("forbidden", str(exc), 403)
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)

    return jsonify({"pdf_id": str(export.id), "file_name": export.file_name}), 201


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

    return jsonify(
        {
            "pdf_id": str(export.id),
            "file_name": export.file_name,
            "download_url": f"/api/v2/questionnaires/history/{session_id}/pdf/download",
            "created_at": export.created_at.isoformat() if export.created_at else None,
        }
    ), 200


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
    return send_file(path, as_attachment=True, download_name=export.file_name)


@questionnaire_v2_bp.get("/dashboard/adoption-history")
@jwt_required()
def dashboard_adoption_history():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/questionnaire-volume")
@jwt_required()
def dashboard_questionnaire_volume():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/user-growth")
@jwt_required()
def dashboard_user_growth():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_user_growth(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/funnel")
@jwt_required()
def dashboard_funnel():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/retention")
@jwt_required()
def dashboard_retention():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/productivity")
@jwt_required()
def dashboard_productivity():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/questionnaire-quality")
@jwt_required()
def dashboard_questionnaire_quality():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/data-quality")
@jwt_required()
def dashboard_data_quality():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/api-health")
@jwt_required()
def dashboard_api_health():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_questionnaire_volume(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/model-monitoring")
@jwt_required()
def dashboard_model_monitoring():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/drift")
@jwt_required()
def dashboard_drift():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/equity")
@jwt_required()
def dashboard_equity():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/human-review")
@jwt_required()
def dashboard_human_review():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_funnel(months=params["months"])), 200


@questionnaire_v2_bp.get("/dashboard/executive-summary")
@jwt_required()
def dashboard_executive_summary():
    schema = DashboardQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error("validation_error", "validation_error", 400, exc.messages)
    return jsonify(service.dashboard_adoption_history(months=params["months"])), 200


@questionnaire_v2_bp.post("/reports/jobs")
@jwt_required()
def create_report_job():
    user_id, user = _current_user()
    if not user_id or not user:
        return _error("invalid_user", "invalid_user", 401)

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
        )
    except ValueError as exc:
        return _error("validation_error", str(exc), 400)
    except Exception:
        db.session.rollback()
        return _server_error("report_failed")

    return jsonify(result), 201
