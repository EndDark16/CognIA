import os
import sys

import pytest
from flask_jwt_extended import create_access_token

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import AppUser, db
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        user = AppUser(
            username=f"predict_api_{os.urandom(4).hex()}",
            email=f"predict_api_{os.urandom(4).hex()}@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": []})
    return {"Authorization": f"Bearer {token}"}


def _valid_predict_payload():
    return {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }


def test_predict_api_valid_payload_returns_expected_shape(client, auth_headers):
    resp = client.post("/api/predict", json=_valid_predict_payload(), headers=auth_headers)

    assert resp.status_code == 200
    body = resp.get_json()
    assert "predictions" in body
    assert "adhd" in body["predictions"]
    assert "elimination" not in body["predictions"]


def test_predict_api_missing_required_input_returns_400(client, auth_headers):
    bad_payload = _valid_predict_payload()
    bad_payload.pop("age")

    resp = client.post("/api/predict", json=bad_payload, headers=auth_headers)

    assert resp.status_code == 400
    body = resp.get_json()
    assert "errors" in body
    assert "age" in body["errors"]


def test_predict_api_invalid_input_value_returns_400(client, auth_headers):
    bad_payload = _valid_predict_payload()
    bad_payload["sleep_problems"] = 99

    resp = client.post("/api/predict", json=bad_payload, headers=auth_headers)

    assert resp.status_code == 400
    body = resp.get_json()
    assert "errors" in body
    assert "sleep_problems" in body["errors"]


def test_predict_api_handles_runtime_model_error(client, auth_headers, monkeypatch):
    from api.routes import predict as predict_route

    def _raise(_payload):
        raise FileNotFoundError("adhd model missing")

    monkeypatch.setattr(predict_route, "predict_all_probabilities", _raise)

    resp = client.post("/api/predict", json=_valid_predict_payload(), headers=auth_headers)

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "server_error"


def test_predict_api_requires_jwt(client):
    resp = client.post("/api/predict", json=_valid_predict_payload())
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"
