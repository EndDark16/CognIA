from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _run_step(cmd: list[str], cwd: Path) -> None:
    print(f"\n>> Running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _print_executive_summary(root: Path) -> None:
    metrics_dir = root / "reports" / "metrics"
    compare_dir = root / "reports" / "comparisons"
    training_dir = root / "reports" / "training"

    binary = pd.read_csv(metrics_dir / "binary_results_summary.csv")
    multilabel = pd.read_csv(metrics_dir / "multilabel_results_summary.csv")
    variant = pd.read_csv(compare_dir / "dataset_variant_comparison.csv")
    registry = pd.read_csv(training_dir / "model_registry.csv")

    best_binary = registry[(registry["task"] == "binary") & (registry["is_primary_recommended"] == 1)]
    best_ml = registry[(registry["task"] == "multilabel") & (registry["is_primary_recommended"] == 1)]

    print("\n=== EXECUTIVE SUMMARY ===")
    print(f"Binary models trained: {len(binary)}")
    print(f"Multilabel models trained: {len(multilabel)}")
    print(f"Best binary models selected: {len(best_binary)}")
    print(f"Best multilabel selected: {len(best_ml)}")
    print("\nBest by disorder:")
    for row in best_binary.sort_values("disorder").itertuples(index=False):
        print(
            f"- {row.disorder}: {row.model_id} | BA={row.balanced_accuracy_test:.4f} "
            f"R={row.recall_test:.4f} S={row.specificity_test:.4f} "
            f"F1={row.f1_test:.4f} thr={row.threshold:.4f} ({row.threshold_method})"
        )
    if not best_ml.empty:
        mid = best_ml.iloc[0]["model_id"]
        ml_row = multilabel[multilabel["model_id"] == mid].iloc[0]
        print(
            f"\nBest multilabel: {mid} | micro_f1={ml_row['micro_f1_test']:.4f} "
            f"macro_f1={ml_row['macro_f1_test']:.4f} subset_acc={ml_row['subset_accuracy_test']:.4f}"
        )
    print(f"\nVariant comparison rows: {len(variant)}")
    print(f"Recommendations report: {compare_dir / 'final_model_recommendations.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full RF training/evaluation/report pipeline.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--versions", type=str, default="strict_no_leakage,research_extended")
    parser.add_argument("--skip-train", action="store_true", help="Skip training steps and only aggregate/report existing results.")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    python = sys.executable
    if not args.skip_train:
        _run_step([python, "scripts/train_random_forest_binary.py", "--root", str(root), "--versions", args.versions], cwd=root)
        _run_step([python, "scripts/train_random_forest_multilabel.py", "--root", str(root), "--versions", args.versions], cwd=root)
    _run_step([python, "scripts/evaluate_models.py", "--root", str(root)], cwd=root)
    _run_step([python, "scripts/generate_model_reports.py", "--root", str(root)], cwd=root)
    _print_executive_summary(root)


if __name__ == "__main__":
    main()
