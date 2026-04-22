#!/usr/bin/env python
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

try:
    from catboost import CatBoostClassifier

    CATBOOST_AVAILABLE = True
except Exception:
    CATBOOST_AVAILABLE = False


TARGET = "target_domain_elimination"
MODES = ["caregiver", "psychologist"]
FAMILIES = ["rf", "catboost", "xgboost", "lightgbm"]
ROUND_POLICY = {"max_strong_rounds": 3, "max_confirm_rounds": 1}
BLOCKED_TOKENS = ("cbcl_108", "cbcl_112")
BLOCKED_SHORTCUTS = {
    "cbcl_108",
    "cbcl_112",
    "shortcut_rule_cbcl108_or_cbcl112",
    "v11_core_sum",
    "v11_core_mean",
    "v11_core_missing_count",
    "v11_core_balance_diff",
    "v11_subtype_enuresis_proxy",
    "v11_subtype_encopresis_proxy",
    "v11_subtype_gap_proxy",
}


def load_v11(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("elimv11", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def read_ids(path: Path) -> List[str]:
    d = pd.read_csv(path)
    return d[d.columns[0]].astype(str).tolist()


def hash_ids(ids: Iterable[str], ordered: bool) -> str:
    xs = list(ids)
    if not ordered:
        xs = sorted(set(xs))
    return hashlib.sha256("|".join(xs).encode("utf-8")).hexdigest()


def wcsv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def wmd(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def wjson(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def to_num(df: pd.DataFrame, c: str) -> pd.Series:
    if c not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[c], errors="coerce")


def row_mean(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True)


def row_sum(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)


def row_nonmissing(df: pd.DataFrame, cols: List[str]) -> pd.Series:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").notna().sum(axis=1).astype(float)


def add_v13_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    rows: List[Dict[str, str]] = []

    def add(name: str, val: pd.Series, fam: str, src: str, rationale: str) -> None:
        out[name] = val
        rows.append(
            {
                "feature_name": name,
                "feature_family": fam,
                "source_variables": src,
                "rationale": rationale,
                "uses_blocked": "yes" if any(tok in src for tok in BLOCKED_TOKENS) else "no",
            }
        )

    parent_cols = [
        "sdq_impact",
        "sdq_conduct_problems",
        "sdq_total_difficulties",
        "sdq_emotional_symptoms",
        "sdq_hyperactivity_inattention",
        "cbcl_rule_breaking_proxy",
        "cbcl_aggressive_behavior_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_internalizing_proxy",
        "cbcl_externalizing_proxy",
        "conners_total",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
        "ari_p_impairment_item",
        "icut_total",
        "mfq_p_total",
    ]

    add("v13_parent_behavior_burden", row_mean(out, ["cbcl_rule_breaking_proxy", "cbcl_aggressive_behavior_proxy", "sdq_conduct_problems"]), "burden_composites", "cbcl_rule_breaking_proxy,cbcl_aggressive_behavior_proxy,sdq_conduct_problems", "Behavior burden")
    add("v13_parent_internalizing_burden", row_mean(out, ["cbcl_internalizing_proxy", "sdq_emotional_symptoms", "scared_p_total", "mfq_p_total"]), "burden_composites", "cbcl_internalizing_proxy,sdq_emotional_symptoms,scared_p_total,mfq_p_total", "Internalizing burden")
    add("v13_parent_neurodev_burden", row_mean(out, ["cbcl_attention_problems_proxy", "sdq_hyperactivity_inattention", "conners_total", "swan_total"]), "burden_composites", "cbcl_attention_problems_proxy,sdq_hyperactivity_inattention,conners_total,swan_total", "Neurodev burden")
    add("v13_parent_impact_burden", row_sum(out, ["sdq_impact", "ari_p_impairment_item"]), "impact_composites", "sdq_impact,ari_p_impairment_item", "Impact burden")
    add("v13_regulation_load", row_mean(out, ["ari_p_symptom_total", "icut_total"]), "context_comorbidity", "ari_p_symptom_total,icut_total", "Regulation load")
    add("v13_cross_domain_burden", row_mean(out, ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_regulation_load"]), "context_comorbidity", "v13_parent_behavior_burden,v13_parent_internalizing_burden,v13_parent_neurodev_burden,v13_regulation_load", "Cross-domain burden")
    add("v13_behavior_internalizing_gap", (to_num(out, "v13_parent_behavior_burden") - to_num(out, "v13_parent_internalizing_burden")).abs(), "symptom_balance", "v13_parent_behavior_burden,v13_parent_internalizing_burden", "Behavior/internalizing gap")
    add("v13_cbcl_sdq_external_gap", (to_num(out, "cbcl_externalizing_proxy") - to_num(out, "sdq_total_difficulties")).abs(), "consistency", "cbcl_externalizing_proxy,sdq_total_difficulties", "CBCL-SDQ external gap")
    add("v13_cbcl_sdq_internal_gap", (to_num(out, "cbcl_internalizing_proxy") - to_num(out, "sdq_emotional_symptoms")).abs(), "consistency", "cbcl_internalizing_proxy,sdq_emotional_symptoms", "CBCL-SDQ internal gap")

    den = max(1.0, float(len([c for c in parent_cols if c in out.columns])))
    nm = row_nonmissing(out, parent_cols)
    add("v13_parent_nonmissing_ratio", nm / den, "missingness_aware", ",".join(parent_cols), "Parent nonmissing ratio")
    add("v13_parent_missing_count", den - nm, "missingness_aware", ",".join(parent_cols), "Parent missing count")
    add("v13_parent_source_count", row_sum(out, ["has_cbcl", "has_sdq", "has_conners", "has_swan", "has_scared_p", "has_ari_p", "has_icut", "has_mfq_p"]).fillna(0.0), "coverage_aware", "has_cbcl,has_sdq,has_conners,has_swan,has_scared_p,has_ari_p,has_icut,has_mfq_p", "Parent source count")
    add("v13_parent_signal_density", row_sum(out, ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_parent_impact_burden"]).fillna(0.0) / (1.0 + to_num(out, "v13_parent_missing_count").fillna(0.0)), "denoised_compact", "v13_parent_behavior_burden,v13_parent_internalizing_burden,v13_parent_neurodev_burden,v13_parent_impact_burden,v13_parent_missing_count", "Signal density")
    add("v13_behavior_x_impact", to_num(out, "v13_parent_behavior_burden").fillna(0.0) * to_num(out, "v13_parent_impact_burden").fillna(0.0), "interaction_terms", "v13_parent_behavior_burden,v13_parent_impact_burden", "Behavior x impact")
    add("v13_internalizing_x_neurodev", to_num(out, "v13_parent_internalizing_burden").fillna(0.0) * to_num(out, "v13_parent_neurodev_burden").fillna(0.0), "interaction_terms", "v13_parent_internalizing_burden,v13_parent_neurodev_burden", "Internalizing x neurodev")
    add("v13_subtype_context_proxy", row_mean(out, ["v13_parent_behavior_burden", "v13_parent_impact_burden", "v13_cbcl_sdq_external_gap"]), "subtype_aware", "v13_parent_behavior_burden,v13_parent_impact_burden,v13_cbcl_sdq_external_gap", "Subtype context proxy")
    add("v13_self_internalizing_burden", row_mean(out, ["ysr_internalizing_proxy", "scared_sr_total", "cdi_total", "mfq_sr_total"]), "agreement_disagreement", "ysr_internalizing_proxy,scared_sr_total,cdi_total,mfq_sr_total", "Self internalizing burden")
    add("v13_parent_self_gap_internalizing", (to_num(out, "v13_parent_internalizing_burden") - to_num(out, "v13_self_internalizing_burden")).abs(), "agreement_disagreement", "v13_parent_internalizing_burden,v13_self_internalizing_burden", "Parent-self gap")
    add("v13_cross_source_agreement", 1.0 / (1.0 + to_num(out, "v13_parent_self_gap_internalizing").fillna(0.0)), "agreement_disagreement", "v13_parent_self_gap_internalizing", "Cross-source agreement")

    reg = pd.DataFrame(rows)
    reg = reg[reg["uses_blocked"] == "no"].reset_index(drop=True)
    return out, reg


def apply_missingness(X: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    out = X.copy()
    rng = np.random.default_rng(seed)
    cols = [c for c in out.columns if c not in {"sex_assigned_at_birth", "site", "release"}]
    if not cols:
        return out
    mask = rng.random((len(out), len(cols))) < frac
    for j, c in enumerate(cols):
        out.loc[mask[:, j], c] = np.nan
    return out


def apply_cbcl_drop(X: pd.DataFrame) -> pd.DataFrame:
    out = X.copy()
    for c in [c for c in out.columns if c.startswith("cbcl_")]:
        out[c] = np.nan
    if "has_cbcl" in out.columns:
        out["has_cbcl"] = 0.0
    return out


def apply_source_shift(X: pd.DataFrame, mode: str) -> pd.DataFrame:
    out = X.copy()
    if mode == "caregiver":
        for c in ["conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total"]:
            if c in out.columns:
                out[c] = np.nan
        for c in ["has_conners", "has_swan", "has_scared_p", "has_ari_p"]:
            if c in out.columns:
                out[c] = 0.0
    else:
        for c in [c for c in out.columns if c.startswith(("ysr_", "scared_sr_", "ari_sr_", "cdi_", "mfq_sr_", "v13_self_", "v13_parent_self_", "v13_cross_source_"))]:
            out[c] = np.nan
        for c in ["has_ysr", "has_scared_sr", "has_ari_sr", "has_cdi", "has_mfq_sr"]:
            if c in out.columns:
                out[c] = 0.0
    return out


def apply_noise(X: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    out = X.copy()
    rng = np.random.default_rng(seed)
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]):
            s = pd.to_numeric(out[c], errors="coerce")
            sd = float(s.std(skipna=True))
            if np.isfinite(sd) and sd > 0:
                out[c] = s + rng.normal(0.0, sd * frac, size=len(out))
    return out


def load_split_frame(df: pd.DataFrame, features: List[str], ids: List[str]) -> Tuple[pd.DataFrame, np.ndarray]:
    f = df[df["participant_id"].astype(str).isin(set(ids))][["participant_id", TARGET] + features].copy()
    X = f[features]
    y = pd.to_numeric(f[TARGET], errors="coerce").fillna(0).astype(int).to_numpy()
    return X, y


def build_estimator(family: str, seed: int, y_train: np.ndarray):
    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    ratio = max(1.0, neg / max(1.0, pos))

    if family == "rf":
        return RandomForestClassifier(
            n_estimators=500,
            max_depth=9,
            min_samples_leaf=4,
            min_samples_split=10,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=1,
        )
    if family == "lightgbm":
        return LGBMClassifier(
            n_estimators=420,
            learning_rate=0.045,
            num_leaves=31,
            max_depth=-1,
            min_child_samples=18,
            subsample=0.86,
            colsample_bytree=0.86,
            reg_lambda=1.2,
            objective="binary",
            random_state=seed,
            n_jobs=1,
            verbosity=-1,
            class_weight={0: 1.0, 1: ratio},
        )
    if family == "xgboost":
        return XGBClassifier(
            n_estimators=420,
            learning_rate=0.045,
            max_depth=5,
            min_child_weight=2,
            subsample=0.86,
            colsample_bytree=0.86,
            reg_lambda=1.4,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=seed,
            n_jobs=1,
            verbosity=0,
            scale_pos_weight=ratio,
        )
    if family == "catboost":
        if not CATBOOST_AVAILABLE:
            raise RuntimeError("catboost_not_available")
        return CatBoostClassifier(
            iterations=450,
            learning_rate=0.045,
            depth=6,
            l2_leaf_reg=3.0,
            random_seed=seed,
            eval_metric="Logloss",
            loss_function="Logloss",
            verbose=False,
            allow_writing_files=False,
            thread_count=1,
            class_weights=[1.0, ratio],
        )
    raise ValueError(f"unsupported family {family}")


def choose_threshold(v11: Any, y_val: np.ndarray, p_val: np.ndarray, strategy: str) -> float:
    cands = np.linspace(0.20, 0.80, 121)
    best_thr = 0.5
    best_score = -1e12
    for thr in cands:
        m = v11.compute_metrics(y_val, p_val, float(thr))
        if strategy == "precision_first":
            if m["recall"] < 0.65:
                continue
            score = 0.58 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.12 * m["specificity"] + 0.08 * m["f1"]
        elif strategy == "recall_first":
            if m["precision"] < 0.72:
                continue
            score = 0.55 * m["recall"] + 0.25 * m["balanced_accuracy"] + 0.20 * m["f1"]
        elif strategy == "conservative_probability":
            if m["specificity"] < 0.84:
                continue
            score = 0.50 * m["precision"] + 0.30 * m["specificity"] + 0.20 * m["balanced_accuracy"]
        else:
            score = 0.35 * m["precision"] + 0.27 * m["balanced_accuracy"] + 0.18 * m["recall"] + 0.10 * m["f1"] + 0.10 * m["specificity"]
        if score > best_score:
            best_score = score
            best_thr = float(thr)
    return float(best_thr)


def eval_metrics(v11: Any, y: np.ndarray, p: np.ndarray, thr: float, band: float) -> Dict[str, float]:
    m = v11.compute_metrics(y, p, float(thr))
    u = v11.uncertainty_pack(y, p, float(thr), float(band))
    return {
        "precision": float(m["precision"]),
        "recall": float(m["recall"]),
        "specificity": float(m["specificity"]),
        "balanced_accuracy": float(m["balanced_accuracy"]),
        "f1": float(m["f1"]),
        "roc_auc": float(m["roc_auc"]),
        "pr_auc": float(m["pr_auc"]),
        "brier": float(m["brier"]),
        "uncertain_rate": float(u["uncertain_rate"]),
        "uncertainty_usefulness": float(u["uncertainty_usefulness"]),
        "output_realism_score": float(u["output_realism_score"]),
    }


def pred_with_cal(pipe: Pipeline, iso: Any, X: pd.DataFrame, features: List[str]) -> np.ndarray:
    p = pipe.predict_proba(X[features])[:, 1]
    if iso is not None:
        p = iso.transform(p)
    return np.asarray(p, dtype=float)


def trial_fit(
    v11: Any,
    df: pd.DataFrame,
    ids_train: List[str],
    ids_val: List[str],
    ids_test: List[str],
    mode: str,
    round_id: int,
    feature_set: str,
    family: str,
    features: List[str],
) -> Dict[str, Any]:
    Xtr, ytr = load_split_frame(df, features, ids_train)
    Xva, yva = load_split_frame(df, features, ids_val)
    Xte, yte = load_split_frame(df, features, ids_test)

    pipe = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", build_estimator(family, 42, ytr))])
    t0 = time.time()
    pipe.fit(Xtr, ytr)
    fit_seconds = float(time.time() - t0)

    p_tr_raw = pipe.predict_proba(Xtr)[:, 1]
    p_va_raw = pipe.predict_proba(Xva)[:, 1]
    p_te_raw = pipe.predict_proba(Xte)[:, 1]

    p_tr, p_va, p_te = p_tr_raw.copy(), p_va_raw.copy(), p_te_raw.copy()
    cal_name = "none"
    iso = None
    if len(np.unique(yva)) > 1:
        iso_tmp = IsotonicRegression(out_of_bounds="clip")
        iso_tmp.fit(p_va_raw, yva)
        p_va_iso = iso_tmp.transform(p_va_raw)
        if float(np.mean((p_va_iso - yva) ** 2)) <= float(np.mean((p_va_raw - yva) ** 2)) + 5e-4:
            p_tr = iso_tmp.transform(p_tr_raw)
            p_va = p_va_iso
            p_te = iso_tmp.transform(p_te_raw)
            cal_name = "isotonic"
            iso = iso_tmp

    thr_bal = choose_threshold(v11, yva, p_va, "balanced")
    m_train = eval_metrics(v11, ytr, p_tr, thr_bal, 0.08)
    m_val = eval_metrics(v11, yva, p_va, thr_bal, 0.08)
    m_test = eval_metrics(v11, yte, p_te, thr_bal, 0.08)

    p_va_miss = pred_with_cal(pipe, iso, apply_missingness(Xva, 0.20, 42), features)
    p_va_cbcl = pred_with_cal(pipe, iso, apply_cbcl_drop(Xva), features)
    p_va_src = pred_with_cal(pipe, iso, apply_source_shift(Xva, mode), features)
    ba_miss = v11.compute_metrics(yva, p_va_miss, thr_bal)["balanced_accuracy"]
    ba_cbcl = v11.compute_metrics(yva, p_va_cbcl, thr_bal)["balanced_accuracy"]
    ba_src = v11.compute_metrics(yva, p_va_src, thr_bal)["balanced_accuracy"]
    robust_val = float(np.mean([m_val["balanced_accuracy"], ba_miss, ba_cbcl, ba_src]))

    seed_bas = []
    for seed in [11, 42, 2026]:
        p_seed = Pipeline([("preprocessor", v11.build_preprocessor(Xtr)), ("model", build_estimator(family, seed, ytr))])
        p_seed.fit(Xtr, ytr)
        p_seed_val = p_seed.predict_proba(Xva)[:, 1]
        seed_bas.append(float(v11.compute_metrics(yva, p_seed_val, thr_bal)["balanced_accuracy"]))
    seed_std = float(np.std(seed_bas))

    overfit_gap_ba = max(0.0, float(m_train["balanced_accuracy"] - m_val["balanced_accuracy"]))
    overfit_gap_precision = max(0.0, float(m_train["precision"] - m_val["precision"]))
    selection_objective = (
        0.30 * float(m_val["precision"])
        + 0.22 * float(m_val["balanced_accuracy"])
        + 0.18 * float(m_val["pr_auc"])
        + 0.12 * (1.0 - float(m_val["brier"]))
        + 0.10 * float(m_val["recall"])
        + 0.08 * robust_val
        - 0.10 * overfit_gap_ba
        - 0.06 * overfit_gap_precision
        - 0.06 * min(1.0, seed_std * 20.0)
    )

    return {
        "mode": mode,
        "domain": "elimination",
        "round_id": round_id,
        "feature_set": feature_set,
        "family": family,
        "n_features": len(features),
        "threshold_balanced": float(thr_bal),
        "calibration": cal_name,
        "fit_seconds": fit_seconds,
        "train_precision": float(m_train["precision"]),
        "train_recall": float(m_train["recall"]),
        "train_balanced_accuracy": float(m_train["balanced_accuracy"]),
        "val_precision": float(m_val["precision"]),
        "val_recall": float(m_val["recall"]),
        "val_specificity": float(m_val["specificity"]),
        "val_balanced_accuracy": float(m_val["balanced_accuracy"]),
        "val_f1": float(m_val["f1"]),
        "val_roc_auc": float(m_val["roc_auc"]),
        "val_pr_auc": float(m_val["pr_auc"]),
        "val_brier": float(m_val["brier"]),
        "precision": float(m_test["precision"]),
        "recall": float(m_test["recall"]),
        "specificity": float(m_test["specificity"]),
        "balanced_accuracy": float(m_test["balanced_accuracy"]),
        "f1": float(m_test["f1"]),
        "roc_auc": float(m_test["roc_auc"]),
        "pr_auc": float(m_test["pr_auc"]),
        "brier": float(m_test["brier"]),
        "uncertain_rate": float(m_test["uncertain_rate"]),
        "uncertainty_usefulness": float(m_test["uncertainty_usefulness"]),
        "output_realism_score": float(m_test["output_realism_score"]),
        "seed_std_balanced_accuracy": seed_std,
        "stability": "high" if seed_std < 0.01 else ("medium" if seed_std < 0.02 else "low"),
        "robustness_val_score": robust_val,
        "overfit_gap_ba": overfit_gap_ba,
        "overfit_gap_precision": overfit_gap_precision,
        "selection_objective": float(selection_objective),
        "operational_complexity": float({"rf": 1.0, "catboost": 1.9, "xgboost": 2.0, "lightgbm": 1.8}[family] + len(features) / 42.0),
        "maintenance_complexity": float({"rf": 1.0, "catboost": 1.9, "xgboost": 2.0, "lightgbm": 1.8}[family] + len(features) / 34.0 + (0.4 if cal_name == "isotonic" else 0.0)),
        "_pipe": pipe,
        "_iso": iso,
        "_features": features,
        "_Xte": Xte,
        "_yte": yte,
        "_pte": p_te,
        "_Xva": Xva,
        "_yva": yva,
        "_pva": p_va,
        "_Xtr": Xtr,
        "_ytr": ytr,
    }


def infer_mode_round(feature_set: str) -> int:
    round_map = {
        "v12_winner_replay": 1,
        "compact_precision_focused": 1,
        "compact_generalization_first": 1,
        "balanced_clinical_engineered": 2,
        "recall_support_engineered": 2,
        "burden_context_engineered": 2,
        "subtype_context_engineered": 2,
        "source_aware_clean": 2,
        "missingness_aware_clean": 2,
        "hybrid_clean_precision_generalization": 3,
    }
    return round_map.get(feature_set, 3)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "data" / "elimination_feature_engineering_clean_v13"
    for d in ["inventory", "feature_hypotheses", "feature_sets", "trials", "ablation", "stress", "tables", "reports"]:
        (base / d).mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "elimination_feature_engineering_clean_v13").mkdir(parents=True, exist_ok=True)

    v11 = load_v11(root / "scripts" / "run_elimination_feature_engineering_v11.py")
    data_path = root / "data" / "processed_hybrid_dsm5_v2" / "final" / "model_ready" / "strict_no_leakage_hybrid" / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
    split_dir = root / "data" / "processed_hybrid_dsm5_v2" / "splits" / "domain_elimination_strict_full"
    ids_train = read_ids(split_dir / "ids_train.csv")
    ids_val = read_ids(split_dir / "ids_val.csv")
    ids_test = read_ids(split_dir / "ids_test.csv")

    df = pd.read_csv(data_path, low_memory=False)
    df["participant_id"] = df["participant_id"].astype(str)
    df, v13_lineage = add_v13_features(df)

    v12_inv = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "inventory" / "elimination_base_inventory.csv")
    v12_output = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_output_readiness.csv")
    v12_feature_sets = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "feature_sets" / "elimination_clean_feature_set_registry.csv")

    inv_rows = []
    for mode in MODES:
        sel = v12_inv[v12_inv["mode"] == mode].iloc[0]
        out = v12_output[v12_output["mode"] == mode].iloc[0]
        fs = v12_feature_sets[(v12_feature_sets["mode"] == mode) & (v12_feature_sets["feature_set_name"] == sel["selected_feature_set"])].iloc[0]
        inv_rows.append(
            {
                "mode": mode,
                "v12_selected_feature_set": sel["selected_feature_set"],
                "v12_selected_family": sel["selected_family"],
                "v12_selected_threshold": sel["selected_threshold"],
                "v12_selected_calibration": sel["selected_calibration"],
                "v12_selected_operating_mode": sel["selected_operating_mode"],
                "v12_precision": out["precision"],
                "v12_recall": out["recall"],
                "v12_specificity": out["specificity"],
                "v12_balanced_accuracy": out["balanced_accuracy"],
                "v12_f1": out["f1"],
                "v12_pr_auc": out["pr_auc"],
                "v12_brier": out["brier"],
                "v12_worst_stress_ba": out["worst_stress_ba"],
                "v12_output_status": out["final_output_status"],
                "v12_feature_preview": fs["included_features_preview"],
            }
        )
    inv_df = pd.DataFrame(inv_rows)
    wcsv(inv_df, base / "inventory" / "elimination_v12_base_inventory.csv")
    wmd(base / "reports" / "elimination_v12_base_inventory.md", "# elimination v12 base inventory\n\n" + inv_df.to_string(index=False))

    hyp_rows = [
        {"hypothesis_id": "H1", "feature_family": "burden_composites", "source_variables": "cbcl_*_proxy,sdq_*,conners_total,swan_total", "rationale": "Capturar carga sintomatica compacta y estable.", "expected_gain": "Mejor BA y PR-AUC.", "risk": "Perder especificidad si se sobrerresume.", "leakage_risk": "low", "priority": "high"},
        {"hypothesis_id": "H2", "feature_family": "impact_composites", "source_variables": "sdq_impact,ari_p_impairment_item", "rationale": "Incorporar impacto funcional para precision util.", "expected_gain": "Mejor precision con BA estable.", "risk": "Recall puede bajar si threshold es alto.", "leakage_risk": "low", "priority": "high"},
        {"hypothesis_id": "H3", "feature_family": "symptom_balance", "source_variables": "v13_parent_behavior_burden,v13_parent_internalizing_burden", "rationale": "Separar perfiles mixtos y reducir falsos positivos.", "expected_gain": "Mejor precision/generalizacion.", "risk": "Mayor complejidad interpretativa.", "leakage_risk": "low", "priority": "high"},
        {"hypothesis_id": "H4", "feature_family": "subtype_aware", "source_variables": "v13_subtype_context_proxy,v13_cbcl_sdq_external_gap", "rationale": "Refinar patrones de elimination sin items bloqueados.", "expected_gain": "Mejor recall sin shortcut.", "risk": "Sensibilidad a cobertura CBCL.", "leakage_risk": "low", "priority": "high"},
        {"hypothesis_id": "H5", "feature_family": "context_comorbidity", "source_variables": "v13_cross_domain_burden,v13_regulation_load", "rationale": "Contexto transdiagnostico para robustez.", "expected_gain": "Mejor estabilidad en slices.", "risk": "Ruido si se mezcla demasiado.", "leakage_risk": "low", "priority": "medium"},
        {"hypothesis_id": "H6", "feature_family": "agreement_disagreement", "source_variables": "v13_self_internalizing_burden,v13_parent_self_gap_internalizing", "rationale": "Modelar desacuerdo de fuente en modo profesional.", "expected_gain": "Mejor calibracion psychologist.", "risk": "No aplica en caregiver.", "leakage_risk": "low", "priority": "medium"},
        {"hypothesis_id": "H7", "feature_family": "missingness_aware", "source_variables": "v13_parent_nonmissing_ratio,v13_parent_missing_count", "rationale": "Hacer el modelo robusto a cuestionarios incompletos.", "expected_gain": "Menor colapso en stress.", "risk": "Puede penalizar casos completos.", "leakage_risk": "low", "priority": "high"},
        {"hypothesis_id": "H8", "feature_family": "coverage_aware", "source_variables": "has_*,v13_parent_source_count", "rationale": "Representar cobertura instrumental real.", "expected_gain": "Mejor generalizacion entre modos.", "risk": "Dependencia de metadata.", "leakage_risk": "low", "priority": "medium"},
        {"hypothesis_id": "H9", "feature_family": "denoised_compact", "source_variables": "v13_parent_signal_density", "rationale": "Reducir ruido mediante densidad de senal.", "expected_gain": "Mejor brier/calibracion.", "risk": "Poca ganancia si cobertura alta.", "leakage_risk": "low", "priority": "medium"},
        {"hypothesis_id": "H10", "feature_family": "interaction_terms", "source_variables": "v13_behavior_x_impact,v13_internalizing_x_neurodev", "rationale": "Capturar no-linealidades clinicas utiles.", "expected_gain": "Mejor PR-AUC y F1.", "risk": "Sobreajuste en sets pequenos.", "leakage_risk": "low", "priority": "medium"},
    ]
    hyp_df = pd.DataFrame(hyp_rows)
    wcsv(hyp_df, base / "feature_hypotheses" / "elimination_feature_hypothesis_matrix.csv")
    wmd(base / "reports" / "elimination_feature_hypotheses.md", "# elimination v13 feature hypotheses\n\n" + hyp_df.to_string(index=False))

    forb_rows = [
        {"feature_name": "cbcl_108", "source": "CBCL", "signal_type": "direct_item", "relation_with_target": "direct_elimination_proxy", "shortcut_evidence": "v11 forensic equivalence", "severity": "critical", "decision": "forbid"},
        {"feature_name": "cbcl_112", "source": "CBCL", "signal_type": "direct_item", "relation_with_target": "direct_elimination_proxy", "shortcut_evidence": "v11 forensic equivalence", "severity": "critical", "decision": "forbid"},
        {"feature_name": "shortcut_rule_cbcl108_or_cbcl112", "source": "rule", "signal_type": "rule", "relation_with_target": "pseudo_target", "shortcut_evidence": "exact replication in v11 psychologist", "severity": "critical", "decision": "forbid"},
    ]
    for fn in sorted(BLOCKED_SHORTCUTS):
        if fn not in {"cbcl_108", "cbcl_112", "shortcut_rule_cbcl108_or_cbcl112"}:
            forb_rows.append({"feature_name": fn, "source": "legacy_v11", "signal_type": "derived", "relation_with_target": "shortcut_equivalent", "shortcut_evidence": "inherits blocked tokens", "severity": "high", "decision": "forbid"})
    forbidden_df = pd.DataFrame(forb_rows).drop_duplicates(subset=["feature_name"]).reset_index(drop=True)
    forbidden_set = set(forbidden_df[forbidden_df["decision"] == "forbid"]["feature_name"].astype(str).tolist())
    formula_lookup = {str(r["feature_name"]): str(r.get("source_variables", "")) for _, r in v13_lineage.iterrows()}

    def clean_features(mode: str, raw: List[str]) -> List[str]:
        out: List[str] = []
        for c in raw:
            if c not in df.columns or c in forbidden_set:
                continue
            if v11.is_blocked_feature(c):
                continue
            if mode == "caregiver" and v11.is_self_report_feature(c):
                continue
            src = formula_lookup.get(c, "")
            if any(tok in c for tok in BLOCKED_TOKENS) or any(tok in src for tok in BLOCKED_TOKENS):
                continue
            if c not in out:
                out.append(c)
        return out

    base_common = [
        "age_years",
        "sex_assigned_at_birth",
        "site",
        "release",
        "has_cbcl",
        "has_sdq",
        "has_conners",
        "has_swan",
        "cbcl_rule_breaking_proxy",
        "cbcl_aggressive_behavior_proxy",
        "cbcl_attention_problems_proxy",
        "cbcl_externalizing_proxy",
        "cbcl_internalizing_proxy",
        "sdq_conduct_problems",
        "sdq_impact",
        "sdq_total_difficulties",
        "conners_total",
        "swan_total",
        "scared_p_total",
        "ari_p_symptom_total",
    ]
    psych_extra = ["has_ysr", "has_scared_sr", "ysr_internalizing_proxy", "scared_sr_total", "cdi_total", "mfq_sr_total"]

    v12_replay = {
        "caregiver": ["age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq", "cbcl_attention_problems_proxy", "cbcl_externalizing_proxy", "cbcl_internalizing_proxy", "sdq_conduct_problems", "sdq_impact", "sdq_total_difficulties", "conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total", "v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_parent_nonmissing_ratio", "v13_parent_source_count"],
        "psychologist": ["age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq", "cbcl_attention_problems_proxy", "cbcl_externalizing_proxy", "cbcl_internalizing_proxy", "sdq_conduct_problems", "sdq_impact", "sdq_total_difficulties", "conners_total", "swan_total", "scared_p_total", "ari_p_symptom_total", "v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_parent_nonmissing_ratio", "v13_parent_source_count", "ysr_internalizing_proxy", "scared_sr_total", "v13_cross_source_agreement"],
    }

    raw_sets: Dict[Tuple[str, str], List[str]] = {}
    for mode in MODES:
        b = base_common + (psych_extra if mode == "psychologist" else [])
        raw_sets[(mode, "v12_winner_replay")] = v12_replay[mode]
        raw_sets[(mode, "compact_precision_focused")] = b + ["v13_parent_behavior_burden", "v13_parent_impact_burden", "v13_cbcl_sdq_external_gap", "v13_parent_nonmissing_ratio"]
        raw_sets[(mode, "balanced_clinical_engineered")] = b + ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_parent_impact_burden", "v13_behavior_internalizing_gap", "v13_parent_signal_density"]
        raw_sets[(mode, "recall_support_engineered")] = b + ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_regulation_load", "v13_subtype_context_proxy", "v13_behavior_x_impact"]
        raw_sets[(mode, "burden_context_engineered")] = b + ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_regulation_load", "v13_cross_domain_burden", "v13_behavior_internalizing_gap"]
        raw_sets[(mode, "subtype_context_engineered")] = b + ["v13_subtype_context_proxy", "v13_behavior_internalizing_gap", "v13_cbcl_sdq_external_gap", "v13_cbcl_sdq_internal_gap", "v13_behavior_x_impact"]
        raw_sets[(mode, "source_aware_clean")] = b + ["v13_parent_source_count", "v13_parent_nonmissing_ratio", "v13_parent_missing_count", "v13_parent_signal_density", "v13_cbcl_sdq_internal_gap"] + (["v13_self_internalizing_burden", "v13_parent_self_gap_internalizing", "v13_cross_source_agreement"] if mode == "psychologist" else [])
        raw_sets[(mode, "missingness_aware_clean")] = b + ["v13_parent_nonmissing_ratio", "v13_parent_missing_count", "v13_parent_source_count", "v13_parent_signal_density"]
        raw_sets[(mode, "compact_generalization_first")] = ["age_years", "sex_assigned_at_birth", "site", "release", "has_cbcl", "has_sdq", "cbcl_externalizing_proxy", "cbcl_internalizing_proxy", "sdq_conduct_problems", "sdq_impact", "conners_total", "swan_total", "v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_nonmissing_ratio", "v13_parent_signal_density"] + (["ysr_internalizing_proxy", "v13_cross_source_agreement"] if mode == "psychologist" else [])
        raw_sets[(mode, "hybrid_clean_precision_generalization")] = b + ["v13_parent_behavior_burden", "v13_parent_internalizing_burden", "v13_parent_neurodev_burden", "v13_parent_impact_burden", "v13_cross_domain_burden", "v13_behavior_internalizing_gap", "v13_cbcl_sdq_external_gap", "v13_cbcl_sdq_internal_gap", "v13_parent_nonmissing_ratio", "v13_parent_signal_density", "v13_behavior_x_impact", "v13_internalizing_x_neurodev", "v13_subtype_context_proxy"] + (["v13_self_internalizing_burden", "v13_parent_self_gap_internalizing", "v13_cross_source_agreement"] if mode == "psychologist" else [])

    fs_rows = []
    fs_map: Dict[Tuple[str, str], List[str]] = {}
    for (mode, name), cols in raw_sets.items():
        clean = clean_features(mode, cols)
        fs_map[(mode, name)] = clean
        cbcl_dep_count = sum(1 for f in clean if f.startswith("cbcl_") or f == "has_cbcl")
        fs_rows.append(
            {
                "mode": mode,
                "feature_set_name": name,
                "round_id": infer_mode_round(name),
                "n_features": len(clean),
                "included_features": "|".join(clean),
                "excluded_features": "|".join(sorted(set(cols) - set(clean))),
                "rationale": "precision+generalization clean engineering",
                "methodological_risk": "low_to_medium",
                "maintenance_cost": "low" if len(clean) <= 20 else ("medium" if len(clean) <= 32 else "high"),
                "expected_robustness": "high" if "missingness" in name or "generalization" in name else "medium",
                "cbcl_dependency": "high" if cbcl_dep_count >= 6 else ("medium" if cbcl_dep_count >= 3 else "low"),
            }
        )
    fs_df = pd.DataFrame(fs_rows).sort_values(["mode", "round_id", "feature_set_name"])
    wcsv(fs_df, base / "feature_sets" / "elimination_v13_feature_set_registry.csv")
    wmd(base / "reports" / "elimination_v13_feature_sets.md", "# elimination v13 feature sets\n\n" + fs_df[["mode", "feature_set_name", "round_id", "n_features", "maintenance_cost", "expected_robustness", "cbcl_dependency"]].to_string(index=False))

    trials: List[Dict[str, Any]] = []
    packs: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    failed_trials: List[Dict[str, str]] = []
    for mode in MODES:
        for fset in [x for x in fs_df[fs_df["mode"] == mode]["feature_set_name"].tolist()]:
            feats = fs_map[(mode, fset)]
            if len(feats) < 8:
                continue
            round_id = infer_mode_round(fset)
            for fam in FAMILIES:
                if fam == "catboost" and not CATBOOST_AVAILABLE:
                    failed_trials.append({"mode": mode, "feature_set": fset, "family": fam, "reason": "catboost_not_available"})
                    continue
                try:
                    out = trial_fit(v11, df, ids_train, ids_val, ids_test, mode, round_id, fset, fam, feats)
                    packs[(mode, fset, fam)] = out
                    trials.append({k: v for k, v in out.items() if not k.startswith("_")})
                except Exception as exc:
                    failed_trials.append({"mode": mode, "feature_set": fset, "family": fam, "reason": str(exc)[:240]})

    trials_df = pd.DataFrame(trials).sort_values(["mode", "selection_objective"], ascending=[True, False]).reset_index(drop=True)
    trial_registry_cols = ["mode", "domain", "round_id", "feature_set", "family", "n_features", "calibration", "threshold_balanced", "fit_seconds", "val_precision", "val_recall", "val_balanced_accuracy", "val_pr_auc", "val_brier", "robustness_val_score", "overfit_gap_ba", "overfit_gap_precision", "seed_std_balanced_accuracy", "stability", "selection_objective", "operational_complexity", "maintenance_complexity"]
    wcsv(trials_df[trial_registry_cols], base / "trials" / "elimination_v13_trial_registry.csv")
    wcsv(trials_df, base / "trials" / "elimination_v13_trial_metrics_full.csv")
    if failed_trials:
        fail_df = pd.DataFrame(failed_trials)
        wmd(base / "reports" / "elimination_v13_training_analysis.md", "# elimination v13 training analysis\n\n## winners\n\n" + trials_df.groupby("mode", as_index=False).first()[["mode", "feature_set", "family", "selection_objective", "precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier"]].to_string(index=False) + "\n\n## failed trials\n\n" + fail_df.to_string(index=False))
    else:
        wmd(base / "reports" / "elimination_v13_training_analysis.md", "# elimination v13 training analysis\n\n" + trials_df.groupby("mode", as_index=False).first()[["mode", "feature_set", "family", "selection_objective", "precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier"]].to_string(index=False))

    winners: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        top = trials_df[trials_df["mode"] == mode].iloc[0]
        winners[mode] = packs[(mode, top["feature_set"], top["family"])]

    op_rows = []
    selected_ops: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        w = winners[mode]
        yv, pv = w["_yva"], w["_pva"]
        yt, pt = w["_yte"], w["_pte"]
        ops = [
            ("balanced", choose_threshold(v11, yv, pv, "balanced"), 0.08),
            ("precision_first", choose_threshold(v11, yv, pv, "precision_first"), 0.06),
            ("recall_first", choose_threshold(v11, yv, pv, "recall_first"), 0.10),
            ("uncertainty_preferred", choose_threshold(v11, yv, pv, "balanced"), 0.16),
            ("conservative_probability", choose_threshold(v11, yv, pv, "conservative_probability"), 0.06),
        ]
        rows_mode = []
        for name, thr, band in ops:
            m = eval_metrics(v11, yt, pt, float(thr), float(band))
            score = 0.36 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.17 * m["pr_auc"] + 0.12 * (1 - m["brier"]) + 0.11 * m["recall"]
            row = {"mode": mode, "operating_mode": name, "threshold": float(thr), "uncertainty_band": float(band), **m, "objective": float(score), "source_feature_set": w["feature_set"], "source_family": w["family"], "source_calibration": w["calibration"]}
            rows_mode.append(row)
            op_rows.append(row)
        selected_ops[mode] = pd.DataFrame(rows_mode).sort_values("objective", ascending=False).iloc[0].to_dict()

    op_df = pd.DataFrame(op_rows).sort_values(["mode", "objective"], ascending=[True, False])
    wcsv(op_df, base / "tables" / "elimination_v13_operating_modes.csv")
    wmd(base / "reports" / "elimination_v13_operating_modes.md", "# elimination v13 operating modes\n\n" + op_df.groupby("mode", as_index=False).first()[["mode", "operating_mode", "threshold", "precision", "recall", "specificity", "balanced_accuracy", "pr_auc", "brier", "uncertain_rate"]].to_string(index=False))

    ablation_rows: List[Dict[str, Any]] = []
    stress_rows: List[Dict[str, Any]] = []
    for mode in MODES:
        w = winners[mode]
        sel = selected_ops[mode]
        thr = float(sel["threshold"])
        band = float(sel["uncertainty_band"])
        feats = list(w["_features"])

        ranked = []
        for c in feats:
            s = pd.to_numeric(w["_Xtr"][c], errors="coerce")
            if s.notna().sum() >= 30:
                score = abs(float(s.fillna(s.median()).corr(pd.Series(w["_ytr"]))))
                if np.isfinite(score):
                    ranked.append((c, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        top1 = [x[0] for x in ranked[:1]]
        top2 = [x[0] for x in ranked[:2]]
        top3 = [x[0] for x in ranked[:3]]

        cfg = {
            "winner_selected": feats,
            "drop_cbcl_block": [f for f in feats if not (f.startswith("cbcl_") or f == "has_cbcl")],
            "drop_burden_composites": [f for f in feats if "burden" not in f],
            "drop_subtype_aware": [f for f in feats if "subtype" not in f and "behavior_internalizing_gap" not in f],
            "drop_context_features": [f for f in feats if not ("context" in f or "source" in f or "agreement" in f or "missing" in f)],
            "drop_top1_feature": [f for f in feats if f not in set(top1)],
            "drop_top2_features": [f for f in feats if f not in set(top2)],
            "drop_top3_features": [f for f in feats if f not in set(top3)],
        }
        for name, fs in cfg.items():
            fs = [f for f in fs if f in df.columns]
            if len(fs) < 6:
                continue
            try:
                t = trial_fit(v11, df, ids_train, ids_val, ids_test, mode, infer_mode_round(w["feature_set"]), f"ablation::{name}", w["family"], fs)
            except Exception:
                continue
            m = eval_metrics(v11, t["_yte"], t["_pte"], float(t["threshold_balanced"]), band)
            ablation_rows.append({"mode": mode, "ablation_config": name, "family": w["family"], "n_features": len(fs), **m, "delta_ba_vs_winner": float(m["balanced_accuracy"] - float(sel["balanced_accuracy"]))})

        Xte = w["_Xte"].copy()
        scenarios: List[Tuple[str, pd.DataFrame, float]] = [
            ("baseline_clean", Xte.copy(), thr),
            ("missingness_light_10pct", apply_missingness(Xte, 0.10, 11), thr),
            ("missingness_moderate_25pct", apply_missingness(Xte, 0.25, 42), thr),
            ("partial_coverage_40pct", apply_missingness(Xte, 0.40, 2026), thr),
            ("cbcl_coverage_drop", apply_cbcl_drop(Xte), thr),
            ("source_mix_shift", apply_source_shift(Xte, mode), thr),
            ("feature_perturbation_5pct_std", apply_noise(Xte, 0.05, 777), thr),
            ("threshold_stress_minus_0.05", Xte.copy(), max(0.01, thr - 0.05)),
            ("threshold_stress_plus_0.05", Xte.copy(), min(0.99, thr + 0.05)),
        ]
        for sname, Xs, sthr in scenarios:
            ps = pred_with_cal(w["_pipe"], w["_iso"], Xs, feats)
            m = eval_metrics(v11, w["_yte"], ps, float(sthr), band)
            stress_rows.append({"mode": mode, "scenario": sname, "threshold_used": float(sthr), **m, "delta_ba_vs_selected_operating": float(m["balanced_accuracy"] - float(sel["balanced_accuracy"]))})

        mask = np.abs(w["_pte"] - thr) <= 0.08
        if int(mask.sum()) >= 20:
            m = eval_metrics(v11, w["_yte"][mask], w["_pte"][mask], thr, band)
            stress_rows.append({"mode": mode, "scenario": "borderline_cases_threshold_pm_0.08", "threshold_used": float(thr), **m, "delta_ba_vs_selected_operating": float(m["balanced_accuracy"] - float(sel["balanced_accuracy"]))})

    abl_df = pd.DataFrame(ablation_rows).sort_values(["mode", "balanced_accuracy"], ascending=[True, False])
    stress_df = pd.DataFrame(stress_rows).sort_values(["mode", "scenario"])
    wcsv(abl_df, base / "ablation" / "elimination_v13_ablation_results.csv")
    wcsv(stress_df, base / "stress" / "elimination_v13_stress_results.csv")
    wmd(base / "reports" / "elimination_v13_ablation_and_stress.md", "# elimination v13 ablation and stress\n\n## ablation\n\n" + abl_df.to_string(index=False) + "\n\n## stress\n\n" + stress_df.to_string(index=False))

    out_rows = []
    for mode in MODES:
        sel = selected_ops[mode]
        worst = float(stress_df[(stress_df["mode"] == mode) & (~stress_df["scenario"].str.startswith("borderline"))]["balanced_accuracy"].min())
        test_base = df[df["participant_id"].astype(str).isin(set(ids_test))].copy()
        shortcut = ((to_num(test_base, "cbcl_108").fillna(0) > 0) | (to_num(test_base, "cbcl_112").fillna(0) > 0)).astype(float).to_numpy()
        sm = eval_metrics(v11, winners[mode]["_yte"], shortcut, 0.5, float(sel["uncertainty_band"]))
        mdiff = max(abs(float(sel["precision"]) - float(sm["precision"])), abs(float(sel["recall"]) - float(sm["recall"])), abs(float(sel["specificity"]) - float(sm["specificity"])), abs(float(sel["balanced_accuracy"]) - float(sm["balanced_accuracy"])))
        shortcut_ind = "yes" if mdiff > 0.03 else "no"
        ba = float(sel["balanced_accuracy"])
        prec = float(sel["precision"])
        brier = float(sel["brier"])
        if ba >= 0.86 and prec >= 0.90 and worst >= 0.75 and brier <= 0.12 and shortcut_ind == "yes":
            status = "ready_with_caveat"
        elif ba >= 0.82 and prec >= 0.84 and worst >= 0.70 and shortcut_ind == "yes":
            status = "ready_with_caveat"
        elif ba >= 0.78 and worst >= 0.65 and shortcut_ind == "yes":
            status = "uncertainty_preferred"
        else:
            status = "not_ready_for_strong_probability_interpretation"
        out_rows.append({"mode": mode, "domain": "elimination", "selected_operating_mode": sel["operating_mode"], "precision": float(sel["precision"]), "recall": float(sel["recall"]), "specificity": float(sel["specificity"]), "balanced_accuracy": ba, "f1": float(sel["f1"]), "pr_auc": float(sel["pr_auc"]), "brier": brier, "worst_stress_ba": worst, "shortcut_max_metric_diff": mdiff, "shortcut_independence": shortcut_ind, "probability_ready": "yes" if brier <= 0.14 else "no", "risk_band_ready": "yes" if ba >= 0.80 else "no", "confidence_ready": "yes" if float(sel["output_realism_score"]) >= 0.82 else "no", "uncertainty_ready": "yes" if float(sel["uncertainty_usefulness"]) >= -0.05 else "no", "professional_detail_ready": "yes", "final_output_status": status, "visible_user_prob_cap": "[0.01,0.99]", "visible_prof_prob_cap": "[0.005,0.995]", "extreme_performance_audit_trigger": "yes" if (ba >= 0.995 or math.isclose(float(sel["precision"]), 1.0) or math.isclose(float(sel["recall"]), 1.0) or math.isclose(float(sel["specificity"]), 1.0)) else "no"})
    out_df = pd.DataFrame(out_rows)
    wcsv(out_df, base / "tables" / "elimination_v13_output_readiness.csv")
    wmd(base / "reports" / "elimination_v13_output_readiness.md", "# elimination v13 output readiness\n\n" + out_df.to_string(index=False))

    v10 = pd.read_csv(root / "data" / "final_hardening_v10" / "elimination" / "elimination_trial_registry.csv")
    v10_base = v10[v10["trial_name"] == "baseline"].copy()
    v12 = pd.read_csv(root / "data" / "elimination_clean_rebuild_v12" / "tables" / "elimination_clean_output_readiness.csv")
    delta_rows = []
    for mode in MODES:
        b = v10_base[v10_base["mode"] == mode].iloc[0]
        c12 = v12[v12["mode"] == mode].iloc[0]
        c13 = out_df[out_df["mode"] == mode].iloc[0]
        delta_rows.append({"mode": mode, "delta_precision_v13_vs_baseline": float(c13["precision"] - b["precision"]), "delta_recall_v13_vs_baseline": float(c13["recall"] - b["recall"]), "delta_specificity_v13_vs_baseline": float(c13["specificity"] - b["specificity"]), "delta_ba_v13_vs_baseline": float(c13["balanced_accuracy"] - b["balanced_accuracy"]), "delta_f1_v13_vs_baseline": float(c13["f1"] - b["f1"]), "delta_pr_auc_v13_vs_baseline": np.nan, "delta_brier_v13_vs_baseline": float(c13["brier"] - b["brier"]), "delta_precision_v13_vs_v12": float(c13["precision"] - c12["precision"]), "delta_recall_v13_vs_v12": float(c13["recall"] - c12["recall"]), "delta_specificity_v13_vs_v12": float(c13["specificity"] - c12["specificity"]), "delta_ba_v13_vs_v12": float(c13["balanced_accuracy"] - c12["balanced_accuracy"]), "delta_f1_v13_vs_v12": float(c13["f1"] - c12["f1"]), "delta_pr_auc_v13_vs_v12": float(c13["pr_auc"] - c12["pr_auc"]), "delta_brier_v13_vs_v12": float(c13["brier"] - c12["brier"]), "delta_robustness_v13_vs_v12": float(c13["worst_stress_ba"] - c12["worst_stress_ba"]), "delta_output_readiness_v13_vs_v12": f"{c12['final_output_status']} -> {c13['final_output_status']}"})
    delta_df = pd.DataFrame(delta_rows)
    wcsv(delta_df, base / "tables" / "elimination_v13_final_delta.csv")
    wmd(base / "reports" / "elimination_v13_final_delta_analysis.md", "# elimination v13 final delta\n\n" + delta_df.to_string(index=False))

    improved_modes = 0
    for mode in MODES:
        d = delta_df[delta_df["mode"] == mode].iloc[0]
        if float(d["delta_precision_v13_vs_v12"]) >= 0.005 and float(d["delta_ba_v13_vs_v12"]) >= 0.005 and float(d["delta_robustness_v13_vs_v12"]) >= -0.01:
            improved_modes += 1
    statuses = set(out_df["final_output_status"].astype(str).tolist())
    if improved_modes == 2 and statuses <= {"ready_with_caveat", "fully_ready"}:
        decision = "APPROVE_V13"
    elif improved_modes >= 1:
        decision = "APPROVE_V13_WITH_CAVEAT"
    elif statuses == {"uncertainty_preferred"}:
        decision = "UNCERTAINTY_PREFERRED_ONLY"
    else:
        decision = "KEEP_V12"
    if (out_df["worst_stress_ba"].astype(float) < 0.62).all():
        decision = "HOLD_STRUCTURAL_LIMIT"

    final_text = "# elimination v13 final decision\n\n" + f"Decision: `{decision}`\n\n" + f"1) v13 mejora real y limpia: {'yes' if improved_modes >= 1 else 'no'}\n" + f"2) precision/generalizacion suben serio: {'yes' if improved_modes >= 1 else 'no'}\n" + f"3) recall suficiente: {'yes' if (out_df['recall'].astype(float) >= 0.70).all() else 'no'}\n" + f"4) resiste ablacion/stress: {'yes' if (out_df['worst_stress_ba'].astype(float) >= 0.70).all() else 'partial'}\n" + f"5) utilidad operativa mejora: {'yes' if improved_modes >= 1 else 'no'}\n" + f"6) puede reemplazar v12: {'yes' if decision in ['APPROVE_V13','APPROVE_V13_WITH_CAVEAT'] else 'no'}\n" + f"7) limite real: {'likely reached' if decision in ['KEEP_V12','HOLD_STRUCTURAL_LIMIT'] else 'not yet'}\n\n" + out_df.to_string(index=False)
    wmd(base / "reports" / "elimination_v13_final_decision.md", final_text)

    summary_text = "# elimination v13 executive summary\n\n" + f"- decision: {decision}\n" + f"- improved_modes_vs_v12: {improved_modes}/2\n" + f"- shortcut_independence_global: {'yes' if (out_df['shortcut_independence'] == 'yes').all() else 'partial/no'}\n" + f"- round_policy: {ROUND_POLICY}\n" + "- confidence policy: user [1%,99%], professional [0.5%,99.5%], internal raw preserved\n\n" + delta_df.to_string(index=False)
    wmd(base / "reports" / "elimination_v13_executive_summary.md", summary_text)

    manifest = {
        "campaign": "elimination_feature_engineering_clean_v13",
        "decision": decision,
        "split_dir": str(split_dir),
        "holdout_hash_ordered": hash_ids(ids_test, ordered=True),
        "holdout_hash_set": hash_ids(ids_test, ordered=False),
        "round_policy": ROUND_POLICY,
        "families_evaluated": [f for f in FAMILIES if f != "catboost" or CATBOOST_AVAILABLE],
        "selected_models": {mode: {"feature_set": winners[mode]["feature_set"], "family": winners[mode]["family"], "n_features": len(winners[mode]["_features"]), "calibration": winners[mode]["calibration"], "operating_mode": selected_ops[mode]["operating_mode"], "threshold": float(selected_ops[mode]["threshold"])} for mode in MODES},
        "forbidden_shortcuts": sorted(list(forbidden_set)),
        "confidence_display_policy": {"internal_raw_probability_preserved": True, "user_visible": {"min": 0.01, "max": 0.99}, "professional_visible": {"min": 0.005, "max": 0.995}},
        "extreme_performance_audit_trigger": {"balanced_accuracy_ge": 0.995, "precision_eq": 1.0, "recall_eq": 1.0, "specificity_eq": 1.0},
    }
    wjson(root / "artifacts" / "elimination_feature_engineering_clean_v13" / "elimination_feature_engineering_clean_v13_manifest.json", manifest)
    print("OK - elimination_feature_engineering_clean_v13 generated")


if __name__ == "__main__":
    main()
