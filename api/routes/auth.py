from datetime import datetime, timezone, timedelta
import re
import unicodedata
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from api.extensions import limiter
from api.security import (
    check_password,
    hash_password,
    log_audit,
    set_refresh_cookie,
    clear_auth_cookies,
    validate_csrf_header,
    requires_mfa_enrollment,
    decrypt_mfa_secret,
    validate_totp,
)
from api.services.email_service import send_welcome_email, send_password_reset
from api.services.password_reset_service import (
    create_reset_token,
    lookup_valid_token,
    mark_token_used,
)
from api.schemas.password_schema import (
    PasswordChangeSchema,
    PasswordForgotSchema,
    PasswordResetSchema,
)
from app.models import (
    AppUser,
    RefreshToken,
    UserSession,
    UserMFA,
    RecoveryCode,
    MFALoginChallenge,
    Role,
    UserRole,
    db,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


from api.cache import roles_cache


def _get_roles(user: AppUser) -> list[str]:
    cached = roles_cache.get(user.id)
    if cached is not None:
        return cached
    names = [role.name for role in user.roles]
    roles_cache.set(user.id, names)
    return names


def _parse_identity(identity: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(identity))
    except (TypeError, ValueError):
        return None


def _access_expires() -> int:
    expires_cfg = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", 900)
    if hasattr(expires_cfg, "total_seconds"):
        return int(expires_cfg.total_seconds())
    return int(expires_cfg)


def _build_auth_response(access_token: str):
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": _access_expires(),
        }
    )


def _revoke_refresh_tokens(user_id: uuid.UUID) -> None:
    RefreshToken.query.filter_by(user_id=user_id, revoked=False).update(
        {"revoked": True}, synchronize_session=False
    )


def _error_response(message: str, error_code: str, status_code: int, details=None):
    payload = {"msg": message, "error": error_code}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def _challenge_ttl_seconds() -> int:
    try:
        return int(current_app.config.get("MFA_CHALLENGE_TTL", 300))
    except Exception:
        return 300


def _enroll_ttl_seconds() -> int:
    try:
        return int(current_app.config.get("MFA_ENROLL_TOKEN_TTL", 600))
    except Exception:
        return 600


_USER_TYPE_ALIASES = {
    "guardian": "guardian",
    "padre": "guardian",
    "tutor": "guardian",
    "padre_tutor": "guardian",
    "parent_tutor": "guardian",
    "psychologist": "psychologist",
    "psicologo": "psychologist",
}

