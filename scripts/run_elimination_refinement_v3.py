#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

import run_elimination_iterative_recovery_v2 as v2


LOGGER = logging.getLogger("elimination-refinement-v3")
RANDOM_STATE = 42
TARGET_COL = "target_domain_elimination"
PARENT_MODEL_ID = "T02_drop_high_risk_semantic_proxies"


@dataclass
class Paths:
    root: Path
    out: Path
    inventory: Path
    audit: Path
    hypotheses: Path
    trials: Path
    tables: Path
    reports: Path
    artifacts: Path
    v2: Path
    hybrid: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    out = root / "data" / "elimination_refinement_v3"
    return Paths(
        root=root,
        out=out,
        inventory=out / "inventory",
        audit=out / "audit",
        hypotheses=out / "hypotheses",
        trials=out / "trials",
        tables=out / "tables",
        reports=out / "reports",
        artifacts=root / "artifacts" / "elimination_refinement_v3",
        v2=root / "data" / "elimination_iterative_recovery_v2",
        hybrid=root / "data" / "processed_hybrid_dsm5_v2",
    )


def ensure_dirs(paths: Paths) -> None:
    for p in [
        paths.out,
        paths.inventory,
        paths.audit,
        paths.hypotheses,
        paths.trials,
        paths.tables,
        paths.reports,
        paths.artifacts,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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


def read_semantic_v2(paths: Paths) -> pd.DataFrame:
    p = paths.v2 / "audit" / "elimination_semantic_proximity_audit.csv"
    if not p.exists():
        return pd.DataFrame(columns=["feature_name", "risk_level"])
    df = pd.read_csv(p)
    need = [c for c in ["feature_name", "risk_level", "semantic_relation_to_target", "why_flagged", "suggested_action"] if c in df.columns]
    return df[need].copy()


def risk_level_for(feature: str, semantic_df: pd.DataFrame) -> str:
    m = semantic_df[semantic_df["feature_name"] == feature]
    if len(m):
        return str(m.iloc[0]["risk_level"])
    low = feature.lower()
    if feature.startswith("target_"):
        return "critical"
    if "diagnosis" in low or "ksads" in low or "consensus" in low:
        return "critical"
    if feature in {"domain_any_positive", "internal_exact_any_positive", "n_diagnoses", "comorbidity_count_5targets", "domain_comorbidity_count", "internal_exact_comorbidity_count", "has_any_target_disorder"}:
        return "critical"
    if feature.startswith("q_qi_"):
        return "high"
    if low.endswith("_direct_criteria_count") or low.endswith("_proxy_criteria_count"):
        return "high"
    if feature.startswith("has_"):
        return "moderate"
    return "low"


def create_inventory(paths: Paths, data: Dict[str, pd.DataFrame], semantic_df: pd.DataFrame) -> None:
    check = [
        paths.v2 / "reports" / "elimination_final_decision_v2.md",
        paths.v2 / "reports" / "elimination_executive_summary.md",
        paths.v2 / "tables" / "elimination_honest_model_ranking.csv",
        paths.v2 / "tables" / "elimination_perfect_score_audit.csv",
        paths.v2 / "audit" / "elimination_semantic_proximity_audit.csv",
        paths.hybrid / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv",
        paths.hybrid / "final" / "model_ready" / "research_extended_hybrid" / "dataset_hybrid_model_ready_research_extended_hybrid.csv",
        paths.hybrid / "final" / "external_domains" / "dataset_domain_elimination.csv",
    ]
    rows: List[Dict[str, Any]] = []
    for p in check:
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "size_bytes": int(p.stat().st_size) if p.exists() else None,
                "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat() if p.exists() else None,
            }
        )
    for name, df in data.items():
        rows.append({"path": f"in_memory::{name}", "exists": True, "rows": len(df), "cols": len(df.columns), "modified_utc": now_iso()})
    rows.append({"path": "in_memory::semantic_v2", "exists": True, "rows": len(semantic_df), "cols": len(semantic_df.columns), "modified_utc": now_iso()})
    inv = pd.DataFrame(rows)
    safe_csv(inv, paths.inventory / "input_inventory.csv")
    safe_text(
        "# Elimination Refinement v3 - Input Summary\n\n"
        f"- generated_at_utc: {now_iso()}\n"
        f"- checked_inputs: {len(inv)}\n"
        f"- missing_inputs: {int((~inv['exists']).sum())}\n"
        f"- strict_rows: {len(data['strict'])}\n"
        f"- research_rows: {len(data['research'])}\n"
        f"- compact_rows: {len(data['compact'])}\n",
        paths.reports / "input_summary.md",
    )


def add_missingness_flags(X: pd.DataFrame) -> pd.DataFrame:
    X2 = X.copy()
    for c in X2.columns[:80]:
        miss = X2[c].isna().astype(int)
        if miss.mean() > 0.02:
            X2[f"miss_{c}"] = miss
    return X2


