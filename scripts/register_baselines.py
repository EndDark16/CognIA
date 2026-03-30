from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List

import pandas as pd

from versioning_utils import (
    ensure_versioning_dirs,
    load_registry,
    save_registry,
    to_json_str,
    utcnow_iso,
)


BASELINE_NAMES = {
    "adhd": "rf_adhd_v1_baseline",
    "anxiety": "rf_anxiety_v1_baseline",
    "depression": "rf_depression_v1_baseline",
    "conduct": "rf_conduct_v1_baseline",
    "elimination": "rf_elimination_v1_baseline",
    "multilabel": "rf_multilabel_v1_baseline",
}


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _read_validation_metrics(root: Path, source_model_id: str) -> Dict[str, float]:
    result = root / "reports" / "training" / source_model_id / "result.json"
    if not result.exists():
        return {}
    data = json.loads(result.read_text(encoding="utf-8"))
    vm = data.get("validation_metrics", {})
    return vm if isinstance(vm, dict) else {}


def _baseline_from_row(root: Path, row: pd.Series) -> Dict[str, str]:
    disorder = row["disorder"]
    model_version = BASELINE_NAMES[disorder]
    task_type = row["task"]
    scope = row["version"]
    dataset_name = row["dataset_name"]
    split_version = f"splits_{scope}_frozen_v1"
    preprocessing_version = "rf_preproc_v1"

    source_pipeline = root / row["artifact_pipeline_path"]
    source_metadata = root / row["artifact_metadata_path"]
    source_calibrated = root / str(row.get("artifact_calibrated_path", "")).strip()

    model_dir = root / "models" / "versioned" / model_version
    artifact_dir = root / "artifacts" / "versioned_models" / model_version
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    _copy_if_exists(source_pipeline, model_dir / "pipeline.joblib")
    _copy_if_exists(source_metadata, model_dir / "metadata.json")
    _copy_if_exists(source_calibrated, model_dir / "calibrated.joblib")

    _copy_if_exists(source_pipeline, artifact_dir / "pipeline.joblib")
    _copy_if_exists(source_metadata, artifact_dir / "metadata.json")
    _copy_if_exists(source_calibrated, artifact_dir / "calibrated.joblib")

    val_metrics = _read_validation_metrics(root, row["model_id"])
    test_metrics = {
        "balanced_accuracy": float(row["balanced_accuracy_test"]) if pd.notna(row["balanced_accuracy_test"]) else None,
        "recall": float(row["recall_test"]) if pd.notna(row["recall_test"]) else None,
        "specificity": float(row["specificity_test"]) if pd.notna(row["specificity_test"]) else None,
        "f1": float(row["f1_test"]) if pd.notna(row["f1_test"]) else None,
        "roc_auc": float(row["roc_auc_test"]) if pd.notna(row["roc_auc_test"]) else None,
        "pr_auc": float(row["pr_auc_test"]) if pd.notna(row["pr_auc_test"]) else None,
    }

    target = "target_multilabel_5" if disorder == "multilabel" else f"target_{disorder}"
    calibration = "sigmoid" if str(row.get("artifact_calibrated_path", "")).strip() else "none"
    notes = "Frozen from existing trained baseline artifacts."

    split_dir = root / "data" / "processed" / "splits" / dataset_name / scope
    train_rows = len(pd.read_csv(split_dir / "ids_train.csv")) if (split_dir / "ids_train.csv").exists() else None
    val_rows = len(pd.read_csv(split_dir / "ids_val.csv")) if (split_dir / "ids_val.csv").exists() else None
    test_rows = len(pd.read_csv(split_dir / "ids_test.csv")) if (split_dir / "ids_test.csv").exists() else None

    n_features_raw = None
    n_features_final = None
    if source_metadata.exists():
        m = json.loads(source_metadata.read_text(encoding="utf-8"))
        n_features_raw = len(m.get("feature_columns", [])) if isinstance(m.get("feature_columns"), list) else None
        if isinstance(m.get("encoded_feature_names"), list):
            n_features_final = len(m["encoded_feature_names"])
        elif n_features_raw is not None:
            n_features_final = n_features_raw

    return {
        "experiment_id": f"exp_{model_version}",
        "model_version": model_version,
        "parent_version": "",
        "model_family": "random_forest",
        "disorder": disorder,
        "target": target,
        "task_type": task_type,
        "dataset_name": dataset_name,
        "dataset_variant": row["variant"],
        "dataset_version": scope,
        "data_scope": scope,
        "split_version": split_version,
        "preprocessing_version": preprocessing_version,
        "training_date": utcnow_iso(),
        "seed": 42,
        "feature_strategy": "baseline_frozen",
        "class_balance_strategy": "from_baseline",
        "calibration_strategy": calibration,
        "threshold_strategy": row.get("threshold_method", "fixed_0_5"),
        "threshold_value": row.get("threshold", 0.5),
        "hyperparameters_json": "{}",
        "train_rows": train_rows,
        "val_rows": val_rows,
        "test_rows": test_rows,
        "n_features_raw": n_features_raw,
        "n_features_final": n_features_final,
        "validation_metrics_json": to_json_str(val_metrics),
        "test_metrics_json": to_json_str(test_metrics),
        "status": "promoted",
        "promoted": "yes",
        "promoted_status": "champion",
        "rejection_reason": "",
        "notes": notes,
        "artifact_dir": str(artifact_dir.relative_to(root)),
        "source_model_id": row["model_id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze existing best models as formal baseline v1.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)

    old_registry = pd.read_csv(root / "reports" / "training" / "model_registry.csv")
    best_rows = old_registry[old_registry["is_primary_recommended"] == 1].copy()
    best_rows = best_rows.sort_values(["task", "disorder"])

    rows: List[Dict[str, str]] = []
    for disorder, version_name in BASELINE_NAMES.items():
        if disorder == "multilabel":
            subset = best_rows[best_rows["task"] == "multilabel"]
        else:
            subset = best_rows[(best_rows["task"] == "binary") & (best_rows["disorder"] == disorder)]
        if subset.empty:
            continue
        rows.append(_baseline_from_row(root, subset.iloc[0]))

    baseline_df = pd.DataFrame(rows)
    registry_path = dirs["reports_versioning"] / "model_registry.csv"
    jsonl_path = dirs["reports_versioning"] / "model_registry.jsonl"
    existing = load_registry(registry_path)
    keep = existing[~existing["model_version"].isin(baseline_df["model_version"].tolist())]
    merged = pd.concat([keep, baseline_df], ignore_index=True, sort=False)
    save_registry(merged, registry_path, jsonl_path)

    lineage_rows = []
    for r in baseline_df.itertuples(index=False):
        lineage_rows.append(
            {
                "experiment_id": r.experiment_id,
                "model_version": r.model_version,
                "parent_version": "",
                "disorder": r.disorder,
                "change_type": "baseline_freeze",
                "description": "Formalized existing best model as baseline v1",
                "data_scope": r.data_scope,
                "dataset_name": r.dataset_name,
                "feature_strategy": r.feature_strategy,
                "class_balance_strategy": r.class_balance_strategy,
                "calibration_strategy": r.calibration_strategy,
                "status": "completed",
                "timestamp": utcnow_iso(),
            }
        )
    pd.DataFrame(lineage_rows).to_csv(dirs["reports_versioning"] / "experiment_lineage.csv", index=False)

    champions = baseline_df[["disorder", "task_type", "model_version", "dataset_name", "data_scope"]].copy()
    champions["status"] = "champion"
    champions["promoted_on"] = utcnow_iso()
    champions.to_csv(dirs["reports_versioning"] / "champion_models.csv", index=False)

    decisions = [
        "# Promotion Decisions",
        "",
        "Baseline v1 frozen from prior training artifacts.",
    ]
    for r in baseline_df.itertuples(index=False):
        decisions.append(f"- {r.disorder}: {r.model_version} promoted as initial champion.")
    (dirs["reports_versioning"] / "promotion_decisions.md").write_text("\n".join(decisions) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
