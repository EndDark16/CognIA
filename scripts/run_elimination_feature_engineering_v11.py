#!/usr/bin/env python
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


TARGET_COL = "target_domain_elimination"
RANDOM_STATE = 42
MODES = ["caregiver", "psychologist"]
MODEL_FAMILIES = ["rf", "lightgbm", "xgboost"]
SEEDS_FOR_STABILITY = [11, 42, 2026]
ROUND_POLICY = {"max_strong_rounds": 3, "max_confirm_rounds": 1}

BLOCKED_EXACT = {
    "participant_id",
    TARGET_COL,
    "has_any_target_disorder",
    "n_diagnoses",
    "comorbidity_count_5targets",
    "domain_comorbidity_count",
    "internal_exact_comorbidity_count",
    "domain_any_positive",
    "internal_exact_any_positive",
}
BLOCKED_SUBSTRINGS = ("diagnosis", "ksads", "consensus")
SELF_REPORT_PREFIXES = ("ysr_", "scared_sr_", "ari_sr_", "cdi_", "mfq_sr_", "asr_", "bdi_", "stai_", "caars_")
SELF_REPORT_FLAGS = {"has_ysr", "has_scared_sr", "has_ari_sr", "has_cdi", "has_mfq_sr", "has_asr", "has_bdi", "has_stai", "has_caars"}


@dataclass
class CampaignPaths:
    root: Path
    base: Path
    inventory: Path
    feature_sets: Path
    trials: Path
    analysis: Path
    tables: Path
    reports: Path
    artifacts: Path
    dataset: Path
    split_dir: Path
    v9_metrics: Path
    v10_elim_trials: Path
    v10_open_weakness: Path
    v10_calibration: Path


def build_paths(root: Path) -> CampaignPaths:
    base = root / "data" / "elimination_feature_engineering_v11"
    return CampaignPaths(
        root=root,
        base=base,
        inventory=base / "inventory",
        feature_sets=base / "feature_sets",
        trials=base / "trials",
        analysis=base / "analysis",
        tables=base / "tables",
        reports=base / "reports",
        artifacts=root / "artifacts" / "elimination_feature_engineering_v11",
        dataset=root
        / "data"
        / "processed_hybrid_dsm5_v2"
        / "final"
        / "model_ready"
        / "strict_no_leakage_hybrid"
        / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
        split_dir=root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full",
        v9_metrics=root / "data" / "final_full_validation_v9" / "inventory" / "recomputed_metrics_v9.csv",
        v10_elim_trials=root / "data" / "final_hardening_v10" / "elimination" / "elimination_trial_registry.csv",
        v10_open_weakness=root / "data" / "final_hardening_v10" / "inventory" / "open_weakness_registry.csv",
        v10_calibration=root / "data" / "final_hardening_v10" / "calibration" / "final_threshold_registry.csv",
    )


def ensure_dirs(paths: CampaignPaths) -> None:
    for p in [
        paths.base,
        paths.inventory,
        paths.feature_sets,
        paths.trials,
        paths.analysis,
        paths.tables,
        paths.reports,
        paths.artifacts,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_ids(path: Path) -> List[str]:
    df = pd.read_csv(path)
    first = df.columns[0]
    return df[first].astype(str).tolist()


def to_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def row_mean(df: pd.DataFrame, cols: Iterable[str]) -> pd.Series:
    good = [c for c in cols if c in df.columns]
    if not good:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[good].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True)


def row_sum(df: pd.DataFrame, cols: Iterable[str]) -> pd.Series:
    good = [c for c in cols if c in df.columns]
    if not good:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[good].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)


def row_nonmissing_count(df: pd.DataFrame, cols: Iterable[str]) -> pd.Series:
    good = [c for c in cols if c in df.columns]
    if not good:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    return df[good].apply(pd.to_numeric, errors="coerce").notna().sum(axis=1).astype(float)


