import bcrypt
from app.models import db, AuditLog, AppUser
from flask import request
from flask_jwt_extended import set_refresh_cookies
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


def set_refresh_cookie(response, refresh_token: str) -> None:
    """Set refresh token cookie (HttpOnly) with CSRF double-submit cookie."""
    set_refresh_cookies(response, refresh_token)


def clear_auth_cookies(response) -> None:
    """Clear auth-related cookies (refresh + csrf)."""
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    response.delete_cookie("csrf_refresh_token", path="/")
    # Also clear default access cookie name to be safe
    response.delete_cookie("access_token_cookie", path="/")


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
