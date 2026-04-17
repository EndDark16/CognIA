import os
import sys

from config.settings import TestingConfig

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.routes import predict as predict_route


VALID_PAYLOAD = {
    "age": 10,
    "sex": 1,
    "conners_inattention_score": 12.5,
    "conners_hyperactivity": 8.1,
    "cbcl_attention_score": 14.0,
    "sleep_problems": 0,
}


def _client(config_class=TestingConfig):
    app = create_app(config_class)
    return app.test_client()


def test_predict_requires_json_body():
    client = _client()
    resp = client.post("/api/predict", data="not-json", content_type="text/plain")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "validation_error"
    assert "details" in body


def test_predict_validation_error_for_missing_fields():
    client = _client()
    payload = dict(VALID_PAYLOAD)
    payload.pop("age")
    resp = client.post("/api/predict", json=payload)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "validation_error"
    assert "age" in body["details"]


def test_predict_internal_error_is_sanitized(monkeypatch):
    client = _client()

    def _boom(_payload):
        raise RuntimeError("sensitive stack trace detail")

    monkeypatch.setattr(predict_route, "predict_all_probabilities", _boom)
    resp = client.post("/api/predict", json=VALID_PAYLOAD)
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "server_error"
    assert "details" not in body
    assert "sensitive" not in str(body)


class PredictRateLimitConfig(TestingConfig):
    RATELIMIT_ENABLED = True
    PREDICT_RATE_LIMIT = "1 per minute"


def test_predict_rate_limit_applies(monkeypatch):
    client = _client(PredictRateLimitConfig)

    monkeypatch.setattr(
        predict_route,
        "predict_all_probabilities",
        lambda _payload: {"adhd": 0.2, "anxiety": 0.1},
    )

    first = client.post("/api/predict", json=VALID_PAYLOAD)
    second = client.post("/api/predict", json=VALID_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.get_json()["error"] == "rate_limited"

