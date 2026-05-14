import uuid
from pathlib import Path
import sys

import joblib
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app
from api.services import questionnaire_v2_service as qv2
from app.models import ModelVersion
from config.settings import TestingConfig


class StrictConfig(TestingConfig):
    TESTING = False


class _ToyModel:
    def predict_proba(self, X):
        risk = min(0.99, max(0.01, (float(X.iloc[0].get("f1", 0.0)) + float(X.iloc[0].get("f2", 0.0))) / 6.0))
        return [[1.0 - risk, risk]]


def _write_model(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(_ToyModel(), path)
    return str(path)


def test_qv2_service_does_not_reference_runtime_v1_registry():
    source = Path(qv2.__file__).read_text(encoding="utf-8")
    assert "questionnaire_runtime_service" not in source
    assert "DOMAIN_MODEL_REGISTRY" not in source


def test_active_model_artifact_resolves_primary_path(tmp_path):
    app = create_app(StrictConfig)
    model_path = _write_model(tmp_path / "primary" / "pipeline.joblib")
    version = ModelVersion(
        model_registry_id=uuid.uuid4(),
        model_version_tag="test-v17-primary",
        artifact_path=model_path,
        fallback_artifact_path="",
        metadata_json={"feature_columns": ["f1", "f2"]},
    )
    with app.app_context():
        prob = qv2._model_probability(version, {"f1": 3, "f2": 2}, "adhd")
    assert 0.0 <= prob <= 1.0


def test_invalid_active_artifact_does_not_silently_fallback_when_not_testing(tmp_path, monkeypatch):
    app = create_app(StrictConfig)
    fallback_path = _write_model(tmp_path / "fallback" / "pipeline.joblib")
    version = ModelVersion(
        model_registry_id=uuid.uuid4(),
        model_version_tag="test-v17-missing-primary",
        artifact_path=str(tmp_path / "missing" / "pipeline.joblib"),
        fallback_artifact_path=fallback_path,
        metadata_json={"feature_columns": ["f1", "f2"]},
    )
    monkeypatch.delenv("ALLOW_LEGACY_MODEL_FALLBACK_FOR_TESTS", raising=False)
    with app.app_context():
        with pytest.raises(qv2.RuntimeArtifactResolutionError):
            qv2._model_probability(version, {"f1": 3, "f2": 2}, "adhd")


def test_low_feature_coverage_is_blocked_outside_testing(tmp_path, monkeypatch):
    app = create_app(StrictConfig)
    model_path = _write_model(tmp_path / "primary2" / "pipeline.joblib")
    version = ModelVersion(
        model_registry_id=uuid.uuid4(),
        model_version_tag="test-v17-coverage-block",
        artifact_path=model_path,
        fallback_artifact_path="",
        metadata_json={"feature_columns": [f"f{i}" for i in range(1, 11)]},
    )
    monkeypatch.delenv("ALLOW_LEGACY_MODEL_FALLBACK_FOR_TESTS", raising=False)
    with app.app_context():
        with pytest.raises(qv2.RuntimeArtifactResolutionError):
            qv2._model_probability(version, {"f1": 1, "f2": 2}, "adhd")


def test_testing_mode_can_use_explicit_fallback_and_skip_coverage_fail(tmp_path, monkeypatch):
    app = create_app(TestingConfig)
    fallback_path = _write_model(tmp_path / "fallback2" / "pipeline.joblib")
    version = ModelVersion(
        model_registry_id=uuid.uuid4(),
        model_version_tag="test-v17-testing-fallback",
        artifact_path=str(tmp_path / "missing2" / "pipeline.joblib"),
        fallback_artifact_path=fallback_path,
        metadata_json={"feature_columns": [f"f{i}" for i in range(1, 11)]},
    )
    monkeypatch.setenv("ALLOW_LEGACY_MODEL_FALLBACK_FOR_TESTS", "true")
    with app.app_context():
        prob = qv2._model_probability(version, {"f1": 1, "f2": 2}, "adhd")
    assert 0.0 <= prob <= 1.0
    monkeypatch.delenv("ALLOW_LEGACY_MODEL_FALLBACK_FOR_TESTS", raising=False)
