from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.models import (
    AppUser,
    UserMFA,
    RecoveryCode,
    MFALoginChallenge,
    RefreshToken,
    db,
)
from api.security import (
    encrypt_mfa_secret,
    decrypt_mfa_secret,
    generate_totp_secret,
    build_totp_uri,
    validate_totp,
    generate_recovery_codes,
    hash_password,
    check_password,
    log_audit,
    clear_auth_cookies,
)
from api.routes.auth import _parse_identity, _error_response
from flask import current_app
from api.extensions import limiter

mfa_bp = Blueprint("mfa", __name__, url_prefix="/api/mfa")


def _validate_challenge(challenge_id: str, user_id) -> MFALoginChallenge | None:
    ch = MFALoginChallenge.query.filter_by(id=challenge_id, user_id=user_id).first()
    if not ch or ch.used_at:
        return None
    if ch.expires_at < datetime.now(timezone.utc):
        return None
    return ch


@mfa_bp.route("/setup", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("MFA_SETUP_RATE_LIMIT", "3 per 10 minutes"))
def mfa_setup():
    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)
    user = db.session.get(AppUser, identity)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    if not user.is_active:
        return _error_response("Account inactive", "inactive_account", 403)
    if user.mfa_enabled:
        return _error_response("MFA already enabled", "mfa_already_enabled", 409)

    secret = generate_totp_secret()
    secret_enc = encrypt_mfa_secret(secret)
    existing = UserMFA.query.filter_by(user_id=identity).first()
    if not existing:
        existing = UserMFA(user_id=identity, method="totp", secret_encrypted=secret_enc)
        db.session.add(existing)
    else:
        existing.secret_encrypted = secret_enc
        existing.method = "totp"
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on MFA setup for %s: %s", identity, e, exc_info=True)
        return _error_response("Database error", "db_error", 500)

    uri = build_totp_uri(secret, user.username, issuer="CogniaApp")
    resp = {"otpauth_uri": uri}
    if current_app.testing or current_app.debug:
        resp["secret"] = secret
    log_audit(identity, "MFA_SETUP_STARTED", "auth", f"User {user.username} started MFA setup")
    return jsonify(resp), 200


@mfa_bp.route("/confirm", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("MFA_CONFIRM_RATE_LIMIT", "5 per 10 minutes"))
def mfa_confirm():
    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    if not code:
        return _error_response("Missing code", "missing_mfa_code", 400)

    user = db.session.get(AppUser, identity)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    if not user.is_active:
        return _error_response("Account inactive", "inactive_account", 403)
    user_mfa = UserMFA.query.filter_by(user_id=identity).first()
    if not user_mfa:
        return _error_response("MFA not initialized", "mfa_not_initialized", 400)

    secret = decrypt_mfa_secret(user_mfa.secret_encrypted)
    if not validate_totp(secret, code):
        log_audit(identity, "MFA_LOGIN_FAILED", "auth", "Invalid TOTP on confirm")
        return _error_response("Invalid code", "invalid_mfa_code", 401)

    user.mfa_enabled = True
    user.mfa_confirmed_at = datetime.now(timezone.utc)
    user.mfa_method = "totp"

    # generate recovery codes
    codes_plain = generate_recovery_codes()
    for c in codes_plain:
        rc = RecoveryCode(user_id=identity, code_hash=hash_password(c))
        db.session.add(rc)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on MFA confirm for %s: %s", identity, e, exc_info=True)
        return _error_response("Database error", "db_error", 500)
    log_audit(identity, "MFA_ENABLED", "auth", "MFA enabled")
    return jsonify({"recovery_codes": codes_plain}), 200


@mfa_bp.route("/disable", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("MFA_DISABLE_RATE_LIMIT", "3 per 10 minutes"))
def mfa_disable():
    identity = _parse_identity(get_jwt_identity())
    if not identity:
        return _error_response("Invalid user", "invalid_user", 401)
    claims = get_jwt()
    if claims.get("mfa_enrollment"):
        return _error_response("Enrollment token not allowed", "mfa_enrollment_only", 403)
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    code = data.get("code")
    recovery = data.get("recovery_code")
    user = db.session.get(AppUser, identity)
    if not user:
        return _error_response("User not found", "user_not_found", 404)
    if not user.is_active:
        return _error_response("Account inactive", "inactive_account", 403)
    if not check_password(password or "", user.password):
        return _error_response("Invalid credentials", "invalid_credentials", 401)
    if not user.mfa_enabled:
        return _error_response("MFA not enabled", "mfa_not_enabled", 400)

    user_mfa = UserMFA.query.filter_by(user_id=identity).first()
    if not user_mfa:
        return _error_response("MFA not enabled", "mfa_not_enabled", 400)

    if code:
        secret = decrypt_mfa_secret(user_mfa.secret_encrypted)
        if not validate_totp(secret, code):
            return _error_response("Invalid code", "invalid_mfa_code", 401)
    elif recovery:
        max_days = int(current_app.config.get("RECOVERY_CODE_MAX_AGE_DAYS", 90))
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        rc = (
            RecoveryCode.query.filter_by(user_id=identity, used_at=None)
            .filter(RecoveryCode.created_at >= cutoff)
            .all()
        )
        ok = False
        for item in rc:
            if check_password(recovery, item.code_hash):
                item.used_at = datetime.now(timezone.utc)
                ok = True
                break
        if not ok:
            return _error_response("Invalid recovery code", "invalid_recovery_code", 401)
    else:
        return _error_response("Missing code or recovery_code", "missing_mfa_code", 400)

    # Disable MFA
    user.mfa_enabled = False
    user.mfa_confirmed_at = None
    user.mfa_method = "none"
    UserMFA.query.filter_by(user_id=identity).delete()
    RecoveryCode.query.filter_by(user_id=identity).delete()
    # revoke refresh tokens
    RefreshToken.query.filter_by(user_id=identity, revoked=False).update({"revoked": True})
    MFALoginChallenge.query.filter_by(user_id=identity, used_at=None).update({"used_at": datetime.now(timezone.utc)})
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Database error on MFA disable for %s: %s", identity, e, exc_info=True)
        return _error_response("Database error", "db_error", 500)
    log_audit(identity, "MFA_DISABLED", "auth", "MFA disabled")
    response = jsonify({"msg": "MFA disabled"})
    clear_auth_cookies(response)
    return response, 200