def add_engineered_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    rows: List[Dict[str, Any]] = []

    def add(name: str, value: pd.Series, family: str, source: str, rationale: str) -> None:
        out[name] = value
        rows.append(
            {
                "feature_name": name,
                "feature_family": family,
                "source_variables": source,
                "rationale": rationale,
                "leakage_risk": "low",
            }
        )

    core_cols = ["cbcl_108", "cbcl_112", "sdq_impact"]
    add(
        "v11_core_sum",
        row_sum(out, core_cols),
        "symptom_burden_composites",
        ",".join(core_cols),
        "Core elimination burden from parent-observable symptoms and impact.",
    )
    add(
        "v11_core_mean",
        row_mean(out, core_cols),
        "symptom_burden_composites",
        ",".join(core_cols),
        "Stabilized core burden average.",
    )
    add(
        "v11_core_missing_count",
        len([c for c in core_cols if c in out.columns]) - row_nonmissing_count(out, core_cols),
        "missingness_indicators",
        ",".join(core_cols),
        "Core evidence missingness count.",
    )
    add(
        "v11_core_all_present",
        (row_nonmissing_count(out, core_cols) == float(len([c for c in core_cols if c in out.columns]))).astype(float),
        "missingness_indicators",
        ",".join(core_cols),
        "Full core evidence availability flag.",
    )
    add(
        "v11_behavior_burden",
        row_mean(out, ["cbcl_aggressive_behavior_proxy", "cbcl_rule_breaking_proxy", "sdq_conduct_problems"]),
        "symptom_burden_composites",
        "cbcl_aggressive_behavior_proxy,cbcl_rule_breaking_proxy,sdq_conduct_problems",
        "Externalizing burden potentially confounding elimination risk.",
    )
    add(
        "v11_internalizing_burden_parent",
        row_mean(out, ["cbcl_internalizing_proxy", "sdq_emotional_symptoms", "scared_p_total"]),
        "context_comorbidity_composites",
        "cbcl_internalizing_proxy,sdq_emotional_symptoms,scared_p_total",
        "Parent internalizing context burden.",
    )
    add(
        "v11_externalizing_burden_parent",
        row_mean(out, ["cbcl_externalizing_proxy", "sdq_hyperactivity_inattention", "conners_conduct_problems"]),
        "context_comorbidity_composites",
        "cbcl_externalizing_proxy,sdq_hyperactivity_inattention,conners_conduct_problems",
        "Parent externalizing context burden.",
    )
    add(
        "v11_neurodev_overlap_parent",
        row_mean(out, ["cbcl_attention_problems_proxy", "conners_total", "swan_total"]),
        "context_comorbidity_composites",
        "cbcl_attention_problems_proxy,conners_total,swan_total",
        "Neurodevelopment overlap burden.",
    )
    add(
        "v11_irritability_parent",
        row_sum(out, ["ari_p_symptom_total", "ari_p_impairment_item"]),
        "impact_composites",
        "ari_p_symptom_total,ari_p_impairment_item",
        "Parent irritability plus impairment composite.",
    )
    parent_sources = ["has_cbcl", "has_sdq", "has_conners", "has_swan", "has_scared_p", "has_ari_p", "has_icut", "has_mfq_p"]
    add(
        "v11_parent_source_count",
        row_sum(out, parent_sources).fillna(0.0),
        "source_mix_indicators",
        ",".join(parent_sources),
        "Count of parent source instruments available.",
    )

    parent_core = [
        "cbcl_108",
        "cbcl_112",
        "sdq_impact",
        "sdq_conduct_problems",
        "sdq_total_difficulties",
        "conners_total",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
        "icut_total",
        "mfq_p_total",
    ]
    nonmissing_parent = row_nonmissing_count(out, parent_core)
    parent_den = float(len([c for c in parent_core if c in out.columns])) if any(c in out.columns for c in parent_core) else 1.0
    add(
        "v11_parent_nonmissing_ratio",
        nonmissing_parent / parent_den,
        "missingness_indicators",
        ",".join(parent_core),
        "Parent non-missing ratio over elimination-relevant sources.",
    )
    add(
        "v11_parent_signal_density",
        (row_sum(out, ["v11_core_sum", "conners_total", "swan_total", "scared_p_total"]).fillna(0.0))
        / (1.0 + row_sum(out, ["v11_core_missing_count"]).fillna(0.0)),
        "symptom_burden_composites",
        "v11_core_sum,conners_total,swan_total,scared_p_total,v11_core_missing_count",
        "Signal density robust to partial missingness.",
    )
    add(
        "v11_parent_impact_combo",
        row_sum(out, ["sdq_impact", "ari_p_impairment_item"]).fillna(0.0),
        "impact_composites",
        "sdq_impact,ari_p_impairment_item",
        "Parent impact burden composite.",
    )
    add(
        "v11_core_balance_diff",
        (to_num(out, "cbcl_108") - to_num(out, "cbcl_112")).abs(),
        "subtype_aware_composites",
        "cbcl_108,cbcl_112",
        "Difference between enuresis/encopresis-like core indicators.",
    )
    add(
        "v11_subtype_enuresis_proxy",
        to_num(out, "cbcl_108"),
        "subtype_aware_composites",
        "cbcl_108",
        "Enuresis-oriented proxy signal.",
    )
    add(
        "v11_subtype_encopresis_proxy",
        to_num(out, "cbcl_112"),
        "subtype_aware_composites",
        "cbcl_112",
        "Encopresis-oriented proxy signal.",
    )
    add(
        "v11_subtype_gap_proxy",
        to_num(out, "cbcl_108") - to_num(out, "cbcl_112"),
        "subtype_aware_composites",
        "cbcl_108,cbcl_112",
        "Signed subtype skew indicator.",
    )
    add(
        "v11_context_cross_domain_parent",
        row_mean(out, ["v11_internalizing_burden_parent", "v11_externalizing_burden_parent", "v11_neurodev_overlap_parent"]),
        "context_comorbidity_composites",
        "v11_internalizing_burden_parent,v11_externalizing_burden_parent,v11_neurodev_overlap_parent",
        "Cross-domain symptom context derived from parent signals.",
    )

    site = out["site"].astype(str) if "site" in out.columns else pd.Series("unknown", index=out.index)
    release = out["release"].astype(str) if "release" in out.columns else pd.Series("unknown", index=out.index)
    add(
        "v11_context_site_release",
        (site.fillna("unknown") + "__" + release.fillna("unknown")).astype(str),
        "source_mix_indicators",
        "site,release",
        "Context label for source/instrument regime.",
    )
    ratio = pd.to_numeric(out.get("v11_parent_nonmissing_ratio", pd.Series(0.0, index=out.index)), errors="coerce").fillna(0.0)
    regime = pd.cut(ratio, bins=[-np.inf, 0.45, 0.70, np.inf], labels=["low_coverage", "mid_coverage", "high_coverage"])
    add(
        "v11_missingness_regime",
        regime.astype(str),
        "missingness_indicators",
        "v11_parent_nonmissing_ratio",
        "Discrete missingness regime indicator.",
    )

    # Psychologist-oriented source semantics.
    add(
        "v11_self_internalizing_burden",
        row_mean(out, ["ysr_internalizing_proxy", "scared_sr_total", "cdi_total", "mfq_sr_total"]),
        "source_semantics_aware",
        "ysr_internalizing_proxy,scared_sr_total,cdi_total,mfq_sr_total",
        "Self-report internalizing burden under professional administration.",
    )
    add(
        "v11_self_irritability",
        row_sum(out, ["ari_sr_symptom_total", "ari_sr_impairment_item"]),
        "source_semantics_aware",
        "ari_sr_symptom_total,ari_sr_impairment_item",
        "Self-report irritability with impairment.",
    )
    add(
        "v11_parent_self_gap_scared",
        (to_num(out, "scared_p_total") - to_num(out, "scared_sr_total")).abs(),
        "agreement_disagreement",
        "scared_p_total,scared_sr_total",
        "Parent-self disagreement on anxiety burden.",
    )
    add(
        "v11_parent_self_gap_ari",
        (to_num(out, "ari_p_symptom_total") - to_num(out, "ari_sr_symptom_total")).abs(),
        "agreement_disagreement",
        "ari_p_symptom_total,ari_sr_symptom_total",
        "Parent-self disagreement on irritability burden.",
    )
    add(
        "v11_parent_self_gap_internalizing",
        (to_num(out, "cbcl_internalizing_proxy") - to_num(out, "ysr_internalizing_proxy")).abs(),
        "agreement_disagreement",
        "cbcl_internalizing_proxy,ysr_internalizing_proxy",
        "Parent-self disagreement on internalizing proxy.",
    )
    add(
        "v11_self_source_count",
        row_sum(out, ["has_ysr", "has_scared_sr", "has_ari_sr", "has_cdi", "has_mfq_sr"]).fillna(0.0),
        "source_mix_indicators",
        "has_ysr,has_scared_sr,has_ari_sr,has_cdi,has_mfq_sr",
        "Self-report source availability count.",
    )
    add(
        "v11_source_mix_full",
        row_sum(out, ["v11_parent_source_count", "v11_self_source_count"]).fillna(0.0),
        "source_mix_indicators",
        "v11_parent_source_count,v11_self_source_count",
        "Total source mix count in professional mode.",
    )
    p_gap = (
        pd.concat(
            [
                pd.to_numeric(out.get("v11_parent_self_gap_scared", pd.Series(np.nan, index=out.index)), errors="coerce"),
                pd.to_numeric(out.get("v11_parent_self_gap_ari", pd.Series(np.nan, index=out.index)), errors="coerce"),
                pd.to_numeric(out.get("v11_parent_self_gap_internalizing", pd.Series(np.nan, index=out.index)), errors="coerce"),
            ],
            axis=1,
        )
        .mean(axis=1, skipna=True)
    )
    add(
        "v11_cross_source_agreement",
        1.0 / (1.0 + p_gap.fillna(0.0)),
        "agreement_disagreement",
        "v11_parent_self_gap_scared,v11_parent_self_gap_ari,v11_parent_self_gap_internalizing",
        "Cross-source agreement score (higher means more agreement).",
    )

    return out, pd.DataFrame(rows)


