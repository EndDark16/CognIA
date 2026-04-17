import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity
from marshmallow import ValidationError

from api.decorators import roles_required
from api.extensions import limiter
from api.schemas.admin_schema import (
    AuditLogQuerySchema,
    EmailUnsubscribeListQuerySchema,
    EvaluationListQuerySchema,
    EvaluationStatusSchema,
    PsychologistDecisionSchema,
    QuestionnaireCloneRequestSchema,
    QuestionnaireListQuerySchema,
    RoleAssignSchema,
    RoleCreateSchema,
    UserListQuerySchema,
    UserPatchSchema,
)
from api.services import admin_service
from app.models import AppUser, AuditLog, EmailUnsubscribe, Evaluation, QuestionnaireTemplate, Role, db


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


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


def _ensure_admin_token():
    claims = get_jwt()
    if claims.get("mfa_enrollment"):
        return _error_response("Enrollment token not allowed", "mfa_enrollment_only", 403)
    return None


def _admin_id() -> uuid.UUID | None:
    return _parse_uuid(get_jwt_identity())


@admin_bp.get("/users")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_list_users():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = UserListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    items, pagination = admin_service.list_users(params)
    return jsonify(
        {
            "items": [
                {
                    "id": str(u.id),
                    "username": u.username,
                    "email": u.email,
                    "full_name": u.full_name,
                    "user_type": u.user_type,
                    "professional_card_number": u.professional_card_number,
                    "colpsic_verified": u.colpsic_verified,
                    "is_active": u.is_active,
                    "roles": [r.name for r in u.roles],
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                }
                for u in items
            ],
            "pagination": pagination,
        }
    ), 200


@admin_bp.patch("/users/<user_id>")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_patch_user(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)

    schema = UserPatchSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)

    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)

    try:
        updated = admin_service.update_user(user, payload, admin_id)
    except ValueError as exc:
        code = str(exc)
        if code == "invalid_user_type":
            return _error_response("Invalid user_type", "invalid_user_type", 400)
        if code == "missing_professional_card":
            return _error_response("Missing professional card number", "missing_professional_card", 400)
        if code == "professional_card_exists":
            return _error_response("Professional card number already exists", "professional_card_exists", 409)
        if code == "invalid_roles":
            return _error_response("Invalid roles", "invalid_roles", 400)
        return _error_response("Invalid request", "invalid_request", 400)

    return jsonify(
        {
            "id": str(updated.id),
            "username": updated.username,
            "email": updated.email,
            "full_name": updated.full_name,
            "user_type": updated.user_type,
            "professional_card_number": updated.professional_card_number,
            "colpsic_verified": updated.colpsic_verified,
            "is_active": updated.is_active,
            "roles": [r.name for r in updated.roles],
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        }
    ), 200


