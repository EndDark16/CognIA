#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export operating modes specification from training outputs.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    modes_dir = root / "reports" / "operating_modes"
    modes_dir.mkdir(parents=True, exist_ok=True)
    mode_csv = modes_dir / "operating_modes_comparison.csv"
    if not mode_csv.exists():
        safe_csv(pd.DataFrame(columns=["trial_id", "mode", "threshold", "precision_test", "recall_test", "specificity_test", "balanced_accuracy_test"]), mode_csv)

    df = pd.read_csv(mode_csv, low_memory=False)
    lines = [
        "# Operating Modes Spec",
        "",
        "This file defines three operational modes for the app output layer.",
        "",
        "1) sensitive",
        "- threshold strategy: lower threshold than recommended",
        "- expected tradeoff: higher recall, lower precision",
        "- use case: screening-first workflows",
        "- risk notes: more false positives",
        "",
        "2) precise",
        "- threshold strategy: higher threshold than recommended",
        "- expected tradeoff: higher precision, lower recall",
        "- use case: prioritize positive predictive value",
        "- risk notes: more false negatives",
        "",
        "3) abstention_assisted",
        "- threshold strategy: recommended threshold + uncertainty band in inference layer",
        "- expected tradeoff: balanced operating point with uncertain cases flagged",
        "- use case: triage with human review",
        "- risk notes: lower coverage due to abstention zone",
        "",
        f"- models covered: {df['trial_id'].nunique() if not df.empty else 0}",
    ]
    safe_text("\n".join(lines) + "\n", modes_dir / "operating_modes_spec.md")


if __name__ == "__main__":
    main()

