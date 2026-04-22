from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ALLOWED_MAIN_CLASSES = {
    "ROBUST_PRIMARY",
    "PRIMARY_WITH_CAVEAT",
    "HOLD_FOR_LIMITATION",
    "REJECT_AS_PRIMARY",
}

LEGACY_SUSPECT_CLASS = "SUSPECT_EASY_DATASET_NEEDS_CAUTION"

CLASS_ORDER = {
    "REJECT_AS_PRIMARY": 0,
    "HOLD_FOR_LIMITATION": 1,
    "PRIMARY_WITH_CAVEAT": 2,
    "ROBUST_PRIMARY": 3,
}

TRUTHY = {"1", "true", "yes", "y", "si", "s"}


@dataclass(frozen=True)
class PolicyInputs:
    operational_csv: Path
    active_csv: Path
    shortcut_inventory_csv: Path | None = None


def normalize_role_label(role: Any) -> str:
    raw = str(role or "").strip().lower()
    if raw == "caregiver":
        return "guardian"
    return raw


def _yes_no(value: Any) -> str:
    return "yes" if str(value or "").strip().lower() in TRUTHY else "no"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _secondary_metric_anomaly(row: pd.Series) -> tuple[str, float, str]:
    roc_auc = _safe_float(row.get("roc_auc"))
    pr_auc = _safe_float(row.get("pr_auc"))
    specificity = _safe_float(row.get("specificity"))
    brier = _safe_float(row.get("brier"))
    balanced_accuracy = _safe_float(row.get("balanced_accuracy"))

    secondary_peak = max(roc_auc, pr_auc, specificity)
    any_gt_098 = roc_auc > 0.98 or pr_auc > 0.98 or specificity > 0.98
    suspicious_combo = (
        (secondary_peak > 0.985 and brier <= 0.03)
        or ((roc_auc > 0.99 or pr_auc > 0.99) and brier <= 0.025)
        or (specificity > 0.99 and balanced_accuracy >= 0.90 and brier <= 0.03)
    )
    anomaly = any_gt_098 or suspicious_combo

    reasons: list[str] = []
    if roc_auc > 0.98:
        reasons.append("roc_auc_gt_0_98")
    if pr_auc > 0.98:
        reasons.append("pr_auc_gt_0_98")
    if specificity > 0.98:
        reasons.append("specificity_gt_0_98")
    if brier <= 0.02:
        reasons.append("brier_very_low")
    if suspicious_combo:
        reasons.append("suspicious_combo_secondary_plus_brier")

    return ("yes" if anomaly else "no"), secondary_peak, ",".join(reasons) if reasons else "none"


def _build_shortcut_index(shortcut_inventory_csv: Path | None) -> dict[tuple[str, str], str]:
    if not shortcut_inventory_csv or not shortcut_inventory_csv.exists():
        return {}
    df = pd.read_csv(shortcut_inventory_csv)
    if not {"domain", "mode", "shortcut_dominance_flag"}.issubset(set(df.columns)):
        return {}
    out: dict[tuple[str, str], str] = {}
    for row in df.to_dict(orient="records"):
        key = (str(row.get("domain", "")).strip().lower(), str(row.get("mode", "")).strip().lower())
        out[key] = _yes_no(row.get("shortcut_dominance_flag"))
    return out


def _build_rationale(row: pd.Series, cls: str, secondary_reasons: str) -> str:
    reasons = [
        f"metrics[ba={_safe_float(row.get('balanced_accuracy')):.3f},f1={_safe_float(row.get('f1')):.3f},p={_safe_float(row.get('precision')):.3f},r={_safe_float(row.get('recall')):.3f},brier={_safe_float(row.get('brier')):.3f}]",
    ]
    for flag in [
        "generalization_risk_flag",
        "overfit_risk_flag",
        "easy_dataset_flag",
        "secondary_metric_anomaly_flag",
        "mode_fragility_flag",
        "shortcut_risk_flag",
        "calibration_concern_flag",
    ]:
        if str(row.get(flag, "no")) == "yes":
            reasons.append(flag)
    if secondary_reasons and secondary_reasons != "none":
        reasons.append(f"secondary_reasons={secondary_reasons}")
    reasons.append(f"class={cls}")
    return "; ".join(reasons)


