import os
import sys

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _valid_predict_payload():
    return {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }


def test_predict_api_valid_payload_returns_expected_shape(client):
    resp = client.post("/api/predict", json=_valid_predict_payload())

    assert resp.status_code == 200
    body = resp.get_json()
    assert "predictions" in body
    assert "adhd" in body["predictions"]
    assert "elimination" not in body["predictions"]


def test_predict_api_missing_required_input_returns_400(client):
    bad_payload = _valid_predict_payload()
    bad_payload.pop("age")

    resp = client.post("/api/predict", json=bad_payload)

    assert resp.status_code == 400
    body = resp.get_json()
    assert "errors" in body
    assert "age" in body["errors"]


def test_predict_api_invalid_input_value_returns_400(client):
    bad_payload = _valid_predict_payload()
    bad_payload["sleep_problems"] = 99

    resp = client.post("/api/predict", json=bad_payload)

    assert resp.status_code == 400
    body = resp.get_json()
    assert "errors" in body
    assert "sleep_problems" in body["errors"]


def test_predict_api_handles_runtime_model_error(client, monkeypatch):
    from api.routes import predict as predict_route

    def _raise(_payload):
        raise FileNotFoundError("adhd model missing")

    monkeypatch.setattr(predict_route, "predict_all_probabilities", _raise)

    resp = client.post("/api/predict", json=_valid_predict_payload())

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "server_error"
