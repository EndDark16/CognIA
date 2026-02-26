import uuid
from datetime import datetime, timezone, timedelta

from flask import current_app
from sqlalchemy import or_

from api.repositories.admin_repository import apply_pagination, apply_sort
from api.security import log_audit, revoke_user_sessions
from api.services.email_service import send_password_reset, send_psychologist_rejected_email
from api.services.password_reset_service import create_reset_token
from api.services.questionnaire_service import (
    activate_template,
    clone_template,
    deactivate_all_templates,
)
from app.models import (
    AppUser,
    AuditLog,
    EmailUnsubscribe,
    Evaluation,
    QuestionnaireTemplate,
    Question,
    RecoveryCode,
    RefreshToken,
    Role,
    UserMFA,
    UserRole,
    db,
)
from api.cache import roles_cache
from api.routes.auth import _normalize_professional_card, _normalize_user_type, _USER_TYPE_ROLE


def _parse_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _now():
    return datetime.now(timezone.utc)


def list_users(filters: dict):
    query = AppUser.query

    q = (filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(AppUser.username.ilike(like), AppUser.email.ilike(like)))

    email = (filters.get("email") or "").strip()
    if email:
        query = query.filter(AppUser.email.ilike(email))

    username = (filters.get("username") or "").strip()
    if username:
        query = query.filter(AppUser.username.ilike(username))

    user_type = (filters.get("user_type") or "").strip()
    if user_type:
        query = query.filter(AppUser.user_type == user_type)

    is_active = filters.get("is_active")
    if is_active is not None:
        query = query.filter(AppUser.is_active == bool(is_active))

    colpsic_verified = filters.get("colpsic_verified")
    if colpsic_verified is not None:
        query = query.filter(AppUser.colpsic_verified == bool(colpsic_verified))

    role = (filters.get("role") or "").strip().upper()
    if role:
        query = (
            query.join(UserRole, UserRole.user_id == AppUser.id)
            .join(Role)
            .filter(Role.name == role)
            .distinct()
        )

    query = apply_sort(
        query,
        model=AppUser,
        sort=filters.get("sort"),
        order=filters.get("order"),
        allowed={"created_at", "email", "username"},
    )

    items, pagination = apply_pagination(query, page=filters["page"], page_size=filters["page_size"])
    return items, pagination


def update_user(user: AppUser, payload: dict, acting_admin_id: uuid.UUID):
    changed_roles = False
    changed_status = False

    if "is_active" in payload and payload["is_active"] is not None:
        user.is_active = bool(payload["is_active"])
        changed_status = True

    required_role = None
    if "user_type" in payload and payload["user_type"] is not None:
        user_type = _normalize_user_type(payload.get("user_type"))
        if not user_type:
            raise ValueError("invalid_user_type")
        user.user_type = user_type
        required_role = _USER_TYPE_ROLE.get(user_type)
        if user_type == "psychologist":
            user.colpsic_verified = False
            user.colpsic_verified_at = None
            user.colpsic_verified_by = None
        changed_status = True

    if "professional_card_number" in payload:
        card = _normalize_professional_card(payload.get("professional_card_number"))
        if user.user_type == "psychologist" and not card:
            raise ValueError("missing_professional_card")
        if card and AppUser.query.filter(AppUser.professional_card_number == card, AppUser.id != user.id).first():
            raise ValueError("professional_card_exists")
        user.professional_card_number = card
        changed_status = True

    if "roles" in payload and payload["roles"] is not None:
        roles = [r.strip().upper() for r in payload["roles"] if r and str(r).strip()]
        if not roles:
            raise ValueError("invalid_roles")
        if required_role and required_role not in roles:
            roles.append(required_role)
        current = {ur.role_id for ur in UserRole.query.filter_by(user_id=user.id).all()}
        desired = []
        for role_name in roles:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name, description=f"Auto-created role: {role_name}")
                db.session.add(role)
                db.session.flush()
            desired.append(role)
            if role.id not in current:
                db.session.add(UserRole(user_id=user.id, role_id=role.id))
        for ur in UserRole.query.filter_by(user_id=user.id).all():
            if ur.role_id not in {r.id for r in desired}:
                db.session.delete(ur)
        roles_cache.set(user.id, [r.name for r in desired])
        changed_roles = True
    elif required_role:
        # Ensure base role for new user_type
        role = Role.query.filter_by(name=required_role).first()
        if not role:
            role = Role(name=required_role, description=f"Auto-created role: {required_role}")
            db.session.add(role)
            db.session.flush()
        if not UserRole.query.filter_by(user_id=user.id, role_id=role.id).first():
            db.session.add(UserRole(user_id=user.id, role_id=role.id))
            roles_cache.set(user.id, [r.name for r in user.roles] + [role.name])
            changed_roles = True

    user.updated_at = _now()
    db.session.add(user)
    db.session.commit()

    if changed_roles or changed_status:
        revoke_user_sessions(user)

    log_audit(acting_admin_id, "ADMIN_USER_UPDATED", "admin", {"user_id": str(user.id)})
    return user


