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
