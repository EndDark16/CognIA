import os
import sys

import pandas as pd
import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services import model_service


def _valid_predict_payload():
    return {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }


def test_predict_all_probabilities_returns_runtime_domain_only():
    result = model_service.predict_all_probabilities(_valid_predict_payload())

    assert isinstance(result, dict)
    assert "adhd" in result
    assert "elimination" not in result
    assert 0.0 <= result["adhd"] <= 1.0


def test_predict_all_probabilities_uses_expected_feature_order(monkeypatch):
    captured = {}

    class _FakeModel:
        pass

    def _fake_load_model(model_name: str):
        captured["model_name"] = model_name
        return _FakeModel()

    def _fake_predict_proba(model, features):
        assert isinstance(features, pd.DataFrame)
        captured["columns"] = features.columns.tolist()
        return 0.42

    monkeypatch.setattr(model_service, "load_model", _fake_load_model)
    monkeypatch.setattr(model_service, "predict_proba", _fake_predict_proba)

    result = model_service.predict_all_probabilities(_valid_predict_payload())

    assert captured["model_name"] == "adhd"
    assert captured["columns"] == [
        "age",
        "sex",
        "conners_inattention_score",
        "conners_hyperactivity",
        "cbcl_attention_score",
        "sleep_problems",
    ]
    assert result == {"adhd": 0.42}


def test_predict_all_probabilities_missing_model_surfaces_error(monkeypatch):
    def _fake_load_model(_model_name: str):
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(model_service, "load_model", _fake_load_model)

    with pytest.raises(FileNotFoundError):
        model_service.predict_all_probabilities(_valid_predict_payload())