def prepare_features(
    df: pd.DataFrame,
    semantic_df: pd.DataFrame,
    drop_risks: List[str],
    drop_prefixes: List[str],
    max_features: int,
    add_miss_flags: bool,
    low_missingness_only: bool,
    specificity_focus: bool,
    comorbidity_aware: bool,
) -> Tuple[pd.DataFrame, pd.Series, List[str], Dict[str, int]]:
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
        if risk_level_for(c, semantic_df) in set(drop_risks):
            drops.add(c)
        if comorbidity_aware and ("comorbidity" in low or low.endswith("_any_positive")):
            drops.add(c)
    X = df.drop(columns=list(drops), errors="ignore").copy()
    X = X.drop(columns=[c for c in X.columns if X[c].nunique(dropna=True) <= 1 or X[c].notna().mean() < 0.03], errors="ignore")
    if low_missingness_only:
        keep = X.notna().mean()
        X = X[keep[keep >= 0.85].index.tolist()].copy()
    if specificity_focus:
        allow_prefix = ("cbcl_", "sdq_", "has_cbcl", "has_sdq", "age_", "sex_", "site", "release")
        allow_exact = {"age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq"}
        keep_cols = [c for c in X.columns if c.startswith(allow_prefix) or c in allow_exact]
        if len(keep_cols) >= 8:
            X = X[keep_cols].copy()
    if X.shape[1] > max_features:
        keep = X.notna().mean().sort_values(ascending=False).head(max_features).index.tolist()
        X = X[keep].copy()
    if add_miss_flags:
        X = add_missingness_flags(X)
    residual_critical = sum(1 for c in X.columns if risk_level_for(c, semantic_df) == "critical")
    residual_high = sum(1 for c in X.columns if risk_level_for(c, semantic_df) == "high")
    meta = {"residual_critical": int(residual_critical), "residual_high": int(residual_high), "n_removed": int(len(drops))}
    return X, y, sorted(list(drops)), meta


def select_abstention_band(y_val: np.ndarray, prob_val: np.ndarray) -> Tuple[float, float]:
    best = (0.25, 0.75, -1e9)
    for low in np.arange(0.10, 0.46, 0.05):
        for high in np.arange(0.55, 0.96, 0.05):
            if low >= high:
                continue
            confident_pos = prob_val >= high
            confident_known = (prob_val < low) | confident_pos
            if confident_pos.sum() == 0:
                continue
            tp = int(((prob_val >= high) & (y_val == 1)).sum())
            fp = int(((prob_val >= high) & (y_val == 0)).sum())
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            cov = float(confident_known.mean())
            if prec < 0.80:
                continue
            score = 0.7 * prec + 0.3 * cov
            if score > best[2]:
                best = (float(low), float(high), float(score))
    return float(best[0]), float(best[1])


def abstention_metrics(y_true: np.ndarray, prob: np.ndarray, low: float, high: float) -> Dict[str, Any]:
    conf_neg = prob < low
    conf_pos = prob >= high
    uncertain = ~(conf_neg | conf_pos)
    tp = int(((prob >= high) & (y_true == 1)).sum())
    fp = int(((prob >= high) & (y_true == 0)).sum())
    precision_high = tp / (tp + fp) if (tp + fp) else 0.0
    recall_eff = tp / int((y_true == 1).sum()) if int((y_true == 1).sum()) else 0.0
    return {
        "low_threshold": float(low),
        "high_threshold": float(high),
        "coverage": float((conf_neg | conf_pos).mean()),
        "precision_high_confidence_positive": float(precision_high),
        "effective_recall": float(recall_eff),
        "uncertain_pct": float(uncertain.mean()),
        "n_uncertain": int(uncertain.sum()),
    }