def classify_operational_row(row: pd.Series) -> tuple[str, str]:
    precision = _safe_float(row.get("precision"))
    recall = _safe_float(row.get("recall"))
    balanced_accuracy = _safe_float(row.get("balanced_accuracy"))
    f1 = _safe_float(row.get("f1"))
    brier = _safe_float(row.get("brier"))

    robust_gate = (
        balanced_accuracy >= 0.90
        and f1 >= 0.85
        and precision >= 0.82
        and recall >= 0.80
        and brier <= 0.06
    )
    minimum_gate = (
        balanced_accuracy >= 0.84
        and f1 >= 0.78
        and precision >= 0.74
        and recall >= 0.68
        and brier <= 0.08
    )

    easy_dataset = str(row.get("easy_dataset_flag")) == "yes"
    shortcut_risk = str(row.get("shortcut_risk_flag")) == "yes"
    secondary_anomaly = str(row.get("secondary_metric_anomaly_flag")) == "yes"
    anomaly_resolved = str(row.get("secondary_anomaly_resolution", "not_required")) == "documented_strong"
    overfit_risk = str(row.get("overfit_risk_flag")) == "yes"
    generalization_risk = str(row.get("generalization_risk_flag")) == "yes"
    mode_fragility = str(row.get("mode_fragility_flag")) == "yes"
    calibration_concern = str(row.get("calibration_concern_flag")) == "yes"

    if easy_dataset or shortcut_risk:
        return "REJECT_AS_PRIMARY", "hard_blocker_easy_or_shortcut"

    if robust_gate and not overfit_risk and not generalization_risk and not mode_fragility and not calibration_concern:
        if secondary_anomaly and not anomaly_resolved:
            return "PRIMARY_WITH_CAVEAT", "robust_metrics_blocked_by_unresolved_secondary_anomaly"
        return "ROBUST_PRIMARY", "passes_robust_gate_without_blockers"

    operational_limited = str(row.get("final_operational_class", "")) == "ACTIVE_LIMITED_USE"
    if not minimum_gate or overfit_risk or generalization_risk or (operational_limited and mode_fragility):
        return "HOLD_FOR_LIMITATION", "fails_minimum_gate_or_has_strong_risk"

    return "PRIMARY_WITH_CAVEAT", "useful_with_explicit_caveat"


def build_normalized_table(inputs: PolicyInputs) -> pd.DataFrame:
    op = pd.read_csv(inputs.operational_csv)
    active = pd.read_csv(inputs.active_csv)
    shortcut_index = _build_shortcut_index(inputs.shortcut_inventory_csv)

    merge_cols = [
        "domain",
        "mode",
        "role",
        "final_operational_class",
        "overfit_flag",
        "generalization_flag",
        "dataset_ease_flag",
        "confidence_pct",
        "confidence_band",
        "operational_caveat",
        "recommended_for_default_use",
    ]
    use_active = active[[c for c in merge_cols if c in active.columns]].copy()
    merged = op.merge(use_active, on=["domain", "mode"], how="left", validate="one_to_one")

    secondary_rows = []
    for _, row in merged.iterrows():
        anomaly_flag, secondary_peak, secondary_reasons = _secondary_metric_anomaly(row)
        key = (str(row["domain"]).strip().lower(), str(row["mode"]).strip().lower())
        shortcut_from_inventory = shortcut_index.get(key, "no")
        caveat = str(row.get("operational_caveat") or "").lower()
        shortcut_risk = (
            shortcut_from_inventory == "yes"
            or "shortcut" in caveat
            or "easy-dataset" in caveat
            or "easy dataset" in caveat
        )
        easy_dataset = _yes_no(row.get("dataset_ease_flag")) == "yes" or str(row.get("final_class")) == LEGACY_SUSPECT_CLASS
        overfit_risk = _yes_no(row.get("overfit_flag")) == "yes" or _safe_float(row.get("overfit_gap_train_val_ba")) > 0.10
        generalization_risk = _yes_no(row.get("generalization_flag")) != "yes"
        mode_fragility = (
            "1_3" in str(row.get("mode"))
            or str(row.get("confidence_band")) in {"limited", "low"}
            or "short mode fragile" in caveat
            or "escalate to richer mode" in caveat
        )
        calibration = str(row.get("calibration") or "").strip().lower()
        calibration_concern = calibration == "none" and _safe_float(row.get("brier")) > 0.05
        secondary_resolution = "por_confirmar" if anomaly_flag == "yes" else "not_required"

        normalized_row = row.copy()
        normalized_row["role_normalized"] = normalize_role_label(row.get("role"))
        normalized_row["generalization_risk_flag"] = "yes" if generalization_risk else "no"
        normalized_row["overfit_risk_flag"] = "yes" if overfit_risk else "no"
        normalized_row["easy_dataset_flag"] = "yes" if easy_dataset else "no"
        normalized_row["secondary_metric_anomaly_flag"] = anomaly_flag
        normalized_row["secondary_metric_peak"] = secondary_peak
        normalized_row["secondary_metric_anomaly_reasons"] = secondary_reasons
        normalized_row["secondary_anomaly_resolution"] = secondary_resolution
        normalized_row["mode_fragility_flag"] = "yes" if mode_fragility else "no"
        normalized_row["shortcut_risk_flag"] = "yes" if shortcut_risk else "no"
        normalized_row["calibration_concern_flag"] = "yes" if calibration_concern else "no"
        normalized_row["legacy_final_class"] = str(row.get("final_class") or "")
        normalized_class, class_reason = classify_operational_row(normalized_row)
        normalized_row["normalized_final_class"] = normalized_class
        normalized_row["classification_reason_code"] = class_reason
        normalized_row["classification_rationale"] = _build_rationale(normalized_row, normalized_class, secondary_reasons)
        secondary_rows.append(normalized_row)

    result = pd.DataFrame(secondary_rows)

    def transition(row: pd.Series) -> str:
        old = str(row.get("legacy_final_class") or "")
        new = str(row.get("normalized_final_class") or "")
        old_rank = CLASS_ORDER.get(old, -1)
        new_rank = CLASS_ORDER.get(new, -1)
        if old == new:
            return "unchanged"
        if old_rank > new_rank:
            return "downgrade"
        if old_rank < new_rank:
            return "upgrade"
        return "changed"

    result["class_transition"] = result.apply(transition, axis=1)
    return result


