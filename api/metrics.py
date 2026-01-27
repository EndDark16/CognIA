import threading
import time
from collections import defaultdict
from flask import Blueprint, jsonify, current_app, request


_LOCK = threading.Lock()
_START_TIME = time.time()
_TOTAL_REQUESTS = 0
_TOTAL_LATENCY_MS = 0.0
_MAX_LATENCY_MS = 0.0
_STATUS_COUNTS = defaultdict(int)


def record_request_metrics(duration_ms: float, status_code: int) -> None:
    """Record minimal in-memory metrics for a request."""
    global _TOTAL_REQUESTS, _TOTAL_LATENCY_MS, _MAX_LATENCY_MS
    with _LOCK:
        _TOTAL_REQUESTS += 1
        _TOTAL_LATENCY_MS += duration_ms
        if duration_ms > _MAX_LATENCY_MS:
            _MAX_LATENCY_MS = duration_ms
        _STATUS_COUNTS[str(status_code)] += 1


def _snapshot_metrics() -> dict:
    with _LOCK:
        avg_latency = (
            _TOTAL_LATENCY_MS / _TOTAL_REQUESTS if _TOTAL_REQUESTS else 0.0
        )
        return {
            "uptime_seconds": int(time.time() - _START_TIME),
            "requests_total": _TOTAL_REQUESTS,
            "latency_ms_avg": round(avg_latency, 2),
            "latency_ms_max": round(_MAX_LATENCY_MS, 2),
            "status_counts": dict(_STATUS_COUNTS),
        }


metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/metrics")
def metrics():
    if not current_app.config.get("METRICS_ENABLED", True):
        return jsonify({"msg": "Metrics disabled"}), 404

    token = current_app.config.get("METRICS_TOKEN")
    token_required = current_app.config.get("METRICS_TOKEN_REQUIRED", False)
    if token_required and not token:
        return jsonify({"msg": "Metrics token not configured", "error": "metrics_token_required"}), 500

    if token or token_required:
        auth = request.headers.get("Authorization", "")
        if not token or auth != f"Bearer {token}":
            return jsonify({"msg": "Unauthorized", "error": "unauthorized"}), 401

    try:
        return jsonify(_snapshot_metrics()), 200
    except Exception:
        current_app.logger.error("Metrics snapshot failed", exc_info=True)
        return jsonify({"msg": "Metrics error", "error": "metrics_error"}), 500
