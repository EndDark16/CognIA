# api/routes/users.py

import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity
from marshmallow import ValidationError, Schema, fields, validate

from api.decorators import roles_required
from api.security import hash_password, log_audit, password_policy_errors
from api.services.email_service import send_welcome_email
from api.routes.auth import (
    _normalize_user_type,
    _normalize_professional_card,
    _normalize_username,
    _normalize_email,
    _is_valid_username,
    _is_valid_email,
    _USER_TYPE_ROLE,
    _PASSWORD_MIN,
)
from api.cache import roles_cache
from app.models import AppUser, Role, UserRole, db


users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")


class UserCreateSchema(Schema):
    username = fields.String(required=True)
    email = fields.String(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    full_name = fields.String(allow_none=True)
    user_type = fields.String(required=True)
    professional_card_number = fields.String(allow_none=True)
    roles = fields.List(fields.String(), allow_none=True)
    is_active = fields.Boolean(load_default=True)


class UserUpdateSchema(Schema):
    email = fields.String(allow_none=True)
    password = fields.String(allow_none=True, validate=validate.Length(min=8, max=128))
    full_name = fields.String(allow_none=True)
    user_type = fields.String(allow_none=True)
    professional_card_number = fields.String(allow_none=True)
    roles = fields.List(fields.String(), allow_none=True)
    is_active = fields.Boolean(allow_none=True)


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


def _ensure_role(name: str) -> Role:
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"Auto-created role: {name}")
        db.session.add(role)
        db.session.flush()
    return role


def _apply_roles(user: AppUser, roles: list[str] | None, required_roles: list[str] | None = None):
    if roles is None and not required_roles:
        return
    normalized = [r.strip().upper() for r in (roles or []) if r and str(r).strip()]
    required_norm = [r.strip().upper() for r in (required_roles or []) if r and str(r).strip()]
    for role_name in required_norm:
        if role_name not in normalized:
            normalized.append(role_name)
    if not normalized:
        return
    current = {ur.role_id for ur in UserRole.query.filter_by(user_id=user.id).all()}
    desired = []
    for role_name in normalized:
        role = _ensure_role(role_name)
        desired.append(role)
        if role.id not in current:
            db.session.add(UserRole(user_id=user.id, role_id=role.id))
    # Remove roles not desired
    for ur in UserRole.query.filter_by(user_id=user.id).all():
        if ur.role_id not in {r.id for r in desired}:
            db.session.delete(ur)
    roles_cache.set(user.id, [r.name for r in desired])


