from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

from versioning_utils import ensure_versioning_dirs, load_registry, metric_value


TARGET_DISORDERS = ["depression", "conduct", "elimination"]


def _is_campaign_model(model_version: str) -> bool:
    mv = str(model_version)
    return mv.startswith("rf_") and ("_v2_" in mv or "_v3_" in mv or "_v4_" in mv)


def _augment_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["val_balanced_accuracy"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    out["val_recall"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    out["val_specificity"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    out["val_f1"] = out["validation_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    out["test_balanced_accuracy"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "balanced_accuracy"))
    out["test_recall"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "recall"))
    out["test_specificity"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "specificity"))
    out["test_f1"] = out["test_metrics_json"].apply(lambda s: metric_value(s, "f1"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Export consolidated experiment reports for versioned RF campaign.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry = load_registry(dirs["reports_versioning"] / "model_registry.csv")

    campaign = registry[
        registry["model_version"].apply(_is_campaign_model)
        & registry["disorder"].isin(TARGET_DISORDERS)
        & (registry["task_type"] == "binary")
    ].copy()
    campaign = _augment_metrics(campaign)
    columns: List[str] = [
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
        "n_features_raw",
        "n_features_final",
        "train_rows",
        "val_rows",
        "test_rows",
        "val_balanced_accuracy",
        "val_recall",
        "val_specificity",
        "val_f1",
        "test_balanced_accuracy",
        "test_recall",
        "test_specificity",
        "test_f1",
        "status",
        "promoted",
        "promoted_status",
        "rejection_reason",
        "notes",
    ]
    if campaign.empty:
        summary = pd.DataFrame(columns=columns)
    else:
        summary = campaign[columns].sort_values(
            ["disorder", "val_balanced_accuracy", "val_recall", "val_specificity"],
            ascending=[True, False, False, False],
        )

    summary.to_csv(dirs["reports_experiments"] / "experiment_results_summary.csv", index=False)
    for disorder in TARGET_DISORDERS:
        summary[summary["disorder"] == disorder].to_csv(
            dirs["reports_experiments"] / f"{disorder}_experiments.csv",
            index=False,
        )


if __name__ == "__main__":
    main()
