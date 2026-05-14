from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from app.models import (
    ModelArtifactRegistry,
    ModelModeDomainActivation,
    ModelRegistry,
    ModelVersion,
    db,
)

OUT_BASE = ROOT / "data" / "hybrid_runtime_artifact_validation_v17"
TABLES_DIR = OUT_BASE / "tables"
VALIDATION_DIR = OUT_BASE / "validation"
REPORTS_DIR = OUT_BASE / "reports"

ACTIVE_CSV = ROOT / "data" / "hybrid_active_modes_freeze_v17" / "tables" / "hybrid_active_models_30_modes.csv"


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _norm_role(role: str) -> str:
    raw = str(role or "").strip().lower()
    if raw == "caregiver":
        return "guardian"
    return raw


def _model_key(domain: str, mode: str, role: str) -> tuple[str, str, str]:
    return str(domain).strip().lower(), str(mode).strip().lower(), _norm_role(role)


def _default_feature_value(feature: str) -> Any:
    key = str(feature or "").strip().lower()
    if key in {"sex_assigned_at_birth", "sex"}:
        return "unknown"
    if key in {"site"}:
        return "CBIC"
    if key in {"age_years", "age"}:
        return 9.0
    return 0.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _to_abs(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    p = Path(path_value)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def _read_feature_columns(model_version: ModelVersion) -> list[str]:
    metadata = model_version.metadata_json or {}
    raw = metadata.get("feature_columns") or []
    return [str(item).strip() for item in raw if str(item).strip()]


@dataclass
class ArtifactCheck:
    resolved_path: str | None
    path_source: str
    artifact_exists: str
    fallback_exists: str


def _resolve_artifact(model_version: ModelVersion) -> ArtifactCheck:
    artifact_path = _to_abs(model_version.artifact_path)
    fallback_path = _to_abs(model_version.fallback_artifact_path)

    artifact_exists = "yes" if artifact_path and artifact_path.exists() else "no"
    fallback_exists = "yes" if fallback_path and fallback_path.exists() else "no"

    if artifact_exists == "yes":
        return ArtifactCheck(str(artifact_path), "artifact_path", artifact_exists, fallback_exists)
    return ArtifactCheck(None, "artifact_path_missing", artifact_exists, fallback_exists)


def main() -> int:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not ACTIVE_CSV.exists():
        raise FileNotFoundError(f"missing_active_csv:{ACTIVE_CSV}")

    active_df = pd.read_csv(ACTIVE_CSV)
    active_map: dict[tuple[str, str, str], list[str]] = {}
    for row in active_df.to_dict(orient="records"):
        feature_columns = [
            item.strip()
            for item in str(row.get("feature_list_pipe") or "").split("|")
            if item and item.strip() and item.strip().lower() != "nan"
        ]
        key = _model_key(row.get("domain"), row.get("mode"), row.get("role"))
        active_map[key] = feature_columns

    app = create_app(_config_class_from_env())
    inventory_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    smoke_rows: list[dict[str, Any]] = []

    with app.app_context():
        activations = (
            ModelModeDomainActivation.query.filter_by(active_flag=True)
            .order_by(ModelModeDomainActivation.domain.asc(), ModelModeDomainActivation.mode_key.asc())
            .all()
        )

        for activation in activations:
            registry = db.session.get(ModelRegistry, activation.model_registry_id)
            version = db.session.get(ModelVersion, activation.model_version_id)
            if not registry or not version:
                continue

            slot_key = _model_key(activation.domain, activation.mode_key, activation.role)
            expected_features = active_map.get(slot_key, [])
            feature_columns = _read_feature_columns(version)
            feature_match = "yes" if feature_columns == expected_features and len(feature_columns) > 0 else "no"

            artifact = _resolve_artifact(version)
            registry_row = (
                ModelArtifactRegistry.query.filter_by(model_version_id=version.id, artifact_kind="runtime_model")
                .order_by(ModelArtifactRegistry.created_at.desc())
                .first()
            )

            artifact_hash = None
            model_family_detected = None
            joblib_load_ok = "no"
            predict_ok = "no"
            prob = None
            predict_error = None
            fallback_verified_for_slot = "na"

            if artifact.resolved_path:
                artifact_path = Path(artifact.resolved_path)
                try:
                    artifact_hash = _sha256(artifact_path)
                    model = joblib.load(artifact_path)
                    joblib_load_ok = "yes"
                    model_family_detected = model.__class__.__name__
                    if hasattr(model, "predict_proba") and feature_columns:
                        x = pd.DataFrame([
                            {feature: _default_feature_value(feature) for feature in feature_columns}
                        ], columns=feature_columns)
                        proba = model.predict_proba(x)
                        if proba is not None:
                            prob = float(proba[0][1])
                            predict_ok = "yes"
                    else:
                        predict_error = "predict_proba_missing_or_feature_columns_empty"
                except Exception as exc:
                    predict_error = f"{type(exc).__name__}:{exc}"

            if version.fallback_artifact_path:
                fallback_verified_for_slot = "configured"

            row = {
                "activation_id": str(activation.id),
                "domain": activation.domain,
                "mode": activation.mode_key,
                "role": activation.role,
                "model_key": registry.model_key,
                "model_version_id": str(version.id),
                "model_version_tag": version.model_version_tag,
                "artifact_path_db": version.artifact_path,
                "fallback_artifact_path_db": version.fallback_artifact_path,
                "artifact_registry_locator": registry_row.artifact_locator if registry_row else None,
                "path_source": artifact.path_source,
                "resolved_artifact_path": artifact.resolved_path,
                "runtime_artifact_available": artifact.artifact_exists,
                "fallback_artifact_available": artifact.fallback_exists,
                "joblib_load_ok": joblib_load_ok,
                "predict_proba_smoke_ok": predict_ok,
                "feature_columns_count": len(feature_columns),
                "feature_columns_expected_count": len(expected_features),
                "feature_columns_match": feature_match,
                "por_confirmar_active_model": "yes"
                if bool((version.metadata_json or {}).get("por_confirmar"))
                else "no",
                "fallback_domain_used": "no",
                "fallback_verified_for_slot": fallback_verified_for_slot,
                "model_family_detected": model_family_detected,
                "artifact_hash": artifact_hash,
                "predict_proba_smoke_probability": prob,
                "predict_proba_error": predict_error,
            }
            inventory_rows.append(row)

            smoke_rows.append(
                {
                    "model_key": registry.model_key,
                    "resolved_artifact_path": artifact.resolved_path,
                    "predict_proba_smoke_ok": predict_ok,
                    "probability": prob,
                    "error": predict_error,
                }
            )

            if artifact_hash:
                hash_rows.append(
                    {
                        "model_key": registry.model_key,
                        "domain": activation.domain,
                        "mode": activation.mode_key,
                        "role": activation.role,
                        "resolved_artifact_path": artifact.resolved_path,
                        "artifact_hash": artifact_hash,
                    }
                )

    inventory_df = pd.DataFrame(inventory_rows)
    hash_df = pd.DataFrame(hash_rows)
    smoke_df = pd.DataFrame(smoke_rows)

    inventory_df.to_csv(TABLES_DIR / "runtime_artifact_inventory_v17.csv", index=False, lineterminator="\n")
    hash_df.to_csv(TABLES_DIR / "runtime_artifact_hashes_v17.csv", index=False, lineterminator="\n")
    smoke_df.to_csv(TABLES_DIR / "runtime_artifact_smoke_predictions_v17.csv", index=False, lineterminator="\n")

    duplicate_hash_count = 0
    if not hash_df.empty:
        duplicate_hash_count = int(hash_df.duplicated(subset=["artifact_hash"], keep=False).sum())

    runtime_artifact_available = int((inventory_df["runtime_artifact_available"] == "yes").sum()) if not inventory_df.empty else 0
    joblib_load_ok = int((inventory_df["joblib_load_ok"] == "yes").sum()) if not inventory_df.empty else 0
    predict_ok = int((inventory_df["predict_proba_smoke_ok"] == "yes").sum()) if not inventory_df.empty else 0
    feature_match = int((inventory_df["feature_columns_match"] == "yes").sum()) if not inventory_df.empty else 0
    por_confirmar = int((inventory_df["por_confirmar_active_model"] == "yes").sum()) if not inventory_df.empty else 0
    legacy_fallback_configured = int(
        (inventory_df["fallback_verified_for_slot"] == "configured").sum()
    ) if not inventory_df.empty else 0

    total_slots = int(inventory_df.shape[0])
    final_status = "pass"
    if not (
        runtime_artifact_available == total_slots
        and joblib_load_ok == total_slots
        and predict_ok == total_slots
        and feature_match == total_slots
        and por_confirmar == 0
        and legacy_fallback_configured == 0
    ):
        final_status = "fail"

    validator_row = {
        "total_active_slots": total_slots,
        "runtime_artifact_available_slots": runtime_artifact_available,
        "joblib_load_ok_slots": joblib_load_ok,
        "predict_proba_smoke_ok_slots": predict_ok,
        "heuristic_fallback_used": 0,
        "legacy_fallback_configured_slots": legacy_fallback_configured,
        "feature_columns_match_slots": feature_match,
        "por_confirmar_active_models": por_confirmar,
        "artifact_duplicate_hash_count": duplicate_hash_count,
        "runtime_artifact_validation_status": final_status,
    }

    pd.DataFrame([validator_row]).to_csv(
        VALIDATION_DIR / "runtime_artifact_validator_v17.csv",
        index=False,
        lineterminator="\n",
    )
    (VALIDATION_DIR / "runtime_artifact_validator_v17.json").write_text(
        json.dumps(validator_row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# Runtime Artifact Validation v17",
        "",
        f"- total_active_slots: {total_slots}",
        f"- runtime_artifact_available: {runtime_artifact_available}/{total_slots}",
        f"- joblib_load_ok: {joblib_load_ok}/{total_slots}",
        f"- predict_proba_smoke_ok: {predict_ok}/{total_slots}",
        f"- feature_columns_match: {feature_match}/{total_slots}",
        f"- por_confirmar_active_models: {por_confirmar}",
        f"- legacy_fallback_configured_slots: {legacy_fallback_configured}",
        f"- artifact_duplicate_hash_count: {duplicate_hash_count}",
        f"- runtime_artifact_validation_status: {final_status}",
        "",
        "## Notes",
        "- Validation is based on active DB rows (`model_mode_domain_activation.active_flag=true`).",
        "- `predict_proba` smoke uses a single dummy row aligned to each model feature contract.",
        "- No heuristic fallback was used inside this validator.",
    ]
    (REPORTS_DIR / "runtime_artifact_validation_report_v17.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(json.dumps(validator_row, ensure_ascii=False))
    return 0 if final_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
