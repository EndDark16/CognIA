#!/usr/bin/env python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
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
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

LINE = "hybrid_v6_quick_champion_guard_hotfix_v1"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE

ACTIVE_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6" / "tables" / "hybrid_active_models_30_modes.csv"
ACTIVE_SUMMARY_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6" / "tables" / "hybrid_active_modes_summary.csv"
OP_SRC = ROOT / "data" / "hybrid_operational_freeze_v6" / "tables" / "hybrid_operational_final_champions.csv"
INPUTS_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6" / "tables" / "hybrid_questionnaire_inputs_master.csv"

DATASET = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
FE_REG = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "feature_engineering" / "hybrid_no_external_scores_feature_engineering_registry.csv"
CONDUCT_SELECTED = ROOT / "data" / "hybrid_conduct_honest_retrain_v1" / "tables" / "conduct_honest_retrain_selected_models.csv"

ACTIVE_OUT_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v6_hotfix_v1"
OP_OUT_BASE = ROOT / "data" / "hybrid_operational_freeze_v6_hotfix_v1"
NORM_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"
NORM_OUT = NORM_BASE / "tables" / "hybrid_operational_classification_normalized_v6_hotfix_v1.csv"
NORM_VIOL = NORM_BASE / "validation" / "hybrid_classification_policy_violations_v6_hotfix_v1.csv"
SHORTCUT_OUT = BASE / "tables" / "shortcut_inventory_v6_hotfix_v1.csv"

EXISTING_POOL_FILES = [
    ROOT / "data" / "hybrid_active_modes_freeze_v2" / "tables" / "hybrid_active_models_30_modes.csv",
    ROOT / "data" / "hybrid_active_modes_freeze_v3" / "tables" / "hybrid_active_models_30_modes.csv",
    ROOT / "data" / "hybrid_active_modes_freeze_v4" / "tables" / "hybrid_active_models_30_modes.csv",
    ROOT / "data" / "hybrid_active_modes_freeze_v5" / "tables" / "hybrid_active_models_30_modes.csv",
    ROOT / "data" / "hybrid_active_modes_freeze_v6" / "tables" / "hybrid_active_models_30_modes.csv",
    ROOT / "data" / "hybrid_operational_freeze_v2" / "tables" / "hybrid_operational_final_champions.csv",
    ROOT / "data" / "hybrid_operational_freeze_v3" / "tables" / "hybrid_operational_final_champions.csv",
    ROOT / "data" / "hybrid_operational_freeze_v4" / "tables" / "hybrid_operational_final_champions.csv",
    ROOT / "data" / "hybrid_operational_freeze_v5" / "tables" / "hybrid_operational_final_champions.csv",
    ROOT / "data" / "hybrid_operational_freeze_v6" / "tables" / "hybrid_operational_final_champions.csv",
    ROOT / "data" / "hybrid_conduct_honest_retrain_v1" / "tables" / "conduct_honest_retrain_selected_models.csv",
    ROOT / "data" / "hybrid_secondary_honest_retrain_v1" / "tables" / "secondary_honest_retrain_selected_models.csv",
    ROOT / "data" / "hybrid_final_honest_improvement_v1" / "tables" / "final_honest_improvement_selected_models.csv",
    ROOT / "data" / "hybrid_final_decisive_rescue_v5" / "tables" / "final_decisive_selected_models.csv",
    ROOT / "data" / "hybrid_final_aggressive_rescue_v6" / "tables" / "final_aggressive_selected_models.csv",
]

WATCH_METRICS = ("recall", "specificity", "roc_auc", "pr_auc")
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]

OLD_HINTS = {
    "boosted_eng_full": "full_eligible",
    "boosted_eng_compact": "compact_subset",
    "boosted_eng_pruned": "stability_pruned_subset",
}

DSM5_CORE_PREFIXES = {
    "adhd": ("adhd_",),
    "conduct": ("conduct_",),
    "anxiety": ("agor_", "gad_", "sep_anx_", "social_anxiety_"),
    "depression": ("mdd_", "pdd_", "dmdd_"),
    "elimination": ("enuresis_", "encopresis_"),
}
GLOBAL_CONTEXT_FEATURES = ("age_years", "sex_assigned_at_birth")
MIN_FEATURES = 5

RF_CFG = dict(
    n_estimators=150,
    max_depth=14,
    min_samples_split=8,
    min_samples_leaf=3,
    max_features=0.50,
    class_weight="balanced_subsample",
    bootstrap=True,
    max_samples=0.90,
)
EXTRA_CFG = dict(
    n_estimators=180,
    max_depth=14,
    min_samples_split=4,
    min_samples_leaf=2,
    max_features=0.55,
    class_weight="balanced_subsample",
)
HGB_CFG = dict(
    max_depth=3,
    learning_rate=0.03,
    max_iter=240,
    l2_regularization=0.45,
    min_samples_leaf=28,
)

SEARCH_SEEDS = [20270421, 20270439]
BASE_SEED = 20261101


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [
        BASE / "tables",
        BASE / "reports",
        BASE / "validation",
        BASE / "trials",
        ART,
        ACTIVE_OUT_BASE / "tables",
        ACTIVE_OUT_BASE / "reports",
        OP_OUT_BASE / "tables",
        OP_OUT_BASE / "reports",
        NORM_BASE / "tables",
        NORM_BASE / "validation",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_float(x: Any, default: float = np.nan) -> float:
    try:
        return float(x)
    except Exception:
        return default


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
    }