def force_password_reset(user: AppUser, *, admin_id: uuid.UUID, request_ip: str | None, user_agent: str | None) -> bool:
    token = create_reset_token(
        user_id=user.id,
        request_ip=request_ip,
        user_agent=user_agent,
    )
    base_url = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    path = current_app.config.get("PASSWORD_RESET_PATH", "/reset-password")
    reset_link = f"{base_url}{path}?token={token}" if base_url else ""
    email_sent = False
    if reset_link:
        send_password_reset(to_email=user.email, reset_link=reset_link, full_name=user.full_name)
        email_sent = True
    revoke_user_sessions(user)
    log_audit(admin_id, "ADMIN_PASSWORD_RESET", "admin", {"user_id": str(user.id)})
    return email_sent


def reset_mfa(user: AppUser, *, admin_id: uuid.UUID):
    UserMFA.query.filter_by(user_id=user.id).delete()
    RecoveryCode.query.filter_by(user_id=user.id).delete()
    user.mfa_enabled = False
    user.mfa_confirmed_at = None
    user.mfa_method = "none"
    db.session.add(user)
    db.session.commit()
    revoke_user_sessions(user)
    log_audit(admin_id, "ADMIN_MFA_RESET", "admin", {"user_id": str(user.id)})


def list_audit_logs(filters: dict):
    query = AuditLog.query
    user_id = _parse_uuid(filters.get("user_id"))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    action = (filters.get("action") or "").strip()
    if action:
        query = query.filter(AuditLog.action == action)
    section = (filters.get("section") or "").strip()
    if section:
        query = query.filter(AuditLog.section == section)
    if filters.get("from_date"):
        query = query.filter(AuditLog.created_at >= filters["from_date"])
    if filters.get("to_date"):
        query = query.filter(AuditLog.created_at <= filters["to_date"])

    query = apply_sort(
        query,
        model=AuditLog,
        sort=filters.get("sort"),
        order=filters.get("order"),
        allowed={"created_at", "action", "section"},
    )

    items, pagination = apply_pagination(query, page=filters["page"], page_size=filters["page_size"])
    return items, pagination


def list_questionnaires(filters: dict):
    query = QuestionnaireTemplate.query
    name = (filters.get("name") or "").strip()
    if name:
        query = query.filter(QuestionnaireTemplate.name.ilike(f"%{name}%"))
    version = (filters.get("version") or "").strip()
    if version:
        query = query.filter(QuestionnaireTemplate.version.ilike(f"%{version}%"))
    if filters.get("is_active") is not None:
        query = query.filter(QuestionnaireTemplate.is_active == bool(filters["is_active"]))
    if filters.get("is_archived") is not None:
        query = query.filter(QuestionnaireTemplate.is_archived == bool(filters["is_archived"]))

    query = apply_sort(
        query,
        model=QuestionnaireTemplate,
        sort=filters.get("sort"),
        order=filters.get("order"),
        allowed={"created_at", "updated_at", "name", "version"},
    )

    items, pagination = apply_pagination(query, page=filters["page"], page_size=filters["page_size"])
    return items, pagination