def _user_payload(user: AppUser):
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "user_type": user.user_type,
        "professional_card_number": user.professional_card_number,
        "colpsic_verified": user.colpsic_verified,
        "is_active": user.is_active,
        "roles": [role.name for role in user.roles],
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@users_bp.get("")
@roles_required("ADMIN")
def list_users():
    guard = _ensure_admin_token()
    if guard:
        return guard
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)
    query = AppUser.query.order_by(AppUser.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({"items": [_user_payload(u) for u in items], "page": page, "page_size": page_size, "total": total}), 200


@users_bp.get("/<user_id>")
@roles_required("ADMIN")
def get_user(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    return jsonify(_user_payload(user)), 200


@users_bp.post("")
@roles_required("ADMIN")
def create_user():
    guard = _ensure_admin_token()
    if guard:
        return guard
    schema = UserCreateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    username = _normalize_username(data.get("username"))
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip() or None
    user_type = _normalize_user_type(data.get("user_type"))
    professional_card_number = _normalize_professional_card(data.get("professional_card_number"))

    if not username or not _is_valid_username(username):
        return _error_response("Invalid username format", "invalid_username", 400)
    if not email or not _is_valid_email(email):
        return _error_response("Invalid email format", "invalid_email", 400)
    min_len = int(current_app.config.get("PASSWORD_MIN_LENGTH", _PASSWORD_MIN))
    if password_policy_errors(password, min_len):
        return _error_response("Weak password", "weak_password", 400)
    if full_name and len(full_name) > 120:
        return _error_response("Full name too long", "invalid_full_name", 400)
    if not user_type:
        return _error_response("Missing or invalid user_type", "invalid_user_type", 400)
    if user_type == "psychologist" and not professional_card_number:
        return _error_response("Missing professional card number", "missing_professional_card", 400)

    if AppUser.query.filter((AppUser.username == username) | (AppUser.email == email)).first():
        return _error_response("Username or email already exists", "user_exists", 409)
    if professional_card_number and AppUser.query.filter_by(professional_card_number=professional_card_number).first():
        return _error_response("Professional card number already exists", "professional_card_exists", 409)

    role_name = _USER_TYPE_ROLE.get(user_type)
    if not role_name:
        return _error_response("Invalid user_type", "invalid_user_type", 400)

    user = AppUser(
        username=username,
        email=email,
        password=hash_password(password),
        full_name=full_name,
        user_type=user_type,
        professional_card_number=professional_card_number,
        is_active=bool(data.get("is_active", True)),
    )
    try:
        db.session.add(user)
        db.session.flush()
        base_role = _ensure_role(role_name)
        db.session.add(UserRole(user_id=user.id, role_id=base_role.id))
        _apply_roles(user, data.get("roles"), required_roles=[role_name])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error creating user: %s", e, exc_info=True)
        return _error_response("Database error", "db_error", 500)

    log_audit(user.id, "USER_CREATED", "users", {"user_id": str(user.id)})
    try:
        send_welcome_email(to_email=user.email, full_name=user.full_name)
    except Exception:
        current_app.logger.error("Failed to schedule welcome email for %s", user.email, exc_info=True)
    return jsonify(_user_payload(user)), 201


@users_bp.patch("/<user_id>")
@roles_required("ADMIN")
def update_user(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)

    schema = UserUpdateSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)

    if "email" in data:
        if data["email"] is None:
            return _error_response("Email cannot be null", "invalid_email", 400)
        email = _normalize_email(data.get("email"))
        if not _is_valid_email(email):
            return _error_response("Invalid email format", "invalid_email", 400)
        if AppUser.query.filter(AppUser.email == email, AppUser.id != user.id).first():
            return _error_response("Email already exists", "email_exists", 409)
        user.email = email

    if "password" in data and data["password"]:
        min_len = int(current_app.config.get("PASSWORD_MIN_LENGTH", _PASSWORD_MIN))
        if password_policy_errors(data["password"], min_len):
            return _error_response("Weak password", "weak_password", 400)
        user.password = hash_password(data["password"])

    if "full_name" in data:
        full_name = (data.get("full_name") or "").strip() or None
        if full_name and len(full_name) > 120:
            return _error_response("Full name too long", "invalid_full_name", 400)
        user.full_name = full_name

    if "user_type" in data and data["user_type"] is not None:
        user_type = _normalize_user_type(data.get("user_type"))
        if not user_type:
            return _error_response("Invalid user_type", "invalid_user_type", 400)
        user.user_type = user_type
        base_role = _USER_TYPE_ROLE.get(user_type)
        if base_role:
            _apply_roles(user, data.get("roles"), required_roles=[base_role])

    if "professional_card_number" in data:
        card = _normalize_professional_card(data.get("professional_card_number"))
        if user.user_type == "psychologist" and not card:
            return _error_response("Missing professional card number", "missing_professional_card", 400)
        if card and AppUser.query.filter(AppUser.professional_card_number == card, AppUser.id != user.id).first():
            return _error_response("Professional card number already exists", "professional_card_exists", 409)
        user.professional_card_number = card
    elif user.user_type != "psychologist":
        user.professional_card_number = None

    if "is_active" in data and data["is_active"] is not None:
        user.is_active = bool(data["is_active"])

    if "roles" in data and "user_type" not in data:
        base_role = _USER_TYPE_ROLE.get(user.user_type)
        _apply_roles(user, data.get("roles"), required_roles=[base_role] if base_role else None)

    try:
        user.updated_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error updating user %s: %s", user.id, e, exc_info=True)
        return _error_response("Database error", "db_error", 500)

    log_audit(user.id, "USER_UPDATED", "users", {"user_id": str(user.id)})
    return jsonify(_user_payload(user)), 200


@users_bp.delete("/<user_id>")
@roles_required("ADMIN")
def deactivate_user(user_id):
    guard = _ensure_admin_token()
    if guard:
        return guard
    identity = _parse_uuid(get_jwt_identity())
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return _error_response("Invalid user_id", "invalid_user_id", 400)
    if identity and user_uuid == identity:
        return _error_response("Cannot deactivate own user", "cannot_deactivate_self", 400)
    user = db.session.get(AppUser, user_uuid)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    user.is_active = False
    try:
        user.updated_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error deactivating user %s: %s", user.id, e, exc_info=True)
        return _error_response("Database error", "db_error", 500)
    log_audit(user.id, "USER_DEACTIVATED", "users", {"user_id": str(user.id)})
    return jsonify({"msg": "user deactivated", "user_id": str(user.id)}), 200