@admin_bp.post("/users/<user_id>/password-reset")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_SECURITY_RATE_LIMIT", "10 per minute"))
def admin_password_reset(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)

    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)

    try:
        email_sent = admin_service.force_password_reset(
            user,
            admin_id=admin_id,
            request_ip=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception as exc:
        current_app.logger.error("Admin password reset failed: %s", exc, exc_info=True)
        return _error_response("Database error", "db_error", 500)

    return jsonify({"msg": "Password reset issued", "email_sent": email_sent}), 200


@admin_bp.post("/users/<user_id>/mfa/reset")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_SECURITY_RATE_LIMIT", "10 per minute"))
def admin_mfa_reset(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.reset_mfa(user, admin_id=admin_id)
    except Exception as exc:
        current_app.logger.error("Admin MFA reset failed: %s", exc, exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "MFA reset", "user_id": str(user.id)}), 200


@admin_bp.get("/audit-logs")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_AUDIT_RATE_LIMIT", "30 per minute"))
def admin_audit_logs():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = AuditLogQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    items, pagination = admin_service.list_audit_logs(params)
    return jsonify(
        {
            "items": [
                {
                    "id": str(a.id),
                    "user_id": str(a.user_id) if a.user_id else None,
                    "action": a.action,
                    "section": a.section,
                    "details": a.details,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in items
            ],
            "pagination": pagination,
        }
    ), 200


@admin_bp.get("/questionnaires")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_questionnaires():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = QuestionnaireListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    items, pagination = admin_service.list_questionnaires(params)
    return jsonify(
        {
            "items": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "version": t.version,
                    "description": t.description,
                    "is_active": t.is_active,
                    "is_archived": t.is_archived,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in items
            ],
            "pagination": pagination,
        }
    ), 200


@admin_bp.post("/questionnaires/<template_id>/publish")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_publish_questionnaire(template_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    template_uuid = _parse_uuid(template_id)
    if not template_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    template = db.session.get(QuestionnaireTemplate, template_uuid)
    if not template:
        return _error_response("Template not found", "template_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)

    try:
        admin_service.publish_questionnaire(template, admin_id=admin_id)
    except ValueError as exc:
        code = str(exc)
        if code == "template_empty":
            return _error_response("Template has no questions", "template_empty", 409)
        if code == "template_archived":
            return _error_response("Template archived", "template_archived", 409)
        return _error_response("Invalid request", "invalid_request", 400)
    except Exception:
        current_app.logger.error("Publish questionnaire failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "template published", "template_id": str(template.id)}), 200


@admin_bp.post("/questionnaires/<template_id>/archive")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_archive_questionnaire(template_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    template_uuid = _parse_uuid(template_id)
    if not template_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    template = db.session.get(QuestionnaireTemplate, template_uuid)
    if not template:
        return _error_response("Template not found", "template_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.archive_questionnaire(template, admin_id=admin_id)
    except Exception:
        current_app.logger.error("Archive questionnaire failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "template archived", "template_id": str(template.id)}), 200


@admin_bp.post("/questionnaires/<template_id>/clone")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_clone_questionnaire(template_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    template_uuid = _parse_uuid(template_id)
    if not template_uuid:
        return _error_response("Invalid template_id", "invalid_template_id", 400)
    template = db.session.get(QuestionnaireTemplate, template_uuid)
    if not template:
        return _error_response("Template not found", "template_not_found", 404)
    schema = QuestionnaireCloneRequestSchema()
    try:
        payload = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    name = (payload.get("name") or template.name).strip()
    version = payload["version"].strip()
    description = payload.get("description")
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    existing = QuestionnaireTemplate.query.filter_by(name=name, version=version).first()
    if existing:
        return _error_response("Template already exists", "template_exists", 409)
    try:
        cloned, count = admin_service.clone_questionnaire(
            template,
            name=name,
            version=version,
            description=description,
            admin_id=admin_id,
        )
    except Exception:
        current_app.logger.error("Clone questionnaire failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify(
        {
            "template_id": str(cloned.id),
            "name": cloned.name,
            "version": cloned.version,
            "question_count": count,
        }
    ), 201


@admin_bp.post("/psychologists/<user_id>/approve")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_SECURITY_RATE_LIMIT", "10 per minute"))
def admin_approve_psychologist(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.approve_psychologist(user, admin_id=admin_id)
    except ValueError as exc:
        code = str(exc)
        if code == "not_psychologist":
            return _error_response("User is not psychologist", "not_psychologist", 400)
        if code == "missing_professional_card":
            return _error_response("Missing professional card number", "missing_professional_card", 400)
        return _error_response("Invalid request", "invalid_request", 400)
    except Exception:
        current_app.logger.error("Approve psychologist failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "psychologist approved", "user_id": str(user.id)}), 200


@admin_bp.post("/psychologists/<user_id>/reject")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_SECURITY_RATE_LIMIT", "10 per minute"))
def admin_reject_psychologist(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    schema = PsychologistDecisionSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    reason = data["reason"].strip()
    if not reason:
        return _error_response("Invalid reason", "invalid_reason", 400)
    try:
        _, email_sent = admin_service.reject_psychologist(
            user,
            admin_id=admin_id,
            reason=reason,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_psychologist":
            return _error_response("User is not psychologist", "not_psychologist", 400)
        if code == "missing_professional_card":
            return _error_response("Missing professional card number", "missing_professional_card", 400)
        return _error_response("Invalid request", "invalid_request", 400)
    except Exception:
        current_app.logger.error("Reject psychologist failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "psychologist rejected", "user_id": str(user.id), "email_sent": email_sent}), 200


@admin_bp.get("/evaluations")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_evaluations():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = EvaluationListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    items, pagination = admin_service.list_evaluations(params)
    return jsonify(
        {
            "items": [
                {
                    "id": str(e.id),
                    "status": e.status,
                    "age_at_evaluation": e.age_at_evaluation,
                    "evaluation_date": e.evaluation_date.isoformat() if e.evaluation_date else None,
                    "subject_id": str(e.subject_id) if e.subject_id else None,
                    "psychologist_id": str(e.psychologist_id) if e.psychologist_id else None,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in items
            ],
            "pagination": pagination,
        }
    ), 200


@admin_bp.patch("/evaluations/<evaluation_id>/status")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_update_evaluation_status(evaluation_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    eval_uuid = _parse_uuid(evaluation_id)
    if not eval_uuid:
        return _error_response("Invalid evaluation_id", "invalid_evaluation_id", 400)
    evaluation = db.session.get(Evaluation, eval_uuid)
    if not evaluation:
        return _error_response("Evaluation not found", "evaluation_not_found", 404)
    schema = EvaluationStatusSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.update_evaluation_status(evaluation, status=data["status"], admin_id=admin_id)
    except ValueError:
        return _error_response("Invalid status", "invalid_status", 400)
    except Exception:
        current_app.logger.error("Update evaluation status failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "status updated", "evaluation_id": str(evaluation.id), "status": evaluation.status}), 200


@admin_bp.get("/roles")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_list_roles():
    guard = _ensure_admin_token()
    if guard:
        return guard
    roles = admin_service.list_roles()
    return jsonify({"items": [{"id": str(r.id), "name": r.name, "description": r.description} for r in roles]}), 200


@admin_bp.post("/roles")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_create_role():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = RoleCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)

    try:
        role = admin_service.create_role(
            name=data["name"].strip().upper(),
            description=(data.get("description") or None),
            admin_id=admin_id,
        )
    except ValueError as exc:
        if str(exc) == "role_exists":
            return _error_response("Role already exists", "role_exists", 409)
        return _error_response("Invalid request", "invalid_request", 400)
    except Exception:
        current_app.logger.error("Create role failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)

    return jsonify({"id": str(role.id), "name": role.name, "description": role.description}), 201


@admin_bp.post("/users/<user_id>/roles")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_assign_roles(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    schema = RoleAssignSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.assign_roles(user, data["roles"], admin_id=admin_id)
    except ValueError:
        return _error_response("Invalid roles", "invalid_roles", 400)
    except Exception:
        current_app.logger.error("Assign roles failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "roles updated", "user_id": str(user.id)}), 200


@admin_bp.get("/email/unsubscribes")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_list_unsubscribes():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = EmailUnsubscribeListQuerySchema()
    try:
        params = schema.load(request.args)
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)
    items, pagination = admin_service.list_unsubscribes(params)
    return jsonify(
        {
            "items": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "reason": u.reason,
                    "source": u.source,
                    "unsubscribed_at": u.unsubscribed_at.isoformat() if u.unsubscribed_at else None,
                }
                for u in items
            ],
            "pagination": pagination,
        }
    ), 200


@admin_bp.post("/email/unsubscribes/<unsubscribe_id>/remove")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_MUTATION_RATE_LIMIT", "20 per minute"))
def admin_remove_unsubscribe(unsubscribe_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    entry_id = _parse_uuid(unsubscribe_id)
    if not entry_id:
        return _error_response("Invalid unsubscribe_id", "invalid_unsubscribe_id", 400)
    entry = db.session.get(EmailUnsubscribe, entry_id)
    if not entry:
        return _error_response("Unsubscribe not found", "unsubscribe_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)
    try:
        admin_service.remove_unsubscribe(entry, admin_id=admin_id)
    except Exception:
        current_app.logger.error("Remove unsubscribe failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)
    return jsonify({"msg": "unsubscribe removed", "email": entry.email}), 200


@admin_bp.get("/email/health")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_email_health():
    guard = _ensure_admin_token()
    if guard:
        return guard
    return jsonify(admin_service.get_email_health()), 200


@admin_bp.get("/metrics")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_LIST_RATE_LIMIT", "60 per minute"))
def admin_metrics():
    guard = _ensure_admin_token()
    if guard:
        return guard
    try:
        snapshot = admin_service.get_metrics_snapshot()
    except Exception:
        current_app.logger.error("Admin metrics failed", exc_info=True)
        return _error_response("Metrics error", "metrics_error", 500)
    return jsonify(snapshot), 200


@admin_bp.post("/impersonate/<user_id>")
@roles_required("ADMIN")
@limiter.limit(lambda: current_app.config.get("ADMIN_SECURITY_RATE_LIMIT", "10 per minute"))
def admin_impersonate_user(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    admin_id = _admin_id()
    if not admin_id:
        return _error_response("Invalid admin", "invalid_admin", 401)

    try:
        token, expires_in = admin_service.impersonate_user(admin_id=admin_id, user=user)
    except Exception:
        current_app.logger.error("Impersonation failed", exc_info=True)
        return _error_response("Database error", "db_error", 500)

    return (
        jsonify(
            {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "impersonated_user_id": str(user.id),
            }
        ),
        200,
    )
