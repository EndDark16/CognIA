#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None

try:
    from catboost import CatBoostClassifier
except Exception:
    CatBoostClassifier = None

LINE = "hybrid_final_aggressive_rescue_v6"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE

ACTIVE_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v5" / "tables" / "hybrid_active_models_30_modes.csv"
OP_SRC = ROOT / "data" / "hybrid_operational_freeze_v5" / "tables" / "hybrid_operational_final_champions.csv"
INPUTS_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v5" / "tables" / "hybrid_questionnaire_inputs_master.csv"
DATASET = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
FE_REG = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "feature_engineering" / "hybrid_no_external_scores_feature_engineering_registry.csv"
CONDUCT_SELECTED = ROOT / "data" / "hybrid_conduct_honest_retrain_v1" / "tables" / "conduct_honest_retrain_selected_models.csv"

ACTIVE_V5_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v6"
OP_V5_BASE = ROOT / "data" / "hybrid_operational_freeze_v6"
NORM_V2_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"

NORMALIZED_V5 = NORM_V2_BASE / "tables" / "hybrid_operational_classification_normalized_v6.csv"
VIOLATIONS_V5 = NORM_V2_BASE / "validation" / "hybrid_classification_policy_violations_v6.csv"
SHORTCUT_PRE_V4 = BASE / "tables" / "shortcut_inventory_v5_precheck.csv"
SHORTCUT_V5 = BASE / "tables" / "shortcut_inventory_v6.csv"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20261101
MARGIN_SEED = 20270421
SEARCH_SEEDS = [20270421]
STABILITY_SEEDS = [20270421, 20270439, 20270501]
BOOTSTRAP_ROUNDS = 80
MIN_FEATURES = 5

EXPLICIT_PRIORITY = {
    ("depression", "caregiver_1_3"),
    ("depression", "caregiver_2_3"),
    ("depression", "caregiver_full"),
    ("depression", "psychologist_1_3"),
    ("depression", "psychologist_full"),
    ("anxiety", "caregiver_2_3"),
    ("anxiety", "caregiver_full"),
    ("anxiety", "psychologist_2_3"),
    ("anxiety", "psychologist_full"),
    ("elimination", "caregiver_1_3"),
    ("elimination", "caregiver_2_3"),
    ("elimination", "caregiver_full"),
    ("elimination", "psychologist_1_3"),
    ("elimination", "psychologist_2_3"),
    ("elimination", "psychologist_full"),
    ("adhd", "psychologist_full"),
    ("conduct", "caregiver_full"),
    ("conduct", "psychologist_full"),
}

OLD_HINTS = {
    "boosted_eng_full": "full_eligible",
    "boosted_eng_compact": "compact_subset",
    "boosted_eng_pruned": "stability_pruned_subset",
}

RF_CFG = {
    "rf_regularized_v4": dict(n_estimators=160, max_depth=14, min_samples_split=8, min_samples_leaf=3, max_features=0.50, class_weight="balanced_subsample", bootstrap=True, max_samples=0.90),
    "rf_precision_guard_v4": dict(n_estimators=180, max_depth=12, min_samples_split=10, min_samples_leaf=4, max_features=0.45, class_weight={0: 1.0, 1: 1.20}, bootstrap=True, max_samples=0.90),
    "rf_recall_guard_v4": dict(n_estimators=180, max_depth=16, min_samples_split=6, min_samples_leaf=2, max_features="sqrt", class_weight={0: 1.0, 1: 1.60}, bootstrap=True, max_samples=0.95),
}
EXTRA_CFG = {
    "extra_regularized_v3": dict(n_estimators=200, max_depth=16, min_samples_split=4, min_samples_leaf=2, max_features=0.55, class_weight="balanced_subsample"),
    "extra_precision_guard_v3": dict(n_estimators=220, max_depth=14, min_samples_split=6, min_samples_leaf=3, max_features=0.45, class_weight={0: 1.0, 1: 1.20}),
}
HGB_CFG = {
    "hgb_regularized_v3": dict(max_depth=4, learning_rate=0.04, max_iter=220, l2_regularization=0.30, min_samples_leaf=20),
    "hgb_conservative_v3": dict(max_depth=3, learning_rate=0.03, max_iter=260, l2_regularization=0.45, min_samples_leaf=28),
}
LOGREG_CFG = {
    "logreg_regularized_v3": dict(max_iter=3200, C=0.40, solver="liblinear", class_weight="balanced"),
    "logreg_balanced_v3": dict(max_iter=3200, C=0.75, solver="liblinear", class_weight="balanced"),
}
XGB_CFG = {"xgb_regularized_v2": dict(n_estimators=180, max_depth=4, learning_rate=0.035, subsample=0.9, colsample_bytree=0.7, reg_lambda=1.7, min_child_weight=2)}
LGBM_CFG = {"lightgbm_regularized_v2": dict(n_estimators=180, num_leaves=31, learning_rate=0.035, subsample=0.9, colsample_bytree=0.7, reg_lambda=1.3)}
CAT_CFG = {"catboost_regularized_v2": dict(iterations=220, depth=5, learning_rate=0.03, l2_leaf_reg=4.0, subsample=0.9)}