def publish_questionnaire(template: QuestionnaireTemplate, *, admin_id: uuid.UUID):
    if template.is_archived:
        raise ValueError("template_archived")
    if Question.query.filter_by(questionnaire_id=template.id).count() == 0:
        raise ValueError("template_empty")
    if template.is_active:
        return template
    deactivate_all_templates()
    activate_template(template)
    template.updated_at = _now()
    db.session.commit()
    log_audit(admin_id, "QUESTIONNAIRE_PUBLISHED", "admin", {"template_id": str(template.id)})
    return template


def archive_questionnaire(template: QuestionnaireTemplate, *, admin_id: uuid.UUID):
    if template.is_archived:
        return template
    template.is_archived = True
    template.is_active = False
    template.archived_at = _now()
    template.updated_at = _now()
    db.session.add(template)
    db.session.commit()
    log_audit(admin_id, "QUESTIONNAIRE_ARCHIVED", "admin", {"template_id": str(template.id)})
    return template


def clone_questionnaire(template: QuestionnaireTemplate, *, name: str, version: str, description: str | None, admin_id: uuid.UUID):
    cloned, count = clone_template(template, name=name, version=version, description=description)
    db.session.commit()
    log_audit(admin_id, "QUESTIONNAIRE_CLONED", "admin", {"source_id": str(template.id), "new_id": str(cloned.id)})
    return cloned, count


def approve_psychologist(user: AppUser, *, admin_id: uuid.UUID):
    if user.user_type != "psychologist":
        raise ValueError("not_psychologist")
    if not user.professional_card_number:
        raise ValueError("missing_professional_card")
    now = _now()
    user.colpsic_verified = True
    user.colpsic_verified_at = now
    user.colpsic_verified_by = admin_id
    user.colpsic_rejected_at = None
    user.colpsic_rejected_by = None
    user.colpsic_reject_reason = None
    user.is_active = True
    user.updated_at = now
    db.session.add(user)
    db.session.commit()
    log_audit(admin_id, "COLPSIC_APPROVED", "admin", {"user_id": str(user.id)})
    return user


def reject_psychologist(user: AppUser, *, admin_id: uuid.UUID, reason: str):
    if user.user_type != "psychologist":
        raise ValueError("not_psychologist")
    if not user.professional_card_number:
        raise ValueError("missing_professional_card")
    now = _now()
    already_rejected = bool(user.colpsic_rejected_at) and not user.colpsic_verified
    user.colpsic_verified = False
    user.colpsic_rejected_at = now
    user.colpsic_rejected_by = admin_id
    user.colpsic_reject_reason = reason
    user.is_active = False
    user.updated_at = now
    db.session.add(user)
    db.session.commit()

    revoke_user_sessions(user)
    log_audit(admin_id, "COLPSIC_REJECTED", "admin", {"user_id": str(user.id), "reason": reason})

    if not already_rejected:
        send_psychologist_rejected_email(
            to_email=user.email,
            full_name=user.full_name,
            reject_reason=reason,
        )
    return user, (not already_rejected)


