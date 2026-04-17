import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


class StrictBlueprintConfig(TestingConfig):
    OPTIONAL_BLUEPRINTS_STRICT = True
    OPTIONAL_BLUEPRINTS_REQUIRED = ["questionnaire_runtime"]


class NonStrictBlueprintConfig(TestingConfig):
    OPTIONAL_BLUEPRINTS_STRICT = False
    OPTIONAL_BLUEPRINTS_REQUIRED = ["questionnaire_runtime"]


def test_required_optional_blueprint_fails_fast(monkeypatch):
    import api.app as app_module

    original_import = app_module.importlib.import_module

    def _patched_import(name, package=None):
        if name == "api.routes.questionnaire_runtime":
            raise ModuleNotFoundError("simulated missing runtime blueprint")
        return original_import(name, package)

    monkeypatch.setattr(app_module.importlib, "import_module", _patched_import)

    with pytest.raises(RuntimeError):
        create_app(StrictBlueprintConfig)


def test_optional_blueprint_can_be_skipped_when_non_strict(monkeypatch):
    import api.app as app_module

    original_import = app_module.importlib.import_module

    def _patched_import(name, package=None):
        if name == "api.routes.questionnaire_runtime":
            raise ModuleNotFoundError("simulated missing runtime blueprint")
        return original_import(name, package)

    monkeypatch.setattr(app_module.importlib, "import_module", _patched_import)

    app = create_app(NonStrictBlueprintConfig)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/questionnaire-runtime/questionnaire/active" not in rules