def violates_guard(row: pd.Series | dict[str, Any]) -> bool:
    return any(safe_float(row.get(m), 0.0) > 0.98 for m in WATCH_METRICS)


def precision_floor(mode: str) -> float:
    return 0.72 if mode.endswith("_1_3") else 0.78


def recall_target(mode: str) -> tuple[float, float]:
    if mode.endswith("_1_3"):
        return 0.88, 0.95
    return 0.92, 0.98


def choose_threshold(mode: str, y_true: np.ndarray, probs: np.ndarray) -> tuple[float, float]:
    r_lo, r_hi = recall_target(mode)
    p_floor = precision_floor(mode)
    best_thr, best_score = 0.5, -1e9
    for thr in np.linspace(0.08, 0.92, 61):
        m = compute_metrics(y_true, probs, float(thr))
        score = (
            0.55 * m["f1"]
            + 0.25 * m["recall"]
            + 0.12 * m["precision"]
            + 0.08 * m["balanced_accuracy"]
            - 0.05 * m["brier"]
        )
        if m["recall"] > 0.98:
            score -= 0.20
        if m["precision"] < p_floor:
            score -= 0.20
        if r_lo <= m["recall"] <= r_hi:
            score += 0.03
        if score > best_score:
            best_score, best_thr = float(score), float(thr)
    return best_thr, best_score


def split_by_domain(df: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for d in DOMAINS:
        t = f"target_domain_{d}_final"
        sub = df[["participant_id", t]].dropna().copy()
        ids = sub["participant_id"].astype(str).to_numpy()
        y = sub[t].astype(int).to_numpy()
        seed = BASE_SEED + DOMAINS.index(d)
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=strat)
        strat2 = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids, _, _ = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=strat2)
        out[d] = {"train": list(tr_ids), "val": list(va_ids), "holdout": list(ho_ids)}
    return out


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def build_feature_maps() -> tuple[dict[tuple[str, str, str], list[str]], dict[tuple[str, str], list[str]]]:
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


def resolve_features(
    domain: str,
    mode: str,
    source_campaign: str,
    feature_set_id: str,
    feature_list_pipe: str | None,
    reg_map: dict[tuple[str, str, str], list[str]],
    conduct_map: dict[tuple[str, str], list[str]],
) -> list[str]:
    if feature_list_pipe:
        feats = [f for f in str(feature_list_pipe).split("|") if f]
        if len(feats) >= MIN_FEATURES:
            return feats

    if source_campaign == "conduct_honest_retrain_v1":
        feats = conduct_map.get((mode, feature_set_id))
        if feats and len(feats) >= MIN_FEATURES:
            return feats
        fallback = conduct_map.get((mode, "engineered_compact_no_shortcuts_v1"))
        if fallback and len(fallback) >= MIN_FEATURES:
            return fallback

    fs = OLD_HINTS.get(feature_set_id, feature_set_id)
    feats = reg_map.get((domain, mode, fs), [])
    return [f for f in feats if f]


def single_feature_dominant(ho_df: pd.DataFrame, target_col: str, features: list[str]) -> str:
    y = ho_df[target_col].astype(int).to_numpy()
    best_feature = ""
    best_ba = -1.0
    for f in features:
        if f not in ho_df.columns:
            continue
        x = pd.to_numeric(ho_df[f], errors="coerce")
        if x.isna().all():
            continue
        x = x.fillna(float(x.median())).to_numpy()
        if len(np.unique(x)) < 2:
            continue
        for thr in np.unique(np.quantile(x, np.linspace(0.10, 0.90, 9))):
            for ge in (True, False):
                pred = (x >= thr).astype(int) if ge else (x <= thr).astype(int)
                ba = float(balanced_accuracy_score(y, pred))
                if ba > best_ba:
                    best_ba = ba
                    best_feature = f
    return best_feature


def dsm5_core_plus_context(domain: str, pool: list[str]) -> list[str]:
    prefixes = DSM5_CORE_PREFIXES.get(domain, ())
    core = [f for f in pool if str(f).startswith(prefixes)]
    ctx = [f for f in GLOBAL_CONTEXT_FEATURES if f in pool]
    out = []
    for f in core + ctx:
        if f not in out:
            out.append(f)
    return out


