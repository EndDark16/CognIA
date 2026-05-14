import bcrypt
import re
from app.models import db, AuditLog, AppUser, RefreshToken
from datetime import datetime, timezone
from flask import current_app, request
from flask_jwt_extended import set_refresh_cookies, unset_jwt_cookies
from cryptography.fernet import Fernet, InvalidToken
import base64
import os
import pyotp
import secrets

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt.hashpw returns bytes, decode to string for DB storage
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against a hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


_PWD_UPPER_RE = re.compile(r"[A-Z]")
_PWD_LOWER_RE = re.compile(r"[a-z]")
_PWD_DIGIT_RE = re.compile(r"\d")
_PWD_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def password_policy_errors(password: str, min_length: int = 8) -> list[str]:
    """Return list of missing password requirements."""
    errors = []
    if len(password) < min_length:
        errors.append(f"min_length:{min_length}")
    if not _PWD_UPPER_RE.search(password or ""):
        errors.append("uppercase")
    if not _PWD_LOWER_RE.search(password or ""):
        errors.append("lowercase")
    if not _PWD_DIGIT_RE.search(password or ""):
        errors.append("number")
    if not _PWD_SPECIAL_RE.search(password or ""):
        errors.append("special")
    return errors

def log_audit(user_id, action, section=None, details=None):
    """Helper to log audit events."""
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            section=section,
            details=details
        )
        db.session.add(audit_entry)
        db.session.commit()
    except Exception as e:
        print(f"Failed to write audit log: {e}")
        db.session.rollback()


def revoke_user_sessions(user: AppUser) -> None:
    """Revoke refresh tokens and mark access tokens as revoked for a user."""
    now = datetime.now(timezone.utc)
    try:
        RefreshToken.query.filter_by(user_id=user.id, revoked=False).update(
            {"revoked": True}, synchronize_session=False
        )
        user.sessions_revoked_at = now
        db.session.add(user)
        db.session.commit()
        # Import local para evitar ciclos durante inicializacion.
        from api.cache import invalidate_user_auth_caches

        invalidate_user_auth_caches(user.id)
    except Exception:
        db.session.rollback()
        raise


def set_refresh_cookie(response, refresh_token: str) -> None:
    """Set refresh token cookie (HttpOnly) with CSRF double-submit cookie."""
    set_refresh_cookies(response, refresh_token)


def clear_auth_cookies(response) -> None:
    """Clear auth-related cookies using framework defaults plus defensive variants."""
    unset_jwt_cookies(response)

    access_cookie = current_app.config.get("JWT_ACCESS_COOKIE_NAME", "access_token_cookie")
    refresh_cookie = current_app.config.get("JWT_REFRESH_COOKIE_NAME", "refresh_token")
    access_csrf_cookie = current_app.config.get("JWT_ACCESS_CSRF_COOKIE_NAME", "csrf_access_token")
    refresh_csrf_cookie = current_app.config.get("JWT_REFRESH_CSRF_COOKIE_NAME", "csrf_refresh_token")

    access_path = current_app.config.get("JWT_ACCESS_COOKIE_PATH", "/")
    refresh_path = current_app.config.get("JWT_REFRESH_COOKIE_PATH", "/api/auth/refresh")
    access_csrf_path = current_app.config.get("JWT_ACCESS_CSRF_COOKIE_PATH", "/")
    refresh_csrf_path = current_app.config.get("JWT_REFRESH_CSRF_COOKIE_PATH", "/")

    cookie_path_by_name = {
        access_cookie: [access_path],
        refresh_cookie: [refresh_path, "/"],
        access_csrf_cookie: [access_csrf_path],
        refresh_csrf_cookie: [refresh_csrf_path, "/", refresh_path],
    }
    cookie_domain = current_app.config.get("JWT_COOKIE_DOMAIN")
    domains = [cookie_domain] if cookie_domain else [None]
    secure = current_app.config.get("JWT_COOKIE_SECURE")
    samesite = current_app.config.get("JWT_COOKIE_SAMESITE")

    seen = set()
    for cookie_name, candidate_paths in cookie_path_by_name.items():
        if not cookie_name:
            continue
        for cookie_path in candidate_paths:
            if not cookie_path:
                continue
            for domain in domains:
                key = (cookie_name, cookie_path, domain)
                if key in seen:
                    continue
                seen.add(key)
                kwargs = {
                    "path": cookie_path,
                    "secure": bool(secure),
                    "samesite": samesite,
                }
                if domain:
                    kwargs["domain"] = domain
                response.delete_cookie(cookie_name, **kwargs)


def validate_csrf_header(header_name: str = "X-CSRF-Token", cookie_name: str = "csrf_refresh_token") -> bool:
    """Validate double-submit CSRF: header must match the CSRF cookie."""
    header_token = request.headers.get(header_name)
    cookie_token = request.cookies.get(cookie_name)
    return bool(header_token and cookie_token and header_token == cookie_token)


def get_user_roles(user: AppUser) -> list[str]:
    """Return role names for a user."""
    return [role.name for role in getattr(user, "roles", [])]


def requires_mfa_enrollment(user: AppUser) -> bool:
    """Return True if the user's roles require MFA enrollment."""
    roles = get_user_roles(user)
    return any(role in ("ADMIN", "PSYCHOLOGIST", "PSICOLOGO") for role in roles)


def _get_fernet() -> Fernet:
    key = os.getenv("MFA_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("MFA_ENCRYPTION_KEY is required for MFA secret encryption")
    try:
        # Accept raw base64 urlsafe or plain string (encode to 32 bytes and base64)
        if len(key) == 32:
            k = base64.urlsafe_b64encode(key.encode())
        elif len(key) >= 43:  # fernet base64 length
            k = key.encode()
        else:
            raise ValueError("Invalid MFA_ENCRYPTION_KEY length")
        return Fernet(k)
    except Exception as e:
        raise RuntimeError(f"Invalid MFA_ENCRYPTION_KEY: {e}")


def encrypt_mfa_secret(plain: str) -> str:
    f = _get_fernet()
    return f.encrypt(plain.encode()).decode()


def decrypt_mfa_secret(cipher: str) -> str:
    f = _get_fernet()
    try:
        return f.decrypt(cipher.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Failed to decrypt MFA secret") from e


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_totp_uri(secret: str, username: str, issuer: str = "CognIA") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def validate_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    totp = pyotp.TOTP(secret)
    try:
        return totp.verify(code, valid_window=valid_window)
    except Exception:
        return False


def generate_recovery_codes(n: int = 10) -> list[str]:
    codes = []
    for _ in range(n):
        codes.append(secrets.token_hex(4))  # 8 hex chars
    return codes