def list_evaluations(filters: dict):
    query = Evaluation.query
    if filters.get("status"):
        query = query.filter(Evaluation.status == filters["status"])
    if filters.get("age_min") is not None:
        query = query.filter(Evaluation.age_at_evaluation >= filters["age_min"])
    if filters.get("age_max") is not None:
        query = query.filter(Evaluation.age_at_evaluation <= filters["age_max"])
    if filters.get("date_from"):
        query = query.filter(Evaluation.evaluation_date >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(Evaluation.evaluation_date <= filters["date_to"])
    psych_id = _parse_uuid(filters.get("psychologist_id"))
    if psych_id:
        query = query.filter(Evaluation.psychologist_id == psych_id)
    subject_id = _parse_uuid(filters.get("subject_id"))
    if subject_id:
        query = query.filter(Evaluation.subject_id == subject_id)

    query = apply_sort(
        query,
        model=Evaluation,
        sort=filters.get("sort"),
        order=filters.get("order"),
        allowed={"created_at", "evaluation_date", "status", "age_at_evaluation"},
    )

    items, pagination = apply_pagination(query, page=filters["page"], page_size=filters["page_size"])
    return items, pagination


def update_evaluation_status(evaluation: Evaluation, *, status: str, admin_id: uuid.UUID):
    allowed = current_app.config.get("EVALUATION_ALLOWED_STATUSES", [])
    if allowed and status not in allowed:
        raise ValueError("invalid_status")
    evaluation.status = status
    evaluation.updated_at = _now()
    db.session.add(evaluation)
    db.session.commit()
    log_audit(admin_id, "EVALUATION_STATUS_UPDATED", "admin", {"evaluation_id": str(evaluation.id), "status": status})
    return evaluation


def list_roles():
    return Role.query.order_by(Role.name.asc()).all()


def create_role(*, name: str, description: str | None, admin_id: uuid.UUID):
    role = Role.query.filter_by(name=name).first()
    if role:
        raise ValueError("role_exists")
    role = Role(name=name, description=description)
    db.session.add(role)
    db.session.commit()
    log_audit(admin_id, "ROLE_CREATED", "admin", {"role": name})
    return role


def assign_roles(user: AppUser, roles: list[str], admin_id: uuid.UUID):
    roles_norm = [r.strip().upper() for r in roles if r and str(r).strip()]
    if not roles_norm:
        raise ValueError("invalid_roles")
    current = {ur.role_id for ur in UserRole.query.filter_by(user_id=user.id).all()}
    desired = []
    for role_name in roles_norm:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f"Auto-created role: {role_name}")
            db.session.add(role)
            db.session.flush()
        desired.append(role)
        if role.id not in current:
            db.session.add(UserRole(user_id=user.id, role_id=role.id))
    for ur in UserRole.query.filter_by(user_id=user.id).all():
        if ur.role_id not in {r.id for r in desired}:
            db.session.delete(ur)
    roles_cache.set(user.id, [r.name for r in desired])
    db.session.commit()
    revoke_user_sessions(user)
    log_audit(admin_id, "ROLES_ASSIGNED", "admin", {"user_id": str(user.id), "roles": roles_norm})


def list_unsubscribes(filters: dict):
    query = EmailUnsubscribe.query
    email = (filters.get("email") or "").strip()
    if email:
        query = query.filter(EmailUnsubscribe.email.ilike(f"%{email}%"))
    if filters.get("from_date"):
        query = query.filter(EmailUnsubscribe.unsubscribed_at >= filters["from_date"])
    if filters.get("to_date"):
        query = query.filter(EmailUnsubscribe.unsubscribed_at <= filters["to_date"])

    query = apply_sort(
        query,
        model=EmailUnsubscribe,
        sort=filters.get("sort"),
        order=filters.get("order"),
        allowed={"unsubscribed_at", "email"},
    )

    items, pagination = apply_pagination(query, page=filters["page"], page_size=filters["page_size"])
    return items, pagination


def remove_unsubscribe(entry: EmailUnsubscribe, *, admin_id: uuid.UUID):
    db.session.delete(entry)
    db.session.commit()
    log_audit(admin_id, "EMAIL_UNSUBSCRIBE_REMOVED", "admin", {"email": entry.email})


def get_email_health():
    return {
        "email_enabled": current_app.config.get("EMAIL_ENABLED", False),
        "smtp_host_configured": bool(current_app.config.get("SMTP_HOST")),
        "smtp_user_configured": bool(current_app.config.get("SMTP_USER")),
        "smtp_use_tls": bool(current_app.config.get("SMTP_USE_TLS")),
        "smtp_use_ssl": bool(current_app.config.get("SMTP_USE_SSL")),
    }


def get_metrics_snapshot():
    from api.metrics import _snapshot_metrics

    return _snapshot_metrics()


def impersonate_user(*, admin_id: uuid.UUID, user: AppUser):
    from flask_jwt_extended import create_access_token

    roles = [role.name for role in user.roles]
    ttl = int(current_app.config.get("ADMIN_IMPERSONATION_TTL_SECONDS", 900))
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"roles": roles, "impersonated": True, "actor_id": str(admin_id)},
        expires_delta=None if ttl <= 0 else timedelta(seconds=ttl),
    )
    log_audit(admin_id, "ADMIN_IMPERSONATE", "admin", {"user_id": str(user.id)})
    return access_token, ttl
