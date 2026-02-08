import os
import sys

import pytest
from marshmallow import ValidationError
from werkzeug.exceptions import BadRequest
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.wrappers import Limit
from limits import parse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config.update(
        PROPAGATE_EXCEPTIONS=False,
        TESTING=True,
    )

    @app.get("/_test/rate-limit")
    def _rate_limit():
        limit = Limit(parse("1/minute"), key_func=lambda: "test", _scope=None)
        raise RateLimitExceeded(limit)

    @app.get("/_test/validation")
    def _validation():
        raise ValidationError({"email": ["Invalid email"]})

    @app.get("/_test/db-unavailable")
    def _db_unavailable():
        raise OperationalError("select 1", {}, Exception("boom"))

    @app.get("/_test/db-error")
    def _db_error():
        raise SQLAlchemyError("boom")

    @app.get("/_test/bad-request")
    def _bad_request():
        raise BadRequest("Bad input")

    @app.get("/_test/runtime")
    def _runtime():
        raise RuntimeError("boom")

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_rate_limit_handler(client):
    resp = client.get("/_test/rate-limit")
    assert resp.status_code == 429
    assert resp.json["error"] == "rate_limited"
    assert resp.json["msg"] == "Too many requests"


def test_validation_handler(client):
    resp = client.get("/_test/validation")
    assert resp.status_code == 400
    assert resp.json["error"] == "validation_error"
    assert resp.json["details"]["email"] == ["Invalid email"]


def test_db_unavailable_handler(client):
    resp = client.get("/_test/db-unavailable")
    assert resp.status_code == 503
    assert resp.json["error"] == "db_unavailable"


def test_db_error_handler(client):
    resp = client.get("/_test/db-error")
    assert resp.status_code == 500
    assert resp.json["error"] == "db_error"


def test_http_error_handler(client):
    resp = client.get("/_test/bad-request")
    assert resp.status_code == 400
    assert resp.json["error"] == "bad_request"
    assert resp.json["msg"] == "Bad input"


def test_unexpected_error_handler(client):
    resp = client.get("/_test/runtime")
    assert resp.status_code == 500
    assert resp.json["error"] == "server_error"


def test_not_found_returns_json(client):
    resp = client.get("/_test/not-found")
    assert resp.status_code == 404
    assert resp.json["error"] == "not_found"
