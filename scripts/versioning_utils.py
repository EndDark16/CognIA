from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

REGISTRY_COLUMNS = [
    "experiment_id",
    "model_version",
    "parent_version",
    "model_family",
    "disorder",
    "target",
    "task_type",
    "dataset_name",
    "dataset_variant",
    "dataset_version",
    "data_scope",
    "split_version",
    "preprocessing_version",
    "training_date",
    "seed",
    "feature_strategy",
    "class_balance_strategy",
    "calibration_strategy",
    "threshold_strategy",
    "threshold_value",
    "recall_floor",
    "balanced_accuracy_tolerance",
    "hyperparameters_json",
    "train_rows",
    "val_rows",
    "test_rows",
    "n_features_raw",
    "n_features_final",
    "validation_metrics_json",
    "test_metrics_json",
    "status",
    "promoted",
    "promoted_status",
    "rejection_reason",
    "notes",
    "artifact_dir",
    "source_model_id",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_versioning_dirs(root: Path) -> Dict[str, Path]:
    paths = {
        "reports_versioning": root / "reports" / "versioning",
        "reports_experiments": root / "reports" / "experiments",
        "reports_promotions": root / "reports" / "promotions",
        "models_versioned": root / "models" / "versioned",
        "models_champions": root / "models" / "champions",
        "artifacts_versioned_models": root / "artifacts" / "versioned_models",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in REGISTRY_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    return out[REGISTRY_COLUMNS]


def load_registry(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame(columns=REGISTRY_COLUMNS)
    df = pd.read_csv(csv_path)
    return _ensure_columns(df)


def save_registry(df: pd.DataFrame, csv_path: Path, jsonl_path: Path) -> None:
    out = _ensure_columns(df).copy()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(csv_path, index=False)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for _, row in out.iterrows():
            rec = row.to_dict()
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def to_json_str(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def from_json_str(data: str | float | int | None) -> Dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, float) and pd.isna(data):
        return {}
    if isinstance(data, dict):
        return data
    if not isinstance(data, str):
        return {}
    data = data.strip()
    if not data:
        return {}
    try:
        parsed = json.loads(data)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def metric_value(metrics_json: str, key: str, default: float = float("nan")) -> float:
    d = from_json_str(metrics_json)
    val = d.get(key, default)
    try:
        return float(val)
    except Exception:
        return default
