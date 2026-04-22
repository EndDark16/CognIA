import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.models.predictor import load_model, predict_proba


class _DummyModel:
    def __init__(self):
        self.last_input = None

    def predict_proba(self, features):
        self.last_input = features
        return np.array([[0.2, 0.8]])


def test_load_model_resolves_runtime_binary():
    model = load_model("adhd")
    assert model is not None
    assert hasattr(model, "predict_proba")


def test_load_model_missing_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_model("domain_that_does_not_exist")


def test_predict_proba_accepts_dict_input():
    model = _DummyModel()
    payload = {"a": 1, "b": 2}

    result = predict_proba(model, payload)

    assert result == 0.8
    assert isinstance(model.last_input, pd.DataFrame)
    assert model.last_input.shape[0] == 1


def test_predict_proba_accepts_list_input():
    model = _DummyModel()

    result = predict_proba(model, [1, 2, 3])

    assert result == 0.8
    assert isinstance(model.last_input, np.ndarray)
    assert model.last_input.shape == (1, 3)


def test_predictor_expected_runtime_path_exists():
    expected = Path("models") / "adhd_model.pkl"
    assert expected.exists(), "Falta binario minimo requerido por runtime: models/adhd_model.pkl"
