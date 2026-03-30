from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def evaluate_abstention_policy(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    base_threshold: float,
    target_high_precision: float,
    min_confident_coverage: float = 0.10,
) -> Tuple[Dict[str, float], pd.DataFrame]:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    n = len(y_true)
    if n == 0:
        raise ValueError("Empty arrays are not supported.")

    low_values = np.linspace(0.05, min(float(base_threshold), 0.5), 20)
    high_values = np.linspace(max(float(base_threshold), 0.5), 0.95, 20)
    if low_values.size == 0:
        low_values = np.array([0.05])
    if high_values.size == 0:
        high_values = np.array([0.95])

    rows = []
    total_pos = max(int((y_true == 1).sum()), 1)
    total_neg = max(int((y_true == 0).sum()), 1)
    for low_thr in low_values:
        for high_thr in high_values:
            if low_thr >= high_thr:
                continue
            pos_mask = y_prob >= high_thr
            neg_mask = y_prob <= low_thr
            uncertain_mask = ~(pos_mask | neg_mask)

            pos_n = int(pos_mask.sum())
            neg_n = int(neg_mask.sum())
            uncertain_n = int(uncertain_mask.sum())
            coverage = float((pos_n + neg_n) / n)

            tp = int(np.logical_and(pos_mask, y_true == 1).sum())
            fp = int(np.logical_and(pos_mask, y_true == 0).sum())
            tn = int(np.logical_and(neg_mask, y_true == 0).sum())
            fn_low = int(np.logical_and(neg_mask, y_true == 1).sum())

            precision_high = float(tp / (tp + fp)) if (tp + fp) else float("nan")
            npv_low = float(tn / (tn + fn_low)) if (tn + fn_low) else float("nan")
            recall_effective = float(tp / total_pos)
            specificity_effective = float(tn / total_neg)

            rows.append(
                {
                    "low_threshold": float(low_thr),
                    "high_threshold": float(high_thr),
                    "coverage": coverage,
                    "uncertain_rate": float(uncertain_n / n),
                    "confident_positive_n": pos_n,
                    "confident_negative_n": neg_n,
                    "uncertain_n": uncertain_n,
                    "precision_high": precision_high,
                    "npv_low": npv_low,
                    "recall_effective": recall_effective,
                    "specificity_effective": specificity_effective,
                }
            )

    df = pd.DataFrame(rows)
    feasible = df[
        (df["coverage"] >= float(min_confident_coverage))
        & (df["precision_high"].fillna(0.0) >= float(target_high_precision))
    ].copy()
    if not feasible.empty:
        best = feasible.sort_values(
            ["precision_high", "coverage", "recall_effective", "specificity_effective"],
            ascending=[False, False, False, False],
        ).iloc[0]
        reason = "target_precision_with_coverage"
    else:
        best = df.sort_values(
            ["precision_high", "coverage", "recall_effective", "specificity_effective"],
            ascending=[False, False, False, False],
        ).iloc[0]
        reason = "fallback_max_precision"

    summary = {
        "low_threshold": float(best["low_threshold"]),
        "high_threshold": float(best["high_threshold"]),
        "coverage": float(best["coverage"]),
        "uncertain_rate": float(best["uncertain_rate"]),
        "precision_high": float(best["precision_high"]) if pd.notna(best["precision_high"]) else float("nan"),
        "npv_low": float(best["npv_low"]) if pd.notna(best["npv_low"]) else float("nan"),
        "recall_effective": float(best["recall_effective"]),
        "specificity_effective": float(best["specificity_effective"]),
        "selection_reason": reason,
        "target_high_precision": float(target_high_precision),
        "min_confident_coverage": float(min_confident_coverage),
    }
    return summary, df.sort_values(
        ["precision_high", "coverage", "recall_effective"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
