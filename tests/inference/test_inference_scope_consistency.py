import json
import os
import sys
from pathlib import Path

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services import model_service


def _load_scope():
    scope_path = Path("artifacts") / "inference_v4" / "promotion_scope.json"
    return json.loads(scope_path.read_text(encoding="utf-8"))


def test_inference_v4_scope_matches_final_expected_domains():
    scope = _load_scope()

    assert set(scope["active_domains"]) == {"adhd", "anxiety", "conduct", "depression"}
    assert set(scope["hold_domains"]) == {"elimination"}


def test_inference_v4_active_and_hold_do_not_overlap():
    scope = _load_scope()
    active = set(scope["active_domains"])
    hold = set(scope["hold_domains"])

    assert active.isdisjoint(hold)


def test_runtime_predictions_respect_hold_domain():
    payload = {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }
    scope = _load_scope()
    result = model_service.predict_all_probabilities(payload)

    runtime_domains = set(result.keys())
    assert runtime_domains.issubset(set(scope["active_domains"]))
    assert "elimination" not in runtime_domains


@pytest.mark.parametrize(
    "required_path",
    [
        "artifacts/inference_v4/promotion_scope.json",
        "reports/final_closure/final_project_closure_report.md",
        "reports/final_closure/inference_scope_final.md",
        "data/final_closure_audit_v1/tables/final_global_closure_matrix.csv",
    ],
)
def test_required_scope_artifacts_exist(required_path):
    assert Path(required_path).exists(), f"Falta artefacto operativo critico: {required_path}"
