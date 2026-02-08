import os
import sys

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services.unsubscribe_service import generate_unsubscribe_token
from app.models import db, EmailUnsubscribe
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_unsubscribe_valid_token_creates_record(client, app):
    email = "User@Example.com"
    with app.app_context():
        token = generate_unsubscribe_token(email)

    resp = client.get(f"/api/email/unsubscribe?token={token}")
    assert resp.status_code == 200

    with app.app_context():
        entry = EmailUnsubscribe.query.filter_by(email="user@example.com").first()
        assert entry is not None


def test_unsubscribe_invalid_token_returns_400(client):
    resp = client.get("/api/email/unsubscribe?token=invalid-token")
    assert resp.status_code == 400


def test_unsubscribe_idempotent(client, app):
    email = "repeat@example.com"
    with app.app_context():
        token = generate_unsubscribe_token(email)

    resp1 = client.get(f"/api/email/unsubscribe?token={token}")
    resp2 = client.get(f"/api/email/unsubscribe?token={token}")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email=email).count() == 1


def test_unsubscribe_post_json(client, app):
    email = "json@example.com"
    with app.app_context():
        token = generate_unsubscribe_token(email)

    resp = client.post("/api/email/unsubscribe", json={"token": token, "reason": "testing"})
    assert resp.status_code == 200

    with app.app_context():
        entry = EmailUnsubscribe.query.filter_by(email=email).first()
        assert entry is not None
        assert entry.reason == "testing"
