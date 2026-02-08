import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.models import PasswordResetToken, db


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invalidate_existing_tokens(user_id) -> None:
    now = datetime.now(timezone.utc)
    PasswordResetToken.query.filter_by(user_id=user_id, used_at=None).update(
        {"used_at": now}, synchronize_session=False
    )


def create_reset_token(*, user_id, request_ip: str | None, user_agent: str | None) -> str:
    ttl_minutes = int(current_app.config.get("PASSWORD_RESET_TOKEN_TTL_MINUTES", 30))
    token = generate_reset_token()
    token_hash = hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    invalidate_existing_tokens(user_id)
    entry = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
        request_ip=request_ip,
        user_agent=user_agent,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return token


def lookup_valid_token(token: str) -> PasswordResetToken | None:
    token_hash = hash_reset_token(token)
    entry = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not entry:
        return None
    expires_at = entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if entry.used_at is not None:
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return entry


def mark_token_used(entry: PasswordResetToken) -> None:
    entry.used_at = datetime.now(timezone.utc)
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