_USER_TYPE_ROLE = {
    "guardian": "GUARDIAN",
    "psychologist": "PSYCHOLOGIST",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_FULL_NAME_MAX = 120
_EMAIL_MAX = 254
_PASSWORD_MIN = 8


def _normalize_user_type(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = unicodedata.normalize("NFKD", str(raw)).encode("ascii", "ignore").decode()
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r"[\s/\-]+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return _USER_TYPE_ALIASES.get(cleaned)


def _normalize_professional_card(raw: str | None) -> str | None:
    if raw is None:
        return None
    card = str(raw).strip()
    if not card:
        return None
    card = re.sub(r"\s+", "", card)
    return card


def _normalize_username(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(raw).strip()


def _normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(raw).strip().lower()


def _is_valid_username(username: str) -> bool:
    return bool(_USERNAME_RE.fullmatch(username or ""))


def _is_valid_email(email: str) -> bool:
    if not email or len(email) > _EMAIL_MAX:
        return False
    return bool(_EMAIL_RE.fullmatch(email))


def _login_rate_key() -> str:
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    if username:
        return f"login:{str(username).strip()}"
    return f"login_ip:{get_remote_address()}"


def _mfa_rate_key() -> str:
    data = request.get_json(silent=True) or {}
    challenge_id = data.get("challenge_id")
    if challenge_id:
        return f"mfa:{str(challenge_id).strip()}"
    return f"mfa_ip:{get_remote_address()}"


def _password_change_rate_key() -> str:
    identity = _parse_identity(get_jwt_identity())
    if identity:
        return f"pwd_change:{identity}:{get_remote_address()}"
    return f"pwd_change_ip:{get_remote_address()}"


def _password_forgot_rate_key() -> str:
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    if email:
        return f"pwd_forgot:{email}:{get_remote_address()}"
    return f"pwd_forgot_ip:{get_remote_address()}"


def _password_forgot_email_key() -> str:
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    return f"pwd_forgot_email:{email}" if email else f"pwd_forgot_email:{get_remote_address()}"


def _password_reset_rate_key() -> str:
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if token:
        return f"pwd_reset:{str(token)[:12]}:{get_remote_address()}"
    return f"pwd_reset_ip:{get_remote_address()}"


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("REGISTER_RATE_LIMIT", "5 per 10 minutes"))
def register():
    data = request.get_json(silent=True) or {}
    username = _normalize_username(data.get("username"))
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip() or None
    user_type = _normalize_user_type(data.get("user_type"))
    professional_card_number = _normalize_professional_card(
        data.get("professional_card_number") or data.get("colpsic_card_number")
    )

    if not username or not email or not password:
        return _error_response("Missing username, email or password", "missing_fields", 400)

    if not _is_valid_username(username):
        return _error_response(
            "Invalid username format",
            "invalid_username",
            400,
        )

    if not _is_valid_email(email):
        return _error_response("Invalid email format", "invalid_email", 400)

    if len(password) < _PASSWORD_MIN:
        return _error_response(
            f"Password must be at least {_PASSWORD_MIN} characters",
            "weak_password",
            400,
        )

    if full_name and len(full_name) > _FULL_NAME_MAX:
        return _error_response("Full name too long", "invalid_full_name", 400)

    if not user_type:
        return _error_response("Missing or invalid user_type", "invalid_user_type", 400)

    if user_type == "psychologist" and not professional_card_number:
        return _error_response(
            "Missing professional card number",
            "missing_professional_card",
            400,
        )

    if professional_card_number and not re.fullmatch(r"[A-Za-z0-9-]{4,32}", professional_card_number):
        return _error_response(
            "Invalid professional card number format",
            "invalid_professional_card",
            400,
        )

    if AppUser.query.filter(
        (AppUser.username == username) | (AppUser.email == email)
    ).first():
        return _error_response("Username or email already exists", "user_exists", 400)

    if professional_card_number and AppUser.query.filter_by(
        professional_card_number=professional_card_number
    ).first():
        return _error_response(
            "Professional card number already exists",
            "professional_card_exists",
            409,
        )

    role_name = _USER_TYPE_ROLE.get(user_type)
    if not role_name:
        return _error_response("Invalid user_type", "invalid_user_type", 400)

    hashed = hash_password(password)
    new_user = AppUser(
        username=username,
        email=email,
        password=hashed,
        full_name=full_name,
        user_type=user_type,
        professional_card_number=professional_card_number,
    )

    try:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f"Auto-created role for {user_type} registration")
            db.session.add(role)
            db.session.flush()
        db.session.add(new_user)
        db.session.flush()
        db.session.add(UserRole(user_id=new_user.id, role_id=role.id))
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.warning("Integrity error on register for %s/%s: %s", username, email, e)
        return _error_response(
            "Username, email or professional card already exists",
            "user_exists",
            400,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Unexpected error on register: %s", e, exc_info=True)
        return jsonify({"msg": "Could not create user"}), 500

    log_audit(new_user.id, "register", "auth", f"User registered: {username}")
    try:
        send_welcome_email(to_email=new_user.email, full_name=new_user.full_name)
    except Exception:
        current_app.logger.error("Failed to schedule welcome email for %s", new_user.email, exc_info=True)
    return jsonify({"msg": "user created", "user_id": new_user.id}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("LOGIN_RATE_LIMIT", "5 per 15 minutes"), key_func=_login_rate_key)
def login():
    data = request.get_json(silent=True) or {}
    username = _normalize_username(data.get("username"))
    password = data.get("password") or ""

    if not username or not password:
        return _error_response("Missing credentials", "missing_credentials", 400)

    if not _is_valid_username(username):
        return _error_response("Invalid username format", "invalid_username", 400)

    user = AppUser.query.filter_by(username=username).first()
    if user:
        try:
            db.session.refresh(user)
        except Exception:
            db.session.rollback()
    if user:
        now = datetime.now(timezone.utc)
        if user.login_locked_until:
            locked_until = user.login_locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                retry_after = int((locked_until - now).total_seconds())
                return _error_response(
                    "Account locked due to failed attempts",
                    "account_locked",
                    423,
                    {"retry_after_seconds": retry_after},
                )
            user.login_locked_until = None
            user.failed_login_attempts = 0

    if not user or not check_password(password, user.password):
        log_audit(
            user.id if user else None,
            "login_failed",
            "auth",
            f"Failed login for: {username}",
        )
        if user:
            try:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                user.last_failed_login_at = datetime.now(timezone.utc)
                max_attempts = int(current_app.config.get("MAX_LOGIN_ATTEMPTS", 5))
                if user.failed_login_attempts >= max_attempts:
                    lock_minutes = int(current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15))
                    user.login_locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
                db.session.add(user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error("Failed to update login attempts for %s: %s", username, e, exc_info=True)
        return _error_response("Invalid credentials", "invalid_credentials", 401)

    if not user.is_active:
        return _error_response("Account inactive", "inactive_account", 403)

    if requires_mfa_enrollment(user) and not user.mfa_enabled:
        expires_in = _enroll_ttl_seconds()
        enrollment_token = create_access_token(
            identity=str(user.id),
            additional_claims={"roles": [], "mfa_enrollment": True},
            expires_delta=timedelta(seconds=expires_in),
        )
        log_audit(user.id, "MFA_ENROLLMENT_REQUIRED", "auth", "MFA enrollment required")
        return (
            jsonify(
                {
                    "mfa_enrollment_required": True,
                    "enrollment_token": enrollment_token,
                    "token_type": "bearer",
                    "expires_in": expires_in,
                    "msg": "MFA enrollment required",
                    "error": "mfa_enrollment_required",
                }
            ),
            200,
        )

    if user.mfa_enabled:
        expires_in = _challenge_ttl_seconds()
        challenge = MFALoginChallenge(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
        try:
            db.session.add(challenge)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error("Database error creating MFA challenge: %s", e, exc_info=True)
            return jsonify({"msg": "Database error"}), 500

        log_audit(user.id, "MFA_LOGIN_CHALLENGE_CREATED", "auth", "MFA login challenge created")
        return (
            jsonify(
                {
                    "mfa_required": True,
                    "challenge_id": str(challenge.id),
                    "expires_in": expires_in,
                    "error": "mfa_required",
                }
            ),
            200,
        )

    roles = _get_roles(user)
    access_token = create_access_token(
        identity=str(user.id), additional_claims={"roles": roles}
    )
    refresh_token = create_refresh_token(identity=str(user.id))

    decoded_refresh = decode_token(refresh_token)
    refresh_jti = decoded_refresh["jti"]
    exp_timestamp = decoded_refresh["exp"]
    expires_at = datetime.fromtimestamp(exp_timestamp, timezone.utc)

    db_refresh_token = RefreshToken(
        jti=refresh_jti, user_id=user.id, expires_at=expires_at
    )
    user_session = UserSession(
        user_id=user.id,
        ip_address=request.remote_addr,
        device_info=request.user_agent.string,
    )

    try:
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.login_locked_until = None
        db.session.add_all([db_refresh_token, user_session])
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on login for user %s: %s", user.id, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    log_audit(user.id, "login_success", "auth", "User logged in")
    response = _build_auth_response(access_token)
    set_refresh_cookie(response, refresh_token)
    return response, 200


@auth_bp.route("/login/mfa", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("LOGIN_MFA_RATE_LIMIT", "5 per 10 minutes"), key_func=_mfa_rate_key)
def login_mfa():
    data = request.get_json(silent=True) or {}
    challenge_raw = data.get("challenge_id")
    code = data.get("code")
    recovery_code = data.get("recovery_code")

    if not challenge_raw:
        return _error_response("Missing challenge_id", "missing_challenge", 400)
    if not code and not recovery_code:
        return _error_response("Missing MFA code", "missing_mfa_code", 400)

    try:
        challenge_id = uuid.UUID(str(challenge_raw))
    except Exception:
        return _error_response("Invalid challenge", "invalid_challenge", 401)

    challenge = MFALoginChallenge.query.filter_by(id=challenge_id).first()
    if not challenge:
        log_audit(None, "MFA_LOGIN_FAILED", "auth", "Invalid or expired MFA challenge")
        return _error_response("Invalid challenge", "invalid_challenge", 401)

    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if challenge.used_at or expires_at < datetime.now(timezone.utc):
        log_audit(None, "MFA_LOGIN_FAILED", "auth", "Invalid or expired MFA challenge")
        return _error_response("Invalid challenge", "invalid_challenge", 401)

    user = db.session.get(AppUser, challenge.user_id)
    if not user or not user.is_active:
        return _error_response("Invalid credentials", "invalid_credentials", 401)
    if requires_mfa_enrollment(user) and not user.mfa_enabled:
        resp = jsonify(
            {
                "mfa_enrollment_required": True,
                "msg": "MFA enrollment required",
                "error": "mfa_enrollment_required",
            }
        )
        clear_auth_cookies(resp)
        return resp, 403

    user_mfa = UserMFA.query.filter_by(user_id=user.id).first()
    if not user_mfa:
        return _error_response("MFA not enabled", "mfa_not_enabled", 403)

    secret = decrypt_mfa_secret(user_mfa.secret_encrypted)
    valid = False
    if code and validate_totp(secret, code):
        valid = True
        user_mfa.last_used_at = datetime.now(timezone.utc)
    elif recovery_code:
        max_days = int(current_app.config.get("RECOVERY_CODE_MAX_AGE_DAYS", 90))
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        recovery_entries = (
            RecoveryCode.query.filter_by(user_id=user.id, used_at=None)
            .filter(RecoveryCode.created_at >= cutoff)
            .all()
        )
        for entry in recovery_entries:
            if check_password(recovery_code, entry.code_hash):
                entry.used_at = datetime.now(timezone.utc)
                valid = True
                break

    if not valid:
        log_audit(user.id, "MFA_LOGIN_FAILED", "auth", "Invalid MFA code")
        return _error_response("Invalid MFA code", "invalid_mfa_code", 401)

    challenge.used_at = datetime.now(timezone.utc)
    roles = _get_roles(user)
    access_token = create_access_token(identity=str(user.id), additional_claims={"roles": roles})
    refresh_token = create_refresh_token(identity=str(user.id))

    decoded_refresh = decode_token(refresh_token)
    refresh_jti = decoded_refresh["jti"]
    exp_timestamp = decoded_refresh["exp"]
    expires_at = datetime.fromtimestamp(exp_timestamp, timezone.utc)

    db_refresh_token = RefreshToken(jti=refresh_jti, user_id=user.id, expires_at=expires_at)
    user_session = UserSession(
        user_id=user.id,
        ip_address=request.remote_addr,
        device_info=request.user_agent.string,
    )

    try:
        db.session.add_all([db_refresh_token, user_session, challenge, user_mfa])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on MFA login for user %s: %s", user.id, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    log_audit(user.id, "MFA_LOGIN_SUCCESS", "auth", "User passed MFA challenge")
    response = _build_auth_response(access_token)
    set_refresh_cookie(response, refresh_token)
    return response, 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True, locations=["cookies"])
def refresh():
    if not validate_csrf_header():
        return _error_response("Missing or invalid CSRF token", "csrf_failed", 403)

    identity = _parse_identity(get_jwt_identity())
    jti = get_jwt().get("jti")

    if not identity or not jti:
        return _error_response("Invalid token", "invalid_token", 401)

    token_entry = RefreshToken.query.filter_by(jti=jti).first()
    if not token_entry or token_entry.revoked or token_entry.user_id != identity:
        return _error_response("Token revoked", "token_revoked", 401)

    user = db.session.get(AppUser, identity)
    if not user or not user.is_active:
        return _error_response("User not found or inactive", "user_inactive", 401)

    if requires_mfa_enrollment(user) and not user.mfa_enabled:
        token_entry.revoked = True
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        resp = jsonify(
            {
                "mfa_enrollment_required": True,
                "msg": "MFA enrollment required",
                "error": "mfa_enrollment_required",
            }
        )
        clear_auth_cookies(resp)
        return resp, 401

    # Revoke current refresh
    token_entry.revoked = True

    roles = _get_roles(user)
    new_access_token = create_access_token(
        identity=str(identity), additional_claims={"roles": roles}
    )
    new_refresh_token = create_refresh_token(identity=str(identity))

    decoded_new_refresh = decode_token(new_refresh_token)
    new_jti = decoded_new_refresh["jti"]
    new_exp = datetime.fromtimestamp(decoded_new_refresh["exp"], timezone.utc)
    db.session.add(
        RefreshToken(
            jti=new_jti,
            user_id=identity,
            expires_at=new_exp,
        )
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error("Database error on refresh for user %s", identity, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    response = _build_auth_response(new_access_token)
    set_refresh_cookie(response, new_refresh_token)
    return response, 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)

    if not validate_csrf_header():
        return _error_response("Missing or invalid CSRF token", "csrf_failed", 403)

    # Revoke all refresh tokens for this user (logout all sessions)
    try:
        RefreshToken.query.filter_by(user_id=identity, revoked=False).update({"revoked": True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error revoking refresh tokens for %s: %s", identity, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    last_session = (
        UserSession.query.filter_by(user_id=identity, ended_at=None)
        .order_by(UserSession.started_at.desc())
        .first()
    )
    if last_session:
        last_session.ended_at = datetime.now(timezone.utc)
        db.session.add(last_session)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on logout for user %s: %s", identity, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    log_audit(identity, "logout", "auth", "User logged out")
    response = jsonify({"message": "logged out"})
    clear_auth_cookies(response)
    return response, 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    claims = get_jwt()
    if claims.get("mfa_enrollment"):
        return _error_response("Enrollment token not allowed", "mfa_enrollment_only", 403)

    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)

    user = db.session.get(AppUser, identity)
    if not user:
        return _error_response("User not found", "user_not_found", 404)

    def _fmt(dt):
        return dt.isoformat() if dt else None

    return (
        jsonify(
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "professional_card_number": user.professional_card_number,
                "is_active": user.is_active,
                "roles": _get_roles(user),
                "mfa_enabled": user.mfa_enabled,
                "mfa_confirmed_at": _fmt(user.mfa_confirmed_at),
                "mfa_method": user.mfa_method,
                "created_at": _fmt(user.created_at),
                "updated_at": _fmt(user.updated_at),
            }
        ),
        200,
    )


@auth_bp.post("/password/change")
@jwt_required()
@limiter.limit(lambda: current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT", "5 per 10 minutes"), key_func=_password_change_rate_key)
def change_password():
    claims = get_jwt()
    if claims.get("mfa_enrollment"):
        return _error_response("Enrollment token not allowed", "mfa_enrollment_only", 403)

    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)
    user = db.session.get(AppUser, identity)
    if not user or not user.is_active:
        return _error_response("User not found or inactive", "user_not_found", 404)

    schema = PasswordChangeSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _error_response("Validation error", "validation_error", 400, exc.messages)

    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_new_password") or ""
    max_len = int(current_app.config.get("PASSWORD_INPUT_MAX", 200))

    if not current_password or not new_password or not confirm_password:
        return _error_response("Missing fields", "missing_fields", 400)
    if len(current_password) > max_len or len(new_password) > max_len or len(confirm_password) > max_len:
        return _error_response("Input too long", "invalid_input", 400)
    if new_password == current_password:
        return _error_response("New password must be different", "invalid_password", 400)
    if new_password != confirm_password:
        return _error_response("Passwords do not match", "password_mismatch", 400)
    min_len = int(current_app.config.get("PASSWORD_MIN_LENGTH", 10))
    if len(new_password) < min_len:
        return _error_response("Weak password", "weak_password", 400)

    if not check_password(current_password, user.password):
        return _error_response("Invalid credentials", "invalid_credentials", 400)

    user.password = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    try:
        _revoke_refresh_tokens(user.id)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on password change for %s: %s", user.id, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    log_audit(user.id, "PASSWORD_CHANGED", "auth", "Password changed")
    return jsonify({"message": "Password updated"}), 200


@auth_bp.post("/password/forgot")
@limiter.limit(lambda: current_app.config.get("PASSWORD_FORGOT_RATE_LIMIT", "5 per 10 minutes"), key_func=get_remote_address)
@limiter.limit(lambda: current_app.config.get("PASSWORD_FORGOT_RATE_LIMIT", "5 per 10 minutes"), key_func=_password_forgot_email_key)
def forgot_password():
    schema = PasswordForgotSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError:
        return jsonify({"message": "If the email exists, a reset link has been sent"}), 200

    email = _normalize_email(data.get("email"))
    if not email or not _is_valid_email(email):
        return jsonify({"message": "If the email exists, a reset link has been sent"}), 200

    user = AppUser.query.filter_by(email=email).first()
    if user and user.is_active:
        try:
            token = create_reset_token(
                user_id=user.id,
                request_ip=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            base_url = current_app.config.get("FRONTEND_URL", "").rstrip("/")
            if not base_url:
                current_app.logger.warning("FRONTEND_URL not configured; skipping password reset email")
            else:
                path = current_app.config.get("PASSWORD_RESET_PATH", "/reset-password")
                reset_link = f"{base_url}{path}?token={token}"
                send_password_reset(to_email=user.email, reset_link=reset_link, full_name=user.full_name)
        except Exception as e:
            current_app.logger.error("Password reset flow failed for %s: %s", email, e, exc_info=True)

    return jsonify({"message": "If the email exists, a reset link has been sent"}), 200


@auth_bp.post("/password/reset")
@limiter.limit(lambda: current_app.config.get("PASSWORD_RESET_RATE_LIMIT", "5 per 10 minutes"), key_func=get_remote_address)
@limiter.limit(lambda: current_app.config.get("PASSWORD_RESET_RATE_LIMIT", "5 per 10 minutes"), key_func=_password_reset_rate_key)
def reset_password():
    schema = PasswordResetSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError:
        return _error_response("Invalid token or password", "invalid_token", 400)

    token = data.get("token")
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_new_password") or ""
    max_len = int(current_app.config.get("PASSWORD_INPUT_MAX", 200))

    if not token or not new_password or not confirm_password:
        return _error_response("Invalid token or password", "invalid_token", 400)
    if len(new_password) > max_len or len(confirm_password) > max_len:
        return _error_response("Invalid token or password", "invalid_token", 400)
    if new_password != confirm_password:
        return _error_response("Invalid token or password", "invalid_token", 400)
    min_len = int(current_app.config.get("PASSWORD_MIN_LENGTH", 10))
    if len(new_password) < min_len:
        return _error_response("Invalid token or password", "invalid_token", 400)

    entry = lookup_valid_token(token)
    if not entry:
        return _error_response("Invalid token or password", "invalid_token", 400)

    user = db.session.get(AppUser, entry.user_id)
    if not user or not user.is_active:
        return _error_response("Invalid token or password", "invalid_token", 400)

    try:
        user.password = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        mark_token_used(entry)
        _revoke_refresh_tokens(user.id)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Password reset failed for %s: %s", user.id, e, exc_info=True)
        return jsonify({"msg": "Database error"}), 500

    log_audit(user.id, "PASSWORD_RESET_COMPLETED", "auth", "Password reset completed")
    return jsonify({"message": "Password updated"}), 200


@auth_bp.get("/password/reset/verify")
@limiter.limit(lambda: current_app.config.get("PASSWORD_VERIFY_RATE_LIMIT", "20 per 10 minutes"), key_func=get_remote_address)
def verify_reset_token():
    token = request.args.get("token")
    if not token:
        return jsonify({"valid": False}), 400
    entry = lookup_valid_token(token)
    if not entry:
        return jsonify({"valid": False}), 400
    return jsonify({"valid": True}), 200
