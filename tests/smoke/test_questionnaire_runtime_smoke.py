import os
import sys
import uuid

import pytest
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.security import hash_password
from app.models import AppUser, db
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        user = AppUser(
            username=f"smoke_{uuid.uuid4().hex[:6]}",
            email=f"smoke_{uuid.uuid4().hex[:6]}@example.com",
            password=hash_password("StrongPass123!"),
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": []})
        yield app, token
        db.session.remove()
        db.drop_all()


def test_questionnaire_runtime_smoke_active_endpoint(app):
    application, token = app
    client = application.test_client()
    res = client.get(
        "/api/v1/questionnaire-runtime/questionnaire/active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "sections" in res.json
    assert "disclosures" in res.json