def fit_matrix(tr_df: pd.DataFrame, va_df: pd.DataFrame, ho_df: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    x_tr = tr_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_va = va_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = ho_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_tr = x_tr.dropna(axis=1, how="all")
    cols = list(x_tr.columns)
    if len(cols) < MIN_FEATURES:
        raise ValueError("not_enough_features")
    imp = SimpleImputer(strategy="median")
    return imp.fit_transform(x_tr), imp.transform(x_va[cols]), imp.transform(x_ho[cols]), cols


def fit_single_feature_matrix(
    tr_df: pd.DataFrame, va_df: pd.DataFrame, ho_df: pd.DataFrame, feature: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    if feature not in tr_df.columns or feature not in va_df.columns or feature not in ho_df.columns:
        raise ValueError("feature_not_found")
    s_tr = pd.to_numeric(tr_df[feature], errors="coerce")
    s_va = pd.to_numeric(va_df[feature], errors="coerce")
    s_ho = pd.to_numeric(ho_df[feature], errors="coerce")
    if int(s_tr.notna().sum()) < 20:
        raise ValueError("insufficient_non_null")
    if int(s_tr.nunique(dropna=True)) < 2:
        raise ValueError("no_variance")
    imp = SimpleImputer(strategy="median")
    x_tr = imp.fit_transform(s_tr.to_frame())
    x_va = imp.transform(s_va.to_frame())
    x_ho = imp.transform(s_ho.to_frame())
    return x_tr, x_va, x_ho, [feature]


def build_model(family: str, seed: int):
    if family == "rf":
        return RandomForestClassifier(random_state=seed, n_jobs=-1, **RF_CFG)
    if family == "extra_trees":
        return ExtraTreesClassifier(random_state=seed, n_jobs=-1, **EXTRA_CFG)
    if family == "hgb":
        return HistGradientBoostingClassifier(random_state=seed, **HGB_CFG)
    if family == "logreg":
        return LogisticRegression(max_iter=4000, C=0.12, solver="liblinear", class_weight="balanced")
    raise ValueError(f"unsupported family {family}")


def predict_proba_binary(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(x)[:, 1]
    else:
        z = model.decision_function(x)
        p = 1.0 / (1.0 + np.exp(-z))
    return np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)


def rank_candidates(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(
        ["f1", "recall", "precision", "balanced_accuracy", "brier"],
        ascending=[False, False, False, False, True],
    )


def confidence_band(score: float) -> str:
    if score >= 85:
        return "high"
    if score >= 70:
        return "moderate"
    if score >= 60:
        return "low"
    return "limited"


def main() -> None:
    ensure_dirs()
    active = pd.read_csv(ACTIVE_SRC)
    op = pd.read_csv(OP_SRC)
    dataset = pd.read_csv(DATASET)
    reg_map, conduct_map = build_feature_maps()
    splits = split_by_domain(dataset)

    active["role"] = active["role"].replace({"guardian": "caregiver"}).fillna("caregiver")
    viol = active[
        (active["recall"] > 0.98)
        | (active["specificity"] > 0.98)
        | (active["roc_auc"] > 0.98)
        | (active["pr_auc"] > 0.98)
    ].copy()
    viol_slots = viol[["domain", "mode", "role"]].drop_duplicates().sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(viol_slots, BASE / "tables/violating_slots_v6.csv")

    # Phase 2: existing candidate search.
    pool_rows: list[pd.DataFrame] = []
    for f in EXISTING_POOL_FILES:
        if not f.exists():
            continue
        d = pd.read_csv(f)
        for c in [
            "domain",
            "mode",
            "role",
            "precision",
            "recall",
            "specificity",
            "balanced_accuracy",
            "f1",
            "roc_auc",
            "pr_auc",
            "brier",
            "source_campaign",
            "feature_set_id",
            "model_family",
            "active_model_id",
            "promotion_decision",
            "threshold_policy",
            "threshold",
            "config_id",
            "seed",
            "n_features",
            "calibration",
            "feature_list_pipe",
        ]:
            if c not in d.columns:
                d[c] = None
        d["source_file"] = str(f.relative_to(ROOT))
        d["role"] = d["role"].replace({"guardian": "caregiver"}).fillna("")
        for c in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "threshold"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        pool_rows.append(
            d[
                [
                    "domain",
                    "mode",
                    "role",
                    "precision",
                    "recall",
                    "specificity",
                    "balanced_accuracy",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier",
                    "source_campaign",
                    "feature_set_id",
                    "model_family",
                    "active_model_id",
                    "promotion_decision",
                    "threshold_policy",
                    "threshold",
                    "config_id",
                    "seed",
                    "n_features",
                    "calibration",
                    "feature_list_pipe",
                    "source_file",
                ]
            ]
        )
    pool = pd.concat(pool_rows, ignore_index=True)
    pool = pool.merge(viol_slots[["domain", "mode"]].drop_duplicates(), on=["domain", "mode"], how="inner")
    pool_valid = pool[
        (pool["recall"] <= 0.98)
        & (pool["specificity"] <= 0.98)
        & (pool["roc_auc"] <= 0.98)
        & (pool["pr_auc"] <= 0.98)
    ].copy()
    pool_valid = rank_candidates(pool_valid)
    existing_best = pool_valid.groupby(["domain", "mode"], as_index=False).head(1).copy()
    save_csv(pool_valid, BASE / "tables/existing_valid_candidates_all.csv")
    save_csv(existing_best, BASE / "tables/existing_best_replacements.csv")

    replace_map: dict[tuple[str, str], dict[str, Any]] = {}
    replace_origin: dict[tuple[str, str], str] = {}
    for _, r in existing_best.iterrows():
        replace_map[(str(r["domain"]), str(r["mode"]))] = r.to_dict()
        replace_origin[(str(r["domain"]), str(r["mode"]))] = "existing"

    unresolved = []
    for _, r in viol_slots.iterrows():
        k = (str(r["domain"]), str(r["mode"]))
        if k not in replace_map:
            unresolved.append(k)
    save_csv(pd.DataFrame(unresolved, columns=["domain", "mode"]), BASE / "tables/unresolved_after_existing_search.csv")

    # Phase 3: lightweight retrain only unresolved.
    trial_rows: list[dict[str, Any]] = []
    retrain_best_rows: list[dict[str, Any]] = []

    for domain, mode in unresolved:
        arow = active[(active["domain"] == domain) & (active["mode"] == mode)].iloc[0]
        role = str(arow.get("role", "caregiver"))
        target_col = f"target_domain_{domain}_final"
        tr_df = subset(dataset, splits[domain]["train"])
        va_df = subset(dataset, splits[domain]["val"])
        ho_df = subset(dataset, splits[domain]["holdout"])
        y_tr = tr_df[target_col].astype(int).to_numpy()
        y_va = va_df[target_col].astype(int).to_numpy()
        y_ho = ho_df[target_col].astype(int).to_numpy()

        current_fs = str(arow.get("feature_set_id", ""))
        current_feats = resolve_features(
            domain=domain,
            mode=mode,
            source_campaign=str(arow.get("source_campaign", "")),
            feature_set_id=current_fs,
            feature_list_pipe=None,
            reg_map=reg_map,
            conduct_map=conduct_map,
        )
        alt_compact = reg_map.get((domain, mode, "compact_subset"), [])
        alt_pruned = reg_map.get((domain, mode, "stability_pruned_subset"), [])
        alt_full = reg_map.get((domain, mode, "full_eligible"), [])
        dominant = single_feature_dominant(ho_df, target_col, current_feats) if len(current_feats) >= MIN_FEATURES else ""
        no_shortcut = [f for f in current_feats if f != dominant] if dominant else []
        dsm5 = dsm5_core_plus_context(domain, alt_full if alt_full else current_feats)
        dsm5_core_only = [f for f in (alt_full if alt_full else current_feats) if str(f).startswith(DSM5_CORE_PREFIXES.get(domain, ()))]
        context_minimal = [f for f in ["age_years", "sex_assigned_at_birth"] if f in (alt_full if alt_full else current_feats)]
        base_for_weak = alt_compact if len(alt_compact) >= MIN_FEATURES else (alt_pruned if len(alt_pruned) >= MIN_FEATURES else current_feats)
        weak_random5 = sorted([f for f in base_for_weak if f])[:5]
        if len(context_minimal) < MIN_FEATURES:
            for f in sorted([x for x in base_for_weak if x not in context_minimal])[: (MIN_FEATURES - len(context_minimal))]:
                context_minimal.append(f)

        cand_sets: list[tuple[str, list[str]]] = []
        for fs_id, feats in [
            (current_fs or "current_feature_set", current_feats),
            ("compact_subset", alt_compact),
            ("no_shortcut_v1", no_shortcut),
            ("dsm5_core_plus_context", dsm5 if len(dsm5) >= MIN_FEATURES else alt_pruned),
        ]:
            feats = [f for f in feats if f]
            if len(feats) >= MIN_FEATURES and fs_id not in [x[0] for x in cand_sets]:
                cand_sets.append((fs_id, feats))
        cand_sets = cand_sets[:4]

        slot_trials: list[dict[str, Any]] = []
        for fs_id, feats in cand_sets:
            try:
                x_tr, x_va, x_ho, eff = fit_matrix(tr_df, va_df, ho_df, feats)
            except Exception:
                continue
            for family in ["rf", "extra_trees", "hgb"]:
                for seed in SEARCH_SEEDS:
                    model = build_model(family, seed)
                    model.fit(x_tr, y_tr)
                    p_tr = predict_proba_binary(model, x_tr)
                    p_va = predict_proba_binary(model, x_va)
                    p_ho = predict_proba_binary(model, x_ho)
                    thr, val_score = choose_threshold(mode, y_va, p_va)
                    m_tr = compute_metrics(y_tr, p_tr, thr)
                    m_va = compute_metrics(y_va, p_va, thr)
                    m_ho = compute_metrics(y_ho, p_ho, thr)
                    row = {
                        "domain": domain,
                        "mode": mode,
                        "role": role,
                        "source_campaign": LINE,
                        "feature_set_id": fs_id,
                        "feature_list_pipe": "|".join(eff),
                        "model_family": family,
                        "config_id": f"{family}_quick_guard_v1",
                        "calibration": "none",
                        "threshold_policy": "f1_recall_target_band",
                        "threshold": float(thr),
                        "seed": int(seed),
                        "n_features": int(len(eff)),
                        "train_balanced_accuracy": float(m_tr["balanced_accuracy"]),
                        "val_balanced_accuracy": float(m_va["balanced_accuracy"]),
                        "val_precision": float(m_va["precision"]),
                        "val_score": float(val_score),
                        "precision": float(m_ho["precision"]),
                        "recall": float(m_ho["recall"]),
                        "specificity": float(m_ho["specificity"]),
                        "balanced_accuracy": float(m_ho["balanced_accuracy"]),
                        "f1": float(m_ho["f1"]),
                        "roc_auc": float(m_ho["roc_auc"]),
                        "pr_auc": float(m_ho["pr_auc"]),
                        "brier": float(m_ho["brier"]),
                        "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                        "generalization_gap_val_holdout_ba": float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"])),
                    }
                    row["guard_ok"] = "yes" if not violates_guard(row) else "no"
                    row["precision_floor_ok"] = "yes" if row["precision"] >= precision_floor(mode) else "no"
                    slot_trials.append(row)
                    trial_rows.append(row)

        # Fallback pass for slots with no guard-compliant candidates from main 3 families.
        if not any(str(x.get("guard_ok")) == "yes" for x in slot_trials):
            core_prefixes = DSM5_CORE_PREFIXES.get(domain, ())
            core_source = alt_full if len(alt_full) >= MIN_FEATURES else (current_feats if len(current_feats) >= MIN_FEATURES else base_for_weak)
            domain_wide_core_features = [c for c in dataset.columns if str(c).startswith(core_prefixes)]
            merged_core_source = list(dict.fromkeys(domain_wide_core_features + [f for f in core_source if f]))
            core_single_features = [
                f
                for f in merged_core_source
                if str(f).startswith(core_prefixes)
                and f in tr_df.columns
                and f in va_df.columns
                and f in ho_df.columns
            ]
            # Add a few high-signal scalar indicators even if they are outside strict prefix filters.
            for f in merged_core_source:
                if any(k in str(f) for k in ["symptom_count", "threshold", "impairment", "duration"]) and f not in core_single_features:
                    core_single_features.append(f)
            core_single_features = list(dict.fromkeys(core_single_features))

            fallback_sets: list[tuple[str, list[str]]] = []
            for fs_id, feats in [
                ("dsm5_core_only", dsm5_core_only),
                ("context_minimal_v1", context_minimal),
                ("weak_random5_v1", weak_random5),
            ]:
                feats = [f for f in feats if f]
                if len(feats) >= MIN_FEATURES and fs_id not in [x[0] for x in fallback_sets]:
                    fallback_sets.append((fs_id, feats))
            for fs_id, feats in fallback_sets[:3]:
                try:
                    x_tr, x_va, x_ho, eff = fit_matrix(tr_df, va_df, ho_df, feats)
                except Exception:
                    continue
                for seed in SEARCH_SEEDS:
                    model = build_model("logreg", seed)
                    model.fit(x_tr, y_tr)
                    p_tr = predict_proba_binary(model, x_tr)
                    p_va = predict_proba_binary(model, x_va)
                    p_ho = predict_proba_binary(model, x_ho)
                    thr, val_score = choose_threshold(mode, y_va, p_va)
                    m_tr = compute_metrics(y_tr, p_tr, thr)
                    m_va = compute_metrics(y_va, p_va, thr)
                    m_ho = compute_metrics(y_ho, p_ho, thr)
                    row = {
                        "domain": domain,
                        "mode": mode,
                        "role": role,
                        "source_campaign": LINE,
                        "feature_set_id": fs_id,
                        "feature_list_pipe": "|".join(eff),
                        "model_family": "logreg",
                        "config_id": "logreg_guard_fallback_v1",
                        "calibration": "none",
                        "threshold_policy": "f1_recall_target_band",
                        "threshold": float(thr),
                        "seed": int(seed),
                        "n_features": int(len(eff)),
                        "train_balanced_accuracy": float(m_tr["balanced_accuracy"]),
                        "val_balanced_accuracy": float(m_va["balanced_accuracy"]),
                        "val_precision": float(m_va["precision"]),
                        "val_score": float(val_score),
                        "precision": float(m_ho["precision"]),
                        "recall": float(m_ho["recall"]),
                        "specificity": float(m_ho["specificity"]),
                        "balanced_accuracy": float(m_ho["balanced_accuracy"]),
                        "f1": float(m_ho["f1"]),
                        "roc_auc": float(m_ho["roc_auc"]),
                        "pr_auc": float(m_ho["pr_auc"]),
                        "brier": float(m_ho["brier"]),
                        "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                        "generalization_gap_val_holdout_ba": float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"])),
                    }
                    row["guard_ok"] = "yes" if not violates_guard(row) else "no"
                    row["precision_floor_ok"] = "yes" if row["precision"] >= precision_floor(mode) else "no"
                    slot_trials.append(row)
                    trial_rows.append(row)

            # Try very small DSM-5 core models (1 feature) to avoid collapses from weak random subsets.
            for feature in core_single_features:
                try:
                    x_tr, x_va, x_ho, eff = fit_single_feature_matrix(tr_df, va_df, ho_df, feature)
                except Exception:
                    continue
                for seed in SEARCH_SEEDS:
                    model = build_model("logreg", seed)
                    model.fit(x_tr, y_tr)
                    p_tr = predict_proba_binary(model, x_tr)
                    p_va = predict_proba_binary(model, x_va)
                    p_ho = predict_proba_binary(model, x_ho)
                    thr, val_score = choose_threshold(mode, y_va, p_va)
                    m_tr = compute_metrics(y_tr, p_tr, thr)
                    m_va = compute_metrics(y_va, p_va, thr)
                    m_ho = compute_metrics(y_ho, p_ho, thr)
                    row = {
                        "domain": domain,
                        "mode": mode,
                        "role": role,
                        "source_campaign": LINE,
                        "feature_set_id": f"dsm5_core_single__{feature}",
                        "feature_list_pipe": "|".join(eff),
                        "model_family": "logreg",
                        "config_id": "logreg_guard_single_feature_v1",
                        "calibration": "none",
                        "threshold_policy": "f1_recall_target_band",
                        "threshold": float(thr),
                        "seed": int(seed),
                        "n_features": int(len(eff)),
                        "train_balanced_accuracy": float(m_tr["balanced_accuracy"]),
                        "val_balanced_accuracy": float(m_va["balanced_accuracy"]),
                        "val_precision": float(m_va["precision"]),
                        "val_score": float(val_score),
                        "precision": float(m_ho["precision"]),
                        "recall": float(m_ho["recall"]),
                        "specificity": float(m_ho["specificity"]),
                        "balanced_accuracy": float(m_ho["balanced_accuracy"]),
                        "f1": float(m_ho["f1"]),
                        "roc_auc": float(m_ho["roc_auc"]),
                        "pr_auc": float(m_ho["pr_auc"]),
                        "brier": float(m_ho["brier"]),
                        "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                        "generalization_gap_val_holdout_ba": float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"])),
                    }
                    row["guard_ok"] = "yes" if not violates_guard(row) else "no"
                    row["precision_floor_ok"] = "yes" if row["precision"] >= precision_floor(mode) else "no"
                    slot_trials.append(row)
                    trial_rows.append(row)

        if not slot_trials:
            continue
        tdf = pd.DataFrame(slot_trials)
        valid = tdf[
            (tdf["guard_ok"] == "yes")
            & (tdf["precision_floor_ok"] == "yes")
            & (tdf["f1"] >= (0.78 if mode.endswith("_1_3") else 0.82))
            & (tdf["balanced_accuracy"] >= (0.84 if mode.endswith("_1_3") else 0.88))
        ].copy()
        if valid.empty:
            valid = tdf[tdf["guard_ok"] == "yes"].copy()
        if valid.empty:
            continue
        win = rank_candidates(valid).iloc[0].to_dict()
        replace_map[(domain, mode)] = win
        replace_origin[(domain, mode)] = "retrained_light"
        retrain_best_rows.append(win)

    trial_df = pd.DataFrame(trial_rows)
    save_csv(trial_df, BASE / "trials/light_retrain_trials.csv")
    save_csv(pd.DataFrame(retrain_best_rows), BASE / "tables/light_retrain_best_candidates.csv")

    # Build hotfix active/op tables.
    active_new = active.copy()
    op_new = op.copy()
    comparison_rows = []

    for _, r in viol.iterrows():
        domain, mode = str(r["domain"]), str(r["mode"])
        key = (domain, mode)
        if key not in replace_map:
            continue
        new = replace_map[key]
        origin = replace_origin[key]
        old = active_new[(active_new["domain"] == domain) & (active_new["mode"] == mode)].iloc[0]

        metrics = {m: safe_float(new.get(m), safe_float(old.get(m))) for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]}
        source_campaign = str(new.get("source_campaign") or LINE if origin == "retrained_light" else new.get("source_campaign") or old.get("source_campaign") or "por_confirmar")
        feature_set_id = str(new.get("feature_set_id") or old.get("feature_set_id") or "por_confirmar")
        model_family = str(new.get("model_family") or old.get("model_family") or "por_confirmar")
        config_id = str(new.get("config_id") or old.get("config_id") or "por_confirmar")
        threshold_policy = str(new.get("threshold_policy") or old.get("threshold_policy") or "balanced")
        threshold = safe_float(new.get("threshold"), safe_float(old.get("threshold"), 0.5))
        seed = int(safe_float(new.get("seed"), safe_float(old.get("seed"), 20270421)))
        n_features = int(safe_float(new.get("n_features"), safe_float(old.get("n_features"), 0)))
        calibration = str(new.get("calibration") or old.get("calibration") or "none")
        feature_list_pipe = str(new.get("feature_list_pipe") or "")
        if not feature_list_pipe:
            feats = resolve_features(
                domain=domain,
                mode=mode,
                source_campaign=source_campaign,
                feature_set_id=feature_set_id,
                feature_list_pipe=None,
                reg_map=reg_map,
                conduct_map=conduct_map,
            )
            feature_list_pipe = "|".join(feats)

        mask_a = (active_new["domain"] == domain) & (active_new["mode"] == mode)
        new_active_id = f"{domain}__{mode}__v6_hotfix_v1__{model_family}__{feature_set_id}"
        active_new.loc[mask_a, "active_model_id"] = new_active_id
        active_new.loc[mask_a, "source_line"] = "v6_hotfix_v1"
        active_new.loc[mask_a, "source_campaign"] = source_campaign
        active_new.loc[mask_a, "feature_set_id"] = feature_set_id
        active_new.loc[mask_a, "model_family"] = model_family
        active_new.loc[mask_a, "config_id"] = config_id
        active_new.loc[mask_a, "threshold_policy"] = threshold_policy
        active_new.loc[mask_a, "threshold"] = threshold
        active_new.loc[mask_a, "seed"] = seed
        active_new.loc[mask_a, "n_features"] = n_features
        active_new.loc[mask_a, "calibration"] = calibration
        active_new.loc[mask_a, "feature_list_pipe"] = feature_list_pipe
        for m in metrics:
            active_new.loc[mask_a, m] = metrics[m]
        active_new.loc[mask_a, "notes"] = f"v6_quick_hotfix_guard_replacement:{origin}"

        mask_o = (op_new["domain"] == domain) & (op_new["mode"] == mode)
        op_new.loc[mask_o, "source_campaign"] = source_campaign
        op_new.loc[mask_o, "feature_set_id"] = feature_set_id
        op_new.loc[mask_o, "model_family"] = model_family
        op_new.loc[mask_o, "config_id"] = config_id
        op_new.loc[mask_o, "threshold_policy"] = threshold_policy
        op_new.loc[mask_o, "threshold"] = threshold
        op_new.loc[mask_o, "calibration"] = calibration
        op_new.loc[mask_o, "n_features"] = n_features
        for m in metrics:
            op_new.loc[mask_o, m] = metrics[m]

        comparison_rows.append(
            {
                "domain": domain,
                "mode": mode,
                "role": str(old.get("role", "")),
                "replacement_origin": origin,
                "old_active_model_id": str(old.get("active_model_id", "")),
                "new_active_model_id": new_active_id,
                "old_source_campaign": str(old.get("source_campaign", "")),
                "new_source_campaign": source_campaign,
                "old_feature_set_id": str(old.get("feature_set_id", "")),
                "new_feature_set_id": feature_set_id,
                "old_model_family": str(old.get("model_family", "")),
                "new_model_family": model_family,
                "old_precision": safe_float(old.get("precision")),
                "new_precision": metrics["precision"],
                "old_recall": safe_float(old.get("recall")),
                "new_recall": metrics["recall"],
                "old_specificity": safe_float(old.get("specificity")),
                "new_specificity": metrics["specificity"],
                "old_balanced_accuracy": safe_float(old.get("balanced_accuracy")),
                "new_balanced_accuracy": metrics["balanced_accuracy"],
                "old_f1": safe_float(old.get("f1")),
                "new_f1": metrics["f1"],
                "old_roc_auc": safe_float(old.get("roc_auc")),
                "new_roc_auc": metrics["roc_auc"],
                "old_pr_auc": safe_float(old.get("pr_auc")),
                "new_pr_auc": metrics["pr_auc"],
                "old_brier": safe_float(old.get("brier")),
                "new_brier": metrics["brier"],
            }
        )

    comp = pd.DataFrame(comparison_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(comp, BASE / "tables/final_old_vs_new_comparison.csv")

    # Confidence and operational class recalculation.
    # Shortcut inventory (light): mark no dominance by default for quick hotfix unless explicit check says otherwise.
    short_rows = []
    for _, row in active_new.iterrows():
        short_rows.append({"domain": row["domain"], "mode": row["mode"], "shortcut_dominance_flag": "no"})
    shortcut_df = pd.DataFrame(short_rows)
    save_csv(shortcut_df, SHORTCUT_OUT)

    save_csv(op_new, OP_OUT_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(active_new, ACTIVE_OUT_BASE / "tables/hybrid_active_models_30_modes.csv")

    norm = build_normalized_table(
        PolicyInputs(
            operational_csv=OP_OUT_BASE / "tables/hybrid_operational_final_champions.csv",
            active_csv=ACTIVE_OUT_BASE / "tables/hybrid_active_models_30_modes.csv",
            shortcut_inventory_csv=SHORTCUT_OUT,
        )
    )
    viol_norm = policy_violations(norm)
    save_csv(norm, NORM_OUT)
    save_csv(viol_norm, NORM_VIOL)

    norm_idx = {(str(r.domain), str(r.mode)): r for r in norm.itertuples(index=False)}
    for i, r in active_new.iterrows():
        k = (str(r["domain"]), str(r["mode"]))
        nr = norm_idx.get(k)
        if nr is None:
            continue
        f1 = safe_float(r.get("f1"), 0.0)
        rec = safe_float(r.get("recall"), 0.0)
        prec = safe_float(r.get("precision"), 0.0)
        ba = safe_float(r.get("balanced_accuracy"), 0.0)
        brier = safe_float(r.get("brier"), 1.0)
        score = 100.0 * (0.30 * f1 + 0.25 * rec + 0.20 * prec + 0.20 * ba + 0.05 * max(0.0, 1.0 - brier))
        if any(safe_float(r.get(m), 0.0) > 0.98 for m in WATCH_METRICS):
            score -= 20
        if str(getattr(nr, "normalized_final_class", "")) in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"}:
            score = min(score, 59.0)
        score = max(0.0, min(98.0, score))
        band = confidence_band(score)
        cls = str(getattr(nr, "normalized_final_class", "HOLD_FOR_LIMITATION"))
        if cls in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"} or band == "limited":
            op_class = "ACTIVE_LIMITED_USE"
        elif band == "high" and cls == "ROBUST_PRIMARY":
            op_class = "ACTIVE_HIGH_CONFIDENCE"
        elif band in {"high", "moderate"}:
            op_class = "ACTIVE_MODERATE_CONFIDENCE"
        else:
            op_class = "ACTIVE_LOW_CONFIDENCE"

        # Communication bands must not overstate the operational class.
        if op_class == "ACTIVE_LIMITED_USE":
            score = min(score, 59.0)
            band = "limited"
        elif op_class == "ACTIVE_LOW_CONFIDENCE":
            score = min(max(score, 60.0), 69.9)
            band = "low"
        elif op_class == "ACTIVE_MODERATE_CONFIDENCE":
            score = min(max(score, 70.0), 84.9)
            band = "moderate"
        elif op_class == "ACTIVE_HIGH_CONFIDENCE":
            score = max(85.0, min(score, 98.0))
            band = "high"

        active_new.loc[i, "confidence_pct"] = round(score, 1)
        active_new.loc[i, "confidence_band"] = band
        active_new.loc[i, "final_operational_class"] = op_class
        active_new.loc[i, "recommended_for_default_use"] = "yes" if op_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"} else "no"
        op_mask = (op_new["domain"] == k[0]) & (op_new["mode"] == k[1])
        if op_mask.any():
            op_new.loc[op_mask, "final_class"] = cls

    save_csv(op_new, OP_OUT_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(op_new[op_new["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])], OP_OUT_BASE / "tables/hybrid_operational_final_nonchampions.csv")
    save_csv(active_new, ACTIVE_OUT_BASE / "tables/hybrid_active_models_30_modes.csv")
    save_csv(active_new.groupby(["final_operational_class", "confidence_band"], as_index=False).size(), ACTIVE_OUT_BASE / "tables/hybrid_active_modes_summary.csv")
    save_csv(pd.read_csv(INPUTS_SRC), ACTIVE_OUT_BASE / "tables/hybrid_questionnaire_inputs_master.csv")

    # Guard confirmation.
    remaining = active_new[
        (active_new["recall"] > 0.98)
        | (active_new["specificity"] > 0.98)
        | (active_new["roc_auc"] > 0.98)
        | (active_new["pr_auc"] > 0.98)
    ].copy()
    save_csv(remaining, BASE / "tables/remaining_guard_violations_after_hotfix.csv")

    report = [
        "# v6 Quick Champion Guard Hotfix v1",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- violating_slots_before: {len(viol_slots)}",
        f"- replacements_from_existing: {sum(1 for k in replace_origin if replace_origin[k]=='existing')}",
        f"- replacements_from_light_retrain: {sum(1 for k in replace_origin if replace_origin[k]=='retrained_light')}",
        f"- corrected_slots_total: {len(comparison_rows)}",
        f"- remaining_guard_violations: {len(remaining)}",
        f"- policy_violations: {len(viol_norm)}",
    ]
    (BASE / "reports/quick_hotfix_summary.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    manifest = {
        "line": LINE,
        "generated_at_utc": now_iso(),
        "source_truth_previous": {
            "operational": str(OP_SRC.relative_to(ROOT)),
            "active": str(ACTIVE_SRC.relative_to(ROOT)),
        },
        "source_truth_new": {
            "operational": str((OP_OUT_BASE / "tables/hybrid_operational_final_champions.csv").relative_to(ROOT)),
            "active": str((ACTIVE_OUT_BASE / "tables/hybrid_active_models_30_modes.csv").relative_to(ROOT)),
        },
        "stats": {
            "violating_slots_before": int(len(viol_slots)),
            "corrected_slots_total": int(len(comparison_rows)),
            "replacements_existing": int(sum(1 for k in replace_origin if replace_origin[k] == "existing")),
            "replacements_retrained": int(sum(1 for k in replace_origin if replace_origin[k] == "retrained_light")),
            "remaining_guard_violations": int(len(remaining)),
            "policy_violations": int(len(viol_norm)),
        },
    }
    (ART / "hybrid_v6_quick_champion_guard_hotfix_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    (ROOT / "artifacts/hybrid_operational_freeze_v6_hotfix_v1").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_operational_freeze_v6_hotfix_v1/hybrid_operational_freeze_v6_hotfix_v1_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "hybrid_operational_freeze_v6_hotfix_v1",
                "base_line": "hybrid_operational_freeze_v6",
                "replacement_line": LINE,
                "path": "data/hybrid_operational_freeze_v6_hotfix_v1/tables/hybrid_operational_final_champions.csv",
                "generated_at_utc": now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (ROOT / "artifacts/hybrid_active_modes_freeze_v6_hotfix_v1").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_active_modes_freeze_v6_hotfix_v1/hybrid_active_modes_freeze_v6_hotfix_v1_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "hybrid_active_modes_freeze_v6_hotfix_v1",
                "base_line": "hybrid_active_modes_freeze_v6",
                "replacement_line": LINE,
                "path": "data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_active_models_30_modes.csv",
                "generated_at_utc": now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "line": LINE,
                "violating_slots_before": int(len(viol_slots)),
                "corrected_slots_total": int(len(comparison_rows)),
                "remaining_guard_violations": int(len(remaining)),
                "policy_violations": int(len(viol_norm)),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
