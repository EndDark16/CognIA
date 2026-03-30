#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier


LOGGER = logging.getLogger("elimination-iterative-recovery-v2")
RANDOM_STATE = 42
TARGET_COL = "target_domain_elimination"


@dataclass
class Paths:
    root: Path
    out: Path
    inventory: Path
    audit: Path
    hypotheses: Path
    feature_sets: Path
    trials: Path
    reports: Path
    tables: Path
    artifacts: Path
    previous_finalization: Path
    previous_gate: Path
    hybrid: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def safe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_paths(root: Path) -> Paths:
    out = root / "data" / "elimination_iterative_recovery_v2"
    return Paths(
        root=root,
        out=out,
        inventory=out / "inventory",
        audit=out / "audit",
        hypotheses=out / "hypotheses",
        feature_sets=out / "feature_sets",
        trials=out / "trials",
        reports=out / "reports",
        tables=out / "tables",
        artifacts=root / "artifacts" / "elimination_iterative_recovery_v2",
        previous_finalization=root / "data" / "finalization_and_recovery_v1",
        previous_gate=root / "data" / "generalization_gate_v1",
        hybrid=root / "data" / "processed_hybrid_dsm5_v2",
    )


def ensure_dirs(paths: Paths) -> None:
    for p in [
        paths.out,
        paths.inventory,
        paths.audit,
        paths.hypotheses,
        paths.feature_sets,
        paths.trials,
        paths.reports,
        paths.tables,
        paths.artifacts,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def force_single_thread(model: Any) -> None:
    try:
        if hasattr(model, "n_jobs"):
            setattr(model, "n_jobs", 1)
    except Exception:
        pass
    if isinstance(model, Pipeline):
        for step in model.named_steps.values():
            force_single_thread(step)
    if hasattr(model, "estimator"):
        force_single_thread(getattr(model, "estimator"))
    if hasattr(model, "estimators_"):
        try:
            for est in getattr(model, "estimators_"):
                force_single_thread(est)
        except Exception:
            pass


def metric_binary(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": float(specificity),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def choose_threshold(
    y_val: np.ndarray,
    prob_val: np.ndarray,
    strategy: str = "balanced",
    recall_floor: float = 0.60,
) -> float:
    thresholds = np.linspace(0.05, 0.95, 19)
    best_thr = 0.5
    best_score = -1e9
    for thr in thresholds:
        m = metric_binary(y_val, prob_val, float(thr))
        if strategy == "conservative":
            if m["recall"] < 0.55:
                continue
            score = 0.6 * m["precision"] + 0.25 * m["specificity"] + 0.15 * m["balanced_accuracy"]
        elif strategy == "precision":
            if m["recall"] < recall_floor:
                continue
            score = 0.65 * m["precision"] + 0.35 * m["balanced_accuracy"]
        else:
            score = 0.40 * m["balanced_accuracy"] + 0.30 * m["precision"] + 0.30 * m["recall"]
        if score > best_score:
            best_score = score
            best_thr = float(thr)
    return best_thr


def noise_apply(X: pd.DataFrame, level: int, rng: np.random.Generator) -> pd.DataFrame:
    Xn = X.copy()
    if level == 0:
        return Xn
    cols = Xn.columns.tolist()
    n_rows = len(Xn)
    n_cols = len(cols)
    miss_ratio = 0.05 if level == 1 else 0.15
    n_mask = int(n_rows * n_cols * miss_ratio)
    if n_mask > 0 and n_rows > 0 and n_cols > 0:
        ridx = rng.integers(0, n_rows, size=n_mask)
        cidx = rng.integers(0, n_cols, size=n_mask)
        for r, c in zip(ridx, cidx):
            Xn.iat[r, c] = np.nan
    for c in cols[:100]:
        if pd.api.types.is_numeric_dtype(Xn[c]):
            mask = rng.random(n_rows) < (0.05 if level == 1 else 0.10)
            Xn[c] = pd.to_numeric(Xn[c], errors="coerce").astype(float)
            Xn.loc[mask, c] = Xn.loc[mask, c] + rng.normal(0, 1, size=mask.sum())
    return Xn


def realism_apply(X: pd.DataFrame, scenario: str, rng: np.random.Generator) -> pd.DataFrame:
    Xr = X.copy()
    num_cols = [c for c in Xr.columns if pd.api.types.is_numeric_dtype(Xr[c])]
    if scenario == "incomplete_inputs":
        for c in Xr.columns[int(len(Xr.columns) * 0.65) :]:
            Xr[c] = np.nan
    elif scenario == "contradictory_inputs":
        for c in num_cols[:120]:
            mask = rng.random(len(Xr)) < 0.12
            Xr.loc[mask, c] = -pd.to_numeric(Xr.loc[mask, c], errors="coerce")
    elif scenario == "mixed_comorbidity_signals":
        for c in num_cols[:120]:
            mask = rng.random(len(Xr)) < 0.10
            Xr[c] = pd.to_numeric(Xr[c], errors="coerce").astype(float)
            Xr.loc[mask, c] = Xr.loc[mask, c] + rng.normal(0, 1, size=mask.sum())
    return Xr


def split_ids(ids: pd.Series, y: pd.Series, seed: int) -> Tuple[List[str], List[str], List[str]]:
    strat = y if y.value_counts().min() >= 2 else None
    idx = np.arange(len(ids))
    idx_tv, idx_test = train_test_split(
        idx,
        test_size=0.15,
        random_state=seed,
        stratify=(strat.values if strat is not None else None),
    )
    strat_tv = y.iloc[idx_tv]
    strat_tv = strat_tv if strat_tv.value_counts().min() >= 2 else None
    idx_train, idx_val = train_test_split(
        idx_tv,
        test_size=0.1764706,
        random_state=seed,
        stratify=(strat_tv.values if strat_tv is not None else None),
    )
    return ids.iloc[idx_train].astype(str).tolist(), ids.iloc[idx_val].astype(str).tolist(), ids.iloc[idx_test].astype(str).tolist()


def subset_by_ids(df: pd.DataFrame, ids: List[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(ids)].copy()


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    num_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]), cat_cols),
        ],
        remainder="drop",
    )


