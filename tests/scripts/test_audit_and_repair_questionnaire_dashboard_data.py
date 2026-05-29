import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.audit_and_repair_questionnaire_dashboard_data import (
    _hash_case_label,
    _normalize_case_label,
    _spread_offset_days,
)
from scripts.ensure_synthetic_dashboard_qa_data import ensure_dashboard_data
from api.app import create_app
from app.models import AppUser, QuestionnaireCase, QuestionnaireSession, db
from config.settings import TestingConfig


def test_normalize_case_label_equivalences():
    a = _normalize_case_label(" Híjo-1 ")
    b = _normalize_case_label("hijo 1")
    c = _normalize_case_label("HIJO__1")
    assert a == b == c


def test_hash_case_label_is_stable_for_equivalent_labels():
    secret = "test-secret"
    first = _hash_case_label("Seguimiento escolar", secret)
    second = _hash_case_label("  seguimiento   ESCOLAR ", secret)
    assert first == second
    assert first


def test_spread_offset_days_deterministic_and_bounded():
    value = _spread_offset_days("seed-123", 90)
    assert value == _spread_offset_days("seed-123", 90)
    assert 0 <= value < 90


def test_ensure_synthetic_dashboard_qa_data_apply_idempotent(tmp_path):
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        first = ensure_dashboard_data(apply=True, rotate_credentials=False, credentials_dir=tmp_path)
        credentials = ensure_dashboard_data(apply=True, rotate_credentials=True, credentials_dir=tmp_path, phase="credentials")
        second = ensure_dashboard_data(apply=True, rotate_credentials=False, credentials_dir=tmp_path)

        assert first["users_created"] >= 9
        assert second["users_created"] == 0
        assert AppUser.query.filter_by(username="synthetic_guardian_dashboard_01").first() is not None
        assert AppUser.query.filter_by(username="syn_psych_dashboard_01").first().colpsic_verified is True
        assert QuestionnaireCase.query.count() >= 15
        assert QuestionnaireSession.query.filter_by(status="processed").count() >= 12
        assert credentials["credentials_written"] >= 9
        assert list(tmp_path.glob("dashboard_qa_credentials_*.txt"))

        db.session.remove()
        db.drop_all()
