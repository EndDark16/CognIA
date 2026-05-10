import os
import sys

from config.settings import TestingConfig, ProductionConfig

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.metrics import configure_metrics, reset_metrics_state
from app.models import db


def _client_with_config(overrides=None):
    reset_metrics_state()
    app = create_app(TestingConfig)
    if overrides:
        app.config.update(overrides)
        configure_metrics(
            sample_size=app.config.get("METRICS_ENDPOINT_SAMPLE_SIZE"),
            exclude_endpoint_details=app.config.get("METRICS_EXCLUDE_ENDPOINT_DETAILS"),
        )
    with app.app_context():
        db.create_all()
    return app.test_client(), app


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_metrics_requires_token_when_configured():
    client, app = _client_with_config({"METRICS_TOKEN": "secret-token"})
    try:
        resp_missing = client.get("/metrics")
        assert resp_missing.status_code == 401

        resp_bad = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
        assert resp_bad.status_code == 401

        resp_ok = client.get(
            "/metrics", headers={"Authorization": "Bearer secret-token"}
        )
        assert resp_ok.status_code == 200
    finally:
        _teardown(app)


def test_metrics_disabled_returns_404():
    client, app = _client_with_config({"METRICS_ENABLED": False})
    try:
        resp = client.get("/metrics")
        assert resp.status_code == 404
    finally:
        _teardown(app)


def test_metrics_keeps_legacy_fields_and_adds_endpoint_breakdown():
    client, app = _client_with_config(
        {
            "METRICS_ENABLED": True,
            "METRICS_TOKEN": None,
            "METRICS_TOKEN_REQUIRED": False,
        }
    )
    try:
        warm = client.get("/healthz")
        assert warm.status_code == 200

        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.get_json()

        # Legacy fields (contract compatibility)
        assert "uptime_seconds" in body
        assert "requests_total" in body
        assert "latency_ms_avg" in body
        assert "latency_ms_max" in body
        assert "status_counts" in body

        # New backward-compatible fields
        assert "endpoint_counts" in body
        assert "endpoint_status_counts" in body
        assert "endpoint_latency_ms_avg" in body
        assert "endpoint_latency_ms_max" in body
        assert "endpoint_latency_ms_p95_approx" in body
        assert "error_counts" in body
    finally:
        _teardown(app)


def test_metrics_can_exclude_health_endpoint_details_without_losing_totals():
    client, app = _client_with_config(
        {
            "METRICS_ENABLED": True,
            "METRICS_TOKEN": None,
            "METRICS_TOKEN_REQUIRED": False,
            "METRICS_EXCLUDE_ENDPOINT_DETAILS": {"/healthz", "/readyz", "healthz", "readyz"},
            "METRICS_ENDPOINT_SAMPLE_SIZE": 32,
        }
    )
    try:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200

        metrics_resp = client.get("/metrics")
        assert metrics_resp.status_code == 200
        body = metrics_resp.get_json()
        assert body["requests_total"] >= 2
        endpoint_counts = body.get("endpoint_counts", {})
        assert all("health" not in str(key) for key in endpoint_counts.keys())
        assert all("ready" not in str(key) for key in endpoint_counts.keys())
    finally:
        _teardown(app)


def test_swagger_disabled_returns_404():
    client, app = _client_with_config({"SWAGGER_ENABLED": False})
    try:
        resp_openapi = client.get("/openapi.yaml")
        assert resp_openapi.status_code == 404

        resp_docs = client.get("/docs")
        assert resp_docs.status_code == 404
    finally:
        _teardown(app)


def test_openapi_public_disabled_by_default_in_production():
    app = create_app(ProductionConfig)
    client = app.test_client()
    resp_openapi = client.get("/openapi.yaml")
    resp_docs = client.get("/docs")
    assert resp_openapi.status_code == 404
    assert resp_docs.status_code == 404


def test_swagger_openapi_source_of_truth_is_docs_openapi_yaml():
    client, app = _client_with_config()
    try:
        resp_openapi = client.get("/openapi.yaml")
        assert resp_openapi.status_code == 200
        spec_path = os.path.join(PROJECT_ROOT, "docs", "openapi.yaml")
        with open(spec_path, "rb") as f:
            expected = f.read()
        assert resp_openapi.data == expected

        resp_docs = client.get("/docs")
        assert resp_docs.status_code == 200
        assert b'url: "/openapi.yaml"' in resp_docs.data
    finally:
        _teardown(app)
