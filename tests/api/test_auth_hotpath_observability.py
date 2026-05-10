import os
import sys
import uuid

from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import AppUser, RefreshToken, Role, UserRole, db
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


def test_auth_me_cache_invalidation_after_admin_user_patch():
    app = _build_app()
    client = app.test_client()
    try:
        with app.app_context():
            target = AppUser(
                username=f"target_{uuid.uuid4().hex[:8]}",
                email=f"target_{uuid.uuid4().hex[:8]}@example.com",
                password="hashed",
                user_type="guardian",
                full_name="Before Cache",
                is_active=True,
            )
            admin = AppUser(
                username=f"admin_{uuid.uuid4().hex[:8]}",
                email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
                password="hashed",
                user_type="guardian",
                is_active=True,
            )
            db.session.add_all([target, admin])
            db.session.flush()
            role = Role(name="ADMIN", description="admin test role")
            db.session.add(role)
            db.session.flush()
            db.session.add(UserRole(user_id=admin.id, role_id=role.id))
            db.session.commit()

            target_token = create_access_token(identity=str(target.id), additional_claims={"roles": []})
            admin_token = create_access_token(identity=str(admin.id), additional_claims={"roles": ["ADMIN"]})

        me_before = client.get("/api/auth/me", headers={"Authorization": f"Bearer {target_token}"})
        assert me_before.status_code == 200
        assert me_before.get_json()["full_name"] == "Before Cache"

        patch_resp = client.patch(
            f"/api/v1/users/{me_before.get_json()['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"full_name": "After Cache"},
        )
        assert patch_resp.status_code == 200

        me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {target_token}"})
        assert me_after.status_code == 200
        assert me_after.get_json()["full_name"] == "After Cache"
    finally:
        _teardown(app)
