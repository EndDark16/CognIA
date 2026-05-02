from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd

from ml_rf_common import binary_metrics, threshold_candidates


@dataclass(frozen=True)
class PrecisionThresholdPolicy:
    recall_floor: float
    balanced_accuracy_floor: float


def _candidate_thresholds(y_prob: np.ndarray) -> Iterable[float]:
    grid = np.linspace(0.05, 0.95, 91)
    uniq = np.unique(np.round(y_prob, 6))
    values = np.unique(np.concatenate([grid, uniq, np.array([0.5])]))
    return [float(v) for v in values if 0.0 <= float(v) <= 1.0]


def _evaluate_thresholds(y_true: np.ndarray, y_prob: np.ndarray) -> pd.DataFrame:
    rows = []
    for thr in _candidate_thresholds(y_prob):
        m = binary_metrics(y_true, y_prob, threshold=thr)
        m["method"] = "grid_precision"
        m["fpr"] = 1.0 - float(m["specificity"])
        m["fnr"] = 1.0 - float(m["recall"])
        rows.append(m)
    return pd.DataFrame(rows)


def optimize_precision_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    policy: PrecisionThresholdPolicy,
) -> Tuple[Dict[str, float], pd.DataFrame]:
    base = threshold_candidates(y_true, y_prob, sensitivity_target=max(policy.recall_floor, 0.5)).copy()
    base["fpr"] = 1.0 - base["specificity"]
    base["fnr"] = 1.0 - base["recall"]
    grid = _evaluate_thresholds(y_true, y_prob)
    merged = pd.concat([base, grid], ignore_index=True, sort=False).drop_duplicates(subset=["threshold"], keep="first")

    merged["meets_recall_floor"] = merged["recall"] >= policy.recall_floor
    merged["meets_bal_acc_floor"] = merged["balanced_accuracy"] >= policy.balanced_accuracy_floor
    merged["meets_constraints"] = merged["meets_recall_floor"] & merged["meets_bal_acc_floor"]

    constrained = merged[merged["meets_constraints"]].copy()
    if not constrained.empty:
        constrained = constrained.sort_values(
            ["precision", "balanced_accuracy", "recall", "specificity"],
            ascending=[False, False, False, False],
        )
        best = constrained.iloc[0].to_dict()
        best["method"] = "precision_constrained"
        best["selection_reason"] = "maximize_precision_under_constraints"
        return best, merged.sort_values(["threshold"]).reset_index(drop=True)

    fallback = merged.sort_values(
        ["precision", "balanced_accuracy", "recall", "specificity"],
        ascending=[False, False, False, False],
    ).iloc[0].to_dict()
    fallback["method"] = "precision_fallback"
    fallback["selection_reason"] = "constraints_unsatisfied_fallback_to_max_precision"
    return fallback, merged.sort_values(["threshold"]).reset_index(drop=True)