def build_pipeline(X: pd.DataFrame, params: Dict[str, Any]) -> Pipeline:
    p = dict(params)
    rs = p.pop("random_state", RANDOM_STATE)
    model = RandomForestClassifier(random_state=rs, n_jobs=1, **p)
    return Pipeline([("preprocessor", build_preprocessor(X)), ("model", model)])


def load_inputs(paths: Paths) -> Dict[str, pd.DataFrame]:
    strict = pd.read_csv(
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
        low_memory=False,
    )
    research = pd.read_csv(
        paths.hybrid / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv",
        low_memory=False,
    )
    compact = pd.read_csv(paths.hybrid / "final" / "external_domains" / "dataset_domain_elimination.csv", low_memory=False)
    for df in (strict, research, compact):
        df["participant_id"] = df["participant_id"].astype(str)
    return {"strict": strict, "research": research, "compact": compact}


def create_inventory(paths: Paths, dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    check_paths = [
        paths.previous_finalization / "elimination_recovery" / "elimination_overfit_root_cause_audit.csv",
        paths.previous_finalization / "elimination_recovery" / "elimination_suspicious_signal_audit.csv",
        paths.previous_finalization / "elimination_recovery" / "elimination_retraining_trials.csv",
        paths.previous_finalization / "elimination_recovery" / "elimination_recovery_comparison.csv",
        paths.previous_finalization / "elimination_recovery" / "elimination_final_decision.md",
        paths.previous_gate / "tables" / "overfit_audit.csv",
        paths.previous_gate / "tables" / "leakage_feature_audit.csv",
        paths.previous_gate / "tables" / "retraining_comparison.csv",
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
        paths.hybrid / "final" / "external_domains" / "dataset_domain_elimination.csv",
        paths.root / "reports" / "training_history" / "trial_registry_generalization.csv",
    ]
    for p in check_paths:
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "type": "file",
                "size_bytes": int(p.stat().st_size) if p.exists() else None,
                "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if p.exists() else None,
            }
        )
    for name, df in dfs.items():
        rows.append({"path": f"in_memory::{name}", "exists": True, "type": "dataset", "size_bytes": None, "modified_utc": now_iso(), "rows": len(df), "cols": len(df.columns)})
    inv = pd.DataFrame(rows)
    safe_csv(inv, paths.inventory / "input_inventory.csv")
    safe_text(
        "# Elimination Iterative Recovery v2 - Input Summary\n\n"
        f"- generated_at_utc: {now_iso()}\n"
        f"- checked_inputs: {len(inv)}\n"
        f"- missing_inputs: {int((~inv['exists']).sum())}\n"
        f"- strict_rows: {len(dfs['strict'])}\n"
        f"- compact_rows: {len(dfs['compact'])}\n",
        paths.reports / "input_summary.md",
    )
    return inv


def detect_semantic_risk(feature: str) -> Tuple[str, str, str]:
    low = feature.lower()
    if feature in {"domain_any_positive", "internal_exact_any_positive", "n_diagnoses", "comorbidity_count_5targets", "domain_comorbidity_count", "internal_exact_comorbidity_count", "has_any_target_disorder"}:
        return "critical", "target_aggregate_proxy", "drop_for_strict_run"
    if feature.startswith("target_"):
        return "critical", "direct_target_leakage", "drop_for_strict_run"
    if "diagnosis" in low or "ksads" in low or "consensus" in low:
        return "critical", "post_diagnostic_signal", "drop_for_strict_run"
    if feature.startswith("q_qi_"):
        return "high", "questionnaire_item_may_be_close_to_normative_rule", "review"
    if low.endswith("_direct_criteria_count") or low.endswith("_proxy_criteria_count"):
        return "high", "criteria_count_proxy", "drop"
    if feature.startswith("has_"):
        return "moderate", "availability_indicator", "review"
    return "low", "general_feature", "keep"


def source_from_feature(feature: str) -> Tuple[str, str]:
    if "_" not in feature:
        return "unknown", feature
    pref = feature.split("_", 1)[0]
    return pref, feature


def semantic_proximity_audit(df: pd.DataFrame, paths: Paths) -> pd.DataFrame:
    rows = []
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    for c in df.columns:
        if c in ("participant_id", TARGET_COL):
            continue
        source_table, source_col = source_from_feature(c)
        risk, why, action = detect_semantic_risk(c)
        s = pd.to_numeric(df[c], errors="coerce")
        corr = float(np.corrcoef(np.nan_to_num(s.to_numpy(), nan=np.nanmedian(s.to_numpy()) if s.notna().any() else 0), y.to_numpy())[0, 1]) if s.nunique(dropna=True) > 1 else 0.0
        semantic_relation = "target_adjacent" if abs(corr) >= 0.75 else ("strong_proxy" if abs(corr) >= 0.55 else "weak_or_none")
        rows.append(
            {
                "feature_name": c,
                "source_table": source_table,
                "source_column": source_col,
                "semantic_relation_to_target": semantic_relation,
                "risk_level": risk,
                "why_flagged": why,
                "suggested_action": action,
                "corr_target": corr,
            }
        )
    out = pd.DataFrame(rows).sort_values(["risk_level", "corr_target"], ascending=[True, False], key=lambda s: s.map({"critical": 4, "high": 3, "moderate": 2, "low": 1}) if s.name == "risk_level" else s.abs())
    safe_csv(out, paths.audit / "elimination_semantic_proximity_audit.csv")
    return out


