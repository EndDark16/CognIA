from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from versioning_utils import ensure_versioning_dirs, load_registry, metric_value


TARGET_DISORDERS = ["depression", "conduct", "elimination"]


def _champions(registry: pd.DataFrame) -> pd.DataFrame:
    champions = registry[
        (registry["task_type"] == "binary")
        & (registry["promoted"].astype(str).str.lower() == "yes")
        & (registry["promoted_status"].astype(str).str.lower() == "champion")
    ].copy()
    return champions


def _row_metrics(row: pd.Series, prefix: str) -> Dict[str, Any]:
    return {
        f"{prefix}_val_balanced_accuracy": metric_value(row["validation_metrics_json"], "balanced_accuracy"),
        f"{prefix}_val_recall": metric_value(row["validation_metrics_json"], "recall"),
        f"{prefix}_val_specificity": metric_value(row["validation_metrics_json"], "specificity"),
        f"{prefix}_val_f1": metric_value(row["validation_metrics_json"], "f1"),
        f"{prefix}_test_balanced_accuracy": metric_value(row["test_metrics_json"], "balanced_accuracy"),
        f"{prefix}_test_recall": metric_value(row["test_metrics_json"], "recall"),
        f"{prefix}_test_specificity": metric_value(row["test_metrics_json"], "specificity"),
        f"{prefix}_test_f1": metric_value(row["test_metrics_json"], "f1"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare champions vs challengers across model versions.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dirs = ensure_versioning_dirs(root)
    registry = load_registry(dirs["reports_versioning"] / "model_registry.csv")

    champions = _champions(registry)
    rows: List[Dict[str, Any]] = []
    for disorder in TARGET_DISORDERS:
        champ = champions[champions["disorder"] == disorder]
        if champ.empty:
            continue
        champ_row = champ.iloc[0]
        challengers = registry[
            (registry["task_type"] == "binary")
            & (registry["disorder"] == disorder)
            & (registry["model_version"] != champ_row["model_version"])
            & (registry["status"].isin(["completed", "promoted", "rejected"]))
        ].copy()
        for _, ch in challengers.iterrows():
            row: Dict[str, Any] = {
                "disorder": disorder,
                "champion_version": champ_row["model_version"],
                "challenger_version": ch["model_version"],
                "champion_dataset": champ_row["dataset_name"],
                "challenger_dataset": ch["dataset_name"],
                "champion_scope": champ_row["data_scope"],
                "challenger_scope": ch["data_scope"],
                "challenger_status": ch["status"],
                "challenger_promoted": ch["promoted"],
                "challenger_notes": ch["notes"],
            }
            row.update(_row_metrics(champ_row, "champion"))
            row.update(_row_metrics(ch, "challenger"))
            row["delta_val_balanced_accuracy"] = (
                row["challenger_val_balanced_accuracy"] - row["champion_val_balanced_accuracy"]
            )
            row["delta_val_recall"] = row["challenger_val_recall"] - row["champion_val_recall"]
            row["delta_val_specificity"] = row["challenger_val_specificity"] - row["champion_val_specificity"]
            row["delta_val_f1"] = row["challenger_val_f1"] - row["champion_val_f1"]
            row["delta_test_balanced_accuracy"] = (
                row["challenger_test_balanced_accuracy"] - row["champion_test_balanced_accuracy"]
            )
            row["delta_test_recall"] = row["challenger_test_recall"] - row["champion_test_recall"]
            row["delta_test_specificity"] = row["challenger_test_specificity"] - row["champion_test_specificity"]
            row["delta_test_f1"] = row["challenger_test_f1"] - row["champion_test_f1"]
            rows.append(row)

    matrix = pd.DataFrame(rows)
    if matrix.empty:
        matrix = pd.DataFrame(
            columns=[
                "disorder",
                "champion_version",
                "challenger_version",
                "delta_val_balanced_accuracy",
                "delta_test_balanced_accuracy",
            ]
        )
    else:
        matrix = matrix.sort_values(
            ["disorder", "delta_val_balanced_accuracy", "delta_val_recall", "delta_val_specificity"],
            ascending=[True, False, False, False],
        )

    matrix.to_csv(dirs["reports_promotions"] / "model_comparison_matrix.csv", index=False)


if __name__ == "__main__":
    main()
