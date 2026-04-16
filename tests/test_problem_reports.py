import io
import os
import sys
from pathlib import Path

import pytest
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import AppUser, db
from config.settings import TestingConfig


class ProblemReportTestingConfig(TestingConfig):
    PROBLEM_REPORT_MAX_ATTACHMENT_BYTES = 1024 * 1024
    PROBLEM_REPORT_ALLOWED_MIME_TYPES = ["image/png", "image/jpeg", "image/webp"]


@pytest.fixture
def app(tmp_path):
    class _Cfg(ProblemReportTestingConfig):
        PROBLEM_REPORT_UPLOAD_DIR = str(tmp_path / "problem_reports_uploads")

    app = create_app(_Cfg)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _user_token(app, username: str, roles: list[str] | None = None, user_type: str = "guardian"):
    with app.app_context():
        user = AppUser(
            username=username,
            email=f"{username}@example.com",
            password="hashed",
            user_type=user_type,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": roles or []})
        return str(user.id), token


def test_create_problem_report_valid(client, app):
    _, token = _user_token(app, "problem_user_1", roles=["GUARDIAN"])
    resp = client.post(
        "/api/problem-reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "issue_type": "questionnaire",
            "description": "No me deja continuar al siguiente bloque del cuestionario.",
            "source_module": "questionnaire",
            "source_path": "/questionnaire/session/abc/page/2",
        },
    )
    assert resp.status_code == 201
    report = resp.json["report"]
    assert report["status"] == "open"
    assert report["issue_type"] == "questionnaire"
    assert report["attachment_count"] == 0
    assert report["report_code"].startswith("PRB-")


def test_create_problem_report_invalid_fields(client, app):
    _, token = _user_token(app, "problem_user_2")
    resp = client.post(
        "/api/problem-reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"issue_type": "invalid_type", "description": "corto"},
    )
    assert resp.status_code == 400
    assert resp.json["error"] == "validation_error"


def test_create_problem_report_with_attachment(client, app):
    _, token = _user_token(app, "problem_user_3")
    resp = client.post(
        "/api/problem-reports",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "issue_type": "ui_issue",
            "description": "La captura muestra que se corta el contenido del reporte.",
            "source_module": "help_center",
            "attachment": (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "evidence.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    report = resp.json["report"]
    assert report["attachment_count"] == 1
    assert len(report["attachments"]) == 1
    assert report["attachments"][0]["original_filename"] == "evidence.png"

    upload_root = Path(app.config["PROBLEM_REPORT_UPLOAD_DIR"])
    saved = list(upload_root.glob("*.png"))
    assert saved


def test_create_problem_report_requires_auth(client):
    resp = client.post(
        "/api/problem-reports",
        json={
            "issue_type": "bug",
            "description": "No autorizado debe fallar.",
        },
    )
    assert resp.status_code == 401


def test_admin_list_problem_reports_with_pagination(client, app):
    _, user_token = _user_token(app, "problem_user_4")
    _, admin_token = _user_token(app, "problem_admin_1", roles=["ADMIN"], user_type="psychologist")

    for idx in range(3):
        resp = client.post(
            "/api/problem-reports",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "issue_type": "bug",
                "description": f"Reporte de prueba {idx} para paginacion en listado admin.",
            },
        )
        assert resp.status_code == 201

    listed = client.get(
        "/api/admin/problem-reports?page=1&page_size=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed.status_code == 200
    assert len(listed.json["items"]) == 2
    assert listed.json["pagination"]["total"] >= 3


def test_non_admin_cannot_list_problem_reports(client, app):
    _, token = _user_token(app, "problem_user_5", roles=["GUARDIAN"])
    resp = client.get(
        "/api/admin/problem-reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_filters_and_update_problem_report(client, app):
    _, user_token = _user_token(app, "problem_user_6", roles=["GUARDIAN"])
    _, admin_token = _user_token(app, "problem_admin_2", roles=["ADMIN"])

    created = client.post(
        "/api/problem-reports",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "issue_type": "data_issue",
            "description": "Los resultados muestran valores fuera de rango en vista historial.",
        },
    )
    assert created.status_code == 201
    report_id = created.json["report"]["id"]

    filtered = client.get(
        "/api/admin/problem-reports?issue_type=data_issue&status=open",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert filtered.status_code == 200
    assert any(item["id"] == report_id for item in filtered.json["items"])

    updated = client.patch(
        f"/api/admin/problem-reports/{report_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "resolved", "admin_notes": "Incidente confirmado y resuelto por ajuste de cache."},
    )
    assert updated.status_code == 200
    assert updated.json["report"]["status"] == "resolved"
    assert updated.json["report"]["admin_notes"] == "Incidente confirmado y resuelto por ajuste de cache."
    assert updated.json["report"]["resolved_at"] is not None


def test_non_admin_cannot_update_problem_report(client, app):
    _, user_token = _user_token(app, "problem_user_7", roles=["GUARDIAN"])
    created = client.post(
        "/api/problem-reports",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "issue_type": "other",
            "description": "Texto suficientemente largo para crear un reporte y probar permisos.",
        },
    )
    assert created.status_code == 201
    report_id = created.json["report"]["id"]

    updated = client.patch(
        f"/api/admin/problem-reports/{report_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"status": "triaged"},
    )
    assert updated.status_code == 403
