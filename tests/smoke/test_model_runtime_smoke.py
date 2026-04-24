import importlib
import json
import os
import sys
from pathlib import Path

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services.model_service import predict_all_probabilities
from config.settings import TestingConfig
from core.models.predictor import load_model


def _valid_predict_payload():
    return {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }


def test_smoke_app_import_and_predict_route_exists():
    app = create_app(TestingConfig)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/predict" in rules


def test_smoke_runtime_required_model_binary_exists():
    required_model = Path("models") / "adhd_model.pkl"
    assert required_model.exists()
    assert required_model.stat().st_size > 0


def test_smoke_can_load_runtime_model():
    model = load_model("adhd")
    assert hasattr(model, "predict_proba")


def test_smoke_runtime_prediction_executes():
    result = predict_all_probabilities(_valid_predict_payload())
    assert "adhd" in result
    assert 0.0 <= result["adhd"] <= 1.0


def test_smoke_run_module_exports_app():
    run_module = importlib.import_module("run")
    assert hasattr(run_module, "app")


def test_smoke_inference_v4_scope_file_is_valid_json():
    scope_path = Path("artifacts") / "inference_v4" / "promotion_scope.json"
    data = json.loads(scope_path.read_text(encoding="utf-8"))
    assert "active_domains" in data
    assert "hold_domains" in data
