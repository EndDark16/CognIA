# api/services/unsubscribe_service.py

from datetime import datetime, timezone

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from sqlalchemy.exc import IntegrityError

from app.models import EmailUnsubscribe, db


def _normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(raw).strip().lower()


def _get_serializer() -> URLSafeTimedSerializer | None:
    secret = current_app.config.get("EMAIL_UNSUBSCRIBE_SECRET") or current_app.config.get("SECRET_KEY")
    if not secret:
        return None
    return URLSafeTimedSerializer(secret_key=secret, salt="email-unsubscribe")


def generate_unsubscribe_token(email: str) -> str | None:
    serializer = _get_serializer()
    if not serializer:
        return None
    normalized = _normalize_email(email)
    if not normalized:
        return None
    return serializer.dumps({"email": normalized})


def verify_unsubscribe_token(token: str) -> str:
    serializer = _get_serializer()
    if not serializer:
        raise RuntimeError("EMAIL_UNSUBSCRIBE_SECRET or SECRET_KEY must be configured")

    max_age_days = current_app.config.get("EMAIL_UNSUBSCRIBE_TOKEN_TTL_DAYS")
    max_age = int(max_age_days) * 86400 if max_age_days else None
    data = serializer.loads(token, max_age=max_age)
    email = _normalize_email(data.get("email"))
    if not email:
        raise BadSignature("Missing email in token")
    return email


def upsert_unsubscribe(
    *,
    email: str,
    reason: str | None,
    source: str | None,
    request_ip: str | None,
    user_agent: str | None,
) -> EmailUnsubscribe:
    normalized = _normalize_email(email)
    if not normalized:
        raise ValueError("Email is required")

    now = datetime.now(timezone.utc)
    entry = EmailUnsubscribe.query.filter_by(email=normalized).first()
    if entry:
        entry.reason = reason or entry.reason
        entry.source = source or entry.source
        entry.request_ip = request_ip or entry.request_ip
        entry.user_agent = user_agent or entry.user_agent
        entry.unsubscribed_at = now
    else:
        entry = EmailUnsubscribe(
            email=normalized,
            reason=reason,
            source=source,
            request_ip=request_ip,
            user_agent=user_agent,
            unsubscribed_at=now,
        )
        db.session.add(entry)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = EmailUnsubscribe.query.filter_by(email=normalized).first()
        if existing:
            return existing
        raise
    except Exception:
        db.session.rollback()
        raise
    return entry