DSM5_CORE_PREFIXES = {
    "adhd": ("adhd_",),
    "conduct": ("conduct_",),
    "anxiety": ("agor_", "gad_", "sep_anx_", "social_anxiety_"),
    "depression": ("mdd_", "pdd_", "dmdd_"),
    "elimination": ("enuresis_", "encopresis_"),
}
DOMAIN_ENG_FEATURE = {
    "adhd": "eng_adhd_core_mean",
    "conduct": "eng_conduct_core_mean",
    "anxiety": "eng_anxiety_core_mean",
    "depression": "eng_depression_core_mean",
    "elimination": "eng_elimination_intensity",
}
GLOBAL_CONTEXT_FEATURES = ("age_years", "sex_assigned_at_birth")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [
        BASE / "tables",
        BASE / "reports",
        BASE / "inventory",
        BASE / "validation",
        BASE / "trials",
        BASE / "bootstrap",
        BASE / "stability",
        BASE / "ablation",
        BASE / "stress",
        ART,
        ACTIVE_V5_BASE / "tables",
        ACTIVE_V5_BASE / "reports",
        ACTIVE_V5_BASE / "validation",
        ACTIVE_V5_BASE / "bootstrap",
        ACTIVE_V5_BASE / "stability",
        ACTIVE_V5_BASE / "ablation",
        ACTIVE_V5_BASE / "stress",
        OP_V5_BASE / "tables",
        OP_V5_BASE / "reports",
        OP_V5_BASE / "validation",
        OP_V5_BASE / "inventory",
        OP_V5_BASE / "bootstrap",
        OP_V5_BASE / "ablation",
        OP_V5_BASE / "stress",
        NORM_V2_BASE / "tables",
        NORM_V2_BASE / "reports",
        NORM_V2_BASE / "inventory",
        NORM_V2_BASE / "validation",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def md_table(df: pd.DataFrame, max_rows: int = 60) -> str:
    if df.empty:
        return "(sin filas)"
    x = df.head(max_rows).copy()
    cols = list(x.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in x.iterrows():
        vals = [f"{r[c]:.6f}" if isinstance(r[c], float) else str(r[c]) for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def safe_roc_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, probs))


def safe_pr_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float(np.mean(y_true))
    return float(average_precision_score(y_true, probs))


def compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (probs >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": safe_roc_auc(y_true, probs),
        "pr_auc": safe_pr_auc(y_true, probs),
        "brier": float(brier_score_loss(y_true, np.clip(probs, 1e-6, 1 - 1e-6))),
        "accuracy": float(accuracy_score(y_true, pred)),
    }


def sec_peak(m: dict[str, float]) -> float:
    return float(max(m["specificity"], m["roc_auc"], m["pr_auc"]))


def sec_anomaly(m: dict[str, float]) -> str:
    return "yes" if sec_peak(m) > 0.98 or (sec_peak(m) > 0.985 and m["brier"] <= 0.03) else "no"


def choose_threshold(policy: str, y_true: np.ndarray, probs: np.ndarray) -> tuple[float, float]:
    if policy == "default_0_5":
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, 0.46 * m["balanced_accuracy"] + 0.2 * m["f1"] + 0.14 * m["precision"] + 0.12 * m["recall"] + 0.08 * m["pr_auc"] - 0.12 * m["brier"]
    best_thr, best_score = 0.5, -1e9
    for thr in np.linspace(0.08, 0.92, 85):
        m = compute_metrics(y_true, probs, float(thr))
        if policy == "precision_min_recall":
            score = -1e9 if m["recall"] < 0.70 or m["balanced_accuracy"] < 0.82 else 0.64 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.10 * m["pr_auc"] + 0.06 * m["recall"]
        elif policy == "recall_constrained":
            score = -1e9 if m["precision"] < 0.76 else 0.52 * m["recall"] + 0.20 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["precision"]
        else:
            score = 0.50 * m["balanced_accuracy"] + 0.20 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
        if score > best_score:
            best_score, best_thr = float(score), float(thr)
    return best_thr, best_score


def build_model(family: str, config_id: str, seed: int):
    if family == "rf":
        cfg = RF_CFG.get(config_id, RF_CFG["rf_regularized_v4"])
        return RandomForestClassifier(random_state=seed, n_jobs=-1, **cfg)
    if family == "extra_trees":
        cfg = EXTRA_CFG.get(config_id, EXTRA_CFG["extra_regularized_v3"])
        return ExtraTreesClassifier(random_state=seed, n_jobs=-1, **cfg)
    if family == "hgb":
        cfg = HGB_CFG.get(config_id, HGB_CFG["hgb_regularized_v3"])
        return HistGradientBoostingClassifier(random_state=seed, **cfg)
    if family == "logreg":
        cfg = LOGREG_CFG.get(config_id, LOGREG_CFG["logreg_regularized_v3"])
        return LogisticRegression(**cfg)
    if family == "xgb" and XGBClassifier is not None:
        cfg = XGB_CFG.get(config_id, XGB_CFG["xgb_regularized_v2"])
        return XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist", random_state=seed, n_jobs=-1, **cfg)
    if family == "lightgbm" and LGBMClassifier is not None:
        cfg = LGBM_CFG.get(config_id, LGBM_CFG["lightgbm_regularized_v2"])
        return LGBMClassifier(objective="binary", random_state=seed, n_jobs=-1, verbosity=-1, **cfg)
    if family == "catboost" and CatBoostClassifier is not None:
        cfg = CAT_CFG.get(config_id, CAT_CFG["catboost_regularized_v2"])
        return CatBoostClassifier(loss_function="Logloss", random_seed=seed, verbose=False, allow_writing_files=False, **cfg)
    raise ValueError(f"unsupported family {family}")


def fit_matrix(tr_df: pd.DataFrame, va_df: pd.DataFrame, ho_df: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    x_tr = tr_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_va = va_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = ho_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_tr = x_tr.dropna(axis=1, how="all")
    cols = list(x_tr.columns)
    imp = SimpleImputer(strategy="median")
    return imp.fit_transform(x_tr), imp.transform(x_va[cols]), imp.transform(x_ho[cols]), cols


def calibrate(y_val: np.ndarray, p_tr_raw: np.ndarray, p_va_raw: np.ndarray, p_ho_raw: np.ndarray, method: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if method == "none" or len(np.unique(y_val)) < 2:
        return p_tr_raw, p_va_raw, p_ho_raw
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p_va_raw, y_val)
        return np.clip(iso.predict(p_tr_raw), 1e-6, 1 - 1e-6), np.clip(iso.predict(p_va_raw), 1e-6, 1 - 1e-6), np.clip(iso.predict(p_ho_raw), 1e-6, 1 - 1e-6)
    lr = LogisticRegression(max_iter=500, solver="lbfgs")
    lr.fit(p_va_raw.reshape(-1, 1), y_val)
    return (
        np.clip(lr.predict_proba(p_tr_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
        np.clip(lr.predict_proba(p_va_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
        np.clip(lr.predict_proba(p_ho_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
    )


def build_splits(df: pd.DataFrame) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    out, rows = {}, []
    for d in DOMAINS:
        t = f"target_domain_{d}_final"
        sub = df[["participant_id", t]].dropna().copy()
        ids = sub["participant_id"].astype(str).to_numpy()
        y = sub[t].astype(int).to_numpy()
        seed = BASE_SEED + DOMAINS.index(d)
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=strat)
        strat2 = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids, va_y, ho_y = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=strat2)
        out[d] = {"train": list(tr_ids), "val": list(va_ids), "holdout": list(ho_ids)}
        rows.append({"domain": d, "train_n": len(tr_ids), "val_n": len(va_ids), "holdout_n": len(ho_ids), "train_pos_rate": float(np.mean(tr_y)), "val_pos_rate": float(np.mean(va_y)), "holdout_pos_rate": float(np.mean(ho_y))})
    return out, pd.DataFrame(rows)


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def load_feature_maps() -> tuple[dict[tuple[str, str, str], list[str]], dict[tuple[str, str], list[str]]]:
    reg = pd.read_csv(FE_REG)
    reg["feature_list"] = reg["feature_list_pipe"].fillna("").apply(lambda s: [f for f in str(s).split("|") if f])
    reg_map = {(str(r.domain), str(r.mode), str(r.feature_set_id)): list(r.feature_list) for r in reg.itertuples(index=False)}
    conduct_map: dict[tuple[str, str], list[str]] = {}
    if CONDUCT_SELECTED.exists():
        cdf = pd.read_csv(CONDUCT_SELECTED)
        for r in cdf.to_dict(orient="records"):
            m, fs = str(r.get("mode", "")), str(r.get("feature_set_id", ""))
            feats = [f for f in str(r.get("feature_list_pipe", "")).split("|") if f]
            if m and fs and feats:
                conduct_map[(m, fs)] = feats
    return reg_map, conduct_map


def feature_list(row: pd.Series, reg_map: dict[tuple[str, str, str], list[str]], conduct_map: dict[tuple[str, str], list[str]]) -> tuple[list[str], str]:
    d, m, fs, src = str(row["domain"]), str(row["mode"]), str(row["feature_set_id"]), str(row["source_campaign"])
    if src == "conduct_honest_retrain_v1":
        if (m, fs) in conduct_map:
            return conduct_map[(m, fs)], "exact_conduct_honest_retrain_v1"
        if (m, "engineered_compact_no_shortcuts_v1") in conduct_map:
            return conduct_map[(m, "engineered_compact_no_shortcuts_v1")], "fallback_conduct_honest_retrain_v1"
        return [], "por_confirmar_missing_conduct_feature_set"
    key = (d, m, fs)
    if src == "boosted_v3":
        hint = OLD_HINTS.get(fs, fs)
        if (d, m, hint) in reg_map:
            return reg_map[(d, m, hint)], "base_only_por_confirmar_engv3"
    if key in reg_map:
        return reg_map[key], "mapped_from_registry"
    return [], "por_confirmar_missing_feature_set"


def single_feature_rule(ho_df: pd.DataFrame, target_col: str, feats: list[str]) -> dict[str, Any]:
    y = ho_df[target_col].astype(int).to_numpy()
    best = {"best_single_feature": "", "best_single_rule": "", "best_single_feature_ba": np.nan}
    top = -1.0
    for f in feats:
        if f not in ho_df.columns:
            continue
        x = pd.to_numeric(ho_df[f], errors="coerce")
        if x.isna().all():
            continue
        x = x.fillna(float(x.median())).to_numpy()
        if len(np.unique(x)) < 2:
            continue
        for thr in np.unique(np.quantile(x, np.linspace(0.05, 0.95, 19))):
            for ge in (True, False):
                pred = (x >= thr).astype(int) if ge else (x <= thr).astype(int)
                ba = float(balanced_accuracy_score(y, pred))
                if ba > top:
                    top = ba
                    best = {"best_single_feature": f, "best_single_rule": f"{f} {'>=' if ge else '<='} {thr:.6g}", "best_single_feature_ba": ba}
    return best


def _uniq(feats: list[str]) -> list[str]:
    return [f for f in dict.fromkeys(feats) if f]


def _domain_core_features(domain: str, feats: list[str]) -> list[str]:
    prefixes = DSM5_CORE_PREFIXES.get(domain, ())
    return [f for f in feats if str(f).startswith(prefixes)]


def _dsm5_feature_sets(domain: str, base_feats: list[str], dominant: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    core = _uniq(_domain_core_features(domain, base_feats))
    ctx = [f for f in GLOBAL_CONTEXT_FEATURES if f in base_feats]
    eng = [f for f in [DOMAIN_ENG_FEATURE.get(domain), "eng_internalizing_index", "eng_externalizing_index", "eng_mood_discrepancy"] if f and f in base_feats]
    if len(core) >= MIN_FEATURES:
        out["dsm5_core_only"] = core
        out["dsm5_core_plus_context"] = _uniq(core + ctx)
        out["dsm5_core_plus_engineered"] = _uniq(core + ctx + eng)
        out["dsm5_pruned"] = [f for f in _uniq(core + ctx + eng) if "_threshold_" not in str(f)]
        weighted = [f for f in _uniq(core + ctx + eng) if any(k in str(f) for k in ["_impairment", "_duration", "_count", "_event_frequency", "_symptom", "_worry", "_depressed", "_irritable"])]
        if len(weighted) >= MIN_FEATURES:
            out["dsm5_weighted_compact"] = weighted
    if dominant:
        out["anti_shortcut_subset_v1"] = [f for f in base_feats if f != dominant and "_threshold_" not in str(f)]
    out["anti_anomaly_subset_v1"] = [f for f in base_feats if "_threshold_" not in str(f) and not str(f).startswith("eng_")]
    if len(out["anti_anomaly_subset_v1"]) < MIN_FEATURES:
        out.pop("anti_anomaly_subset_v1", None)
    return {k: _uniq(v) for k, v in out.items() if len(_uniq(v)) >= MIN_FEATURES}


def candidate_sets(domain: str, mode: str, old_fs: str, old_feats: list[str], dominant: str, reg_map: dict[tuple[str, str, str], list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if old_feats:
        out[old_fs] = _uniq(old_feats)
    if old_feats and dominant and dominant in old_feats:
        out[f"{old_fs}_no_shortcut_v1"] = [f for f in old_feats if f != dominant]
    no_eng = [f for f in old_feats if not str(f).startswith("eng_")]
    if len(no_eng) >= MIN_FEATURES:
        out[f"{old_fs}_no_eng_v1"] = _uniq(no_eng)
    for fs in [
        "full_eligible",
        "precision_oriented_subset",
        "compact_subset",
        "stability_pruned_subset",
        "balanced_subset",
        "engineered_compact",
        "engineered_pruned",
        "engineered_full",
    ]:
        k = (domain, mode, fs)
        if k in reg_map and len(reg_map[k]) >= MIN_FEATURES:
            out[fs] = _uniq(reg_map[k])
    base_pool = out.get("full_eligible", out.get(old_fs, old_feats))
    for fs, feats in _dsm5_feature_sets(domain, base_pool, dominant).items():
        out[fs] = feats
    if "stability_pruned_subset" in out:
        robust = [f for f in out["stability_pruned_subset"] if not str(f).startswith("eng_")]
        if len(robust) >= MIN_FEATURES:
            out["stress_robust_subset_v1"] = _uniq(robust)
    clean: dict[str, list[str]] = {}
    for fs, feats in out.items():
        uniq = _uniq(feats)
        if len(uniq) >= MIN_FEATURES:
            clean[fs] = uniq
    return clean


def _predict_prob_like(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(x)[:, 1]
    elif hasattr(model, "decision_function"):
        z = model.decision_function(x)
        p = 1.0 / (1.0 + np.exp(-z))
    else:
        p = model.predict(x)
    return np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)


def _fit_with_weights(model, family: str, x: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None):
    if sample_weight is None:
        model.fit(x, y)
        return
    try:
        if family == "catboost":
            model.fit(x, y, sample_weight=sample_weight)
        else:
            model.fit(x, y, sample_weight=sample_weight)
    except TypeError:
        model.fit(x, y)


def _frontier_hint(x_tr: np.ndarray, y_tr: np.ndarray) -> np.ndarray:
    try:
        lr = LogisticRegression(max_iter=400, solver="lbfgs")
        lr.fit(x_tr, y_tr)
        return _predict_prob_like(lr, x_tr)
    except Exception:
        return np.repeat(float(np.mean(y_tr)), len(y_tr))


def _build_sample_weights(strategy: str, y_tr: np.ndarray, mode: str, domain: str, probs_hint: np.ndarray | None = None) -> np.ndarray | None:
    if strategy == "none":
        return None
    w = np.ones(len(y_tr), dtype=float)
    pos_rate = float(np.mean(y_tr))
    pos_mask = y_tr == 1
    if strategy in {"class_minor_boost", "combined_aggressive"}:
        ratio = min(3.0, max(1.25, (1.0 - pos_rate) / max(pos_rate, 1e-6)))
        w[pos_mask] *= ratio
    if strategy in {"mode_fragile", "combined_aggressive"} and (mode.endswith("_1_3") or mode.endswith("_2_3")):
        w[pos_mask] *= 1.30
    if strategy in {"cost_asym", "combined_aggressive"}:
        cost = 1.80 if domain in {"depression", "anxiety", "elimination"} else 1.40
        w[pos_mask] *= cost
    if strategy in {"frontier_hard", "combined_aggressive"} and probs_hint is not None:
        uncertainty = np.abs(probs_hint - 0.5) <= 0.14
        w[uncertainty] *= 1.35
    return np.clip(w, 0.5, 8.0)


def _family_plan(pass_name: str) -> list[tuple[str, list[str]]]:
    if pass_name == "pass_a":
        return [
            ("rf", ["rf_regularized_v4"]),
            ("extra_trees", ["extra_regularized_v3"]),
            ("hgb", ["hgb_regularized_v3"]),
            ("logreg", ["logreg_regularized_v3"]),
        ]
    if pass_name == "pass_b":
        return [
            ("rf", ["rf_recall_guard_v4"]),
            ("extra_trees", ["extra_precision_guard_v3"]),
            ("hgb", ["hgb_conservative_v3"]),
            ("logreg", ["logreg_balanced_v3"]),
        ]
    return [
        ("rf", ["rf_precision_guard_v4"]),
        ("hgb", ["hgb_regularized_v3"]),
    ]


def _weight_plan(pass_name: str) -> list[str]:
    if pass_name == "pass_a":
        return ["none", "class_minor_boost"]
    if pass_name == "pass_b":
        return ["none", "cost_asym", "mode_fragile"]
    return ["none", "combined_aggressive"]


def search_slot(
    domain: str,
    mode: str,
    role: str,
    tr_df: pd.DataFrame,
    va_df: pd.DataFrame,
    ho_df: pd.DataFrame,
    target_col: str,
    cand_fs: dict[str, list[str]],
    seeds: list[int],
    pass_name: str,
) -> tuple[pd.DataFrame, pd.Series | None]:
    rows = []
    y_tr = tr_df[target_col].astype(int).to_numpy()
    y_va = va_df[target_col].astype(int).to_numpy()
    y_ho = ho_df[target_col].astype(int).to_numpy()
    if pass_name == "pass_a":
        cal_methods = ["none"]
        threshold_policies = ["balanced"]
    elif pass_name == "pass_b":
        cal_methods = ["none"]
        threshold_policies = ["balanced", "precision_min_recall"]
    else:
        cal_methods = ["none"]
        threshold_policies = ["balanced", "recall_constrained"]
    weight_policies = _weight_plan(pass_name)
    family_plan = _family_plan(pass_name)

    for fs_id, feats in cand_fs.items():
        try:
            x_tr, x_va, x_ho, eff_cols = fit_matrix(tr_df, va_df, ho_df, feats)
        except Exception:
            continue
        if len(eff_cols) < MIN_FEATURES:
            continue
        probs_hint = _frontier_hint(x_tr, y_tr)
        for fam, cfgs in family_plan:
            for cfg in cfgs:
                for seed in seeds:
                    for w_policy in weight_policies:
                        sw = _build_sample_weights(w_policy, y_tr, mode, domain, probs_hint)
                        try:
                            m = build_model(fam, cfg, int(seed))
                            _fit_with_weights(m, fam, x_tr, y_tr, sw)
                        except Exception:
                            continue
                        p_tr_raw = _predict_prob_like(m, x_tr)
                        p_va_raw = _predict_prob_like(m, x_va)
                        p_ho_raw = _predict_prob_like(m, x_ho)
                        for cal in cal_methods:
                            p_tr, p_va, p_ho = calibrate(y_va, p_tr_raw, p_va_raw, p_ho_raw, cal)
                            for pol in threshold_policies:
                                thr, _ = choose_threshold(pol, y_va, p_va)
                                mt = compute_metrics(y_tr, p_tr, thr)
                                mv = compute_metrics(y_va, p_va, thr)
                                mh = compute_metrics(y_ho, p_ho, thr)
                                overfit = float(mt["balanced_accuracy"] - mv["balanced_accuracy"])
                                gen_gap = float(abs(mv["balanced_accuracy"] - mh["balanced_accuracy"]))
                                sel = (
                                    0.36 * mv["balanced_accuracy"]
                                    + 0.18 * mv["f1"]
                                    + 0.16 * mv["pr_auc"]
                                    + 0.14 * mv["precision"]
                                    + 0.12 * mv["recall"]
                                    - 0.12 * max(0.0, overfit)
                                    - 0.10 * max(0.0, gen_gap)
                                    - (0.012 if sec_anomaly(mh) == "yes" else 0.0)
                                    + (0.006 if fs_id.startswith("dsm5_") else 0.0)
                                )
                                rows.append(
                                    {
                                        "domain": domain,
                                        "mode": mode,
                                        "role": role,
                                        "pass_name": pass_name,
                                        "weight_policy": w_policy,
                                        "feature_set_id": fs_id,
                                        "feature_list_pipe": "|".join(eff_cols),
                                        "model_family": fam,
                                        "config_id": cfg,
                                        "calibration": cal,
                                        "threshold_policy": pol,
                                        "threshold": float(thr),
                                        "seed": int(seed),
                                        "n_features": int(len(eff_cols)),
                                        "train_balanced_accuracy": mt["balanced_accuracy"],
                                        "val_balanced_accuracy": mv["balanced_accuracy"],
                                        "val_precision": mv["precision"],
                                        "precision": mh["precision"],
                                        "recall": mh["recall"],
                                        "specificity": mh["specificity"],
                                        "balanced_accuracy": mh["balanced_accuracy"],
                                        "f1": mh["f1"],
                                        "roc_auc": mh["roc_auc"],
                                        "pr_auc": mh["pr_auc"],
                                        "brier": mh["brier"],
                                        "overfit_gap_train_val_ba": overfit,
                                        "generalization_gap_val_holdout_ba": gen_gap,
                                        "secondary_max_metric": sec_peak(mh),
                                        "secondary_metric_anomaly_flag": sec_anomaly(mh),
                                        "quality_label": "bueno"
                                        if (mh["balanced_accuracy"] >= 0.90 and mh["f1"] >= 0.85 and mh["precision"] >= 0.82 and mh["recall"] >= 0.78 and mh["brier"] <= 0.06)
                                        else ("aceptable" if mh["balanced_accuracy"] >= 0.84 and mh["f1"] >= 0.78 else "malo"),
                                        "val_selection_score": float(sel),
                                    }
                                )
    if not rows:
        return pd.DataFrame(), None
    trials = pd.DataFrame(rows)
    winner = (
        trials.sort_values(
            [
                "val_selection_score",
                "val_balanced_accuracy",
                "val_precision",
                "secondary_max_metric",
                "n_features",
            ],
            ascending=[False, False, False, True, True],
        )
        .iloc[0]
        .copy()
    )
    return trials, winner


def nrm(x: float, lo: float, hi: float) -> float:
    x = float(x)
    if x <= lo:
        return 0.0
    if x >= hi:
        return 1.0
    return (x - lo) / (hi - lo)


def conf_band(v: float) -> str:
    if v >= 86:
        return "high"
    if v >= 72:
        return "moderate"
    if v >= 60:
        return "low"
    return "limited"


def main() -> None:
    ensure_dirs()
    active = pd.read_csv(ACTIVE_SRC)
    op = pd.read_csv(OP_SRC)
    data = pd.read_csv(DATASET)
    reg_map, conduct_map = load_feature_maps()
    splits, split_df = build_splits(data)
    save_csv(split_df, BASE / "validation/split_registry.csv")

    dup = pd.DataFrame([{"dataset_rows": int(len(data)), "full_vector_duplicates_anywhere": int(data.drop(columns=["participant_id"], errors="ignore").astype(str).agg("|".join, axis=1).duplicated(keep=False).sum())}])
    save_csv(dup, BASE / "validation/duplicate_audit_global.csv")

    # Build precheck shortcut inventory and baseline normalization.
    pre_rows = []
    for _, r in active.iterrows():
        d, m = str(r["domain"]), str(r["mode"])
        feats, st = feature_list(r, reg_map, conduct_map)
        ho = subset(data, splits[d]["holdout"])
        t = f"target_domain_{d}_final"
        sc = single_feature_rule(ho, t, feats) if feats else {"best_single_feature": "", "best_single_rule": "", "best_single_feature_ba": np.nan}
        model_ba = float(r["balanced_accuracy"])
        ba = float(sc["best_single_feature_ba"]) if pd.notna(sc["best_single_feature_ba"]) else np.nan
        gap = float(ba - model_ba) if pd.notna(ba) else np.nan
        pre_rows.append({"domain": d, "mode": m, "best_single_feature": sc["best_single_feature"], "best_single_feature_ba": ba, "shortcut_gap_vs_model_ba": gap, "shortcut_dominance_flag": "yes" if pd.notna(gap) and gap >= 0.05 else "no", "feature_audit_status": st})
    pre_short = pd.DataFrame(pre_rows)
    save_csv(pre_short, SHORTCUT_PRE_V4)

    norm_v4 = build_normalized_table(PolicyInputs(operational_csv=OP_SRC, active_csv=ACTIVE_SRC, shortcut_inventory_csv=SHORTCUT_PRE_V4))
    save_csv(norm_v4, BASE / "tables/normalized_v4_snapshot.csv")

    # Focus inventory.
    norm_idx = {(str(r.domain), str(r.mode)): r for r in norm_v4.itertuples(index=False)}
    focus_rows = []
    for _, r in active.iterrows():
        d, m = str(r["domain"]), str(r["mode"])
        sec = max(float(r["specificity"]), float(r["roc_auc"]), float(r["pr_auc"]))
        sec_flag = "yes" if sec > 0.98 else "no"
        explicit = (d, m) in EXPLICIT_PRIORITY
        focus_mode = m.endswith("_2_3") or m.endswith("_full")
        high_conf_anom = str(r["confidence_band"]) == "high" and sec_flag == "yes"
        dep_limited = d == "depression" and str(r["final_operational_class"]) == "ACTIVE_LIMITED_USE"
        if not (explicit or (focus_mode and sec_flag == "yes") or high_conf_anom or dep_limited):
            continue
        feats, st = feature_list(r, reg_map, conduct_map)
        ho = subset(data, splits[d]["holdout"])
        t = f"target_domain_{d}_final"
        sc = single_feature_rule(ho, t, feats) if feats else {"best_single_feature": "", "best_single_rule": "", "best_single_feature_ba": np.nan}
        ba = float(sc["best_single_feature_ba"]) if pd.notna(sc["best_single_feature_ba"]) else np.nan
        gap = float(ba - float(r["balanced_accuracy"])) if pd.notna(ba) else np.nan
        causes = []
        if sec_flag == "yes":
            causes.append("secondary_metric_anomaly")
        if pd.notna(gap) and gap >= 0.05:
            causes.append("single_feature_shortcut_risk")
        if float(r["balanced_accuracy"]) < 0.88:
            causes.append("limited_separability_or_underfit")
        if float(r["precision"]) < 0.80:
            causes.append("precision_tradeoff")
        if float(r["recall"]) < 0.75:
            causes.append("recall_tradeoff")
        if not causes:
            causes.append("confidence_alignment_check")
        nrow = norm_idx.get((d, m))
        focus_rows.append({
            "domain": d, "mode": m, "role": str(r["role"]), "active_model_id": str(r["active_model_id"]), "source_campaign": str(r["source_campaign"]), "feature_set_id": str(r["feature_set_id"]),
            "confidence_pct": float(r["confidence_pct"]), "confidence_band": str(r["confidence_band"]),
            "precision": float(r["precision"]), "recall": float(r["recall"]), "specificity": float(r["specificity"]), "balanced_accuracy": float(r["balanced_accuracy"]), "f1": float(r["f1"]), "roc_auc": float(r["roc_auc"]), "pr_auc": float(r["pr_auc"]), "brier": float(r["brier"]),
            "secondary_metric_peak": sec, "secondary_metric_anomaly_flag": sec_flag, "feature_audit_status": st, "old_feature_list_pipe": "|".join(feats),
            "old_best_single_feature": sc["best_single_feature"], "old_best_single_rule": sc["best_single_rule"], "old_best_single_feature_ba": ba, "old_shortcut_gap_vs_model_ba": gap,
            "root_cause_hypothesis": "|".join(causes), "normalized_final_class": str(getattr(nrow, "normalized_final_class", "por_confirmar")),
        })
    focus = pd.DataFrame(focus_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(focus, BASE / "tables/focus_slots_inventory.csv")

    margin_rows, pass_a_trials, pass_b_trials, pass_c_trials, selected = [], [], [], [], []
    for r in focus.itertuples(index=False):
        d, m, role = str(r.domain), str(r.mode), str(r.role)
        old_row = active[(active["domain"] == d) & (active["mode"] == m)].iloc[0]
        tr, va, ho = subset(data, splits[d]["train"]), subset(data, splits[d]["val"]), subset(data, splits[d]["holdout"])
        t = f"target_domain_{d}_final"
        old_feats = [f for f in str(r.old_feature_list_pipe).split("|") if f]
        all_cands = candidate_sets(d, m, str(r.feature_set_id), old_feats, str(r.old_best_single_feature), reg_map)
        if not all_cands:
            margin_rows.append({"domain": d, "mode": m, "margin_status": "no_candidate_feature_sets"})
            selected.append({"domain": d, "mode": m, "role": role, "active_model_id": str(old_row["active_model_id"]), "promotion_decision": "HOLD_FOR_LIMITATION", "hold_reason": "no_candidate_feature_sets", "root_cause_hypothesis": str(r.root_cause_hypothesis)})
            continue

        pass_a_keys = [
            str(r.feature_set_id),
            "precision_oriented_subset",
            "compact_subset",
            "engineered_compact",
            "engineered_pruned",
            "full_eligible",
        ]
        pass_a_cands = {k: all_cands[k] for k in pass_a_keys if k in all_cands}
        if not pass_a_cands:
            pass_a_cands = {k: v for k, v in list(all_cands.items())[:4]}
        pass_a_cands = dict(list(pass_a_cands.items())[:5])
        a_trials, a_win = search_slot(d, m, role, tr, va, ho, t, pass_a_cands, [MARGIN_SEED], pass_name="pass_a")
        if not a_trials.empty:
            pass_a_trials.extend(a_trials.to_dict(orient="records"))

        pass_b_cands = {k: v for k, v in all_cands.items() if any(token in k for token in ["dsm5_", "_no_shortcut_", "_no_eng_", "anti_", "stress_robust", "balanced_subset", "stability_pruned_subset"])}
        if not pass_b_cands:
            pass_b_cands = {k: v for k, v in all_cands.items() if k not in pass_a_cands}
        if not pass_b_cands:
            pass_b_cands = pass_a_cands
        pass_b_cands = dict(list(pass_b_cands.items())[:6])
        b_trials, b_win = search_slot(d, m, role, tr, va, ho, t, pass_b_cands, SEARCH_SEEDS, pass_name="pass_b")
        if not b_trials.empty:
            pass_b_trials.extend(b_trials.to_dict(orient="records"))

        old_sec = "yes" if max(float(old_row["specificity"]), float(old_row["roc_auc"]), float(old_row["pr_auc"])) > 0.98 else "no"
        run_pass_c = True
        if b_win is not None:
            b_dba = float(b_win["balanced_accuracy"]) - float(old_row["balanced_accuracy"])
            b_df1 = float(b_win["f1"]) - float(old_row["f1"])
            b_dpr = float(b_win["pr_auc"]) - float(old_row["pr_auc"])
            b_material = b_dba >= 0.010 or b_df1 >= 0.015 or b_dpr >= 0.015
            b_anom_res = old_sec == "yes" and str(b_win["secondary_metric_anomaly_flag"]) == "no"
            if b_material and (old_sec == "no" or b_anom_res):
                run_pass_c = False

        c_trials, c_win = pd.DataFrame(), None
        if run_pass_c:
            pass_c_cands = {k: v for k, v in all_cands.items() if any(token in k for token in ["dsm5_", "anti_", "engineered_", "full_eligible"])}
            if not pass_c_cands:
                pass_c_cands = all_cands
            pass_c_cands = dict(list(pass_c_cands.items())[:4])
            c_trials, c_win = search_slot(d, m, role, tr, va, ho, t, pass_c_cands, SEARCH_SEEDS, pass_name="pass_c")
            if not c_trials.empty:
                pass_c_trials.extend(c_trials.to_dict(orient="records"))

        all_trials = pd.concat([x for x in [a_trials, b_trials, c_trials] if not x.empty], ignore_index=True) if (not a_trials.empty or not b_trials.empty or not c_trials.empty) else pd.DataFrame()
        if all_trials.empty:
            margin_rows.append({"domain": d, "mode": m, "margin_status": "no_candidate_trials"})
            selected.append({"domain": d, "mode": m, "role": role, "active_model_id": str(old_row["active_model_id"]), "promotion_decision": "HOLD_FOR_LIMITATION", "hold_reason": "no_candidate_trials", "root_cause_hypothesis": str(r.root_cause_hypothesis)})
            continue

        win = (
            all_trials.sort_values(
                [
                    "val_selection_score",
                    "val_balanced_accuracy",
                    "val_precision",
                    "secondary_max_metric",
                    "n_features",
                ],
                ascending=[False, False, False, True, True],
            )
            .iloc[0]
            .copy()
        )

        margin_rows.append(
            {
                "domain": d,
                "mode": m,
                "old_balanced_accuracy": float(r.balanced_accuracy),
                "new_balanced_accuracy": float(win["balanced_accuracy"]),
                "old_f1": float(r.f1),
                "new_f1": float(win["f1"]),
                "old_pr_auc": float(r.pr_auc),
                "new_pr_auc": float(win["pr_auc"]),
                "old_secondary_metric_anomaly_flag": str(r.secondary_metric_anomaly_flag),
                "new_secondary_metric_anomaly_flag": str(win["secondary_metric_anomaly_flag"]),
                "winner_pass": str(win.get("pass_name", "por_confirmar")),
                "winner_weight_policy": str(win.get("weight_policy", "none")),
                "winner_feature_set_id": str(win.get("feature_set_id", "por_confirmar")),
                "margin_status": "material_candidate"
                if (
                    float(win["balanced_accuracy"]) - float(r.balanced_accuracy) >= 0.010
                    or float(win["f1"]) - float(r.f1) >= 0.015
                    or float(win["pr_auc"]) - float(r.pr_auc) >= 0.015
                )
                else "near_ceiling_or_minor_gain",
            }
        )

        old_sec_peak = max(float(old_row["specificity"]), float(old_row["roc_auc"]), float(old_row["pr_auc"]))
        dba = float(win["balanced_accuracy"]) - float(old_row["balanced_accuracy"])
        df1 = float(win["f1"]) - float(old_row["f1"])
        dpr = float(win["pr_auc"]) - float(old_row["pr_auc"])
        dprec = float(win["precision"]) - float(old_row["precision"])
        drec = float(win["recall"]) - float(old_row["recall"])
        pass_gen = (
            float(win["overfit_gap_train_val_ba"]) <= 0.10
            and float(win["generalization_gap_val_holdout_ba"]) <= 0.09
            and float(win["precision"]) >= 0.74
            and float(win["recall"]) >= 0.68
            and float(win["balanced_accuracy"]) >= 0.84
            and float(win["brier"]) <= 0.08
        )
        material = dba >= 0.010 or df1 >= 0.015 or dpr >= 0.015 or (drec >= 0.04 and dprec >= -0.015) or (dprec >= 0.04 and drec >= -0.015)
        anomaly_resolution = old_sec == "yes" and str(win["secondary_metric_anomaly_flag"]) == "no" and dba >= -0.005 and df1 >= -0.010
        class_up = (
            str(old_row["final_operational_class"]) == "ACTIVE_LIMITED_USE"
            and float(win["balanced_accuracy"]) >= 0.88
            and float(win["f1"]) >= 0.82
            and float(win["precision"]) >= 0.78
            and float(win["recall"]) >= 0.76
            and float(win["brier"]) <= 0.065
        )
        severe_reg = dba < -0.012 or df1 < -0.015 or dpr < -0.020
        anomaly_guard = (
            True
            if old_sec == "no"
            else (
                str(win["secondary_metric_anomaly_flag"]) == "no"
                or (
                    str(win["secondary_metric_anomaly_flag"]) == "yes"
                    and float(win["secondary_max_metric"]) <= old_sec_peak - 0.003
                    and dba >= 0.0
                    and df1 >= 0.0
                )
            )
        )
        promote = bool(pass_gen and anomaly_guard and not severe_reg and (material or anomaly_resolution or class_up))
        winner_hypothesis = str(r.root_cause_hypothesis)
        if str(win.get("feature_set_id", "")).startswith("dsm5_"):
            winner_hypothesis = f"{winner_hypothesis}|dsm5_core_signal_strengthened"
        if str(win.get("weight_policy", "none")) != "none":
            winner_hypothesis = f"{winner_hypothesis}|weighting_boundary_adjustment"
        selected.append({
            "domain": d, "mode": m, "role": role, "active_model_id": str(old_row["active_model_id"]), "source_campaign_old": str(old_row["source_campaign"]), "feature_set_id_old": str(old_row["feature_set_id"]),
            **win.to_dict(),
            "old_precision": float(old_row["precision"]), "old_recall": float(old_row["recall"]), "old_specificity": float(old_row["specificity"]), "old_balanced_accuracy": float(old_row["balanced_accuracy"]), "old_f1": float(old_row["f1"]), "old_roc_auc": float(old_row["roc_auc"]), "old_pr_auc": float(old_row["pr_auc"]), "old_brier": float(old_row["brier"]), "old_confidence_pct": float(old_row["confidence_pct"]), "old_final_operational_class": str(old_row["final_operational_class"]),
            "delta_precision": dprec, "delta_recall": drec, "delta_balanced_accuracy": dba, "delta_f1": df1, "delta_pr_auc": dpr, "delta_brier": float(win["brier"]) - float(old_row["brier"]),
            "old_secondary_anomaly": old_sec, "new_secondary_anomaly": str(win["secondary_metric_anomaly_flag"]), "promotion_decision": "PROMOTE_NOW" if promote else "HOLD_FOR_LIMITATION",
            "generalization_ok": "yes" if pass_gen else "no",
            "material_gain_ok": "yes" if material else "no",
            "anomaly_resolution_ok": "yes" if anomaly_resolution else "no",
            "class_upgrade_candidate": "yes" if class_up else "no",
            "anomaly_guard_ok": "yes" if anomaly_guard else "no",
            "root_cause_hypothesis": winner_hypothesis,
        })

    margin_df, selected_df = pd.DataFrame(margin_rows), pd.DataFrame(selected)
    save_csv(margin_df, BASE / "tables/focus_margin_audit.csv")
    save_csv(pd.DataFrame(pass_a_trials), BASE / "trials/focus_pass_a_trials.csv")
    save_csv(pd.DataFrame(pass_b_trials), BASE / "trials/focus_pass_b_trials.csv")
    save_csv(pd.DataFrame(pass_c_trials), BASE / "trials/focus_pass_c_trials.csv")
    all_trials_df = pd.concat(
        [x for x in [pd.DataFrame(pass_a_trials), pd.DataFrame(pass_b_trials), pd.DataFrame(pass_c_trials)] if not x.empty],
        ignore_index=True,
    ) if (pass_a_trials or pass_b_trials or pass_c_trials) else pd.DataFrame()
    save_csv(all_trials_df, BASE / "trials/final_aggressive_retrain_trials.csv")
    save_csv(selected_df, BASE / "tables/final_aggressive_selected_models.csv")
    save_csv(
        selected_df[
            [
                c
                for c in [
                    "domain",
                    "mode",
                    "active_model_id",
                    "promotion_decision",
                    "pass_name",
                    "weight_policy",
                    "model_family",
                    "feature_set_id",
                    "config_id",
                    "calibration",
                    "threshold_policy",
                    "threshold",
                    "old_precision",
                    "precision",
                    "old_recall",
                    "recall",
                    "old_balanced_accuracy",
                    "balanced_accuracy",
                    "old_f1",
                    "f1",
                    "old_roc_auc",
                    "roc_auc",
                    "old_pr_auc",
                    "pr_auc",
                    "old_brier",
                    "brier",
                    "delta_precision",
                    "delta_recall",
                    "delta_balanced_accuracy",
                    "delta_f1",
                    "delta_pr_auc",
                    "delta_brier",
                    "old_secondary_anomaly",
                    "new_secondary_anomaly",
                    "generalization_ok",
                    "material_gain_ok",
                    "anomaly_resolution_ok",
                    "class_upgrade_candidate",
                    "anomaly_guard_ok",
                    "root_cause_hypothesis",
                ]
                if c in selected_df.columns
            ]
        ],
        BASE / "tables/final_old_vs_new_comparison.csv",
    )
    save_csv(
        focus[
            [
                c
                for c in [
                    "domain",
                    "mode",
                    "role",
                    "source_campaign",
                    "feature_set_id",
                    "secondary_metric_anomaly_flag",
                    "old_best_single_feature",
                    "old_best_single_feature_ba",
                    "old_shortcut_gap_vs_model_ba",
                    "root_cause_hypothesis",
                ]
                if c in focus.columns
            ]
        ],
        BASE / "tables/root_cause_by_slot.csv",
    )
    if not all_trials_df.empty:
        fam_eval = (
            all_trials_df.groupby(
                ["domain", "mode", "pass_name", "model_family", "config_id", "feature_set_id", "weight_policy"],
                as_index=False,
            )
            .agg(
                trials=("val_selection_score", "size"),
                best_val_score=("val_selection_score", "max"),
                best_holdout_ba=("balanced_accuracy", "max"),
                best_holdout_f1=("f1", "max"),
                best_holdout_pr_auc=("pr_auc", "max"),
            )
            .sort_values(["domain", "mode", "best_val_score"], ascending=[True, True, False])
        )
        save_csv(fam_eval, BASE / "tables/families_feature_sets_evaluated.csv")
        weight_eff = (
            all_trials_df.groupby(["domain", "mode", "weight_policy"], as_index=False)
            .agg(
                best_ba=("balanced_accuracy", "max"),
                best_f1=("f1", "max"),
                best_pr_auc=("pr_auc", "max"),
                best_selection=("val_selection_score", "max"),
            )
            .sort_values(["domain", "mode", "best_selection"], ascending=[True, True, False])
        )
        save_csv(weight_eff, BASE / "tables/weighting_effects_summary.csv")
        dsm = all_trials_df.copy()
        dsm["dsm5_variant"] = dsm["feature_set_id"].apply(lambda x: "yes" if str(x).startswith("dsm5_") else "no")
        dsm_eff = (
            dsm.groupby(["domain", "mode", "dsm5_variant"], as_index=False)
            .agg(
                best_ba=("balanced_accuracy", "max"),
                best_f1=("f1", "max"),
                best_pr_auc=("pr_auc", "max"),
                best_selection=("val_selection_score", "max"),
            )
            .sort_values(["domain", "mode", "dsm5_variant"], ascending=[True, True, False])
        )
        save_csv(dsm_eff, BASE / "tables/dsm5_variant_effects_summary.csv")

    promoted = {(str(r["domain"]), str(r["mode"])): r for _, r in selected_df.iterrows() if str(r.get("promotion_decision", "")) == "PROMOTE_NOW"}
    promoted_feature_map = {
        (str(r.get("domain")), str(r.get("mode"))): [f for f in str(r.get("feature_list_pipe", "")).split("|") if f]
        for _, r in selected_df.iterrows()
        if str(r.get("promotion_decision", "")) == "PROMOTE_NOW"
    }
    op_v5, active_v5 = op.copy(), active.copy()
    for (d, m), r in promoted.items():
        mo = (op_v5["domain"] == d) & (op_v5["mode"] == m)
        if mo.any():
            op_v5.loc[mo, "source_campaign"] = LINE
            op_v5.loc[mo, "model_family"] = str(r["model_family"])
            op_v5.loc[mo, "feature_set_id"] = str(r["feature_set_id"])
            op_v5.loc[mo, "calibration"] = str(r["calibration"])
            op_v5.loc[mo, "threshold_policy"] = str(r["threshold_policy"])
            op_v5.loc[mo, "threshold"] = float(r["threshold"])
            for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
                op_v5.loc[mo, k] = float(r[k])
            op_v5.loc[mo, "overfit_gap_train_val_ba"] = float(r.get("overfit_gap_train_val_ba", np.nan))
        ma = (active_v5["domain"] == d) & (active_v5["mode"] == m)
        if ma.any():
            active_v5.loc[ma, "active_model_id"] = f"{d}__{m}__{LINE}__{r['model_family']}__{r['feature_set_id']}"
            active_v5.loc[ma, "source_line"] = LINE
            active_v5.loc[ma, "source_campaign"] = LINE
            active_v5.loc[ma, "model_family"] = str(r["model_family"])
            active_v5.loc[ma, "feature_set_id"] = str(r["feature_set_id"])
            active_v5.loc[ma, "config_id"] = str(r["config_id"])
            active_v5.loc[ma, "calibration"] = str(r["calibration"])
            active_v5.loc[ma, "threshold_policy"] = str(r["threshold_policy"])
            active_v5.loc[ma, "threshold"] = float(r["threshold"])
            active_v5.loc[ma, "seed"] = int(r["seed"])
            active_v5.loc[ma, "n_features"] = int(r["n_features"])
            for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
                active_v5.loc[ma, k] = float(r[k])
            active_v5.loc[ma, "notes"] = "final_aggressive_rescue_v6_replacement"

    # Global evidence for 30 slots.
    ev_rows, st_rows, bs_rows, ab_rows, stress_rows = [], [], [], [], []
    for _, r in active_v5.iterrows():
        d, m = str(r["domain"]), str(r["mode"])
        tr, va, ho = subset(data, splits[d]["train"]), subset(data, splits[d]["val"]), subset(data, splits[d]["holdout"])
        t = f"target_domain_{d}_final"
        if (d, m) in promoted_feature_map:
            feats, st = promoted_feature_map[(d, m)], "exact_from_v6_selected_features"
        else:
            feats, st = feature_list(r, reg_map, conduct_map)
        if len(feats) < MIN_FEATURES:
            ev_rows.append({"domain": d, "mode": m, "evidence_status": "no_features", "feature_audit_status": st, "shortcut_dominance_flag": "por_confirmar"})
            continue
        try:
            x_tr, x_va, x_ho, eff = fit_matrix(tr, va, ho, feats)
            y_tr, y_va, y_ho = tr[t].astype(int).to_numpy(), va[t].astype(int).to_numpy(), ho[t].astype(int).to_numpy()
            model = build_model(str(r["model_family"]), str(r["config_id"]), int(r.get("seed", MARGIN_SEED)))
            model.fit(x_tr, y_tr)
            p_tr_raw, p_va_raw, p_ho_raw = _predict_prob_like(model, x_tr), _predict_prob_like(model, x_va), _predict_prob_like(model, x_ho)
            p_tr, p_va, p_ho = calibrate(y_va, p_tr_raw, p_va_raw, p_ho_raw, str(r.get("calibration", "none")))
            thr = float(r.get("threshold", 0.5))
            mt, mv, mh = compute_metrics(y_tr, p_tr, thr), compute_metrics(y_va, p_va, thr), compute_metrics(y_ho, p_ho, thr)
            overfit, gen = float(mt["balanced_accuracy"] - mv["balanced_accuracy"]), float(abs(mv["balanced_accuracy"] - mh["balanced_accuracy"]))
            sts = []
            for s in STABILITY_SEEDS:
                ms = build_model(str(r["model_family"]), str(r["config_id"]), int(s))
                ms.fit(x_tr, y_tr)
                ps_tr_raw, ps_va_raw, ps_ho_raw = _predict_prob_like(ms, x_tr), _predict_prob_like(ms, x_va), _predict_prob_like(ms, x_ho)
                _, _, ps = calibrate(y_va, ps_tr_raw, ps_va_raw, ps_ho_raw, str(r.get("calibration", "none")))
                mm = compute_metrics(y_ho, ps, thr)
                sts.append(mm)
                st_rows.append({"domain": d, "mode": m, "seed": int(s), "precision": mm["precision"], "recall": mm["recall"], "balanced_accuracy": mm["balanced_accuracy"], "pr_auc": mm["pr_auc"], "brier": mm["brier"]})
            ba_std = float(np.std([x["balanced_accuracy"] for x in sts])) if sts else np.nan
            p_std = float(np.std([x["precision"] for x in sts])) if sts else np.nan
            r_std = float(np.std([x["recall"] for x in sts])) if sts else np.nan
            idx = np.arange(len(y_ho))
            rng = np.random.default_rng(20270511)
            ba_b, pr_b = [], []
            for _ in range(BOOTSTRAP_ROUNDS):
                sidx = rng.choice(idx, size=len(idx), replace=True)
                mm = compute_metrics(y_ho[sidx], p_ho[sidx], thr)
                ba_b.append(mm["balanced_accuracy"]); pr_b.append(mm["pr_auc"])
            bci = float(np.quantile(ba_b, 0.975) - np.quantile(ba_b, 0.025))
            prci = float(np.quantile(pr_b, 0.975) - np.quantile(pr_b, 0.025))
            bs_rows.extend([{"domain": d, "mode": m, "metric": "balanced_accuracy", "ci_low": float(np.quantile(ba_b, 0.025)), "ci_high": float(np.quantile(ba_b, 0.975)), "ci_width": bci}, {"domain": d, "mode": m, "metric": "pr_auc", "ci_low": float(np.quantile(pr_b, 0.025)), "ci_high": float(np.quantile(pr_b, 0.975)), "ci_width": prci}])
            stress = []
            for dthr in [-0.10, -0.05, 0.05, 0.10]:
                mm = compute_metrics(y_ho, p_ho, float(np.clip(thr + dthr, 0.05, 0.95)))
                delta = float(mm["balanced_accuracy"] - mh["balanced_accuracy"])
                stress.append(delta)
                stress_rows.append({"domain": d, "mode": m, "stress_type": "threshold", "scenario": f"threshold_shift_{dthr:+.2f}", "balanced_accuracy": mm["balanced_accuracy"], "delta_ba": delta})
            xh = ho[eff].copy().apply(pd.to_numeric, errors="coerce")
            med = xh.median(numeric_only=True)
            mask = np.random.default_rng(20270513).random(xh.shape) < 0.10
            xh = xh.mask(mask).fillna(med)
            mm = compute_metrics(y_ho, _predict_prob_like(model, xh.to_numpy()), thr)
            md = float(mm["balanced_accuracy"] - mh["balanced_accuracy"])
            stress.append(md)
            stress_rows.append({"domain": d, "mode": m, "stress_type": "missingness", "scenario": "missing_10pct", "balanced_accuracy": mm["balanced_accuracy"], "delta_ba": md})
            ab = np.nan
            if hasattr(model, "feature_importances_") and len(model.feature_importances_) == len(eff):
                top3 = pd.Series(model.feature_importances_, index=eff).sort_values(ascending=False).head(min(3, len(eff))).index.tolist()
                rem = [f for f in eff if f not in top3]
                if len(rem) >= MIN_FEATURES:
                    xtr2, xva2, xho2, _ = fit_matrix(tr, va, ho, rem)
                    m2 = build_model(str(r["model_family"]), str(r["config_id"]), int(r.get("seed", MARGIN_SEED)))
                    m2.fit(xtr2, y_tr)
                    mm2 = compute_metrics(y_ho, _predict_prob_like(m2, xho2), thr)
                    ab = float(mm2["balanced_accuracy"] - mh["balanced_accuracy"])
                    ab_rows.append({"domain": d, "mode": m, "ablation_case": "drop_top3", "delta_ba": ab, "delta_pr_auc": float(mm2["pr_auc"] - mh["pr_auc"]), "removed_features": "|".join(top3)})
            sc = single_feature_rule(ho, t, eff)
            sba = float(sc["best_single_feature_ba"]) if pd.notna(sc["best_single_feature_ba"]) else np.nan
            sg = float(sba - mh["balanced_accuracy"]) if pd.notna(sba) else np.nan
            ev_rows.append({"domain": d, "mode": m, "feature_count": len(eff), "feature_audit_status": st, "source_campaign": str(r["source_campaign"]), "feature_set_id": str(r["feature_set_id"]), "overfit_gap_train_val_ba": overfit, "generalization_gap_val_holdout_ba": gen, "stability_ba_std": ba_std, "stability_precision_std": p_std, "stability_recall_std": r_std, "bootstrap_ba_ci_width": bci, "bootstrap_pr_auc_ci_width": prci, "stress_worst_delta_ba": float(min(stress)) if stress else np.nan, "ablation_drop3_delta_ba": ab, "best_single_feature": sc["best_single_feature"], "best_single_feature_ba": sba, "shortcut_gap_vs_model_ba": sg, "shortcut_dominance_flag": "yes" if pd.notna(sg) and sg >= 0.05 else "no", "evidence_status": "ok"})
        except Exception:
            ev_rows.append({"domain": d, "mode": m, "evidence_status": "train_error", "feature_audit_status": st, "shortcut_dominance_flag": "por_confirmar"})

    ev_df = pd.DataFrame(ev_rows)
    save_csv(ev_df, BASE / "validation/global_model_evidence_v6.csv")
    save_csv(pd.DataFrame(st_rows), BASE / "stability/global_seed_stability_v6.csv")
    save_csv(pd.DataFrame(bs_rows), BASE / "bootstrap/global_bootstrap_v6.csv")
    save_csv(pd.DataFrame(ab_rows), BASE / "ablation/global_ablation_v6.csv")
    save_csv(pd.DataFrame(stress_rows), BASE / "stress/global_stress_v6.csv")
    save_csv(ev_df[["domain", "mode", "shortcut_dominance_flag"]], SHORTCUT_V5)

    save_csv(op_v5, OP_V5_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(active_v5, ACTIVE_V5_BASE / "tables/hybrid_active_models_30_modes.csv")

    norm_v5 = build_normalized_table(PolicyInputs(operational_csv=OP_V5_BASE / "tables/hybrid_operational_final_champions.csv", active_csv=ACTIVE_V5_BASE / "tables/hybrid_active_models_30_modes.csv", shortcut_inventory_csv=SHORTCUT_V5))
    viol = policy_violations(norm_v5)
    save_csv(norm_v5, NORMALIZED_V5)
    save_csv(viol, VIOLATIONS_V5)

    # Recalculate confidence and operational class for all rows.
    nidx = {(str(r.domain), str(r.mode)): r for r in norm_v5.itertuples(index=False)}
    eidx = {(str(r.domain), str(r.mode)): r for r in ev_df.itertuples(index=False)}
    for i, r in active_v5.iterrows():
        k = (str(r["domain"]), str(r["mode"]))
        nr = nidx[k]
        er = eidx.get(k)
        if er is None:
            continue
        s = 0.0
        s += 20 * nrm(float(r["precision"]), 0.55, 0.95)
        s += 18 * nrm(float(r["recall"]), 0.55, 0.95)
        s += 22 * nrm(float(r["balanced_accuracy"]), 0.60, 0.98)
        s += 14 * nrm(float(r["pr_auc"]), 0.60, 0.98)
        s += 8 * nrm(float(r["roc_auc"]), 0.65, 0.99)
        s += 10 * nrm(0.12 - float(r["brier"]), 0.0, 0.12)
        cls = str(getattr(nr, "normalized_final_class", "HOLD_FOR_LIMITATION"))
        s += {"ROBUST_PRIMARY": 4, "PRIMARY_WITH_CAVEAT": -1.5, "HOLD_FOR_LIMITATION": -14, "REJECT_AS_PRIMARY": -20}.get(cls, -8)
        for flag, pen in [("overfit_risk_flag", 10), ("generalization_risk_flag", 8), ("easy_dataset_flag", 12), ("shortcut_risk_flag", 12), ("secondary_metric_anomaly_flag", 8), ("mode_fragility_flag", 4), ("calibration_concern_flag", 3)]:
            if str(getattr(nr, flag, "no")) == "yes":
                s -= pen
        if pd.notna(getattr(er, "stability_ba_std", np.nan)):
            s -= 10 * nrm(float(getattr(er, "stability_ba_std")), 0.015, 0.040)
        if pd.notna(getattr(er, "bootstrap_ba_ci_width", np.nan)):
            s -= 8 * nrm(float(getattr(er, "bootstrap_ba_ci_width")), 0.040, 0.120)
        if pd.notna(getattr(er, "stress_worst_delta_ba", np.nan)):
            s -= 8 * nrm(abs(min(float(getattr(er, "stress_worst_delta_ba")), 0.0)), 0.040, 0.120)
        if pd.notna(getattr(er, "ablation_drop3_delta_ba", np.nan)):
            s -= 8 * nrm(abs(min(float(getattr(er, "ablation_drop3_delta_ba")), 0.0)), 0.030, 0.120)
        conf = round(max(0.0, min(98.0, s)), 1)
        if cls in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"}:
            conf = min(conf, 59.0)
        if str(getattr(nr, "easy_dataset_flag", "no")) == "yes" or str(getattr(nr, "shortcut_risk_flag", "no")) == "yes":
            conf = min(conf, 69.0)
        if str(getattr(nr, "secondary_metric_anomaly_flag", "no")) == "yes":
            conf = min(conf, 84.0)
        if str(getattr(nr, "overfit_risk_flag", "no")) == "yes" or str(getattr(nr, "generalization_risk_flag", "no")) == "yes":
            conf = min(conf, 79.0)
        band = conf_band(conf)
        if band == "high" and (str(getattr(nr, "secondary_metric_anomaly_flag", "no")) == "yes" or str(getattr(nr, "easy_dataset_flag", "no")) == "yes" or str(getattr(nr, "shortcut_risk_flag", "no")) == "yes"):
            band = "moderate"
        if cls in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"} or band == "limited":
            op_class = "ACTIVE_LIMITED_USE"
        elif band == "high" and cls == "ROBUST_PRIMARY":
            op_class = "ACTIVE_HIGH_CONFIDENCE"
        elif band == "high":
            op_class = "ACTIVE_MODERATE_CONFIDENCE"
        elif band == "moderate":
            op_class = "ACTIVE_MODERATE_CONFIDENCE"
        else:
            op_class = "ACTIVE_LOW_CONFIDENCE"
        caveats = []
        for f, label in [("secondary_metric_anomaly_flag", "secondary metric anomaly"), ("shortcut_risk_flag", "shortcut risk"), ("easy_dataset_flag", "easy dataset risk"), ("overfit_risk_flag", "overfit risk"), ("generalization_risk_flag", "generalization risk"), ("mode_fragility_flag", "mode fragility"), ("calibration_concern_flag", "calibration concern")]:
            if str(getattr(nr, f, "no")) == "yes":
                caveats.append(label)
        if float(r["precision"]) < 0.80:
            caveats.append("low precision")
        if float(r["recall"]) < 0.75:
            caveats.append("low recall")
        if pd.notna(getattr(er, "stress_worst_delta_ba", np.nan)) and float(getattr(er, "stress_worst_delta_ba")) < -0.08:
            caveats.append("stress sensitivity")
        active_v5.loc[i, "confidence_pct"] = conf
        active_v5.loc[i, "confidence_band"] = band
        active_v5.loc[i, "final_operational_class"] = op_class
        active_v5.loc[i, "operational_caveat"] = "; ".join(dict.fromkeys(caveats)) if caveats else "none"
        active_v5.loc[i, "recommended_for_default_use"] = "yes" if op_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"} and cls in {"ROBUST_PRIMARY", "PRIMARY_WITH_CAVEAT"} and str(getattr(nr, "easy_dataset_flag", "no")) == "no" and str(getattr(nr, "shortcut_risk_flag", "no")) == "no" else "no"
        active_v5.loc[i, "overfit_flag"] = "yes" if pd.notna(getattr(er, "overfit_gap_train_val_ba", np.nan)) and float(getattr(er, "overfit_gap_train_val_ba")) > 0.10 else "no"
        active_v5.loc[i, "generalization_flag"] = "no" if pd.notna(getattr(er, "generalization_gap_val_holdout_ba", np.nan)) and float(getattr(er, "generalization_gap_val_holdout_ba")) > 0.09 else "yes"
        mo = (op_v5["domain"] == k[0]) & (op_v5["mode"] == k[1])
        if mo.any():
            op_v5.loc[mo, "final_class"] = cls
            if pd.notna(getattr(er, "overfit_gap_train_val_ba", np.nan)):
                op_v5.loc[mo, "overfit_gap_train_val_ba"] = float(getattr(er, "overfit_gap_train_val_ba"))

    save_csv(op_v5, OP_V5_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(op_v5[op_v5["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])], OP_V5_BASE / "tables/hybrid_operational_final_nonchampions.csv")
    save_csv(op_v5[["domain", "mode", "source_campaign", "final_class", "quality_label", "overfit_gap_train_val_ba"]], OP_V5_BASE / "validation/hybrid_operational_overfit_audit.csv")
    gen = ev_df[["domain", "mode", "generalization_gap_val_holdout_ba", "evidence_status"]].copy()
    gen["generalization_flag"] = gen["generalization_gap_val_holdout_ba"].apply(lambda x: "yes" if pd.notna(x) and float(x) <= 0.09 else "no")
    save_csv(gen, OP_V5_BASE / "validation/hybrid_operational_generalization_audit.csv")
    save_csv(pd.DataFrame(bs_rows), OP_V5_BASE / "bootstrap/hybrid_operational_bootstrap_intervals.csv")
    save_csv(pd.DataFrame(ab_rows), OP_V5_BASE / "ablation/hybrid_operational_ablation.csv")
    save_csv(pd.DataFrame(stress_rows), OP_V5_BASE / "stress/hybrid_operational_stress.csv")

    save_csv(active_v5, ACTIVE_V5_BASE / "tables/hybrid_active_models_30_modes.csv")
    save_csv(active_v5.groupby(["final_operational_class", "confidence_band"], as_index=False).size(), ACTIVE_V5_BASE / "tables/hybrid_active_modes_summary.csv")
    save_csv(pd.read_csv(INPUTS_SRC), ACTIVE_V5_BASE / "tables/hybrid_questionnaire_inputs_master.csv")
    save_csv(ev_df, ACTIVE_V5_BASE / "validation/global_model_evidence_v6.csv")
    save_csv(pd.DataFrame(st_rows), ACTIVE_V5_BASE / "stability/hybrid_active_seed_stability_v6.csv")
    save_csv(pd.DataFrame(bs_rows), ACTIVE_V5_BASE / "bootstrap/hybrid_active_bootstrap_v6.csv")
    save_csv(pd.DataFrame(ab_rows), ACTIVE_V5_BASE / "ablation/hybrid_active_ablation_v6.csv")
    save_csv(pd.DataFrame(stress_rows), ACTIVE_V5_BASE / "stress/hybrid_active_stress_v6.csv")

    demoted = selected_df[selected_df.get("promotion_decision", "") == "PROMOTE_NOW"].copy()
    if not demoted.empty:
        demoted = demoted.assign(status="demoted_from_primary_due_replacement", reason=f"replaced_by_{LINE}")
    save_csv(demoted, BASE / "inventory/models_demoted.csv")
    save_csv(pd.DataFrame([{"domain": r.get("domain"), "mode": r.get("mode"), "old_active_model_id": r.get("active_model_id"), "promotion_decision": r.get("promotion_decision"), "new_model_family": r.get("model_family"), "new_feature_set_id": r.get("feature_set_id"), "delta_balanced_accuracy": r.get("delta_balanced_accuracy"), "delta_f1": r.get("delta_f1"), "delta_pr_auc": r.get("delta_pr_auc"), "delta_brier": r.get("delta_brier"), "root_cause_hypothesis": r.get("root_cause_hypothesis")} for _, r in selected_df.iterrows()]), OP_V5_BASE / "inventory/v5_to_v6_replacement_map.csv")

    merged = active.merge(active_v5, on=["domain", "mode"], suffixes=("_old", "_new"))
    merged["delta_confidence"] = merged["confidence_pct_new"] - merged["confidence_pct_old"]

    report = [
        "# Hybrid Final Aggressive Rescue v6 - Executive Summary",
        "",
        "Aggressive final campaign to maximize real model quality while preserving methodological honesty and operational contract.",
        "",
        "## Focus slots",
        md_table(focus[["domain", "mode", "source_campaign", "feature_set_id", "confidence_pct", "confidence_band", "secondary_metric_anomaly_flag", "root_cause_hypothesis"]]) if not focus.empty else "(sin focus slots)",
        "",
        "## Selection result",
        md_table(selected_df[["domain", "mode", "promotion_decision", "model_family", "feature_set_id", "delta_balanced_accuracy", "delta_f1", "delta_pr_auc", "old_secondary_anomaly", "new_secondary_anomaly", "root_cause_hypothesis"]]) if not selected_df.empty else "(sin seleccion)",
        "",
        "## Active class counts v6",
        active_v5["final_operational_class"].value_counts().to_string(),
        "",
        "## Confidence bands v6",
        active_v5["confidence_band"].value_counts().to_string(),
        "",
        "## Policy violations v6",
        f"- violations={len(viol)}",
    ]
    (BASE / "reports/hybrid_final_aggressive_rescue_summary.md").write_text("\n".join(report).strip() + "\n", encoding="utf-8")
    (OP_V5_BASE / "reports/hybrid_operational_freeze_summary.md").write_text(
        "\n".join(["# Hybrid Operational Freeze v6 - Summary", "", "## Final class counts", op_v5["final_class"].value_counts().to_string(), "", "## Replacements", md_table(pd.read_csv(OP_V5_BASE / "inventory/v5_to_v6_replacement_map.csv"))]) + "\n",
        encoding="utf-8",
    )
    (ACTIVE_V5_BASE / "reports/hybrid_active_modes_freeze_summary.md").write_text(
        "\n".join(["# Hybrid Active Modes Freeze v6 - Summary", "", "## Active class counts", active_v5["final_operational_class"].value_counts().to_string(), "", "## Top confidence changes", md_table(merged.sort_values("delta_confidence").head(15)[["domain", "mode", "confidence_pct_old", "confidence_pct_new", "delta_confidence", "confidence_band_old", "confidence_band_new", "final_operational_class_old", "final_operational_class_new"]])]) + "\n",
        encoding="utf-8",
    )

    summary = pd.DataFrame([{"line": "v6", "rows": int(len(norm_v5)), "normalized_robust": int((norm_v5["normalized_final_class"] == "ROBUST_PRIMARY").sum()), "normalized_caveat": int((norm_v5["normalized_final_class"] == "PRIMARY_WITH_CAVEAT").sum()), "normalized_hold": int((norm_v5["normalized_final_class"] == "HOLD_FOR_LIMITATION").sum()), "normalized_reject": int((norm_v5["normalized_final_class"] == "REJECT_AS_PRIMARY").sum()), "downgrades": int((norm_v5["class_transition"] == "downgrade").sum()), "violations": int(len(viol))}])
    save_csv(summary, NORM_V2_BASE / "tables/hybrid_classification_normalization_summary_v6.csv")
    save_csv(norm_v5, NORMALIZED_V5)
    save_csv(viol, VIOLATIONS_V5)
    (NORM_V2_BASE / "reports/hybrid_classification_normalization_summary_v6.md").write_text(
        "\n".join(["# Hybrid Classification Normalization v2 (v6)", "", "## Summary", md_table(summary), "", "## Priority review", md_table(norm_v5.sort_values(["secondary_metric_anomaly_flag", "normalized_final_class"], ascending=[False, True]).head(30)[["domain", "mode", "legacy_final_class", "normalized_final_class", "secondary_metric_anomaly_flag", "overfit_risk_flag", "shortcut_risk_flag", "easy_dataset_flag", "classification_reason_code"]])]) + "\n",
        encoding="utf-8",
    )

    files = []
    for p in sorted([x for x in BASE.rglob("*") if x.is_file()]):
        files.append({"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": int(p.stat().st_size)})
    promoted_n = int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum())
    (ART / "hybrid_final_aggressive_rescue_v6_manifest.json").write_text(json.dumps({"line": LINE, "generated_at_utc": now_iso(), "source_truth_previous": {"operational": str(OP_SRC.relative_to(ROOT)), "active": str(ACTIVE_SRC.relative_to(ROOT))}, "source_truth_new": {"operational": str((OP_V5_BASE / "tables/hybrid_operational_final_champions.csv").relative_to(ROOT)), "active": str((ACTIVE_V5_BASE / "tables/hybrid_active_models_30_modes.csv").relative_to(ROOT))}, "stats": {"focus_slots": int(len(focus)), "promoted": promoted_n, "policy_violations": int(len(viol))}, "generated_files": files}, indent=2), encoding="utf-8")
    (ROOT / "artifacts/hybrid_operational_freeze_v6").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_operational_freeze_v6/hybrid_operational_freeze_v6_manifest.json").write_text(json.dumps({"run_id": "hybrid_operational_freeze_v6", "base_line": "hybrid_operational_freeze_v5", "replacement_line": LINE, "replaced_pairs": promoted_n, "path": "data/hybrid_operational_freeze_v6/tables/hybrid_operational_final_champions.csv", "generated_at_utc": now_iso()}, indent=2), encoding="utf-8")
    (ROOT / "artifacts/hybrid_active_modes_freeze_v6").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_active_modes_freeze_v6/hybrid_active_modes_freeze_v6_manifest.json").write_text(json.dumps({"run_id": "hybrid_active_modes_freeze_v6", "base_line": "hybrid_active_modes_freeze_v5", "replacement_line": LINE, "replaced_pairs": promoted_n, "path": "data/hybrid_active_modes_freeze_v6/tables/hybrid_active_models_30_modes.csv", "generated_at_utc": now_iso()}, indent=2), encoding="utf-8")
    (ROOT / "artifacts/hybrid_classification_normalization_v2").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_classification_normalization_v2/hybrid_classification_normalization_v2_manifest.json").write_text(json.dumps({"run_id": "hybrid_classification_normalization_v2", "generated_at_utc": now_iso(), "source_operational_v6": "data/hybrid_operational_freeze_v6/tables/hybrid_operational_final_champions.csv", "source_active_v6": "data/hybrid_active_modes_freeze_v6/tables/hybrid_active_models_30_modes.csv", "outputs": {"normalized_v6": str(NORMALIZED_V5.relative_to(ROOT)), "violations_v6": str(VIOLATIONS_V5.relative_to(ROOT))}, "policy_violation_count_v6": int(len(viol))}, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "line": LINE, "focus_slots": int(len(focus)), "promoted": promoted_n, "policy_violations": int(len(viol))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
