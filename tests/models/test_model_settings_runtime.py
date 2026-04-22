import os
import sys

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.settings import Config


def test_settings_evaluation_age_defaults_are_runtime_safe():
    assert Config.EVALUATION_MIN_AGE == 6
    assert Config.EVALUATION_MAX_AGE == 11
    assert Config.EVALUATION_MIN_AGE <= Config.EVALUATION_MAX_AGE


def test_settings_allowed_statuses_include_runtime_flow():
    statuses = set(Config.EVALUATION_ALLOWED_STATUSES)
    assert {"draft", "submitted", "completed"}.issubset(statuses)


@pytest.mark.parametrize("expected_key", ["MODEL_PATH", "SECRET_KEY", "JWT_SECRET_KEY"])
def test_settings_has_required_runtime_keys(expected_key):
    assert hasattr(Config, expected_key)
