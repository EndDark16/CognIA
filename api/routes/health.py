import time
from threading import Lock
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from app.models import db


health_bp = Blueprint("health", __name__)
_READINESS_CACHE_LOCK = Lock()
_READINESS_CACHE = {
    "expires_at": 0.0,
    "status_code": 503,
    "payload": {"status": "not_ready"},
}


@health_bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@health_bp.get("/readyz")
def readyz():
    ttl = max(0.0, float(current_app.config.get("READINESS_CACHE_TTL_SECONDS", 3)))
    now = time.monotonic()

    if ttl > 0:
        with _READINESS_CACHE_LOCK:
            if now < _READINESS_CACHE["expires_at"]:
                cached_payload = dict(_READINESS_CACHE["payload"])
                cached_payload["cached"] = True
                return jsonify(cached_payload), int(_READINESS_CACHE["status_code"])

    with _READINESS_CACHE_LOCK:
        now = time.monotonic()
        if ttl > 0 and now < _READINESS_CACHE["expires_at"]:
            cached_payload = dict(_READINESS_CACHE["payload"])
            cached_payload["cached"] = True
            return jsonify(cached_payload), int(_READINESS_CACHE["status_code"])

        payload, status_code = _run_readiness_check()
        payload["cached"] = False
        if ttl > 0:
            _READINESS_CACHE["payload"] = dict(payload)
            _READINESS_CACHE["status_code"] = int(status_code)
            _READINESS_CACHE["expires_at"] = now + ttl
        return jsonify(payload), status_code


def _run_readiness_check():
    start = time.monotonic()
    timeout_ms = max(100, int(current_app.config.get("READINESS_DB_TIMEOUT_MS", 2000)))
    try:
        bind = db.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            # Avoid long blocking checks while still validating DB dependency.
            db.session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        db.session.execute(text("SELECT 1"))
        db.session.rollback()
        latency_ms = (time.monotonic() - start) * 1000.0
        return {"status": "ready", "latency_ms": round(latency_ms, 2)}, 200
    except Exception:
        current_app.logger.warning("Readiness check failed", exc_info=True)
        db.session.rollback()
        return {"status": "not_ready"}, 503
