from datetime import datetime, timezone, timedelta
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
from app.models import (
    AppUser,
    RefreshToken,
    UserSession,
    UserMFA,
    RecoveryCode,
    MFALoginChallenge,
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


def _error_response(message: str, error_code: str, status_code: int):
    return jsonify({"msg": message, "error": error_code}), status_code


def _challenge_ttl_seconds() -> int:
    try:
        return int(current_app.config.get("MFA_CHALLENGE_TTL", 300))
    except Exception:
        return 300


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name")

    if not username or not email or not password:
        return _error_response("Missing username, email or password", "missing_fields", 400)

    if len(password) < 8:
        return _error_response("Password must be at least 8 characters", "weak_password", 400)

    if AppUser.query.filter(
        (AppUser.username == username) | (AppUser.email == email)
    ).first():
        return _error_response("Username or email already exists", "user_exists", 400)

    hashed = hash_password(password)
    new_user = AppUser(
        username=username, email=email, password=hashed, full_name=full_name
    )

    try:
        db.session.add(new_user)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.warning("Integrity error on register for %s/%s: %s", username, email, e)
        return jsonify({"msg": "Username or email already exists"}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Unexpected error on register: %s", e, exc_info=True)
        return jsonify({"msg": "Could not create user"}), 500

    log_audit(new_user.id, "register", "auth", f"User registered: {username}")
    return jsonify({"msg": "user created", "user_id": new_user.id}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 15 minutes")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return _error_response("Missing credentials", "missing_credentials", 400)

    user = AppUser.query.filter_by(username=username).first()
    if not user or not check_password(password, user.password):
        log_audit(
            user.id if user else None,
            "login_failed",
            "auth",
            f"Failed login for: {username}",
        )
        return _error_response("Invalid credentials", "invalid_credentials", 401)

    if not user.is_active:
        return _error_response("Account inactive", "inactive_account", 403)

    if requires_mfa_enrollment(user) and not user.mfa_enabled:
        log_audit(user.id, "MFA_ENROLLMENT_REQUIRED", "auth", "MFA enrollment required")
        return (
            jsonify(
                {
                    "mfa_enrollment_required": True,
                    "msg": "MFA enrollment required",
                    "error": "mfa_enrollment_required",
                }
            ),
            403,
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
        db.session.add_all([db_refresh_token, user_session])
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
@limiter.limit("3 per 10 minutes")
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
        recovery_entries = RecoveryCode.query.filter_by(user_id=user.id, used_at=None).all()
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

    refresh_cookie = request.cookies.get("refresh_token")
    if refresh_cookie:
        try:
            decoded = decode_token(refresh_cookie)
            refresh_jti = decoded.get("jti")
            token_entry = RefreshToken.query.filter_by(jti=refresh_jti).first()
            if token_entry:
                token_entry.revoked = True
                db.session.add(token_entry)
        except Exception:
            pass

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