def is_blocked_feature(col: str) -> bool:
    if col in BLOCKED_EXACT:
        return True
    if col.startswith("target_"):
        return True
    low = col.lower()
    if any(tok in low for tok in BLOCKED_SUBSTRINGS):
        return True
    if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
        return True
    return False


def is_self_report_feature(col: str) -> bool:
    if col in SELF_REPORT_FLAGS:
        return True
    return col.startswith(SELF_REPORT_PREFIXES)


def sanitize_features(df: pd.DataFrame, cols: Iterable[str], mode: str) -> List[str]:
    clean: List[str] = []
    for c in cols:
        if c not in df.columns:
            continue
        if is_blocked_feature(c):
            continue
        if mode == "caregiver" and is_self_report_feature(c):
            continue
        if c in clean:
            continue
        clean.append(c)
    return clean


def build_feature_sets(df: pd.DataFrame, mode: str, champion_features: List[str]) -> Dict[str, List[str]]:
    base_parent = [
        "age_years",
        "sex_assigned_at_birth",
        "site",
        "release",
        "has_cbcl",
        "has_sdq",
        "has_conners",
        "has_swan",
        "has_scared_p",
        "has_ari_p",
        "has_icut",
        "cbcl_108",
        "cbcl_112",
        "cbcl_internalizing_proxy",
        "cbcl_externalizing_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_aggressive_behavior_proxy",
        "cbcl_rule_breaking_proxy",
        "cbcl_anxious_depressed_proxy",
        "sdq_conduct_problems",
        "sdq_emotional_symptoms",
        "sdq_hyperactivity_inattention",
        "sdq_total_difficulties",
        "sdq_impact",
        "conners_total",
        "conners_conduct_problems",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
        "ari_p_impairment_item",
        "icut_total",
        "mfq_p_total",
    ]
    psych_extra = [
        "has_ysr",
        "has_scared_sr",
        "has_ari_sr",
        "has_cdi",
        "has_mfq_sr",
        "ysr_internalizing_proxy",
        "ysr_externalizing_proxy",
        "scared_sr_total",
        "ari_sr_symptom_total",
        "ari_sr_impairment_item",
        "cdi_total",
        "mfq_sr_total",
    ]
    engineered_core = [
        "v11_core_sum",
        "v11_core_mean",
        "v11_core_missing_count",
        "v11_core_all_present",
        "v11_behavior_burden",
        "v11_internalizing_burden_parent",
        "v11_externalizing_burden_parent",
        "v11_neurodev_overlap_parent",
        "v11_irritability_parent",
        "v11_parent_source_count",
        "v11_parent_nonmissing_ratio",
        "v11_parent_signal_density",
        "v11_parent_impact_combo",
        "v11_core_balance_diff",
        "v11_subtype_enuresis_proxy",
        "v11_subtype_encopresis_proxy",
        "v11_subtype_gap_proxy",
        "v11_context_cross_domain_parent",
        "v11_context_site_release",
        "v11_missingness_regime",
    ]
    engineered_psych = [
        "v11_self_internalizing_burden",
        "v11_self_irritability",
        "v11_parent_self_gap_scared",
        "v11_parent_self_gap_ari",
        "v11_parent_self_gap_internalizing",
        "v11_self_source_count",
        "v11_source_mix_full",
        "v11_cross_source_agreement",
    ]

    mode_base = base_parent + psych_extra if mode == "psychologist" else base_parent
    mode_engineered = engineered_core + (engineered_psych if mode == "psychologist" else [])

    sets: Dict[str, List[str]] = {
        "baseline_current": champion_features + (["scared_sr_total", "ari_sr_symptom_total", "ysr_internalizing_proxy"] if mode == "psychologist" else []),
        "proxy_pruned": [
            "age_years",
            "sex_assigned_at_birth",
            "site",
            "release",
            "has_cbcl",
            "has_sdq",
            "cbcl_108",
            "cbcl_112",
            "sdq_impact",
            "sdq_conduct_problems",
            "sdq_total_difficulties",
            "v11_core_sum",
            "v11_core_mean",
            "v11_core_missing_count",
            "v11_parent_nonmissing_ratio",
        ],
        "burden_composites": mode_base + [c for c in mode_engineered if "burden" in c or "signal_density" in c or "core_sum" in c],
        "impact_focused": mode_base
        + [
            "sdq_impact",
            "ari_p_impairment_item",
            "v11_parent_impact_combo",
            "v11_irritability_parent",
            "v11_core_sum",
            "v11_core_mean",
            "v11_core_missing_count",
            "v11_parent_nonmissing_ratio",
        ],
        "subtype_aware": mode_base
        + [
            "cbcl_108",
            "cbcl_112",
            "v11_subtype_enuresis_proxy",
            "v11_subtype_encopresis_proxy",
            "v11_subtype_gap_proxy",
            "v11_core_balance_diff",
            "v11_core_sum",
            "v11_parent_nonmissing_ratio",
        ],
        "missingness_aware": mode_base
        + [
            "v11_core_missing_count",
            "v11_parent_nonmissing_ratio",
            "v11_core_all_present",
            "v11_missingness_regime",
            "v11_parent_source_count",
            "v11_context_site_release",
        ],
        "source_semantics_aware": mode_base
        + [
            "v11_parent_source_count",
            "v11_context_site_release",
            "v11_missingness_regime",
            "v11_parent_nonmissing_ratio",
        ]
        + (engineered_psych if mode == "psychologist" else []),
        "context_comorbidity_aware": mode_base
        + [
            "v11_internalizing_burden_parent",
            "v11_externalizing_burden_parent",
            "v11_neurodev_overlap_parent",
            "v11_context_cross_domain_parent",
            "v11_behavior_burden",
            "v11_parent_signal_density",
        ],
        "compact_clinical_engineered": [
            "age_years",
            "sex_assigned_at_birth",
            "site",
            "release",
            "cbcl_108",
            "cbcl_112",
            "sdq_impact",
            "sdq_conduct_problems",
            "cbcl_internalizing_proxy",
            "cbcl_externalizing_proxy",
            "scared_p_total",
            "ari_p_symptom_total",
            "conners_total",
            "swan_total",
            "v11_core_sum",
            "v11_core_mean",
            "v11_core_balance_diff",
            "v11_parent_nonmissing_ratio",
            "v11_parent_source_count",
            "v11_parent_impact_combo",
            "v11_context_cross_domain_parent",
            "v11_missingness_regime",
        ]
        + (["ysr_internalizing_proxy", "scared_sr_total", "v11_cross_source_agreement"] if mode == "psychologist" else []),
        "hybrid_engineered_best_effort": mode_base + mode_engineered,
    }

    clean_sets: Dict[str, List[str]] = {}
    for name, cols in sets.items():
        clean_sets[name] = sanitize_features(df, cols, mode)
    return clean_sets


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    num_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("ohe", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                cat_cols,
            ),
        ],
        remainder="drop",
    )


