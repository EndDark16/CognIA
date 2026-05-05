import os
import sys

from config.settings import TestingConfig, ProductionConfig

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db


def _client_with_config(overrides=None):
    app = create_app(TestingConfig)
    if overrides:
        app.config.update(overrides)
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