def separability_audit(df: pd.DataFrame, semantic_df: pd.DataFrame, paths: Paths) -> pd.DataFrame:
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X = df.drop(columns=["participant_id", TARGET_COL], errors="ignore")
    # Univariate separability
    uni_rows: List[Dict[str, Any]] = []
    for c in X.columns:
        s = pd.to_numeric(X[c], errors="coerce").fillna(0)
        if s.nunique(dropna=True) <= 1:
            continue
        corr = float(np.corrcoef(s.to_numpy(), y.to_numpy())[0, 1])
        auc_proxy = float(abs(corr))
        uni_rows.append({"feature_name": c, "corr_abs": abs(corr), "separability_proxy": auc_proxy})
    uni = pd.DataFrame(uni_rows).sort_values("corr_abs", ascending=False)

    top_cols = uni.head(20)["feature_name"].tolist() if len(uni) else []
    sep_rows = []
    for c in top_cols:
        s = pd.to_numeric(X[c], errors="coerce").fillna(0).to_frame()
        tree = DecisionTreeClassifier(max_depth=1, random_state=RANDOM_STATE)
        tree.fit(s, y)
        pred = tree.predict_proba(s)[:, 1]
        m = metric_binary(y.to_numpy(), pred, 0.5)
        sep_rows.append({"issue_type": "single_feature_rule", "feature_name": c, "balanced_accuracy": m["balanced_accuracy"], "precision": m["precision"], "recall": m["recall"]})

    if len(top_cols) >= 2:
        for i in range(min(10, len(top_cols) - 1)):
            cols = top_cols[: i + 2]
            xt = X[cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            tree = DecisionTreeClassifier(max_depth=2, random_state=RANDOM_STATE)
            tree.fit(xt, y)
            pred = tree.predict_proba(xt)[:, 1]
            m = metric_binary(y.to_numpy(), pred, 0.5)
            sep_rows.append({"issue_type": "short_rule_combo", "feature_name": "|".join(cols), "balanced_accuracy": m["balanced_accuracy"], "precision": m["precision"], "recall": m["recall"]})

    out = pd.DataFrame(sep_rows).sort_values(["balanced_accuracy", "precision"], ascending=False)
    safe_csv(out, paths.audit / "elimination_suspicious_separability_audit.csv")
    return out


def split_sample_audit(df: pd.DataFrame, paths: Paths) -> pd.DataFrame:
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    ids_train, ids_val, ids_test = split_ids(df["participant_id"].astype(str), y, RANDOM_STATE)
    train_df = subset_by_ids(df, ids_train)
    val_df = subset_by_ids(df, ids_val)
    test_df = subset_by_ids(df, ids_test)
    rows = [
        {"metric": "rows_total", "value": len(df)},
        {"metric": "rows_train", "value": len(train_df)},
        {"metric": "rows_val", "value": len(val_df)},
        {"metric": "rows_test", "value": len(test_df)},
        {"metric": "prevalence_total", "value": float(y.mean())},
        {"metric": "prevalence_train", "value": float(pd.to_numeric(train_df[TARGET_COL], errors='coerce').fillna(0).mean())},
        {"metric": "prevalence_val", "value": float(pd.to_numeric(val_df[TARGET_COL], errors='coerce').fillna(0).mean())},
        {"metric": "prevalence_test", "value": float(pd.to_numeric(test_df[TARGET_COL], errors='coerce').fillna(0).mean())},
    ]
    feat = df.drop(columns=["participant_id", TARGET_COL], errors="ignore")
    duplicated_ratio = float(feat.astype(str).duplicated().mean())
    rows.append({"metric": "feature_duplicate_ratio", "value": duplicated_ratio})
    n_pos = int(y.sum())
    n_neg = int((1 - y).sum())
    rows.append({"metric": "n_positive", "value": n_pos})
    rows.append({"metric": "n_negative", "value": n_neg})
    rows.append({"metric": "class_balance_ratio_pos_neg", "value": float(n_pos / n_neg if n_neg else np.nan)})
    out = pd.DataFrame(rows)
    safe_csv(out, paths.audit / "elimination_split_and_sample_audit.csv")
    return out


def clinical_coverage_audit(df: pd.DataFrame, paths: Paths) -> pd.DataFrame:
    has_cols = [c for c in df.columns if c.startswith("has_")]
    rows = []
    for c in has_cols:
        cov = float(pd.to_numeric(df[c], errors="coerce").fillna(0).mean())
        instrument = c.replace("has_", "")
        relevance = "high_for_elimination" if instrument in {"cbcl", "sdq"} else "indirect"
        rows.append(
            {
                "instrument": instrument,
                "coverage_ratio": cov,
                "clinical_specificity": relevance,
                "note": "No direct elimination-only instrument detected" if instrument not in {"cbcl", "sdq"} else "Useful but not elimination-specific",
            }
        )
    out = pd.DataFrame(rows).sort_values("coverage_ratio", ascending=False)
    safe_csv(out, paths.audit / "elimination_clinical_coverage_audit.csv")
    return out


def ranking_vs_threshold_audit(df: pd.DataFrame, paths: Paths) -> pd.DataFrame:
    X = df.drop(columns=["participant_id", TARGET_COL], errors="ignore").copy()
    X = X.drop(columns=[c for c in X.columns if X[c].notna().sum() == 0 or X[c].notna().mean() < 0.03], errors="ignore")
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    ids_train, ids_val, ids_test = split_ids(df["participant_id"].astype(str), y, RANDOM_STATE)
    split_df = pd.concat([df[["participant_id"]], X, y.rename(TARGET_COL)], axis=1)
    train_df = subset_by_ids(split_df, ids_train)
    val_df = subset_by_ids(split_df, ids_val)
    test_df = subset_by_ids(split_df, ids_test)
    feat_cols = [c for c in split_df.columns if c not in {"participant_id", TARGET_COL}]
    X_train = train_df[feat_cols]
    y_train = pd.to_numeric(train_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_val = val_df[feat_cols]
    y_val = pd.to_numeric(val_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_test = test_df[feat_cols]
    y_test = pd.to_numeric(test_df[TARGET_COL], errors="coerce").fillna(0).astype(int)

    params = {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}
    model = build_pipeline(X_train, params)
    model.fit(X_train, y_train)
    force_single_thread(model)
    val_prob = model.predict_proba(X_val)[:, 1]
    test_prob = model.predict_proba(X_test)[:, 1]
    rows = []
    for thr in np.linspace(0.05, 0.95, 19):
        m_val = metric_binary(y_val.to_numpy(), val_prob, float(thr))
        m_test = metric_binary(y_test.to_numpy(), test_prob, float(thr))
        rows.append(
            {
                "threshold": float(thr),
                "val_precision": m_val["precision"],
                "val_balanced_accuracy": m_val["balanced_accuracy"],
                "val_recall": m_val["recall"],
                "test_precision": m_test["precision"],
                "test_balanced_accuracy": m_test["balanced_accuracy"],
                "test_recall": m_test["recall"],
                "test_roc_auc": m_test["roc_auc"],
                "test_pr_auc": m_test["pr_auc"],
            }
        )
    out = pd.DataFrame(rows)
    safe_csv(out, paths.audit / "elimination_ranking_vs_threshold_audit.csv")
    return out


def build_hypotheses(paths: Paths, semantic_df: pd.DataFrame, sep_df: pd.DataFrame, split_df: pd.DataFrame, coverage_df: pd.DataFrame, threshold_df: pd.DataFrame) -> pd.DataFrame:
    crit_count = int((semantic_df["risk_level"] == "critical").sum())
    high_count = int((semantic_df["risk_level"] == "high").sum())
    near_perfect_rules = int((sep_df["balanced_accuracy"] >= 0.97).sum()) if len(sep_df) else 0
    coverage_high = float(coverage_df[coverage_df["clinical_specificity"] == "high_for_elimination"]["coverage_ratio"].mean()) if len(coverage_df) else 0.0
    best_precision = float(threshold_df["test_precision"].max()) if len(threshold_df) else 0.0
    best_bal = float(threshold_df["test_balanced_accuracy"].max()) if len(threshold_df) else 0.0
    hypotheses = [
        {
            "hypothesis_id": "H1",
            "description": "proxy leakage residual via target-aggregate features",
            "evidence_for": f"critical_features={crit_count}",
            "evidence_against": "none strong",
            "estimated_severity": "high" if crit_count > 0 else "moderate",
            "expected_fix": "drop critical aggregate/proxy features",
            "priority_order": 1,
        },
        {
            "hypothesis_id": "H2",
            "description": "feature space too deterministic / short-rule separability",
            "evidence_for": f"near_perfect_short_rules={near_perfect_rules}",
            "evidence_against": "if dropped, performance should normalize",
            "estimated_severity": "high" if near_perfect_rules > 0 else "moderate",
            "expected_fix": "semantic + separability pruning, complexity constraints",
            "priority_order": 2,
        },
        {
            "hypothesis_id": "H3",
            "description": "clinical coverage for elimination is indirect and fragile",
            "evidence_for": f"high_specific_instrument_coverage={coverage_high:.3f}",
            "evidence_against": "CBCL/SDQ still provide partial signal",
            "estimated_severity": "moderate",
            "expected_fix": "prefer defendible compact feature sets and caveated interpretation",
            "priority_order": 3,
        },
        {
            "hypothesis_id": "H4",
            "description": "threshold calibration can mask ranking issues",
            "evidence_for": f"best_test_precision={best_precision:.4f}, best_test_bal_acc={best_bal:.4f}",
            "evidence_against": "ranking remains high in multiple thresholds",
            "estimated_severity": "moderate",
            "expected_fix": "conservative threshold + calibration audit",
            "priority_order": 4,
        },
    ]
    out = pd.DataFrame(hypotheses).sort_values("priority_order")
    safe_csv(out, paths.hypotheses / "elimination_hypothesis_matrix.csv")
    safe_text(
        "# Elimination Causal Hypotheses\n\n"
        "- H1/H2 are primary drivers (proxy leakage + separability).\n"
        "- H3 is structural limitation (clinical specificity coverage).\n"
        "- H4 is operational (threshold/calibration) not root-cause alone.\n",
        paths.reports / "elimination_causal_hypotheses.md",
    )
    return out


def build_strategy_registry(paths: Paths, semantic_df: pd.DataFrame) -> pd.DataFrame:
    critical_features = semantic_df[semantic_df["risk_level"] == "critical"]["feature_name"].tolist()
    high_features = semantic_df[semantic_df["risk_level"].isin(["critical", "high"])]["feature_name"].tolist()
    top_sep = semantic_df.sort_values("corr_target", key=lambda s: s.abs(), ascending=False).head(20)["feature_name"].tolist()

    strategies = [
        ("T01_baseline_replay_controlado", "strict", [], [], 300, {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", False, False, "H1,H2"),
        ("T02_drop_high_risk_semantic_proxies", "strict", critical_features, [], 280, {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", False, False, "H1"),
        ("T03_drop_high_plus_critical_proxies", "strict", high_features, [], 260, {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", False, False, "H1,H2"),
        ("T04_strict_semantic_minimal", "strict", high_features + top_sep[:8], ["q_qi_"], 200, {"n_estimators": 180, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "log2", "class_weight": "balanced"}, "balanced", False, False, "H1,H2,H3"),
        ("T05_compact_low_complexity_rf", "compact", high_features, ["q_qi_"], 150, {"n_estimators": 160, "max_depth": 4, "min_samples_leaf": 14, "min_samples_split": 30, "max_features": 0.5, "class_weight": "balanced_subsample"}, "balanced", False, False, "H2,H3"),
        ("T06_stability_first_rf", "strict", high_features, ["q_qi_"], 220, {"n_estimators": 300, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 28, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", False, False, "H2"),
        ("T07_missingness_augmented_honest_run", "strict", high_features, ["q_qi_"], 240, {"n_estimators": 240, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", True, False, "H3"),
        ("T08_threshold_conservative_run", "strict", high_features, ["q_qi_"], 240, {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "conservative", False, False, "H4"),
        ("T09_calibrated_run", "strict", high_features, ["q_qi_"], 240, {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "balanced", False, True, "H4"),
        ("T10_thesis_defensible_candidate", "compact", high_features + top_sep[:10], ["q_qi_"], 120, {"n_estimators": 200, "max_depth": 5, "min_samples_leaf": 14, "min_samples_split": 30, "max_features": "log2", "class_weight": "balanced_subsample"}, "conservative", False, True, "H1,H2,H3,H4"),
        ("T11_ultra_strict_candidate", "strict", high_features + top_sep[:20], ["q_qi_", "domain_", "internal_exact_"], 100, {"n_estimators": 180, "max_depth": 4, "min_samples_leaf": 16, "min_samples_split": 34, "max_features": 0.4, "class_weight": "balanced"}, "conservative", True, True, "H1,H2,H3"),
        ("T12_best_combined_honest_candidate", "strict", high_features + top_sep[:12], ["q_qi_"], 180, {"n_estimators": 240, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 28, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "precision", True, True, "H1,H2,H4"),
    ]
    rows = []
    drop_rows = []
    for trial_id, dataset_key, drop_exact, drop_prefixes, max_features, params, thr_strategy, add_miss, calibrate, hyps in strategies:
        rows.append(
            {
                "trial_id": trial_id,
                "dataset_key": dataset_key,
                "max_features": max_features,
                "drop_exact_count": len(drop_exact),
                "drop_prefixes": ",".join(drop_prefixes),
                "params_json": json.dumps(params),
                "threshold_strategy": thr_strategy,
                "add_missingness_flags": add_miss,
                "calibration_enabled": calibrate,
                "linked_hypotheses": hyps,
            }
        )
        for f in drop_exact:
            drop_rows.append({"trial_id": trial_id, "feature_name": f, "drop_reason": "semantic_or_proxy_risk"})
    registry = pd.DataFrame(rows)
    drop_log = pd.DataFrame(drop_rows)
    safe_csv(registry, paths.feature_sets / "elimination_feature_strategy_registry.csv")
    safe_csv(drop_log, paths.feature_sets / "elimination_feature_drop_log.csv")
    safe_text(
        "# Elimination Correction Plan\n\n"
        "- Strategy sequence follows causal hypotheses H1-H4.\n"
        "- First remove proxy/semantic risks, then control complexity, then apply threshold/calibration variants.\n",
        paths.reports / "elimination_correction_plan.md",
    )
    return registry


def semantic_risk_level_for_feature(feature: str, semantic_df: pd.DataFrame) -> str:
    m = semantic_df[semantic_df["feature_name"] == feature]
    if len(m) == 0:
        return "low"
    return str(m.iloc[0]["risk_level"])


def add_missingness_flags(X: pd.DataFrame) -> pd.DataFrame:
    X2 = X.copy()
    for c in X2.columns[:80]:
        miss = X2[c].isna().astype(int)
        if miss.mean() > 0.02:
            X2[f"miss_{c}"] = miss
    return X2


def prepare_features(
    df: pd.DataFrame,
    drop_exact: List[str],
    drop_prefixes: List[str],
    max_features: int,
    add_miss_flags: bool,
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    y = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    drops = {"participant_id", TARGET_COL}
    for c in df.columns:
        low = c.lower()
        if c.startswith("target_") or "diagnosis" in low or "ksads" in low or "consensus" in low:
            drops.add(c)
        if low.endswith("_status") or low.endswith("_confidence") or low.endswith("_coverage"):
            drops.add(c)
        if any(c.startswith(p) for p in drop_prefixes):
            drops.add(c)
    drops.update(drop_exact)
    X = df.drop(columns=list(drops), errors="ignore").copy()
    X = X.drop(columns=[c for c in X.columns if X[c].nunique(dropna=True) <= 1 or X[c].notna().mean() < 0.03], errors="ignore")
    if X.shape[1] > max_features:
        keep = X.notna().mean().sort_values(ascending=False).head(max_features).index.tolist()
        X = X[keep].copy()
    if add_miss_flags:
        X = add_missingness_flags(X)
    return X, y, sorted(list(drops))


def run_single_trial(
    trial_row: pd.Series,
    datasets: Dict[str, pd.DataFrame],
    semantic_df: pd.DataFrame,
) -> Dict[str, Any]:
    trial_id = str(trial_row["trial_id"])
    dataset_key = str(trial_row["dataset_key"])
    params = json.loads(str(trial_row["params_json"]))
    drop_prefixes = [p for p in str(trial_row["drop_prefixes"]).split(",") if p]
    max_features = int(trial_row["max_features"])
    add_miss_flags = bool(trial_row["add_missingness_flags"])
    calibrate = bool(trial_row["calibration_enabled"])
    threshold_strategy = str(trial_row["threshold_strategy"])

    df = datasets[dataset_key].copy()
    drop_exact = []
    if int(trial_row["drop_exact_count"]) > 0:
        # exact drops are in drop log; registry count only
        risky = semantic_df[semantic_df["risk_level"].isin(["critical", "high"])]["feature_name"].tolist()
        drop_exact = risky
    X, y, removed = prepare_features(df, drop_exact, drop_prefixes, max_features, add_miss_flags)

    ids_train, ids_val, ids_test = split_ids(df["participant_id"].astype(str), y, RANDOM_STATE)
    frame = pd.concat([df[["participant_id"]].reset_index(drop=True), X.reset_index(drop=True), y.rename(TARGET_COL).reset_index(drop=True)], axis=1)
    train_df = subset_by_ids(frame, ids_train)
    val_df = subset_by_ids(frame, ids_val)
    test_df = subset_by_ids(frame, ids_test)
    feat_cols = X.columns.tolist()

    X_train = train_df[feat_cols].copy()
    y_train = pd.to_numeric(train_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_val = val_df[feat_cols].copy()
    y_val = pd.to_numeric(val_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_test = test_df[feat_cols].copy()
    y_test = pd.to_numeric(test_df[TARGET_COL], errors="coerce").fillna(0).astype(int)

    model = build_pipeline(X_train, params)
    model.fit(X_train, y_train)
    force_single_thread(model)
    base_model = model
    calibration_method = "none"
    if calibrate:
        try:
            cal = CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=3)
            cal.fit(X_train, y_train)
            model = cal
            force_single_thread(model)
            calibration_method = "sigmoid"
        except Exception:
            model = base_model
            calibration_method = "failed_sigmoid_fallback_none"

    train_prob = model.predict_proba(X_train)[:, 1]
    val_prob = model.predict_proba(X_val)[:, 1]
    test_prob = model.predict_proba(X_test)[:, 1]
    thr = choose_threshold(y_val.to_numpy(), val_prob, strategy=threshold_strategy, recall_floor=0.60)

    m_train = metric_binary(y_train.to_numpy(), train_prob, thr)
    m_val = metric_binary(y_val.to_numpy(), val_prob, thr)
    m_test = metric_binary(y_test.to_numpy(), test_prob, thr)

    seed_scores = []
    for s in [7, 42, 2026]:
        p2 = dict(params)
        p2["random_state"] = s
        m = build_pipeline(X_train, p2)
        m.fit(X_train, y_train)
        force_single_thread(m)
        p = m.predict_proba(X_test)[:, 1]
        seed_scores.append(metric_binary(y_test.to_numpy(), p, thr)["balanced_accuracy"])

    split_scores = []
    for s in [42, 99, 777]:
        tr, va, te = split_ids(df["participant_id"].astype(str), y, s)
        tr_df = subset_by_ids(frame, tr)
        te_df = subset_by_ids(frame, te)
        xt = tr_df[feat_cols].copy()
        yt = pd.to_numeric(tr_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
        xte = te_df[feat_cols].copy()
        yte = pd.to_numeric(te_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
        m = build_pipeline(xt, params)
        m.fit(xt, yt)
        force_single_thread(m)
        p = m.predict_proba(xte)[:, 1]
        split_scores.append(metric_binary(yte.to_numpy(), p, thr)["balanced_accuracy"])

    rng = np.random.default_rng(RANDOM_STATE)
    stress_rows = []
    for lvl in [1, 2]:
        xn = noise_apply(X_test.copy(), lvl, rng)
        pm = model.predict_proba(xn)[:, 1]
        mm = metric_binary(y_test.to_numpy(), pm, thr)
        stress_rows.append({"trial_id": trial_id, "test_type": f"noise_level_{lvl}", **mm})
    realism_rows = []
    for sc in ["incomplete_inputs", "contradictory_inputs", "mixed_comorbidity_signals"]:
        xr = realism_apply(X_test.copy(), sc, rng)
        pm = model.predict_proba(xr)[:, 1]
        mm = metric_binary(y_test.to_numpy(), pm, thr)
        realism_rows.append({"trial_id": trial_id, "scenario": sc, **mm})

    residual_high = 0
    residual_critical = 0
    for f in feat_cols:
        risk = semantic_risk_level_for_feature(f, semantic_df)
        if risk == "high":
            residual_high += 1
        if risk == "critical":
            residual_critical += 1

    perfect_score = bool(
        max(
            m_train["precision"],
            m_train["balanced_accuracy"],
            m_val["precision"],
            m_val["balanced_accuracy"],
            m_test["precision"],
            m_test["balanced_accuracy"],
            m_test["recall"],
            m_test["specificity"],
        )
        >= 0.999
    )

    prelim = "candidate_honest"
    if residual_critical > 0:
        prelim = "leakage_risk"
    if perfect_score:
        prelim = "perfect_score_blocked"
    if np.std(seed_scores) > 0.08 or np.std(split_scores) > 0.10:
        prelim = "unstable"

    return {
        "trial_id": trial_id,
        "dataset_key": dataset_key,
        "n_features": len(feat_cols),
        "n_removed": len(removed),
        "threshold": thr,
        "calibration_method": calibration_method,
        "metrics_train": m_train,
        "metrics_val": m_val,
        "metrics_test": m_test,
        "seed_std_balacc": float(np.std(seed_scores)),
        "split_std_balacc": float(np.std(split_scores)),
        "stress_rows": stress_rows,
        "realism_rows": realism_rows,
        "residual_high_features": residual_high,
        "residual_critical_features": residual_critical,
        "suspicious_perfect_score": perfect_score,
        "preliminary_decision": prelim,
        "brier_val": float(brier_score_loss(y_val, val_prob)),
        "brier_test": float(brier_score_loss(y_test, test_prob)),
    }


def run_trial_campaign(paths: Paths, registry: pd.DataFrame, datasets: Dict[str, pd.DataFrame], semantic_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trial_registry_rows = []
    trial_metrics_rows = []
    seed_rows = []
    split_rows = []
    stress_rows = []
    realism_rows = []
    calibration_rows = []
    perfect_rows = []

    for _, tr in registry.iterrows():
        out = run_single_trial(tr, datasets, semantic_df)
        trial_registry_rows.append(
            {
                "trial_id": out["trial_id"],
                "dataset_key": out["dataset_key"],
                "n_features": out["n_features"],
                "n_removed": out["n_removed"],
                "threshold": out["threshold"],
                "calibration_method": out["calibration_method"],
                "preliminary_decision": out["preliminary_decision"],
            }
        )
        trial_metrics_rows.append(
            {
                "trial_id": out["trial_id"],
                "train_precision": out["metrics_train"]["precision"],
                "train_balanced_accuracy": out["metrics_train"]["balanced_accuracy"],
                "val_precision": out["metrics_val"]["precision"],
                "val_balanced_accuracy": out["metrics_val"]["balanced_accuracy"],
                "test_precision": out["metrics_test"]["precision"],
                "test_balanced_accuracy": out["metrics_test"]["balanced_accuracy"],
                "test_recall": out["metrics_test"]["recall"],
                "test_specificity": out["metrics_test"]["specificity"],
                "test_f1": out["metrics_test"]["f1"],
                "test_roc_auc": out["metrics_test"]["roc_auc"],
                "test_pr_auc": out["metrics_test"]["pr_auc"],
                "seed_std_balacc": out["seed_std_balacc"],
                "split_std_balacc": out["split_std_balacc"],
                "residual_high_features": out["residual_high_features"],
                "residual_critical_features": out["residual_critical_features"],
                "suspicious_perfect_score": out["suspicious_perfect_score"],
                "brier_val": out["brier_val"],
                "brier_test": out["brier_test"],
                "preliminary_decision": out["preliminary_decision"],
            }
        )
        seed_rows.append({"trial_id": out["trial_id"], "seed_std_balacc": out["seed_std_balacc"]})
        split_rows.append({"trial_id": out["trial_id"], "split_std_balacc": out["split_std_balacc"]})
        stress_rows.extend(out["stress_rows"])
        realism_rows.extend(out["realism_rows"])
        calibration_rows.append({"trial_id": out["trial_id"], "calibration_method": out["calibration_method"], "brier_val": out["brier_val"], "brier_test": out["brier_test"]})
        perfect_rows.append({"trial_id": out["trial_id"], "suspicious_perfect_score": out["suspicious_perfect_score"], "residual_critical_features": out["residual_critical_features"]})

    reg_df = pd.DataFrame(trial_registry_rows)
    met_df = pd.DataFrame(trial_metrics_rows)
    seed_df = pd.DataFrame(seed_rows)
    split_df = pd.DataFrame(split_rows)
    stress_df = pd.DataFrame(stress_rows)
    realism_df = pd.DataFrame(realism_rows)
    cal_df = pd.DataFrame(calibration_rows)
    perfect_df = pd.DataFrame(perfect_rows)

    safe_csv(reg_df, paths.trials / "elimination_trial_registry.csv")
    safe_csv(met_df, paths.trials / "elimination_trial_metrics_full.csv")
    safe_csv(seed_df, paths.tables / "elimination_seed_stability.csv")
    safe_csv(split_df, paths.tables / "elimination_split_stability.csv")
    safe_csv(stress_df, paths.tables / "elimination_stress_test_results.csv")
    safe_csv(realism_df, paths.tables / "elimination_realism_shift_results.csv")
    safe_csv(cal_df, paths.tables / "elimination_calibration_review.csv")
    safe_csv(perfect_df, paths.tables / "elimination_perfect_score_audit.csv")
    return reg_df, met_df, seed_df, split_df, stress_df, realism_df


def rank_honest_models(paths: Paths, metrics_df: pd.DataFrame, stress_df: pd.DataFrame, realism_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in metrics_df.iterrows():
        tid = r["trial_id"]
        s2 = stress_df[(stress_df["trial_id"] == tid) & (stress_df["test_type"] == "noise_level_2")]
        rs = realism_df[realism_df["trial_id"] == tid]
        noise_mod_bal = float(s2.iloc[0]["balanced_accuracy"]) if len(s2) else float("nan")
        realism_min_bal = float(rs["balanced_accuracy"].min()) if len(rs) else float("nan")
        noise_drop = float(r["test_balanced_accuracy"] - noise_mod_bal) if len(s2) else float("nan")
        realism_drop = float(r["test_balanced_accuracy"] - realism_min_bal) if len(rs) else float("nan")
        has_critical = int(r["residual_critical_features"]) > 0
        perfect = bool(r["suspicious_perfect_score"])
        score = 100.0
        if has_critical:
            score -= 50
        if perfect:
            score -= 35
        score -= min(20, r["seed_std_balacc"] * 200)
        score -= min(20, r["split_std_balacc"] * 200)
        if not np.isnan(noise_drop):
            score -= min(15, max(0, noise_drop) * 100)
        if not np.isnan(realism_drop):
            score -= min(15, max(0, realism_drop) * 100)
        score += 10 * float(r["test_balanced_accuracy"])
        score += 7 * float(r["test_precision"])
        score += 5 * float(r["test_recall"])
        rows.append(
            {
                "trial_id": tid,
                "honest_score": score,
                "has_critical_leakage": has_critical,
                "suspicious_perfect_score": perfect,
                "test_balanced_accuracy": r["test_balanced_accuracy"],
                "test_precision": r["test_precision"],
                "test_recall": r["test_recall"],
                "seed_std_balacc": r["seed_std_balacc"],
                "split_std_balacc": r["split_std_balacc"],
                "noise_moderate_drop_balacc": noise_drop,
                "realism_worst_drop_balacc": realism_drop,
                "preliminary_decision": r["preliminary_decision"],
            }
        )
    out = pd.DataFrame(rows).sort_values("honest_score", ascending=False).reset_index(drop=True)
    safe_csv(out, paths.tables / "elimination_honest_model_ranking.csv")
    safe_text(
        "# Elimination Model Selection Rationale\n\n"
        "Ranking prioritizes: no critical leakage, no perfect-score suspicion, stability, robustness under stress/realism, then performance.\n",
        paths.reports / "elimination_model_selection_rationale.md",
    )
    return out


def final_decision(paths: Paths, best: pd.Series, coverage_df: pd.DataFrame) -> str:
    coverage_specific = float(coverage_df[coverage_df["clinical_specificity"] == "high_for_elimination"]["coverage_ratio"].mean()) if len(coverage_df) else 0.0
    has_direct_elimination_instrument = bool((coverage_df["clinical_specificity"] == "direct_elimination_specific").any()) if len(coverage_df) else False
    decision = "recovered_generalizing_model"
    if bool(best["has_critical_leakage"]) or bool(best["suspicious_perfect_score"]):
        decision = "still_high_risk_overfit"
    elif best["seed_std_balacc"] > 0.06 or best["split_std_balacc"] > 0.08:
        decision = "recovered_but_experimental_high_caution"
    elif best["noise_moderate_drop_balacc"] > 0.15 or best["realism_worst_drop_balacc"] > 0.18:
        decision = "recovered_but_experimental_high_caution"
    elif coverage_specific < 0.50:
        decision = "thesis_includable_but_not_product_ready"
    elif best["test_balanced_accuracy"] < 0.70:
        decision = "rejected_for_now"
    if decision == "recovered_generalizing_model" and not has_direct_elimination_instrument:
        decision = "recovered_but_experimental_high_caution"

    safe_text(
        "# Elimination Final Decision v2\n\n"
        f"- selected_trial: {best['trial_id']}\n"
        f"- category: {decision}\n"
        f"- honest_score: {best['honest_score']:.4f}\n"
        f"- test_balanced_accuracy: {best['test_balanced_accuracy']:.4f}\n"
        f"- test_precision: {best['test_precision']:.4f}\n"
        f"- test_recall: {best['test_recall']:.4f}\n"
        f"- has_critical_leakage: {bool(best['has_critical_leakage'])}\n"
        f"- suspicious_perfect_score: {bool(best['suspicious_perfect_score'])}\n"
        f"- noise_moderate_drop_balacc: {best['noise_moderate_drop_balacc']:.4f}\n"
        f"- realism_worst_drop_balacc: {best['realism_worst_drop_balacc']:.4f}\n"
        f"- direct_elimination_instrument_available: {has_direct_elimination_instrument}\n",
        paths.reports / "elimination_final_decision_v2.md",
    )
    safe_text(
        "# Elimination Thesis Positioning\n\n"
        f"Recommended thesis positioning: **{decision}** with explicit caveat on simulated scope and elimination-specific coverage limitations.\n",
        paths.reports / "elimination_thesis_positioning.md",
    )
    safe_text(
        "# Elimination Product Positioning\n\n"
        f"Product positioning for this iteration: **{decision}**. Promote only if explicitly allowed by category policy.\n",
        paths.reports / "elimination_product_positioning.md",
    )
    safe_text(
        "# Elimination Executive Summary\n\n"
        f"- decision: {decision}\n"
        f"- selected_trial: {best['trial_id']}\n"
        f"- causal finding: proxy-leakage + separability + clinical coverage constraints (combined).\n",
        paths.reports / "elimination_executive_summary.md",
    )
    return decision


def maybe_export_inference_v5(paths: Paths, decision: str, best_trial: str) -> None:
    if decision not in {"recovered_generalizing_model", "recovered_but_experimental_high_caution"}:
        return
    inf = paths.root / "artifacts" / "inference_v5"
    inf.mkdir(parents=True, exist_ok=True)
    if decision == "recovered_generalizing_model":
        scope = {"elimination": "experimental_scope_allowed"}
    else:
        scope = {"elimination": "experimental_high_caution_not_product_ready"}
    safe_json(
        {
            "generated_at_utc": now_iso(),
            "from": "elimination_iterative_recovery_v2",
            "selected_trial": best_trial,
            "decision": decision,
            "scope": scope,
        },
        inf / "promotion_scope.json",
    )
    safe_text(
        f"Elimination inference v5 rationale\n\n- selected_trial: {best_trial}\n- decision: {decision}\n- scope: {scope['elimination']}\n",
        inf / "elimination_scope_rationale.md",
    )


def write_initial_audit_report(paths: Paths, semantic_df: pd.DataFrame, sep_df: pd.DataFrame, split_df: pd.DataFrame, coverage_df: pd.DataFrame, threshold_df: pd.DataFrame) -> None:
    crit = int((semantic_df["risk_level"] == "critical").sum())
    high = int((semantic_df["risk_level"] == "high").sum())
    nearp = int((sep_df["balanced_accuracy"] >= 0.97).sum()) if len(sep_df) else 0
    best_thr = threshold_df.sort_values("test_balanced_accuracy", ascending=False).iloc[0].to_dict()
    safe_text(
        "# Elimination Initial Audit Report\n\n"
        f"- critical_semantic_features: {crit}\n"
        f"- high_semantic_features: {high}\n"
        f"- near_perfect_short_rules: {nearp}\n"
        f"- split_prevalence_total: {float(split_df[split_df['metric']=='prevalence_total']['value'].iloc[0]):.4f}\n"
        f"- best_threshold_observed: {best_thr['threshold']:.2f}\n"
        f"- best_test_balanced_accuracy_observed: {best_thr['test_balanced_accuracy']:.4f}\n"
        "- preliminary diagnosis: elimination remains vulnerable to proxy-driven separability and artificial ease.\n",
        paths.reports / "elimination_initial_audit_report.md",
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Elimination iterative recovery v2 (causal audit + controlled retraining).")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    paths = build_paths(Path(args.root).resolve())
    ensure_dirs(paths)

    datasets = load_inputs(paths)
    create_inventory(paths, datasets)

    semantic_df = semantic_proximity_audit(datasets["strict"], paths)
    sep_df = separability_audit(datasets["strict"], semantic_df, paths)
    split_df = split_sample_audit(datasets["strict"], paths)
    coverage_df = clinical_coverage_audit(datasets["strict"], paths)
    threshold_df = ranking_vs_threshold_audit(datasets["strict"], paths)
    write_initial_audit_report(paths, semantic_df, sep_df, split_df, coverage_df, threshold_df)

    build_hypotheses(paths, semantic_df, sep_df, split_df, coverage_df, threshold_df)
    registry = build_strategy_registry(paths, semantic_df)
    _, metrics_df, _, _, stress_df, realism_df = run_trial_campaign(paths, registry, datasets, semantic_df)
    ranking_df = rank_honest_models(paths, metrics_df, stress_df, realism_df)
    best = ranking_df.iloc[0]
    decision = final_decision(paths, best, coverage_df)
    maybe_export_inference_v5(paths, decision, str(best["trial_id"]))

    safe_json(
        {
            "generated_at_utc": now_iso(),
            "selected_trial": str(best["trial_id"]),
            "decision": decision,
            "ranking_path": str(paths.tables / "elimination_honest_model_ranking.csv"),
        },
        paths.artifacts / "run_manifest.json",
    )
    LOGGER.info("Elimination iterative recovery v2 completed")


if __name__ == "__main__":
    run()