def policy_violations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    checks: list[pd.DataFrame] = []

    robust = df[df["normalized_final_class"] == "ROBUST_PRIMARY"].copy()
    if not robust.empty:
        v_easy = robust[robust["easy_dataset_flag"] == "yes"].copy()
        if not v_easy.empty:
            v_easy["violation"] = "easy_dataset_as_robust"
            checks.append(v_easy)

        v_shortcut = robust[robust["shortcut_risk_flag"] == "yes"].copy()
        if not v_shortcut.empty:
            v_shortcut["violation"] = "shortcut_risk_as_robust"
            checks.append(v_shortcut)

        v_secondary = robust[
            (robust["secondary_metric_anomaly_flag"] == "yes")
            & (robust["secondary_anomaly_resolution"] != "documented_strong")
        ].copy()
        if not v_secondary.empty:
            v_secondary["violation"] = "secondary_anomaly_unresolved_as_robust"
            checks.append(v_secondary)

    invalid_class = df[~df["normalized_final_class"].isin(ALLOWED_MAIN_CLASSES)].copy()
    if not invalid_class.empty:
        invalid_class["violation"] = "invalid_main_class"
        checks.append(invalid_class)

    if checks:
        return pd.concat(checks, ignore_index=True)
    return df.iloc[0:0].copy()


def build_review_list(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    rows = []
    for _, row in df.iterrows():
        old_class = str(row.get("legacy_final_class") or "")
        new_class = str(row.get("normalized_final_class") or "")
        old_rank = CLASS_ORDER.get(old_class, -1)
        new_rank = CLASS_ORDER.get(new_class, -1)
        mode = str(row.get("mode") or "")

        if old_class == new_class:
            review_bucket = "mantener_igual"
        elif old_rank > new_rank and new_class == "PRIMARY_WITH_CAVEAT":
            review_bucket = "bajar_a_primary_with_caveat"
        elif old_rank > new_rank and new_class == "HOLD_FOR_LIMITATION":
            review_bucket = "bajar_a_hold_for_limitation"
        elif new_class == "REJECT_AS_PRIMARY":
            review_bucket = "bajar_a_reject_as_primary"
        else:
            review_bucket = "revision_pendiente_futuro_retraining"

        needs_retrain_review = (
            str(row.get("overfit_risk_flag")) == "yes"
            or str(row.get("shortcut_risk_flag")) == "yes"
            or str(row.get("easy_dataset_flag")) == "yes"
            or (
                str(row.get("secondary_metric_anomaly_flag")) == "yes"
                and ("_full" in mode or "_2_3" in mode)
            )
        )
        if needs_retrain_review and review_bucket == "mantener_igual":
            review_bucket = "revision_pendiente_futuro_retraining"

        score = 0
        if "_full" in mode or "_2_3" in mode:
            score += 3
        if str(row.get("secondary_metric_anomaly_flag")) == "yes":
            score += 4
        if str(row.get("overfit_risk_flag")) == "yes":
            score += 4
        if str(row.get("shortcut_risk_flag")) == "yes":
            score += 5
        if str(row.get("easy_dataset_flag")) == "yes":
            score += 5
        if str(row.get("class_transition")) == "downgrade":
            score += 2

        rows.append(
            {
                "domain": row.get("domain"),
                "mode": mode,
                "role_normalized": row.get("role_normalized"),
                "legacy_final_class": old_class,
                "normalized_final_class": new_class,
                "class_transition": row.get("class_transition"),
                "review_bucket": review_bucket,
                "priority_score": score,
                "secondary_metric_anomaly_flag": row.get("secondary_metric_anomaly_flag"),
                "overfit_risk_flag": row.get("overfit_risk_flag"),
                "generalization_risk_flag": row.get("generalization_risk_flag"),
                "easy_dataset_flag": row.get("easy_dataset_flag"),
                "shortcut_risk_flag": row.get("shortcut_risk_flag"),
                "mode_fragility_flag": row.get("mode_fragility_flag"),
                "calibration_concern_flag": row.get("calibration_concern_flag"),
                "classification_rationale": row.get("classification_rationale"),
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(
        by=["priority_score", "review_bucket", "domain", "mode"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)
    return out
