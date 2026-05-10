import threading
import time
from collections import defaultdict, deque
from flask import Blueprint, jsonify, current_app, request


_LOCK = threading.Lock()
_START_TIME = time.time()
_TOTAL_REQUESTS = 0
_TOTAL_LATENCY_MS = 0.0
_MAX_LATENCY_MS = 0.0
_STATUS_COUNTS = defaultdict(int)
_ENDPOINT_COUNTS = defaultdict(int)
_ENDPOINT_STATUS_COUNTS = defaultdict(int)
_ENDPOINT_LATENCY_TOTAL_MS = defaultdict(float)
_ENDPOINT_LATENCY_MAX_MS = defaultdict(float)
_ENDPOINT_LATENCY_SAMPLES = defaultdict(lambda: deque(maxlen=512))
_ERROR_COUNTS = defaultdict(int)

_ERROR_KEYS = {
    "db_unavailable",
    "rate_limited",
    "validation_error",
    "server_error",
    "runtime_artifact_unavailable",
}


def record_request_metrics(
    duration_ms: float,
    status_code: int,
    endpoint: str | None = None,
) -> None:
    """Record minimal in-memory metrics for a request."""
    global _TOTAL_REQUESTS, _TOTAL_LATENCY_MS, _MAX_LATENCY_MS
    endpoint_key = endpoint or "unknown"
    status_key = str(status_code)
    with _LOCK:
        _TOTAL_REQUESTS += 1
        _TOTAL_LATENCY_MS += duration_ms
        if duration_ms > _MAX_LATENCY_MS:
            _MAX_LATENCY_MS = duration_ms
        _STATUS_COUNTS[status_key] += 1

        _ENDPOINT_COUNTS[endpoint_key] += 1
        _ENDPOINT_STATUS_COUNTS[f"{endpoint_key}|{status_key}"] += 1
        _ENDPOINT_LATENCY_TOTAL_MS[endpoint_key] += duration_ms
        if duration_ms > _ENDPOINT_LATENCY_MAX_MS[endpoint_key]:
            _ENDPOINT_LATENCY_MAX_MS[endpoint_key] = duration_ms
        _ENDPOINT_LATENCY_SAMPLES[endpoint_key].append(float(duration_ms))


def record_error_metric(error_key: str) -> None:
    key = str(error_key or "").strip().lower()
    if key not in _ERROR_KEYS:
        return
    with _LOCK:
        _ERROR_COUNTS[key] += 1


def _approx_p95(values: deque[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round(0.95 * (len(ordered) - 1)))
    return float(ordered[max(0, min(index, len(ordered) - 1))])


def _snapshot_metrics() -> dict:
    with _LOCK:
        avg_latency = (
            _TOTAL_LATENCY_MS / _TOTAL_REQUESTS if _TOTAL_REQUESTS else 0.0
        )
        endpoint_avg = {}
        endpoint_max = {}
        endpoint_p95 = {}
        for endpoint, count in _ENDPOINT_COUNTS.items():
            endpoint_avg[endpoint] = round(
                (_ENDPOINT_LATENCY_TOTAL_MS[endpoint] / count) if count else 0.0,
                2,
            )
            endpoint_max[endpoint] = round(_ENDPOINT_LATENCY_MAX_MS[endpoint], 2)
            endpoint_p95[endpoint] = round(
                _approx_p95(_ENDPOINT_LATENCY_SAMPLES[endpoint]),
                2,
            )

        return {
            "uptime_seconds": int(time.time() - _START_TIME),
            "requests_total": _TOTAL_REQUESTS,
            "latency_ms_avg": round(avg_latency, 2),
            "latency_ms_max": round(_MAX_LATENCY_MS, 2),
            "status_counts": dict(_STATUS_COUNTS),
            "endpoint_counts": dict(_ENDPOINT_COUNTS),
            "endpoint_status_counts": dict(_ENDPOINT_STATUS_COUNTS),
            "endpoint_latency_ms_avg": endpoint_avg,
            "endpoint_latency_ms_max": endpoint_max,
            "endpoint_latency_ms_p95_approx": endpoint_p95,
            "error_counts": dict(_ERROR_COUNTS),
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
