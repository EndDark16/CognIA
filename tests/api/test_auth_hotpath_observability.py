import os
import sys
import uuid

from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import AppUser, RefreshToken, db
from config.settings import TestingConfig


def _build_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
    return app


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_access_token_request_does_not_query_refresh_tokens(monkeypatch):
    app = _build_app()
    client = app.test_client()
    try:
        with app.app_context():
            user = AppUser(
                username=f"hotpath_{uuid.uuid4().hex[:8]}",
                email=f"hotpath_{uuid.uuid4().hex[:8]}@example.com",
                password="hashed",
                user_type="guardian",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            access_token = create_access_token(identity=str(user.id), additional_claims={"roles": []})

        real_query = db.session.query

        def guarded_query(model, *args, **kwargs):
            if model is RefreshToken:
                raise AssertionError("Access token path should not query refresh_token table")
            return real_query(model, *args, **kwargs)

        monkeypatch.setattr(db.session, "query", guarded_query)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200
        assert resp.get_json()["id"]
    finally:
        _teardown(app)


def test_request_id_header_generated_and_propagated():
    app = _build_app()
    client = app.test_client()
    try:
        generated = client.get("/healthz")
        assert generated.status_code == 200
        assert generated.get_json() == {"status": "ok"}
        assert generated.headers.get("X-Request-ID")

        incoming_id = "req-observability-1234"
        propagated = client.get("/healthz", headers={"X-Request-ID": incoming_id})
        assert propagated.status_code == 200
        assert propagated.get_json() == {"status": "ok"}
        assert propagated.headers.get("X-Request-ID") == incoming_id
    finally:
        _teardown(app)
