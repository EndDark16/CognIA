import time
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from app.models import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@health_bp.get("/readyz")
def readyz():
    start = time.monotonic()
    try:
        db.session.execute(text("SELECT 1"))
        db.session.rollback()
        latency_ms = (time.monotonic() - start) * 1000.0
        return jsonify({"status": "ready", "latency_ms": round(latency_ms, 2)}), 200
    except Exception:
        current_app.logger.warning("Readiness check failed", exc_info=True)
        return jsonify({"status": "not_ready"}), 503
