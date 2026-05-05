import os
import sys
import time

from config.settings import TestingConfig

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db


def _client():
    app = create_app(TestingConfig)
    # Ensure metrics endpoint isn't blocked by env-level token in tests
    app.config["METRICS_TOKEN"] = None
    with app.app_context():
        db.create_all()
    return app.test_client(), app


def test_healthz_and_readyz():
    client, app = _client()
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200

    resp_ready = client.get("/readyz")
    assert resp_ready.status_code == 200

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_metrics_endpoint():
    client, app = _client()
    resp_metrics = client.get("/metrics")
    assert resp_metrics.status_code == 200
    body = resp_metrics.json
    assert "requests_total" in body
    assert "latency_ms_avg" in body

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_openapi_and_docs():
    client, app = _client()
    resp_openapi = client.get("/openapi.yaml")
    assert resp_openapi.status_code == 200
    assert b"openapi: 3.0.3" in resp_openapi.data

    resp_docs = client.get("/docs")
    assert resp_docs.status_code == 200

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_readyz_uses_short_cache_window(monkeypatch):
    from api.routes import health as health_module

    client, app = _client()
    app.config["READINESS_CACHE_TTL_SECONDS"] = 1
    health_module._READINESS_CACHE["expires_at"] = 0.0

    execute_count = {"value": 0}
    original_execute = db.session.execute

    def _counted_execute(*args, **kwargs):
        execute_count["value"] += 1
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(db.session, "execute", _counted_execute)

    first = client.get("/readyz")
    second = client.get("/readyz")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json().get("cached") is False
    assert second.get_json().get("cached") is True
    assert execute_count["value"] == 1

    time.sleep(1.1)
    third = client.get("/readyz")
    assert third.status_code == 200
    assert third.get_json().get("cached") is False
    assert execute_count["value"] == 2

    with app.app_context():
        db.session.remove()
        db.drop_all()
