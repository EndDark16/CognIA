import os
import sys

from config.settings import TestingConfig

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db


def _client():
    app = create_app(TestingConfig)
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