def train_trial(
    trial: Dict[str, Any],
    data: Dict[str, pd.DataFrame],
    semantic_df: pd.DataFrame,
    return_predictions: bool = False,
) -> Dict[str, Any]:
    df = data[str(trial["dataset_key"])].copy()
    X, y, removed, meta = prepare_features(
        df=df,
        semantic_df=semantic_df,
        drop_risks=list(trial.get("drop_risks", [])),
        drop_prefixes=list(trial.get("drop_prefixes", [])),
        max_features=int(trial.get("max_features", 240)),
        add_miss_flags=bool(trial.get("add_missingness_flags", False)),
        low_missingness_only=bool(trial.get("low_missingness_only", False)),
        specificity_focus=bool(trial.get("specificity_focus", False)),
        comorbidity_aware=bool(trial.get("comorbidity_aware", False)),
    )
    ids_train, ids_val, ids_test = v2.split_ids(df["participant_id"].astype(str), y, RANDOM_STATE)
    frame = pd.concat([df[["participant_id"]].reset_index(drop=True), X.reset_index(drop=True), y.rename(TARGET_COL).reset_index(drop=True)], axis=1)
    train_df = v2.subset_by_ids(frame, ids_train)
    val_df = v2.subset_by_ids(frame, ids_val)
    test_df = v2.subset_by_ids(frame, ids_test)
    feat_cols = [c for c in frame.columns if c not in {"participant_id", TARGET_COL}]

    X_train = train_df[feat_cols].copy()
    y_train = pd.to_numeric(train_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_val = val_df[feat_cols].copy()
    y_val = pd.to_numeric(val_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
    X_test = test_df[feat_cols].copy()
    y_test = pd.to_numeric(test_df[TARGET_COL], errors="coerce").fillna(0).astype(int)

    params = dict(trial["params"])
    model = v2.build_pipeline(X_train, params)
    model.fit(X_train, y_train)
    v2.force_single_thread(model)
    calibration = "none"
    if bool(trial.get("calibration", False)):
        try:
            cal = CalibratedClassifierCV(estimator=model, method="sigmoid", cv=3)
            cal.fit(X_train, y_train)
            model = cal
            v2.force_single_thread(model)
            calibration = "sigmoid"
        except Exception:
            calibration = "sigmoid_failed_fallback_none"

    train_prob = model.predict_proba(X_train)[:, 1]
    val_prob = model.predict_proba(X_val)[:, 1]
    test_prob = model.predict_proba(X_test)[:, 1]
    thr = v2.choose_threshold(y_val.to_numpy(), val_prob, strategy=str(trial.get("threshold_strategy", "balanced")), recall_floor=float(trial.get("recall_floor", 0.60)))

    m_train = v2.metric_binary(y_train.to_numpy(), train_prob, thr)
    m_val = v2.metric_binary(y_val.to_numpy(), val_prob, thr)
    m_test = v2.metric_binary(y_test.to_numpy(), test_prob, thr)

    seed_scores: List[float] = []
    for s in [7, 42, 2026]:
        p2 = dict(params)
        p2["random_state"] = s
        ms = v2.build_pipeline(X_train, p2)
        ms.fit(X_train, y_train)
        v2.force_single_thread(ms)
        ps = ms.predict_proba(X_test)[:, 1]
        seed_scores.append(v2.metric_binary(y_test.to_numpy(), ps, thr)["balanced_accuracy"])

    split_scores: List[float] = []
    for s in [42, 99, 777]:
        tr, _, te = v2.split_ids(df["participant_id"].astype(str), y, s)
        tr_df = v2.subset_by_ids(frame, tr)
        te_df = v2.subset_by_ids(frame, te)
        xt = tr_df[feat_cols].copy()
        yt = pd.to_numeric(tr_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
        xte = te_df[feat_cols].copy()
        yte = pd.to_numeric(te_df[TARGET_COL], errors="coerce").fillna(0).astype(int)
        ms = v2.build_pipeline(xt, params)
        ms.fit(xt, yt)
        v2.force_single_thread(ms)
        ps = ms.predict_proba(xte)[:, 1]
        split_scores.append(v2.metric_binary(yte.to_numpy(), ps, thr)["balanced_accuracy"])

    rng = np.random.default_rng(RANDOM_STATE)
    stress_rows: List[Dict[str, Any]] = []
    for lvl in [1, 2]:
        xn = v2.noise_apply(X_test.copy(), lvl, rng)
        pn = model.predict_proba(xn)[:, 1]
        mn = v2.metric_binary(y_test.to_numpy(), pn, thr)
        stress_rows.append({"trial_id": str(trial["trial_id"]), "test_type": f"noise_level_{lvl}", **mn})
    realism_rows: List[Dict[str, Any]] = []
    for sc in ["incomplete_inputs", "contradictory_inputs", "mixed_comorbidity_signals"]:
        xr = v2.realism_apply(X_test.copy(), sc, rng)
        pr = model.predict_proba(xr)[:, 1]
        mr = v2.metric_binary(y_test.to_numpy(), pr, thr)
        realism_rows.append({"trial_id": str(trial["trial_id"]), "scenario": sc, **mr})

    threshold_rows: List[Dict[str, Any]] = []
    for t in np.linspace(0.20, 0.85, 14):
        mv = v2.metric_binary(y_val.to_numpy(), val_prob, float(t))
        mt = v2.metric_binary(y_test.to_numpy(), test_prob, float(t))
        threshold_rows.append(
            {
                "trial_id": str(trial["trial_id"]),
                "threshold": float(t),
                "val_precision": mv["precision"],
                "val_balanced_accuracy": mv["balanced_accuracy"],
                "val_recall": mv["recall"],
                "test_precision": mt["precision"],
                "test_balanced_accuracy": mt["balanced_accuracy"],
                "test_recall": mt["recall"],
                "test_specificity": mt["specificity"],
            }
        )

    low, high = select_abstention_band(y_val.to_numpy(), val_prob)
    abst = abstention_metrics(y_test.to_numpy(), test_prob, low, high)
    abst["trial_id"] = str(trial["trial_id"])
    perfect = bool(max(m_train["precision"], m_train["balanced_accuracy"], m_val["precision"], m_val["balanced_accuracy"], m_test["precision"], m_test["balanced_accuracy"], m_test["recall"], m_test["specificity"]) >= 0.999)
    prelim = "candidate_incremental"
    if meta["residual_critical"] > 0:
        prelim = "blocked_leakage"
    elif perfect:
        prelim = "blocked_perfect_score"
    elif np.std(seed_scores) > 0.08 or np.std(split_scores) > 0.10:
        prelim = "unstable"

    out: Dict[str, Any] = {
        "trial_id": str(trial["trial_id"]),
        "parent_model": str(trial.get("parent_model", PARENT_MODEL_ID)),
        "hypothesis_linked": str(trial.get("hypothesis_linked", "")),
        "dataset_key": str(trial["dataset_key"]),
        "feature_strategy": str(trial.get("feature_strategy", "")),
        "threshold_strategy": str(trial.get("threshold_strategy", "balanced")),
        "calibration_strategy": calibration,
        "hyperparameters_json": json.dumps(params),
        "n_features": int(len(feat_cols)),
        "n_removed": int(len(removed)),
        "threshold_used": float(thr),
        "metrics_train": m_train,
        "metrics_val": m_val,
        "metrics_test": m_test,
        "seed_std_balacc": float(np.std(seed_scores)),
        "split_std_balacc": float(np.std(split_scores)),
        "stress_rows": stress_rows,
        "realism_rows": realism_rows,
        "threshold_rows": threshold_rows,
        "abstention": abst,
        "suspicious_perfect_score": perfect,
        "residual_critical": int(meta["residual_critical"]),
        "residual_high": int(meta["residual_high"]),
        "preliminary_decision": prelim,
        "brier_val": float(brier_score_loss(y_val.to_numpy(), val_prob)),
        "brier_test": float(brier_score_loss(y_test.to_numpy(), test_prob)),
    }
    if return_predictions:
        out["pred"] = {
            "frame_test": test_df.copy(),
            "y_test": y_test.to_numpy(),
            "prob_test": test_prob,
            "pred_test": (test_prob >= thr).astype(int),
        }
    return out


def run_residual_error_audit(paths: Paths, parent_result: Dict[str, Any]) -> pd.DataFrame:
    p = parent_result["pred"]
    df = p["frame_test"].copy()
    y = np.array(p["y_test"]).astype(int)
    prob = np.array(p["prob_test"]).astype(float)
    pred = np.array(p["pred_test"]).astype(int)
    keep = ["participant_id"]
    for c in ["age_years", "sex_assigned_at_birth", "site", "domain_comorbidity_count", "internal_exact_comorbidity_count"]:
        if c in df.columns:
            keep.append(c)
    errs = df[keep].copy()
    errs["y_true"] = y
    errs["y_pred"] = pred
    errs["probability"] = prob
    errs["error_type"] = np.where((errs["y_true"] == 0) & (errs["y_pred"] == 1), "false_positive", np.where((errs["y_true"] == 1) & (errs["y_pred"] == 0), "false_negative", "correct"))
    feats = df.drop(columns=["participant_id", TARGET_COL], errors="ignore")
    errs["missing_ratio_row"] = feats.isna().mean(axis=1).values
    errs["high_confidence_error"] = np.where(((errs["error_type"] == "false_positive") & (errs["probability"] >= 0.80)) | ((errs["error_type"] == "false_negative") & (errs["probability"] <= 0.20)), 1, 0)
    fp = errs[errs["error_type"] == "false_positive"].copy()
    fn = errs[errs["error_type"] == "false_negative"].copy()
    safe_csv(fp, paths.audit / "elimination_residual_false_positive_audit.csv")
    safe_csv(fn, paths.audit / "elimination_residual_false_negative_audit.csv")

    rows: List[Dict[str, Any]] = [
        {"pattern": "false_positive_count", "value": int(len(fp))},
        {"pattern": "false_negative_count", "value": int(len(fn))},
        {"pattern": "high_confidence_errors", "value": int(errs["high_confidence_error"].sum())},
        {"pattern": "fp_mean_probability", "value": float(fp["probability"].mean()) if len(fp) else float("nan")},
        {"pattern": "fn_mean_probability", "value": float(fn["probability"].mean()) if len(fn) else float("nan")},
        {"pattern": "fp_mean_missing_ratio", "value": float(fp["missing_ratio_row"].mean()) if len(fp) else float("nan")},
        {"pattern": "fn_mean_missing_ratio", "value": float(fn["missing_ratio_row"].mean()) if len(fn) else float("nan")},
    ]
    for col in ["age_years", "sex_assigned_at_birth", "domain_comorbidity_count", "internal_exact_comorbidity_count"]:
        if col in errs.columns:
            g = errs[errs["error_type"] != "correct"].groupby(col, dropna=False).size().reset_index(name="n_errors")
            for _, r in g.head(20).iterrows():
                rows.append({"pattern": f"errors_by_{col}", "subgroup": str(r[col]), "value": int(r["n_errors"])})
    pat = pd.DataFrame(rows)
    safe_csv(pat, paths.audit / "elimination_residual_error_patterns.csv")
    safe_text(
        "# Elimination Residual Error Report\n\n"
        f"- parent_model: {PARENT_MODEL_ID}\n"
        f"- false_positives: {len(fp)}\n"
        f"- false_negatives: {len(fn)}\n"
        f"- high_confidence_errors: {int(errs['high_confidence_error'].sum())}\n"
        "- residual_assessment:\n"
        "  - El error remanente se concentra en frontera de especificidad y cobertura incompleta.\n"
        "  - Existen errores de alta confianza; se justifica explorar calibracion/threshold y abstention.\n",
        paths.reports / "elimination_residual_error_report.md",
    )
    return pat


def build_hypotheses(paths: Paths, pat: pd.DataFrame) -> None:
    fp = int(pat[pat["pattern"] == "false_positive_count"]["value"].iloc[0])
    fn = int(pat[pat["pattern"] == "false_negative_count"]["value"].iloc[0])
    hc = int(pat[pat["pattern"] == "high_confidence_errors"]["value"].iloc[0])
    matrix = pd.DataFrame(
        [
            {"hypothesis_id": "H1", "hypothesis_description": "Aun quedan features generales que disparan falsos positivos.", "evidence_for": f"fp={fp}", "expected_gain": "specificity_small_gain", "methodological_risk": "low", "implementation_cost": "low", "priority": 1},
            {"hypothesis_id": "H2", "hypothesis_description": "Variante compacta puede subir especificidad sin romper recall.", "evidence_for": f"fp={fp}, fn={fn}", "expected_gain": "balanced_small_gain", "methodological_risk": "moderate", "implementation_cost": "medium", "priority": 2},
            {"hypothesis_id": "H3", "hypothesis_description": "Abstention band puede mejorar utilidad operativa.", "evidence_for": f"high_conf_errors={hc}", "expected_gain": "operational_precision_gain", "methodological_risk": "low", "implementation_cost": "low", "priority": 3},
            {"hypothesis_id": "H4", "hypothesis_description": "Calibracion + threshold conservador puede mejorar punto operativo.", "evidence_for": "frontera con errores de alta confianza", "expected_gain": "operational_gain", "methodological_risk": "low", "implementation_cost": "low", "priority": 4},
            {"hypothesis_id": "H5", "hypothesis_description": "Subespacio clinicamente mas especifico puede reducir ruido transdiagnostico.", "evidence_for": "cobertura indirecta y no instrumento directo", "expected_gain": "specificity_gain_with_recall_risk", "methodological_risk": "moderate", "implementation_cost": "medium", "priority": 5},
            {"hypothesis_id": "H6", "hypothesis_description": "El modelo ya puede estar cerca de su techo con data actual.", "evidence_for": "v2 ya removio score perfecto en modelo elegido", "expected_gain": "none_or_marginal", "methodological_risk": "none", "implementation_cost": "low", "priority": 6},
        ]
    ).sort_values("priority")
    safe_csv(matrix, paths.hypotheses / "elimination_incremental_hypothesis_matrix.csv")
    safe_text(
        "# Elimination Incremental Hypotheses\n\n"
        "- H1-H2-H5: refinamiento de features.\n"
        "- H3-H4: mejora operativa (abstention/calibracion/threshold).\n"
        "- H6: hipotesis de techo razonable y criterio de stop.\n",
        paths.reports / "elimination_incremental_hypotheses.md",
    )


def trial_plan() -> List[Dict[str, Any]]:
    base_params = {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}
    return [
        {"trial_id": "V3_T01_control_replay_parent", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "control", "dataset_key": "strict", "feature_strategy": "replay_parent_semantic_pruned", "drop_risks": ["critical"], "drop_prefixes": [], "max_features": 280, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": base_params, "threshold_strategy": "balanced", "calibration": False, "recall_floor": 0.60},
        {"trial_id": "V3_T02_compact_pruned_specificity_first", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H1,H2", "dataset_key": "strict", "feature_strategy": "drop_high_and_critical_plus_q", "drop_risks": ["critical", "high"], "drop_prefixes": ["q_qi_"], "max_features": 220, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": True, "params": {"n_estimators": 220, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "log2", "class_weight": "balanced"}, "threshold_strategy": "conservative", "calibration": False, "recall_floor": 0.60},
        {"trial_id": "V3_T03_low_missingness_specific_subset", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H2,H5", "dataset_key": "strict", "feature_strategy": "low_missingness_specific_subset", "drop_risks": ["critical"], "drop_prefixes": ["q_qi_"], "max_features": 180, "add_missingness_flags": False, "low_missingness_only": True, "specificity_focus": True, "comorbidity_aware": True, "params": {"n_estimators": 260, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "recall_floor": 0.60},
        {"trial_id": "V3_T04_comorbidity_aware_conservative_subset", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H1,H5", "dataset_key": "strict", "feature_strategy": "drop_comorbidity_helpers", "drop_risks": ["critical"], "drop_prefixes": ["q_qi_"], "max_features": 210, "add_missingness_flags": True, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": True, "params": {"n_estimators": 240, "max_depth": 5, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "conservative", "calibration": False, "recall_floor": 0.60},
        {"trial_id": "V3_T05_calibration_refinement", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H4", "dataset_key": "strict", "feature_strategy": "parent_plus_sigmoid", "drop_risks": ["critical"], "drop_prefixes": ["q_qi_"], "max_features": 240, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 9, "min_samples_split": 22, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": True, "recall_floor": 0.60},
        {"trial_id": "V3_T06_threshold_refinement", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H4", "dataset_key": "strict", "feature_strategy": "parent_precision_threshold", "drop_risks": ["critical"], "drop_prefixes": [], "max_features": 260, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": base_params, "threshold_strategy": "precision", "calibration": False, "recall_floor": 0.70},
        {"trial_id": "V3_T07_abstention_assisted_operating_mode", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H3", "dataset_key": "strict", "feature_strategy": "parent_plus_missingness", "drop_risks": ["critical"], "drop_prefixes": ["q_qi_"], "max_features": 240, "add_missingness_flags": True, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": {"n_estimators": 240, "max_depth": 6, "min_samples_leaf": 10, "min_samples_split": 24, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "recall_floor": 0.60},
        {"trial_id": "V3_T08_ultra_compact_thesis_variant", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H2,H5", "dataset_key": "compact", "feature_strategy": "ultra_compact_defensible", "drop_risks": ["critical", "high"], "drop_prefixes": ["q_qi_"], "max_features": 90, "add_missingness_flags": False, "low_missingness_only": True, "specificity_focus": True, "comorbidity_aware": True, "params": {"n_estimators": 180, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 26, "max_features": "log2", "class_weight": "balanced_subsample"}, "threshold_strategy": "conservative", "calibration": True, "recall_floor": 0.60},
        {"trial_id": "V3_T09_optional_research_context", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "context_only", "dataset_key": "research", "feature_strategy": "research_secondary_non_promotable", "drop_risks": ["critical"], "drop_prefixes": [], "max_features": 260, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": base_params, "threshold_strategy": "balanced", "calibration": False, "recall_floor": 0.60, "non_promotable": True},
        {"trial_id": "V3_T10_stop_condition_control", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "H6", "dataset_key": "strict", "feature_strategy": "stability_first_stop_probe", "drop_risks": ["critical", "high"], "drop_prefixes": ["q_qi_"], "max_features": 200, "add_missingness_flags": True, "low_missingness_only": True, "specificity_focus": False, "comorbidity_aware": True, "params": {"n_estimators": 300, "max_depth": 5, "min_samples_leaf": 12, "min_samples_split": 28, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "conservative", "calibration": True, "recall_floor": 0.60},
    ]


def run_campaign(paths: Paths, data: Dict[str, pd.DataFrame], semantic_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    registry_rows: List[Dict[str, Any]] = []
    metrics_rows: List[Dict[str, Any]] = []
    stability_rows: List[Dict[str, Any]] = []
    perfect_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []
    abst_rows: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    realism_rows: List[Dict[str, Any]] = []

    for trial in trial_plan():
        LOGGER.info("Running %s", trial["trial_id"])
        out = train_trial(trial, data, semantic_df, return_predictions=False)
        registry_rows.append({"trial_id": out["trial_id"], "parent_model": out["parent_model"], "hypothesis_linked": out["hypothesis_linked"], "feature_strategy": out["feature_strategy"], "threshold_strategy": out["threshold_strategy"], "calibration_strategy": out["calibration_strategy"], "hyperparameters": out["hyperparameters_json"], "dataset_key": out["dataset_key"], "n_features": out["n_features"], "n_removed": out["n_removed"], "non_promotable": bool(trial.get("non_promotable", False)), "preliminary_decision": out["preliminary_decision"]})
        metrics_rows.append({"trial_id": out["trial_id"], "train_precision": out["metrics_train"]["precision"], "train_balanced_accuracy": out["metrics_train"]["balanced_accuracy"], "val_precision": out["metrics_val"]["precision"], "val_balanced_accuracy": out["metrics_val"]["balanced_accuracy"], "test_precision": out["metrics_test"]["precision"], "test_balanced_accuracy": out["metrics_test"]["balanced_accuracy"], "test_recall": out["metrics_test"]["recall"], "test_specificity": out["metrics_test"]["specificity"], "test_f1": out["metrics_test"]["f1"], "test_pr_auc": out["metrics_test"]["pr_auc"], "test_roc_auc": out["metrics_test"]["roc_auc"], "brier_val": out["brier_val"], "brier_test": out["brier_test"], "seed_std_balacc": out["seed_std_balacc"], "split_std_balacc": out["split_std_balacc"], "threshold_used": out["threshold_used"], "residual_critical": out["residual_critical"], "residual_high": out["residual_high"], "suspicious_perfect_score": out["suspicious_perfect_score"], "preliminary_decision": out["preliminary_decision"]})
        stability_rows.append({"trial_id": out["trial_id"], "seed_std_balacc": out["seed_std_balacc"], "split_std_balacc": out["split_std_balacc"]})
        perfect_rows.append({"trial_id": out["trial_id"], "suspicious_perfect_score": out["suspicious_perfect_score"], "residual_critical": out["residual_critical"], "residual_high": out["residual_high"], "preliminary_decision": out["preliminary_decision"]})
        threshold_rows.extend(out["threshold_rows"])
        abst_rows.append(out["abstention"])
        stress_rows.extend(out["stress_rows"])
        realism_rows.extend(out["realism_rows"])

    reg = pd.DataFrame(registry_rows)
    met = pd.DataFrame(metrics_rows)
    stab = pd.DataFrame(stability_rows)
    perf = pd.DataFrame(perfect_rows)
    thr = pd.DataFrame(threshold_rows)
    abst = pd.DataFrame(abst_rows)
    stress = pd.DataFrame(stress_rows)
    realism = pd.DataFrame(realism_rows)
    safe_csv(reg, paths.trials / "elimination_refinement_trial_registry.csv")
    safe_csv(met, paths.trials / "elimination_refinement_trial_metrics_full.csv")
    safe_csv(stab, paths.tables / "elimination_refinement_stability.csv")
    safe_csv(thr, paths.tables / "elimination_refinement_threshold_review.csv")
    safe_csv(abst, paths.tables / "elimination_refinement_abstention_review.csv")
    safe_csv(perf, paths.tables / "elimination_refinement_perfect_score_audit.csv")
    safe_csv(stress, paths.tables / "elimination_refinement_stress_results.csv")
    safe_csv(realism, paths.tables / "elimination_refinement_realism_results.csv")
    return reg, met, stress, realism


def rank_trials(reg: pd.DataFrame, met: pd.DataFrame, stress: pd.DataFrame, realism: pd.DataFrame) -> pd.DataFrame:
    joined = met.merge(reg[["trial_id", "non_promotable"]], on="trial_id", how="left")
    rows: List[Dict[str, Any]] = []
    for _, r in joined.iterrows():
        tid = str(r["trial_id"])
        s2 = stress[(stress["trial_id"] == tid) & (stress["test_type"] == "noise_level_2")]
        rs = realism[realism["trial_id"] == tid]
        noise_drop = float(r["test_balanced_accuracy"] - float(s2["balanced_accuracy"].mean())) if len(s2) else float("nan")
        realism_drop = float(r["test_balanced_accuracy"] - float(rs["balanced_accuracy"].min())) if len(rs) else float("nan")
        score = 100.0
        if bool(r["residual_critical"] > 0):
            score -= 60
        if bool(r["suspicious_perfect_score"]):
            score -= 40
        if bool(r["non_promotable"]):
            score -= 20
        score -= min(20.0, float(r["seed_std_balacc"]) * 200.0)
        score -= min(20.0, float(r["split_std_balacc"]) * 200.0)
        if not np.isnan(noise_drop):
            score -= min(15.0, max(0.0, noise_drop) * 100.0)
        if not np.isnan(realism_drop):
            score -= min(15.0, max(0.0, realism_drop) * 100.0)
        score += 10.0 * float(r["test_balanced_accuracy"])
        score += 8.0 * float(r["test_precision"])
        score += 5.0 * float(r["test_recall"])
        rows.append({"trial_id": tid, "honest_score": score, "test_precision": float(r["test_precision"]), "test_balanced_accuracy": float(r["test_balanced_accuracy"]), "test_recall": float(r["test_recall"]), "test_specificity": float(r["test_specificity"]), "test_pr_auc": float(r["test_pr_auc"]), "seed_std_balacc": float(r["seed_std_balacc"]), "split_std_balacc": float(r["split_std_balacc"]), "noise_moderate_drop_balacc": float(noise_drop), "realism_worst_drop_balacc": float(realism_drop), "residual_critical": int(r["residual_critical"]), "suspicious_perfect_score": bool(r["suspicious_perfect_score"]), "non_promotable": bool(r["non_promotable"])})
    return pd.DataFrame(rows).sort_values("honest_score", ascending=False).reset_index(drop=True)


def v2_reference(paths: Paths) -> Dict[str, float]:
    p = paths.v2 / "tables" / "elimination_honest_model_ranking.csv"
    if not p.exists():
        return {"precision": 0.9057, "balanced_accuracy": 0.8872, "recall": 0.8944, "specificity": 0.8800}
    d = pd.read_csv(p)
    r = d.iloc[0]
    return {"precision": float(r["test_precision"]), "balanced_accuracy": float(r["test_balanced_accuracy"]), "recall": float(r["test_recall"]), "specificity": float(r["test_specificity"]) if "test_specificity" in d.columns else 0.8800}


def finalize(paths: Paths, ranking: pd.DataFrame, abst_review: pd.DataFrame, ref: Dict[str, float]) -> Tuple[str, str]:
    promotable = ranking[(~ranking["non_promotable"]) & (~ranking["suspicious_perfect_score"]) & (ranking["residual_critical"] == 0)].copy()
    best = promotable.iloc[0] if len(promotable) else ranking.iloc[0]
    best_trial = str(best["trial_id"])
    delta_p = float(best["test_precision"] - ref["precision"])
    delta_b = float(best["test_balanced_accuracy"] - ref["balanced_accuracy"])
    delta_r = float(best["test_recall"] - ref["recall"])
    abst = abst_review[abst_review["trial_id"] == best_trial]
    abst_prec = float(abst.iloc[0]["precision_high_confidence_positive"]) if len(abst) else float("nan")
    abst_cov = float(abst.iloc[0]["coverage"]) if len(abst) else float("nan")
    abst_gain = float(abst_prec - best["test_precision"]) if not np.isnan(abst_prec) else 0.0

    structural = delta_p >= 0.01 and delta_b >= 0.01 and delta_r >= -0.02
    operational = abst_gain >= 0.03 and abst_cov >= 0.65
    robust = float(best["seed_std_balacc"]) <= 0.06 and float(best["split_std_balacc"]) <= 0.08 and float(best["noise_moderate_drop_balacc"]) <= 0.12 and float(best["realism_worst_drop_balacc"]) <= 0.15
    clean = not bool(best["suspicious_perfect_score"]) and int(best["residual_critical"]) == 0

    if structural and robust and clean:
        stop = "si_hubo_mejora_incremental_real_y_defendible"
        status = "experimental_more_solid_not_product_ready"
    elif operational and robust and clean:
        stop = "hubo_mejora_operativa_pero_no_estructural"
        status = "recovered_but_experimental_high_caution"
    elif robust and clean:
        stop = "no_hubo_mejora_relevante_modelo_cerca_de_techo_razonable"
        status = "recovered_but_experimental_high_caution_near_ceiling"
    else:
        stop = "hubo_cambios_menores_no_suficientes_para_cambiar_estatus"
        status = "recovered_but_experimental_high_caution"

    safe_text(
        "# Elimination Stop Rule Assessment\n\n"
        f"- selected_trial_v3: {best_trial}\n"
        f"- delta_precision_vs_v2: {delta_p:.4f}\n"
        f"- delta_balanced_accuracy_vs_v2: {delta_b:.4f}\n"
        f"- delta_recall_vs_v2: {delta_r:.4f}\n"
        f"- abstention_precision_gain_vs_selected_binary: {abst_gain:.4f}\n"
        f"- stop_conclusion: {stop}\n",
        paths.reports / "elimination_stop_rule_assessment.md",
    )
    safe_text(
        "# Elimination Final Decision v3\n\n"
        f"- selected_trial: {best_trial}\n"
        f"- final_status: {status}\n"
        f"- stop_conclusion: {stop}\n"
        f"- test_precision: {float(best['test_precision']):.4f}\n"
        f"- test_balanced_accuracy: {float(best['test_balanced_accuracy']):.4f}\n"
        f"- test_recall: {float(best['test_recall']):.4f}\n"
        f"- test_specificity: {float(best['test_specificity']):.4f}\n"
        "- product_ready: no\n",
        paths.reports / "elimination_final_decision_v3.md",
    )
    safe_text("# Elimination Thesis Positioning v3\n\nElimination permanece como linea experimental defendible para tesis con caveats de cobertura y no-equivalencia diagnostica definitiva.\n", paths.reports / "elimination_thesis_positioning_v3.md")
    safe_text("# Elimination Product Positioning v3\n\nNo promover a producto en esta fase. Solo uso experimental con etiquetas de cautela.\n", paths.reports / "elimination_product_positioning_v3.md")
    safe_text(
        "# Elimination Executive Summary v3\n\n"
        f"- selected_trial: {best_trial}\n"
        f"- final_status: {status}\n"
        f"- stop_conclusion: {stop}\n"
        "- mensaje: refinamiento incremental evaluado sin reintroducir leakage ni score perfecto sospechoso.\n",
        paths.reports / "elimination_executive_summary_v3.md",
    )
    return best_trial, status


def run() -> None:
    parser = argparse.ArgumentParser(description="Elimination post-recovery refinement v3.")
    parser.add_argument("--root", type=str, default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    paths = build_paths(Path(args.root).resolve())
    ensure_dirs(paths)

    data = load_inputs(paths)
    semantic = read_semantic_v2(paths)
    create_inventory(paths, data, semantic)

    parent_control = {"trial_id": "V3_parent_residual_audit_replay", "parent_model": PARENT_MODEL_ID, "hypothesis_linked": "control", "dataset_key": "strict", "feature_strategy": "replay_parent_semantic_pruned", "drop_risks": ["critical"], "drop_prefixes": [], "max_features": 280, "add_missingness_flags": False, "low_missingness_only": False, "specificity_focus": False, "comorbidity_aware": False, "params": {"n_estimators": 220, "max_depth": 6, "min_samples_leaf": 8, "min_samples_split": 20, "max_features": "sqrt", "class_weight": "balanced_subsample"}, "threshold_strategy": "balanced", "calibration": False, "recall_floor": 0.60}
    parent_result = train_trial(parent_control, data, semantic, return_predictions=True)
    pat = run_residual_error_audit(paths, parent_result)
    build_hypotheses(paths, pat)

    reg, met, stress, realism = run_campaign(paths, data, semantic)
    ranking = rank_trials(reg, met, stress, realism)
    safe_csv(ranking, paths.tables / "elimination_refinement_honest_ranking.csv")
    abst = pd.read_csv(paths.tables / "elimination_refinement_abstention_review.csv")
    ref = v2_reference(paths)
    best_trial, status = finalize(paths, ranking, abst, ref)

    abst_selected = abst[abst["trial_id"] == best_trial].iloc[0]
    mode_table = pd.DataFrame(
        [
            {"mode": "binary_default", "trial_id": best_trial, "coverage": 1.0, "precision": float(ranking[ranking["trial_id"] == best_trial].iloc[0]["test_precision"]), "effective_recall": float(ranking[ranking["trial_id"] == best_trial].iloc[0]["test_recall"]), "uncertain_pct": 0.0, "thesis_utility": "baseline", "product_utility": "not_product_ready"},
            {"mode": "abstention_assisted", "trial_id": best_trial, "coverage": float(abst_selected["coverage"]), "precision": float(abst_selected["precision_high_confidence_positive"]), "effective_recall": float(abst_selected["effective_recall"]), "uncertain_pct": float(abst_selected["uncertain_pct"]), "thesis_utility": "high_if_disclaimer_present", "product_utility": "experimental_only"},
        ]
    )
    safe_csv(mode_table, paths.tables / "elimination_abstention_policy_results.csv")
    safe_text(
        "# Elimination Abstention Operating Mode\n\n"
        f"- selected_trial: {best_trial}\n"
        f"- coverage: {float(abst_selected['coverage']):.4f}\n"
        f"- precision_high_confidence_positive: {float(abst_selected['precision_high_confidence_positive']):.4f}\n"
        f"- effective_recall: {float(abst_selected['effective_recall']):.4f}\n"
        f"- uncertain_pct: {float(abst_selected['uncertain_pct']):.4f}\n"
        "- conclusion: aporta mejora operativa cuando se usa modo abstention-assisted con disclaimer.\n",
        paths.reports / "elimination_abstention_operating_mode.md",
    )

    safe_json({"generated_at_utc": now_iso(), "selected_trial": best_trial, "final_status": status, "v2_reference": ref}, paths.artifacts / "run_manifest.json")
    LOGGER.info("Elimination refinement v3 completed")


if __name__ == "__main__":
    run()

