#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_FILES = [
    "trial_registry.csv",
    "fold_metrics_history.csv",
    "hyperparameter_search_history.csv",
    "n_estimators_curve.csv",
    "learning_curve_history.csv",
    "threshold_sweep_history.csv",
    "calibration_history.csv",
    "model_comparison_history.csv",
    "feature_importance_history.csv",
    "permutation_importance_history.csv",
]


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and export consolidated RF training history files.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    history_dir = root / "reports" / "training_history"
    history_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for name in REQUIRED_FILES:
        p = history_dir / name
        exists = p.exists()
        n_rows = 0
        n_cols = 0
        if exists:
            df = pd.read_csv(p, low_memory=False)
            n_rows, n_cols = df.shape
        rows.append({"file": name, "exists": int(exists), "rows": int(n_rows), "columns": int(n_cols)})
    inv = pd.DataFrame(rows)
    safe_csv(inv, history_dir / "training_history_inventory.csv")


if __name__ == "__main__":
    main()

