from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

from versioning_utils import ensure_versioning_dirs, load_registry, metric_value


PRIMARY_DISORDERS = ["depression", "conduct", "elimination"]


def _is_precision_model(model_version: str) -> bool:
    return "_precision_" in str(model_version)


def _augment(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["val_precision"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "precision"))
    out["val_recall"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    out["val_specificity"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    out["val_balanced_accuracy"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    out["val_f1"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    out["test_precision"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "precision"))
    out["test_recall"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    out["test_specificity"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    out["test_balanced_accuracy"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    out["test_f1"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Export precision campaign reports.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry = load_registry(dirs["reports_versioning"] / "model_registry.csv")

    precision = registry[
        registry["model_version"].apply(_is_precision_model)
        & (registry["task_type"] == "binary")
    ].copy()
    precision = _augment(precision)

    cols: List[str] = [
        "model_version",
        "parent_version",
        "disorder",
        "dataset_name",
        "dataset_variant",
        "data_scope",
        "feature_strategy",
        "class_balance_strategy",
        "calibration_strategy",
        "threshold_strategy",
        "threshold_value",
        "recall_floor",
        "balanced_accuracy_tolerance",
        "train_rows",
        "val_rows",
        "test_rows",
        "n_features_raw",
        "n_features_final",
        "val_precision",
        "val_recall",
        "val_specificity",
        "val_balanced_accuracy",
        "val_f1",
        "test_precision",
        "test_recall",
        "test_specificity",
        "test_balanced_accuracy",
        "test_f1",
        "status",
        "promoted",
        "promoted_status",
        "rejection_reason",
        "notes",
    ]

    summary = precision[cols].sort_values(
        ["disorder", "val_precision", "val_balanced_accuracy", "val_recall"],
        ascending=[True, False, False, False],
    )
    summary.to_csv(dirs["reports_experiments"] / "precision_experiment_results_summary.csv", index=False)
    for disorder in PRIMARY_DISORDERS:
        summary[summary["disorder"] == disorder].to_csv(
            dirs["reports_experiments"] / f"{disorder}_precision_experiments.csv",
            index=False,
        )


if __name__ == "__main__":
    main()