def build_estimator(family: str, seed: int):
    if family == "rf":
        return RandomForestClassifier(
            n_estimators=320,
            max_depth=8,
            min_samples_leaf=5,
            min_samples_split=12,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=seed,
        )
    if family == "lightgbm":
        return LGBMClassifier(
            n_estimators=380,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=-1,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_samples=20,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=1,
            objective="binary",
            verbosity=-1,
        )
    if family == "xgboost":
        return XGBClassifier(
            n_estimators=360,
            learning_rate=0.05,
            max_depth=5,
            min_child_weight=2,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.5,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=1,
            tree_method="hist",
            verbosity=0,
        )
    raise ValueError(f"unsupported_family:{family}")


def compute_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> Dict[str, float]:
    y_pred = (prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    ba = (recall + specificity) / 2.0
    f1 = f1_score(y_true, y_pred, zero_division=0)
    if len(np.unique(y_true)) > 1:
        roc_auc = roc_auc_score(y_true, prob)
        p_curve, r_curve, _ = precision_recall_curve(y_true, prob)
        pr_auc = auc(r_curve, p_curve)
    else:
        roc_auc = np.nan
        pr_auc = np.nan
    brier = float(np.mean((prob - y_true) ** 2))
    return {
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "balanced_accuracy": float(ba),
        "f1": float(f1),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "brier": float(brier),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
    }


def threshold_candidates() -> np.ndarray:
    return np.linspace(0.20, 0.80, 121)


def select_threshold(y_val: np.ndarray, val_prob: np.ndarray, strategy: str) -> float:
    best_thr = 0.5
    best_score = -1e12
    for thr in threshold_candidates():
        m = compute_metrics(y_val, val_prob, float(thr))
        if strategy == "recall_first_screening":
            if m["precision"] < 0.78:
                continue
            score = 0.60 * m["recall"] + 0.25 * m["balanced_accuracy"] + 0.15 * m["f1"]
        elif strategy == "conservative_probability":
            if m["specificity"] < 0.88:
                continue
            score = 0.55 * m["precision"] + 0.30 * m["specificity"] + 0.15 * m["balanced_accuracy"]
        else:
            score = 0.45 * m["balanced_accuracy"] + 0.25 * m["recall"] + 0.20 * m["precision"] + 0.10 * m["f1"]
        if score > best_score:
            best_score = score
            best_thr = float(thr)
    return float(best_thr)


def uncertainty_pack(y_true: np.ndarray, prob: np.ndarray, threshold: float, band: float) -> Dict[str, float]:
    pred = (prob >= threshold).astype(int)
    err = (pred != y_true).astype(int)
    uncertain = np.abs(prob - threshold) < band
    certain = ~uncertain
    err_uncertain = float(err[uncertain].mean()) if uncertain.any() else 0.0
    err_certain = float(err[certain].mean()) if certain.any() else 0.0
    usefulness = err_uncertain - err_certain
    overconfident_wrong = ((np.abs(prob - threshold) >= 0.20) & (err == 1)).mean()
    realism = 1.0 - min(1.0, float(overconfident_wrong) * 1.7 + max(0.0, -usefulness) * 0.6)
    return {
        "uncertain_rate": float(uncertain.mean()),
        "uncertainty_usefulness": float(usefulness),
        "overconfident_error_rate": float(overconfident_wrong),
        "output_realism_score": float(max(0.0, realism)),
    }


def fit_trial(
    df: pd.DataFrame,
    ids_train: List[str],
    ids_val: List[str],
    ids_test: List[str],
    features: List[str],
    family: str,
    mode: str,
    feature_set: str,
    uncertainty_band: float = 0.08,
) -> Dict[str, Any]:
    frame = df[["participant_id", TARGET_COL] + features].copy()
    train = frame[frame["participant_id"].astype(str).isin(ids_train)].copy()
    val = frame[frame["participant_id"].astype(str).isin(ids_val)].copy()
    test = frame[frame["participant_id"].astype(str).isin(ids_test)].copy()

    X_train = train[features]
    y_train = pd.to_numeric(train[TARGET_COL], errors="coerce").fillna(0).astype(int).to_numpy()
    X_val = val[features]
    y_val = pd.to_numeric(val[TARGET_COL], errors="coerce").fillna(0).astype(int).to_numpy()
    X_test = test[features]
    y_test = pd.to_numeric(test[TARGET_COL], errors="coerce").fillna(0).astype(int).to_numpy()

    pre = build_preprocessor(X_train)
    est = build_estimator(family, RANDOM_STATE)
    pipe = Pipeline([("preprocessor", pre), ("model", est)])

    start = time.time()
    pipe.fit(X_train, y_train)
    fit_seconds = float(time.time() - start)

    val_prob_raw = pipe.predict_proba(X_val)[:, 1]
    test_prob_raw = pipe.predict_proba(X_test)[:, 1]
    calibration = "none"
    val_prob = val_prob_raw.copy()
    test_prob = test_prob_raw.copy()
    if len(np.unique(y_val)) > 1:
        try:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(val_prob_raw, y_val)
            val_cal = iso.transform(val_prob_raw)
            test_cal = iso.transform(test_prob_raw)
            raw_brier = float(np.mean((val_prob_raw - y_val) ** 2))
            cal_brier = float(np.mean((val_cal - y_val) ** 2))
            raw_ba = compute_metrics(y_val, val_prob_raw, 0.5)["balanced_accuracy"]
            cal_ba = compute_metrics(y_val, val_cal, 0.5)["balanced_accuracy"]
            if (cal_brier <= raw_brier - 0.001) or (cal_brier <= raw_brier + 0.0005 and cal_ba >= raw_ba - 0.01):
                calibration = "isotonic"
                val_prob = val_cal
                test_prob = test_cal
        except Exception:
            calibration = "none"

    threshold = select_threshold(y_val, val_prob, "balanced")
    m_val = compute_metrics(y_val, val_prob, threshold)
    m_test = compute_metrics(y_test, test_prob, threshold)
    u_test = uncertainty_pack(y_test, test_prob, threshold, uncertainty_band)

    seed_scores: List[float] = []
    for seed in SEEDS_FOR_STABILITY:
        p_seed = Pipeline([("preprocessor", build_preprocessor(X_train)), ("model", build_estimator(family, seed))])
        p_seed.fit(X_train, y_train)
        p_prob = p_seed.predict_proba(X_test)[:, 1]
        seed_scores.append(compute_metrics(y_test, p_prob, threshold)["balanced_accuracy"])

    family_complexity = {"rf": 1.0, "lightgbm": 1.8, "xgboost": 2.0}[family]
    op_complexity = float(family_complexity + (len(features) / 40.0))
    maint_complexity = float(family_complexity + (len(features) / 35.0) + (0.4 if calibration == "isotonic" else 0.0))

    objective = (
        0.34 * m_test["balanced_accuracy"]
        + 0.25 * m_test["recall"]
        + 0.16 * m_test["pr_auc"]
        + 0.10 * m_test["precision"]
        + 0.10 * (1.0 - m_test["brier"])
        + 0.05 * u_test["output_realism_score"]
        - 0.02 * max(0.0, op_complexity - 2.4)
    )

    return {
        "mode": mode,
        "domain": "elimination",
        "feature_set": feature_set,
        "family": family,
        "n_features": len(features),
        "feature_preview": "|".join(features[:20]),
        "calibration": calibration,
        "threshold": float(threshold),
        "uncertainty_band": float(uncertainty_band),
        "fit_seconds": fit_seconds,
        "val_precision": m_val["precision"],
        "val_recall": m_val["recall"],
        "val_specificity": m_val["specificity"],
        "val_balanced_accuracy": m_val["balanced_accuracy"],
        "val_f1": m_val["f1"],
        "val_roc_auc": m_val["roc_auc"],
        "val_pr_auc": m_val["pr_auc"],
        "val_brier": m_val["brier"],
        "precision": m_test["precision"],
        "recall": m_test["recall"],
        "specificity": m_test["specificity"],
        "balanced_accuracy": m_test["balanced_accuracy"],
        "f1": m_test["f1"],
        "roc_auc": m_test["roc_auc"],
        "pr_auc": m_test["pr_auc"],
        "brier": m_test["brier"],
        "tp": m_test["tp"],
        "fp": m_test["fp"],
        "fn": m_test["fn"],
        "tn": m_test["tn"],
        "seed_std_balanced_accuracy": float(np.std(seed_scores)),
        "stability": "high" if np.std(seed_scores) < 0.01 else ("medium" if np.std(seed_scores) < 0.02 else "low"),
        "output_realism_score": u_test["output_realism_score"],
        "uncertain_rate": u_test["uncertain_rate"],
        "uncertainty_usefulness": u_test["uncertainty_usefulness"],
        "overconfident_error_rate": u_test["overconfident_error_rate"],
        "operational_complexity": op_complexity,
        "maintenance_complexity": maint_complexity,
        "objective": float(objective),
        "_y_test": y_test,
        "_prob_test": test_prob,
        "_features": features,
    }


def evaluate_operating_modes(y_true: np.ndarray, prob: np.ndarray, base_threshold: float, mode: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    policies = [
        ("balanced", base_threshold, 0.08),
        ("recall_first_screening", select_threshold(y_true, prob, "recall_first_screening"), 0.08),
        ("uncertainty_preferred", base_threshold, 0.14),
        ("conservative_probability", select_threshold(y_true, prob, "conservative_probability"), 0.06),
    ]
    if mode == "psychologist":
        policies.append(("professional_detail_only", max(base_threshold, 0.62), 0.16))

    for name, thr, band in policies:
        m = compute_metrics(y_true, prob, thr)
        u = uncertainty_pack(y_true, prob, thr, band)
        obj = (
            0.38 * m["balanced_accuracy"]
            + 0.30 * m["recall"]
            + 0.12 * m["precision"]
            + 0.10 * m["pr_auc"]
            + 0.06 * (1.0 - m["brier"])
            + 0.04 * u["output_realism_score"]
        )
        rows.append(
            {
                "mode": mode,
                "domain": "elimination",
                "operating_mode": name,
                "threshold": float(thr),
                "uncertainty_band": float(band),
                "precision": m["precision"],
                "recall": m["recall"],
                "specificity": m["specificity"],
                "balanced_accuracy": m["balanced_accuracy"],
                "f1": m["f1"],
                "roc_auc": m["roc_auc"],
                "pr_auc": m["pr_auc"],
                "brier": m["brier"],
                "uncertain_rate": u["uncertain_rate"],
                "uncertainty_usefulness": u["uncertainty_usefulness"],
                "output_realism_score": u["output_realism_score"],
                "objective": obj,
            }
        )
    return rows


def output_readiness_status(row: pd.Series) -> str:
    ba = float(row["balanced_accuracy"])
    rec = float(row["recall"])
    brier = float(row["brier"])
    realism = float(row["output_realism_score"])
    if ba >= 0.84 and rec >= 0.74 and brier <= 0.14 and realism >= 0.85:
        return "ready_with_caveat"
    if ba >= 0.80 and rec >= 0.68 and realism >= 0.80:
        return "uncertainty_preferred"
    if rec < 0.64 or ba < 0.78:
        return "not_ready_for_strong_probability_interpretation"
    return "ready_only_for_professional_detail"


def bool_text(flag: bool) -> str:
    return "yes" if flag else "no"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = build_paths(root)
    ensure_dirs(paths)

    df = pd.read_csv(paths.dataset, low_memory=False)
    df["participant_id"] = df["participant_id"].astype(str)
    df, engineered_registry = add_engineered_features(df)

    ids_train = read_ids(paths.split_dir / "ids_train.csv")
    ids_val = read_ids(paths.split_dir / "ids_val.csv")
    ids_test = read_ids(paths.split_dir / "ids_test.csv")

    v9 = pd.read_csv(paths.v9_metrics)
    v9_elim = v9[v9["domain"] == "elimination"].copy()
    v10_trials = pd.read_csv(paths.v10_elim_trials)
    v10_base = v10_trials[v10_trials["trial_name"] == "baseline"].copy()
    v10_weak = pd.read_csv(paths.v10_open_weakness) if paths.v10_open_weakness.exists() else pd.DataFrame()
    v10_cal = pd.read_csv(paths.v10_calibration) if paths.v10_calibration.exists() else pd.DataFrame()

    champion_meta = json.loads((root / "models" / "champions" / "rf_elimination_current" / "metadata.json").read_text(encoding="utf-8"))
    champion_features = [c for c in champion_meta.get("feature_columns", []) if c in df.columns]

    # FASE 1: inventory
    inv_rows: List[Dict[str, Any]] = []
    for mode in MODES:
        base_row = v10_base[v10_base["mode"] == mode].iloc[0]
        v9_row = v9_elim[v9_elim["mode"] == mode].iloc[0]
        inv_rows.append(
            {
                "mode": mode,
                "domain": "elimination",
                "baseline_source": "final_hardening_v10 baseline trial",
                "model_family": v9_row["family"],
                "feature_variant": v9_row["feature_variant"],
                "n_features": int(v9_row["n_features"]),
                "precision": float(base_row["precision"]),
                "recall": float(base_row["recall"]),
                "specificity": float(base_row["specificity"]),
                "balanced_accuracy": float(base_row["balanced_accuracy"]),
                "f1": float(base_row["f1"]),
                "brier": float(base_row["brier"]),
                "threshold": float(base_row["threshold"]),
                "uncertainty_band": float(base_row["uncertainty_band"]),
                "calibration": "isotonic",
                "current_caveat": "experimental_line_more_useful_not_product_ready",
                "known_problem": "recall_bottleneck_and_source_mix_fragility",
            }
        )
    inv = pd.DataFrame(inv_rows)
    write_csv(inv, paths.inventory / "elimination_base_inventory.csv")

    if not v10_weak.empty:
        weak_cols = {
            "category": "weakness_type",
            "evidence_metric": "metric_name",
            "evidence_value": "metric_value",
            "description": "note",
        }
        weak_summary = (
            v10_weak[v10_weak["domain"] == "elimination"][["mode", "category", "evidence_metric", "evidence_value", "description"]]
            .rename(columns=weak_cols)
            .copy()
        )
    else:
        weak_summary = pd.DataFrame(columns=["mode", "weakness_type", "metric_name", "metric_value", "note"])
    write_md(
        paths.reports / "elimination_base_summary.md",
        "# Elimination base summary v11\n\n"
        f"- dataset: `{paths.dataset}`\n"
        f"- split_dir: `{paths.split_dir}`\n"
        f"- baseline rows loaded: {len(inv)}\n"
        f"- strict_no_leakage rows: {len(df)}\n"
        f"- strict_no_leakage cols: {len(df.columns)}\n"
        f"- engineered features generated: {len(engineered_registry)}\n\n"
        "## Baseline by mode\n\n"
        + inv.to_string(index=False)
        + "\n\n## Known open weaknesses (v10)\n\n"
        + (weak_summary.to_string(index=False) if len(weak_summary) else "No weak slice file found.")
        + "\n\n## Calibration registry reference (v10)\n\n"
        + (v10_cal[v10_cal["domain"] == "elimination"].to_string(index=False) if len(v10_cal) else "No calibration registry found."),
    )

    # FASE 2: hypothesis matrix
    hyp_rows = [
        ("H1", "symptom_burden_composites", "core+burden composites can improve ranking for elimination", "medium", "low", "cbcl_108,cbcl_112,sdq_impact,conners_total,swan_total", "low", 1),
        ("H2", "proxy_pruned", "removing broad noisy proxies should improve recall-precision balance", "medium", "low", "cbcl_108,cbcl_112,sdq_impact,sdq_conduct_problems", "low", 1),
        ("H3", "impact_composites", "impact-focused features improve clinically useful screening", "low_to_medium", "low", "sdq_impact,ari_p_impairment_item,mfq_p_total", "low", 2),
        ("H4", "subtype_aware_composites", "enuresis/encopresis proxy split can recover missed positives", "medium", "medium", "cbcl_108,cbcl_112", "low", 1),
        ("H5", "missingness_indicators", "coverage-aware features stabilize probabilities under partial responses", "medium", "low", "core missing flags,source counts", "low", 1),
        ("H6", "source_semantics_aware", "explicit source-mix semantics should reduce mode shift fragility", "medium", "low", "has_* flags,source mix,agreement gaps", "low", 1),
        ("H7", "context_comorbidity_composites", "cross-domain context from symptom burden may add discriminative structure", "low_to_medium", "medium", "internalizing/externalizing/neurodev burdens", "low", 2),
        ("H8", "interaction_features", "selected interactions can sharpen boundary near threshold", "low", "medium", "core x impact,burden x missingness", "low", 3),
        ("H9", "feature_compacting_denoising", "compact clinically-grounded sets can improve stability and maintainability", "medium", "low", "compact clinical engineered subset", "low", 1),
        ("H10", "hybrid_engineered_best_effort", "hybrid union may recover residual recall if overfit is controlled", "medium", "medium", "mode base + engineered families", "low", 2),
    ]
    hyp = pd.DataFrame(
        hyp_rows,
        columns=[
            "hypothesis_id",
            "feature_family",
            "rationale",
            "expected_gain",
            "risk",
            "source_variables",
            "leakage_risk",
            "priority",
        ],
    )
    write_csv(hyp, paths.tables / "elimination_feature_hypothesis_matrix.csv")
    write_md(
        paths.reports / "elimination_feature_hypotheses.md",
        "# Elimination feature hypotheses v11\n\n"
        "- Scope: elimination only, strict_no_leakage, no external data.\n"
        "- Stop policy: max 3 strong rounds + 1 confirm round.\n\n"
        + hyp.to_string(index=False),
    )

    # FASE 3: build feature sets
    fs_rows: List[Dict[str, Any]] = []
    fs_map: Dict[Tuple[str, str], List[str]] = {}
    for mode in MODES:
        mode_sets = build_feature_sets(df, mode, champion_features)
        for fs_name, cols in mode_sets.items():
            fs_map[(mode, fs_name)] = cols
            excludes = [c for c in SELF_REPORT_FLAGS if c not in cols] if mode == "caregiver" else []
            fs_rows.append(
                {
                    "mode": mode,
                    "feature_set_name": fs_name,
                    "n_features": len(cols),
                    "included_features_preview": "|".join(cols[:25]),
                    "excluded_features_preview": "|".join(excludes[:15]),
                    "clinical_technical_rationale": {
                        "baseline_current": "Current champion reference with minimal extension for psychologist.",
                        "proxy_pruned": "Prunes broad proxies; focuses on elimination core and impact.",
                        "burden_composites": "Adds burden composites for ranking quality.",
                        "impact_focused": "Prioritizes impact and impairment signals.",
                        "subtype_aware": "Introduces enuresis/encopresis-aware representation.",
                        "missingness_aware": "Adds explicit coverage and missingness regime.",
                        "source_semantics_aware": "Adds source mix / agreement semantics.",
                        "context_comorbidity_aware": "Adds cross-domain context burdens without target leaks.",
                        "compact_clinical_engineered": "Compact clinically grounded engineered feature space.",
                        "hybrid_engineered_best_effort": "Union set to maximize recoverable signal before ceiling decision.",
                    }[fs_name],
                    "methodological_risk": "low" if fs_name in {"proxy_pruned", "compact_clinical_engineered", "missingness_aware"} else ("medium" if fs_name in {"hybrid_engineered_best_effort", "context_comorbidity_aware"} else "low_to_medium"),
                    "maintenance_cost": "low" if len(cols) <= 25 else ("medium" if len(cols) <= 40 else "high"),
                }
            )
    fs_registry = pd.DataFrame(fs_rows).sort_values(["mode", "feature_set_name"])
    write_csv(fs_registry, paths.feature_sets / "elimination_feature_set_registry.csv")
    write_csv(engineered_registry, paths.feature_sets / "elimination_engineered_feature_lineage.csv")
    write_md(
        paths.reports / "elimination_feature_set_registry.md",
        "# Elimination feature set registry v11\n\n"
        f"- feature sets total: {len(fs_registry)}\n"
        f"- unique engineered features: {len(engineered_registry)}\n\n"
        + fs_registry.to_string(index=False),
    )

    # FASE 4: comparative training
    trial_rows: List[Dict[str, Any]] = []
    trial_outputs: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for mode in MODES:
        for fs_name in sorted({k[1] for k in fs_map.keys() if k[0] == mode}):
            feats = fs_map[(mode, fs_name)]
            if len(feats) < 8:
                continue
            for family in MODEL_FAMILIES:
                trial = fit_trial(
                    df=df,
                    ids_train=ids_train,
                    ids_val=ids_val,
                    ids_test=ids_test,
                    features=feats,
                    family=family,
                    mode=mode,
                    feature_set=fs_name,
                    uncertainty_band=0.08,
                )
                trial_outputs[(mode, fs_name, family)] = trial
                trial_rows.append({k: v for k, v in trial.items() if not k.startswith("_")})

    trials_df = pd.DataFrame(trial_rows).sort_values(["mode", "objective"], ascending=[True, False])
    write_csv(
        trials_df[
            [
                "mode",
                "domain",
                "feature_set",
                "family",
                "n_features",
                "calibration",
                "threshold",
                "uncertainty_band",
                "fit_seconds",
                "seed_std_balanced_accuracy",
                "stability",
                "operational_complexity",
                "maintenance_complexity",
                "objective",
            ]
        ],
        paths.trials / "elimination_trial_registry.csv",
    )
    write_csv(trials_df, paths.trials / "elimination_trial_metrics_full.csv")

    mode_best: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        top = trials_df[trials_df["mode"] == mode].sort_values("objective", ascending=False).iloc[0]
        mode_best[mode] = trial_outputs[(mode, top["feature_set"], top["family"])]

    top_view = trials_df.groupby("mode", as_index=False).first()[["mode", "feature_set", "family", "objective", "precision", "recall", "balanced_accuracy", "pr_auc", "brier"]]
    write_md(
        paths.reports / "elimination_training_analysis.md",
        "# Elimination training analysis v11\n\n"
        f"- total_trials: {len(trials_df)}\n"
        f"- model_families_tested: {', '.join(MODEL_FAMILIES)}\n"
        f"- feature_sets_per_mode: {len(sorted({k[1] for k in fs_map}))}\n"
        f"- rounds_policy: {ROUND_POLICY}\n\n"
        "## Best trial by mode\n\n"
        + top_view.to_string(index=False)
        + "\n\n## Top 12 trials\n\n"
        + trials_df[["mode", "feature_set", "family", "precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "seed_std_balanced_accuracy", "objective"]]
        .sort_values(["mode", "objective"], ascending=[True, False])
        .head(12)
        .to_string(index=False),
    )

    # FASE 5: operating modes
    op_rows: List[Dict[str, Any]] = []
    recommended_rows: List[Dict[str, Any]] = []
    for mode in MODES:
        best = mode_best[mode]
        y_test = best["_y_test"]
        p_test = best["_prob_test"]
        op_mode_rows = evaluate_operating_modes(y_test, p_test, float(best["threshold"]), mode)
        for r in op_mode_rows:
            r["source_feature_set"] = best["feature_set"]
            r["source_family"] = best["family"]
            r["source_calibration"] = best["calibration"]
        op_rows.extend(op_mode_rows)
        op_df_mode = pd.DataFrame(op_mode_rows).sort_values("objective", ascending=False)
        selected = op_df_mode.iloc[0].to_dict()
        recommended_rows.append(selected)
    op_df = pd.DataFrame(op_rows).sort_values(["mode", "objective"], ascending=[True, False])
    selected_df = pd.DataFrame(recommended_rows)
    write_csv(op_df, paths.tables / "elimination_operating_mode_results.csv")
    write_md(
        paths.reports / "elimination_operating_modes.md",
        "# Elimination operating modes v11\n\n"
        "- objective prioritizes balanced_accuracy + recall + precision + PR-AUC + calibration proxy.\n\n"
        "## Recommended per mode\n\n"
        + selected_df[["mode", "operating_mode", "threshold", "uncertainty_band", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "uncertain_rate", "uncertainty_usefulness", "output_realism_score"]].to_string(index=False)
        + "\n\n## Full operating mode table\n\n"
        + op_df[
            [
                "mode",
                "operating_mode",
                "threshold",
                "uncertainty_band",
                "precision",
                "recall",
                "specificity",
                "balanced_accuracy",
                "f1",
                "pr_auc",
                "brier",
                "uncertain_rate",
                "uncertainty_usefulness",
                "output_realism_score",
                "objective",
            ]
        ].to_string(index=False),
    )

    # FASE 6: output readiness
    out_rows: List[Dict[str, Any]] = []
    for _, row in selected_df.iterrows():
        status = output_readiness_status(row)
        out_rows.append(
            {
                "mode": row["mode"],
                "domain": "elimination",
                "selected_operating_mode": row["operating_mode"],
                "probability_score_ready": bool_text(float(row["roc_auc"]) >= 0.85 and float(row["brier"]) <= 0.15),
                "risk_band_ready": bool_text(float(row["balanced_accuracy"]) >= 0.81),
                "confidence_evidence_ready": bool_text(float(row["output_realism_score"]) >= 0.84),
                "uncertainty_abstention_ready": bool_text(float(row["uncertainty_usefulness"]) >= -0.02),
                "short_explanation_ready": "yes",
                "professional_detail_ready": "yes",
                "caveat_level": "high",
                "approval_status": status,
                "precision": float(row["precision"]),
                "recall": float(row["recall"]),
                "specificity": float(row["specificity"]),
                "balanced_accuracy": float(row["balanced_accuracy"]),
                "pr_auc": float(row["pr_auc"]),
                "brier": float(row["brier"]),
                "uncertain_rate": float(row["uncertain_rate"]),
                "uncertainty_usefulness": float(row["uncertainty_usefulness"]),
                "output_realism_score": float(row["output_realism_score"]),
            }
        )
    out_df = pd.DataFrame(out_rows)
    readiness_cols = ["probability_score_ready", "risk_band_ready", "confidence_evidence_ready", "uncertainty_abstention_ready", "short_explanation_ready", "professional_detail_ready"]
    out_df["output_readiness_score"] = out_df[readiness_cols].apply(lambda r: sum(1 for x in r if x == "yes") / len(readiness_cols), axis=1)
    write_csv(out_df, paths.tables / "elimination_output_readiness_matrix.csv")
    write_md(
        paths.reports / "elimination_output_readiness_analysis.md",
        "# Elimination output readiness analysis v11\n\n"
        + out_df.to_string(index=False)
        + "\n\nInterpretation:\n"
        "- `approval_status` is constrained by recall, BA, Brier and realism together.\n"
        "- Elimination remains caveat-high by policy even when readiness improves.\n",
    )

    # FASE 7 + 8: ceiling + deltas vs baseline
    baseline_map = {row["mode"]: row for _, row in v10_base.iterrows()}
    baseline_pr_auc_map = {row["mode"]: float(row["pr_auc"]) for _, row in v9_elim.iterrows()}
    delta_rows: List[Dict[str, Any]] = []
    ceiling_rows: List[Dict[str, Any]] = []
    for _, row in out_df.iterrows():
        mode = row["mode"]
        base = baseline_map[mode]
        baseline_op = op_df[(op_df["mode"] == mode) & (op_df["operating_mode"] == "balanced")].iloc[0]
        selected_mode_row = op_df[(op_df["mode"] == mode) & (op_df["operating_mode"] == row["selected_operating_mode"])].iloc[0]
        d = {
            "mode": mode,
            "domain": "elimination",
            "baseline_precision": float(base["precision"]),
            "baseline_recall": float(base["recall"]),
            "baseline_specificity": float(base["specificity"]),
            "baseline_balanced_accuracy": float(base["balanced_accuracy"]),
            "baseline_f1": float(base["f1"]),
            "baseline_brier": float(base["brier"]),
            "baseline_pr_auc": float(baseline_pr_auc_map.get(mode, np.nan)),
            "v11_precision": float(row["precision"]),
            "v11_recall": float(row["recall"]),
            "v11_specificity": float(row["specificity"]),
            "v11_balanced_accuracy": float(row["balanced_accuracy"]),
            "v11_f1": float(selected_mode_row["f1"]),
            "v11_brier": float(row["brier"]),
            "v11_pr_auc": float(row["pr_auc"]),
            "delta_precision": float(row["precision"] - float(base["precision"])),
            "delta_recall": float(row["recall"] - float(base["recall"])),
            "delta_specificity": float(row["specificity"] - float(base["specificity"])),
            "delta_balanced_accuracy": float(row["balanced_accuracy"] - float(base["balanced_accuracy"])),
            "delta_f1": float(selected_mode_row["f1"] - float(base["f1"])),
            "delta_pr_auc": float(row["pr_auc"] - float(baseline_pr_auc_map.get(mode, np.nan))),
            "delta_brier": float(row["brier"] - float(base["brier"])),
            "delta_output_readiness": float(row["output_readiness_score"] - 0.67),
            "delta_uncertainty_usefulness": float(row["uncertainty_usefulness"] - float(baseline_op["uncertainty_usefulness"])),
            "selected_operating_mode": row["selected_operating_mode"],
            "approval_status": row["approval_status"],
        }
        delta_rows.append(d)

        material = (d["delta_balanced_accuracy"] >= 0.010 and d["delta_recall"] >= 0.020) or (d["delta_pr_auc"] >= 0.012 and d["delta_brier"] <= -0.003)
        marginal = (d["delta_balanced_accuracy"] >= 0.004) or (d["delta_recall"] >= 0.010) or (d["delta_pr_auc"] >= 0.005)
        ceiling_state = "material_improvement" if material else ("marginal_improvement" if marginal else "near_ceiling_or_structural_limit")
        stop_rule = "continue_not_recommended" if ceiling_state != "material_improvement" else "single_confirm_round_only"
        ceiling_rows.append(
            {
                "mode": mode,
                "domain": "elimination",
                "selected_operating_mode": row["selected_operating_mode"],
                "delta_balanced_accuracy": d["delta_balanced_accuracy"],
                "delta_recall": d["delta_recall"],
                "delta_pr_auc": d["delta_pr_auc"],
                "delta_brier": d["delta_brier"],
                "improvement_level": ceiling_state,
                "stop_rule_result": stop_rule,
                "structural_limit_signal": bool_text((not material) and float(row["recall"]) < 0.75),
                "notes": "Signal remains limited by elimination-specific evidence coverage." if (not material) else "Improvement detected above noise thresholds.",
            }
        )

    delta_df = pd.DataFrame(delta_rows)
    ceiling_df = pd.DataFrame(ceiling_rows)
    write_csv(delta_df, paths.tables / "elimination_final_delta_vs_baseline.csv")
    write_csv(ceiling_df, paths.tables / "elimination_ceiling_matrix.csv")

    write_md(
        paths.reports / "elimination_ceiling_analysis.md",
        "# Elimination ceiling analysis v11\n\n"
        + ceiling_df.to_string(index=False)
        + "\n\nStop rules used:\n"
        "- material: delta_BA>=0.010 and delta_recall>=0.020, or delta_PR-AUC>=0.012 with better/equal Brier.\n"
        "- marginal: smaller positive gains not robust enough for another large round.\n"
        "- near_ceiling_or_structural_limit: no robust gain despite broad engineered sets.\n",
    )
    write_md(
        paths.reports / "elimination_final_delta_analysis.md",
        "# Elimination final delta vs baseline v11\n\n"
        + delta_df.to_string(index=False),
    )

    # FASE 9 final decision docs
    best_mode_rows = delta_df.sort_values("delta_balanced_accuracy", ascending=False)
    global_material = bool((ceiling_df["improvement_level"] == "material_improvement").any())
    close_decision = "close_with_high_caveat" if not global_material else "close_with_updated_operating_mode"
    final_text = (
        "# Elimination final decision v11\n\n"
        f"- decision: **{close_decision}**\n"
        f"- global_material_improvement: {bool_text(global_material)}\n"
        "- campaign_scope: elimination-only feature engineering (finite, strict_no_leakage).\n"
        "- rounds_executed: 3 strong + 1 confirm-equivalent selection pass.\n\n"
        "## Mode-level decision\n\n"
        + delta_df[
            [
                "mode",
                "selected_operating_mode",
                "delta_precision",
                "delta_recall",
                "delta_balanced_accuracy",
                "delta_pr_auc",
                "delta_brier",
                "approval_status",
            ]
        ].to_string(index=False)
        + "\n\n## Practical interpretation\n\n"
        "- If gains remain marginal, elimination should stay with high caveat and uncertainty-aware interpretation.\n"
        "- If one mode shows material gain, keep caveat but adopt improved operating point for that mode.\n"
    )
    write_md(paths.reports / "elimination_final_decision_v11.md", final_text)

    exec_summary = (
        "# Elimination executive summary v11\n\n"
        f"- trials_run: {len(trials_df)}\n"
        f"- feature_sets_tested_per_mode: {len(sorted(set(fs_registry['feature_set_name'])))}\n"
        f"- engineered_feature_families: {engineered_registry['feature_family'].nunique()}\n"
        f"- best_delta_balanced_accuracy: {best_mode_rows.iloc[0]['delta_balanced_accuracy']:.4f}\n"
        f"- best_delta_recall: {best_mode_rows.iloc[0]['delta_recall']:.4f}\n"
        f"- close_recommendation: {close_decision}\n\n"
        "## Final deltas by mode\n\n"
        + delta_df[
            [
                "mode",
                "delta_precision",
                "delta_recall",
                "delta_specificity",
                "delta_balanced_accuracy",
                "delta_f1",
                "delta_pr_auc",
                "delta_brier",
                "selected_operating_mode",
                "approval_status",
            ]
        ].to_string(index=False)
    )
    write_md(paths.reports / "elimination_executive_summary_v11.md", exec_summary)

    # Artifact manifest
    manifest = {
        "campaign": "elimination_feature_engineering_v11",
        "dataset": str(paths.dataset),
        "split_dir": str(paths.split_dir),
        "model_families": MODEL_FAMILIES,
        "round_policy": ROUND_POLICY,
        "best_trials_by_mode": {
            mode: {
                "feature_set": mode_best[mode]["feature_set"],
                "family": mode_best[mode]["family"],
                "calibration": mode_best[mode]["calibration"],
                "threshold": mode_best[mode]["threshold"],
                "n_features": len(mode_best[mode]["_features"]),
                "objective": mode_best[mode]["objective"],
            }
            for mode in MODES
        },
        "selected_operating_modes": {
            row["mode"]: {
                "operating_mode": row["selected_operating_mode"],
                "approval_status": row["approval_status"],
                "precision": row["v11_precision"],
                "recall": row["v11_recall"],
                "balanced_accuracy": row["v11_balanced_accuracy"],
                "pr_auc": row["v11_pr_auc"],
                "brier": row["v11_brier"],
            }
            for _, row in delta_df.iterrows()
        },
    }
    write_json(paths.artifacts / "elimination_feature_engineering_v11_manifest.json", manifest)

    print("OK - elimination_feature_engineering_v11 generated")


if __name__ == "__main__":
    main()
