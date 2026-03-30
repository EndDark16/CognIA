from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml_rf_common import safe_csv, select_best_binary_per_disorder


def _normalize_binary(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["task"] = "binary"
    out["metric_primary"] = out["balanced_accuracy_test"]
    out["metric_secondary"] = out["recall_test"]
    return out


def _normalize_multilabel(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["task"] = "multilabel"
    out["metric_primary"] = out["micro_f1_test"]
    out["metric_secondary"] = out["subset_accuracy_test"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate training outputs into comparison reports.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    metrics_dir = root / "reports" / "metrics"
    compare_dir = root / "reports" / "comparisons"
    compare_dir.mkdir(parents=True, exist_ok=True)

    binary = pd.read_csv(metrics_dir / "binary_model_results_detailed.csv")
    multilabel = pd.read_csv(metrics_dir / "multilabel_model_results_detailed.csv")

    binary_summary_cols = [
        "model_id",
        "dataset_name",
        "version",
        "disorder",
        "variant",
        "target",
        "n_features",
        "balanced_accuracy_test",
        "recall_test",
        "specificity_test",
        "f1_test",
        "roc_auc_test",
        "pr_auc_test",
        "brier_score_test",
        "threshold_method",
        "threshold_value",
        "search_param_source",
        "artifact_pipeline_path",
    ]
    binary_summary = binary[binary_summary_cols].sort_values(
        ["disorder", "version", "variant", "balanced_accuracy_test"], ascending=[True, True, True, False]
    )
    safe_csv(binary_summary, metrics_dir / "binary_results_summary.csv")

    multilabel_summary_cols = [
        "model_id",
        "dataset_name",
        "version",
        "n_features",
        "subset_accuracy_test",
        "hamming_loss_test",
        "micro_f1_test",
        "macro_f1_test",
        "weighted_f1_test",
        "artifact_pipeline_path",
    ]
    multilabel_summary = multilabel[multilabel_summary_cols].sort_values(["version"])
    safe_csv(multilabel_summary, metrics_dir / "multilabel_results_summary.csv")

    combined = pd.concat([_normalize_binary(binary), _normalize_multilabel(multilabel)], ignore_index=True, sort=False)
    safe_csv(
        combined[
            [
                "task",
                "model_id",
                "dataset_name",
                "version",
                "metric_primary",
                "metric_secondary",
                "n_features",
                "artifact_pipeline_path",
            ]
        ],
        metrics_dir / "per_dataset_results.csv",
    )

    # strict vs research for binary datasets matched by disorder+variant
    b = binary.copy()
    strict = b[b["version"] == "strict_no_leakage"][
        ["disorder", "variant", "model_id", "balanced_accuracy_test", "recall_test", "specificity_test", "f1_test", "roc_auc_test"]
    ].rename(
        columns={
            "model_id": "model_id_strict",
            "balanced_accuracy_test": "balanced_accuracy_strict",
            "recall_test": "recall_strict",
            "specificity_test": "specificity_strict",
            "f1_test": "f1_strict",
            "roc_auc_test": "roc_auc_strict",
        }
    )
    research = b[b["version"] == "research_extended"][
        ["disorder", "variant", "model_id", "balanced_accuracy_test", "recall_test", "specificity_test", "f1_test", "roc_auc_test"]
    ].rename(
        columns={
            "model_id": "model_id_research",
            "balanced_accuracy_test": "balanced_accuracy_research",
            "recall_test": "recall_research",
            "specificity_test": "specificity_research",
            "f1_test": "f1_research",
            "roc_auc_test": "roc_auc_research",
        }
    )
    strict_vs_research = strict.merge(research, on=["disorder", "variant"], how="outer")
    strict_vs_research["delta_balanced_accuracy_research_minus_strict"] = (
        strict_vs_research["balanced_accuracy_research"] - strict_vs_research["balanced_accuracy_strict"]
    )
    strict_vs_research["delta_recall_research_minus_strict"] = strict_vs_research["recall_research"] - strict_vs_research["recall_strict"]
    strict_vs_research["delta_specificity_research_minus_strict"] = (
        strict_vs_research["specificity_research"] - strict_vs_research["specificity_strict"]
    )

    # Append multilabel strict vs research
    m_strict = multilabel[multilabel["version"] == "strict_no_leakage"][
        ["model_id", "micro_f1_test", "subset_accuracy_test", "macro_f1_test"]
    ]
    m_research = multilabel[multilabel["version"] == "research_extended"][
        ["model_id", "micro_f1_test", "subset_accuracy_test", "macro_f1_test"]
    ]
    if not m_strict.empty and not m_research.empty:
        ml_row = pd.DataFrame(
            [
                {
                    "disorder": "multilabel",
                    "variant": "master",
                    "model_id_strict": m_strict.iloc[0]["model_id"],
                    "model_id_research": m_research.iloc[0]["model_id"],
                    "balanced_accuracy_strict": float("nan"),
                    "balanced_accuracy_research": float("nan"),
                    "recall_strict": float("nan"),
                    "recall_research": float("nan"),
                    "specificity_strict": float("nan"),
                    "specificity_research": float("nan"),
                    "f1_strict": m_strict.iloc[0]["micro_f1_test"],
                    "f1_research": m_research.iloc[0]["micro_f1_test"],
                    "roc_auc_strict": float("nan"),
                    "roc_auc_research": float("nan"),
                    "delta_balanced_accuracy_research_minus_strict": float("nan"),
                    "delta_recall_research_minus_strict": float("nan"),
                    "delta_specificity_research_minus_strict": float("nan"),
                }
            ]
        )
        strict_vs_research = pd.concat([strict_vs_research, ml_row], ignore_index=True, sort=False)
    safe_csv(strict_vs_research.sort_values(["disorder", "variant"]), compare_dir / "strict_vs_research.csv")

    # Variant comparison (strict primary)
    strict_binary = binary[binary["version"] == "strict_no_leakage"].copy()
    strict_binary = strict_binary.sort_values(
        ["disorder", "balanced_accuracy_test", "recall_test", "specificity_test", "f1_test", "brier_score_test", "n_features"],
        ascending=[True, False, False, False, False, True, True],
    )
    strict_binary["rank_within_disorder"] = strict_binary.groupby("disorder").cumcount() + 1
    safe_csv(
        strict_binary[
            [
                "disorder",
                "variant",
                "model_id",
                "rank_within_disorder",
                "balanced_accuracy_test",
                "recall_test",
                "specificity_test",
                "f1_test",
                "roc_auc_test",
                "pr_auc_test",
                "brier_score_test",
                "n_features",
            ]
        ],
        compare_dir / "dataset_variant_comparison.csv",
    )

    best = select_best_binary_per_disorder(strict_binary)
    safe_csv(best, metrics_dir / "binary_best_per_disorder.csv")


if __name__ == "__main__":
    main()
