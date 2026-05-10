#!/usr/bin/env python
from __future__ import annotations

import json
import math
import re
import sys
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations


LINE = "hybrid_structural_mode_rescue_v1"
FREEZE_LABEL = "v8"
SOURCE_LINE = "v8_structural_mode_rescue_v1"

BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE

ACTIVE_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6_hotfix_v1" / "tables" / "hybrid_active_models_30_modes.csv"
ACTIVE_SUMMARY_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6_hotfix_v1" / "tables" / "hybrid_active_modes_summary.csv"
OP_SRC = ROOT / "data" / "hybrid_operational_freeze_v6_hotfix_v1" / "tables" / "hybrid_operational_final_champions.csv"
INPUTS_SRC = ROOT / "data" / "hybrid_active_modes_freeze_v6_hotfix_v1" / "tables" / "hybrid_questionnaire_inputs_master.csv"
DATASET = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2" / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
FE_REG = (
    ROOT
    / "data"
    / "hybrid_no_external_scores_rebuild_v2"
    / "feature_engineering"
    / "hybrid_no_external_scores_feature_engineering_registry.csv"
)

ACTIVE_OUT_BASE = ROOT / "data" / f"hybrid_active_modes_freeze_{FREEZE_LABEL}"
OP_OUT_BASE = ROOT / "data" / f"hybrid_operational_freeze_{FREEZE_LABEL}"
NORM_BASE = ROOT / "data" / "hybrid_classification_normalization_v2"
NORM_OUT = NORM_BASE / "tables" / f"hybrid_operational_classification_normalized_{FREEZE_LABEL}.csv"
NORM_VIOL = NORM_BASE / "validation" / f"hybrid_classification_policy_violations_{FREEZE_LABEL}.csv"
SHORTCUT_OUT = BASE / "tables" / "shortcut_inventory_structural_mode_rescue_v1.csv"

WATCH_METRICS = ("recall", "specificity", "roc_auc", "pr_auc")
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
MODES = [
    "caregiver_1_3",
    "caregiver_2_3",
    "caregiver_full",
    "psychologist_1_3",
    "psychologist_2_3",
    "psychologist_full",
]
ROLES = ["caregiver", "psychologist"]
BASE_SEED = 20261101
SEARCH_SEEDS = [20270421, 20270439, 20270501]
BOOTSTRAP_ROUNDS = 80
MIN_FEATURES = 8

BLACKLIST_MODEL_IDS = {
    "adhd__caregiver_1_3__rebuild_v2__rf__engineered_full",
    "adhd__caregiver_2_3__rebuild_v2__rf__engineered_compact",
    "adhd__psychologist_1_3__rebuild_v2__rf__engineered_compact",
    "adhd__psychologist_2_3__rebuild_v2__rf__engineered_pruned",
    "anxiety__psychologist_1_3__v6_hotfix_v1__hgb__engineered_full",
    "conduct__caregiver_2_3__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1",
    "depression__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset",
    "depression__caregiver_2_3__hybrid_final_decisive_rescue_v5__rf__precision_oriented_subset",
    "depression__psychologist_1_3__rebuild_v2__rf__stability_pruned_subset",
    "depression__psychologist_2_3__final_honest_improvement_v1__rf__compact_subset",
    "elimination__caregiver_1_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
    "elimination__caregiver_2_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
    "elimination__psychologist_1_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
    "elimination__psychologist_2_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
}

STRUCTURAL_EXTRA_RESCUE_MODEL_IDS = {
    "anxiety__psychologist_full__v6_hotfix_v1__logreg__dsm5_core_single__sep_anx_symptom_count",
    "elimination__caregiver_full__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
    "elimination__psychologist_full__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive",
}

PROTECTED_NO_TOUCH_IDS = {
    "anxiety__caregiver_1_3__rebuild_v2__rf__engineered_full",
    "anxiety__caregiver_2_3__v6_hotfix_v1__logreg__engineered_pruned_no_eng_v1",
    "anxiety__psychologist_2_3__v6_hotfix_v1__logreg__engineered_pruned_no_eng_v1",
    "conduct__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset",
    "conduct__psychologist_1_3__rebuild_v2__rf__compact_subset",
    "conduct__psychologist_2_3__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1",
}

DSM5_CORE_PREFIXES = {
    "adhd": ("adhd_",),
    "conduct": ("conduct_",),
    "anxiety": ("agor_", "gad_", "sep_anx_", "social_anxiety_"),
    "depression": ("mdd_", "pdd_", "dmdd_"),
    "elimination": ("enuresis_", "encopresis_"),
}
GLOBAL_CONTEXT_FEATURES = {"age_years", "sex_assigned_at_birth"}
CORE_FEATURE_TYPES = {
    "symptom_item",
    "impairment_item",
    "duration_item",
    "duration_months",
    "frequency_item",
    "context_flag",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [
        BASE / "tables",
        BASE / "reports",
        BASE / "trials",
        BASE / "validation",
        BASE / "bootstrap",
        BASE / "stability",
        BASE / "stress",
        BASE / "subsets",
        ART,
        ACTIVE_OUT_BASE / "tables",
        ACTIVE_OUT_BASE / "reports",
        OP_OUT_BASE / "tables",
        OP_OUT_BASE / "reports",
        NORM_BASE / "tables",
        NORM_BASE / "validation",
        ROOT / "artifacts" / f"hybrid_active_modes_freeze_{FREEZE_LABEL}",
        ROOT / "artifacts" / f"hybrid_operational_freeze_{FREEZE_LABEL}",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def safe_float(value: Any, default: float = np.nan) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def yes_no(value: Any) -> bool:
    return str(value or "").strip().lower() in {"yes", "si", "s", "true", "1", "y"}


def slug_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()


def md_table(df: pd.DataFrame, max_rows: int = 80) -> str:
    if df.empty:
        return "_sin datos_"
    x = df.head(max_rows).copy()
    cols = [str(c) for c in x.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in x.iterrows():
        vals = []
        for c in x.columns:
            v = row[c]
            if pd.isna(v):
                vals.append("")
            elif isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("|", "\\|"))
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
    }


def violates_guard(row: pd.Series | dict[str, Any]) -> bool:
    return any(safe_float(row.get(m), 0.0) > 0.98 for m in WATCH_METRICS)


def recall_target(mode: str) -> tuple[float, float]:
    if mode.endswith("_1_3"):
        return 0.88, 0.95
    return 0.92, 0.98


def mode_ratio(mode: str) -> float:
    if mode.endswith("_1_3"):
        return 1.0 / 3.0
    if mode.endswith("_2_3"):
        return 2.0 / 3.0
    return 1.0


def target_feature_count(mode: str, full_n: int) -> int:
    if mode.endswith("_full"):
        return int(full_n)
    return max(MIN_FEATURES, int(round(full_n * mode_ratio(mode))))


def precision_floor(mode: str, domain: str, old_precision: float) -> float:
    base = 0.70 if mode.endswith("_1_3") else 0.75
    if domain in {"adhd", "depression"} and mode.endswith("_1_3"):
        base = 0.60
    return max(0.55, min(base, old_precision - 0.02 if old_precision >= 0.65 else old_precision - 0.04))


def choose_threshold(mode: str, domain: str, y_true: np.ndarray, probs: np.ndarray, p_floor: float) -> tuple[float, float]:
    r_lo, r_hi = recall_target(mode)
    best_thr, best_score = 0.5, -1e9
    for thr in np.linspace(0.08, 0.92, 85):
        m = compute_metrics(y_true, probs, float(thr))
        score = (
            0.46 * m["f1"]
            + 0.24 * m["recall"]
            + 0.14 * m["precision"]
            + 0.11 * m["balanced_accuracy"]
            + 0.05 * max(0.0, 1.0 - m["brier"])
        )
        if r_lo <= m["recall"] <= r_hi:
            score += 0.035
        if m["recall"] > 0.98:
            score -= 0.35
        if m["specificity"] > 0.98:
            score -= 0.20
        if m["precision"] < p_floor:
            score -= 0.18 + (p_floor - m["precision"])
        if domain in {"depression", "adhd"} and m["recall"] < r_lo:
            score -= 0.05
        if score > best_score:
            best_score = float(score)
            best_thr = float(thr)
    return best_thr, best_score


def split_by_domain(df: pd.DataFrame) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    out: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []
    for d in DOMAINS:
        target = f"target_domain_{d}_final"
        sub = df[["participant_id", target]].dropna().copy()
        ids = sub["participant_id"].astype(str).to_numpy()
        y = sub[target].astype(int).to_numpy()
        seed = BASE_SEED + DOMAINS.index(d)
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=strat)
        strat2 = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids, _, _ = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=strat2)
        out[d] = {"train": list(tr_ids), "val": list(va_ids), "holdout": list(ho_ids)}
        for split, split_ids in out[d].items():
            rows.append({"domain": d, "split": split, "n": len(split_ids)})
    return out, pd.DataFrame(rows)


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def load_feature_registry() -> dict[tuple[str, str, str], list[str]]:
    reg = pd.read_csv(FE_REG)
    reg["features"] = reg["feature_list_pipe"].fillna("").apply(lambda s: [f for f in str(s).split("|") if f])
    return {
        (str(r.domain), str(getattr(r, "mode")), str(r.feature_set_id)): list(r.features)
        for r in reg.itertuples(index=False)
    }


def load_input_meta() -> dict[str, dict[str, Any]]:
    inp = pd.read_csv(INPUTS_SRC)
    out: dict[str, dict[str, Any]] = {}
    for row in inp.to_dict(orient="records"):
        feature = str(row.get("feature", "")).strip()
        if feature:
            out[feature] = row
    return out


def full_universe(domain: str, role: str, reg_map: dict[tuple[str, str, str], list[str]], data_cols: set[str]) -> list[str]:
    mode = f"{role}_full"
    feats = reg_map.get((domain, mode, "full_eligible"), [])
    clean = []
    for f in feats:
        if f in data_cols and f not in clean and not f.startswith("target_domain_"):
            clean.append(f)
    return clean


def fit_numeric(
    tr_df: pd.DataFrame,
    va_df: pd.DataFrame,
    ho_df: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], np.ndarray]:
    cols = [f for f in features if f in tr_df.columns and f in va_df.columns and f in ho_df.columns]
    x_tr = tr_df[cols].copy().apply(pd.to_numeric, errors="coerce")
    x_tr = x_tr.dropna(axis=1, how="all")
    eff = list(x_tr.columns)
    if len(eff) < MIN_FEATURES:
        raise ValueError("not_enough_features")
    x_va = va_df[eff].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = ho_df[eff].copy().apply(pd.to_numeric, errors="coerce")
    imp = SimpleImputer(strategy="median")
    xtr = imp.fit_transform(x_tr)
    xva = imp.transform(x_va)
    xho = imp.transform(x_ho)
    medians = np.nanmedian(xtr, axis=0)
    return xtr, xva, xho, eff, medians


def build_model(family: str, seed: int, pos_rate: float, config_id: str | None = None):
    if family == "rf":
        return RandomForestClassifier(
            n_estimators=120,
            max_depth=5,
            min_samples_split=18,
            min_samples_leaf=10,
            max_features=0.35,
            class_weight="balanced_subsample",
            bootstrap=True,
            max_samples=0.90,
            random_state=seed,
            n_jobs=-1,
        )
    if family == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=140,
            max_depth=5,
            min_samples_split=18,
            min_samples_leaf=10,
            max_features=0.35,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        )
    if family == "hgb":
        if config_id == "hgb_guard_mid_v1":
            return HistGradientBoostingClassifier(
                max_depth=1,
                learning_rate=0.018,
                max_iter=42,
                l2_regularization=2.5,
                min_samples_leaf=120,
                random_state=seed,
            )
        return HistGradientBoostingClassifier(
            max_depth=1,
            learning_rate=0.02,
            max_iter=40,
            l2_regularization=3.0,
            min_samples_leaf=120,
            random_state=seed,
        )
    if family == "logreg":
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(max_iter=5000, C=(0.01 if config_id == "logreg_guard_mid_v1" else 0.001), solver="liblinear", class_weight="balanced"),
                ),
            ]
        )
    raise ValueError(f"unsupported family {family}")


def predict_proba_binary(model: Any, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(x)[:, 1]
    elif hasattr(model, "decision_function"):
        z = model.decision_function(x)
        p = 1.0 / (1.0 + np.exp(-z))
    else:
        p = model.predict(x)
    return np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)


def sample_weight(y: np.ndarray, domain: str, mode: str) -> np.ndarray:
    pos = max(float(np.mean(y)), 1e-6)
    neg = max(1.0 - pos, 1e-6)
    ratio = min(3.0, max(1.15, neg / pos))
    if domain in {"depression", "adhd", "elimination"}:
        ratio *= 1.18
    if mode.endswith("_1_3"):
        ratio *= 1.10
    w = np.ones(len(y), dtype=float)
    w[y == 1] *= min(4.0, ratio)
    return w


def fit_with_optional_weights(model: Any, family: str, x: np.ndarray, y: np.ndarray, w: np.ndarray) -> None:
    if isinstance(model, Pipeline):
        try:
            model.fit(x, y, model__sample_weight=w)
            return
        except TypeError:
            pass
    if family in {"hgb", "logreg"}:
        try:
            model.fit(x, y, sample_weight=w)
            return
        except TypeError:
            pass
    model.fit(x, y)


def model_importances(model: Any, n: int) -> np.ndarray:
    if hasattr(model, "feature_importances_"):
        vals = np.asarray(model.feature_importances_, dtype=float)
    elif isinstance(model, Pipeline):
        lr = model.named_steps.get("model")
        vals = np.abs(np.asarray(getattr(lr, "coef_", np.zeros((1, n))))[0])
    elif hasattr(model, "coef_"):
        vals = np.abs(np.asarray(model.coef_)[0])
    else:
        vals = np.zeros(n, dtype=float)
    if vals.shape[0] != n:
        vals = np.resize(vals, n)
    total = float(np.sum(vals))
    return vals / total if total > 0 else vals


def feature_domain_score(domain: str, feature: str, meta: dict[str, Any]) -> float:
    prefixes = DSM5_CORE_PREFIXES.get(domain, ())
    if str(feature).startswith(prefixes):
        return 1.0
    if yes_no(meta.get(f"input_needed_for_{domain}")):
        return 0.70
    domains_final = str(meta.get("domains_final") or "").lower().split("|")
    if domain in domains_final:
        return 0.70
    if feature in GLOBAL_CONTEXT_FEATURES:
        return 0.45
    return 0.25


def robust_feature_ranking(
    domain: str,
    role: str,
    full_feats: list[str],
    tr_df: pd.DataFrame,
    y_tr: np.ndarray,
    meta_map: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    if len(full_feats) < MIN_FEATURES:
        raise ValueError(f"full_universe_too_small:{domain}:{role}")
    xtr, _, _, eff, _ = fit_numeric(tr_df, tr_df, tr_df, full_feats)
    importances = np.zeros(len(eff), dtype=float)
    for family, seed in [("rf", 20270421), ("extra_trees", 20270439), ("logreg", 20270501)]:
        model = build_model(family, seed, float(np.mean(y_tr)))
        w = sample_weight(y_tr, domain, f"{role}_full")
        fit_with_optional_weights(model, family, xtr, y_tr, w)
        importances += model_importances(model, len(eff))
    importances = importances / 3.0
    if importances.max() > 0:
        importances = importances / importances.max()

    max_rank = 1.0
    ranks = []
    for f in eff:
        meta = meta_map.get(f, {})
        r = safe_float(meta.get(f"{role}_rank"), np.nan)
        if pd.notna(r):
            ranks.append(r)
    if ranks:
        max_rank = max(ranks)

    rows = []
    for i, f in enumerate(eff):
        meta = meta_map.get(f, {})
        raw_rank = safe_float(meta.get(f"{role}_rank"), np.nan)
        rank_score = 0.45 if pd.isna(raw_rank) else 1.0 - ((raw_rank - 1.0) / max(max_rank - 1.0, 1.0))
        rank_score = float(np.clip(rank_score, 0.0, 1.0))
        ftype = str(meta.get("feature_type") or "").strip().lower()
        rationale = str(meta.get("selection_rationale") or "").lower()
        core_score = 1.0 if ftype in CORE_FEATURE_TYPES or "core_symptom" in rationale else 0.45
        domain_score = feature_domain_score(domain, f, meta)
        composite = 0.50 * float(importances[i]) + 0.20 * rank_score + 0.20 * domain_score + 0.10 * core_score
        rows.append(
            {
                "domain": domain,
                "role": role,
                "feature": f,
                "model_importance_score": float(importances[i]),
                "questionnaire_rank": raw_rank,
                "rank_score": rank_score,
                "domain_score": domain_score,
                "core_score": core_score,
                "composite_importance": float(composite),
                "feature_type": ftype,
                "selection_rationale": str(meta.get("selection_rationale") or ""),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["composite_importance", "domain_score", "rank_score", "feature"],
        ascending=[False, False, False, True],
    )


def unique_list(items: list[str]) -> list[str]:
    return [x for x in dict.fromkeys(items) if x]


def structured_subset(
    domain: str,
    role: str,
    mode: str,
    ranking: pd.DataFrame,
    reg_map: dict[tuple[str, str, str], list[str]],
    data_cols: set[str],
) -> dict[str, list[str]]:
    full_feats = ranking["feature"].tolist()
    full_n = len(full_feats)
    n_target = target_feature_count(mode, full_n)
    mode_label = "full" if mode.endswith("_full") else ("2_3" if mode.endswith("_2_3") else "1_3")
    out: dict[str, list[str]] = {}

    ranked = unique_list(full_feats[:n_target])
    out[f"structural_ranked_{mode_label}"] = ranked

    core_mask = ranking["feature"].astype(str).apply(lambda f: str(f).startswith(DSM5_CORE_PREFIXES.get(domain, ())))
    core = ranking[core_mask]["feature"].tolist()
    context = [
        f
        for f in ranking["feature"].tolist()
        if f in GLOBAL_CONTEXT_FEATURES or any(tok in f for tok in ["context", "impairment", "duration", "frequency"])
    ]
    dsm5 = unique_list((core + context + full_feats)[:n_target])
    if len(dsm5) >= MIN_FEATURES:
        out[f"structural_dsm5_plus_context_{mode_label}"] = dsm5

    compact_n = max(MIN_FEATURES, int(round(n_target * 0.82)))
    compact = unique_list(full_feats[:compact_n])
    if len(compact) >= MIN_FEATURES:
        out[f"structural_compact_{mode_label}"] = compact

    no_context = [f for f in full_feats if "context" not in f and f not in GLOBAL_CONTEXT_FEATURES]
    pruned = unique_list(no_context[:n_target])
    if len(pruned) >= MIN_FEATURES:
        out[f"structural_pruned_{mode_label}"] = pruned

    registry_mode = mode
    for fs in ["stability_pruned_subset", "compact_subset"]:
        feats = [f for f in reg_map.get((domain, registry_mode, fs), []) if f in data_cols]
        if not feats:
            continue
        lower = max(MIN_FEATURES, int(n_target * 0.55))
        upper = int(n_target * 1.35)
        if lower <= len(feats) <= upper:
            out[f"registry_{fs}"] = unique_list(feats)
            break

    clean: dict[str, list[str]] = {}
    for fs, feats in out.items():
        eff = [f for f in unique_list(feats) if f in data_cols]
        if len(eff) >= MIN_FEATURES:
            clean[fs] = eff
        if len(clean) >= 5:
            break
    return clean


def single_feature_rule(ho_df: pd.DataFrame, target_col: str, features: list[str]) -> dict[str, Any]:
    y = ho_df[target_col].astype(int).to_numpy()
    best = {"best_single_feature": "", "best_single_rule": "", "best_single_feature_ba": np.nan}
    top = -1.0
    for f in features:
        if f not in ho_df.columns:
            continue
        x = pd.to_numeric(ho_df[f], errors="coerce")
        if x.isna().all() or x.nunique(dropna=True) < 2:
            continue
        vals = x.fillna(float(x.median())).to_numpy()
        for thr in np.unique(np.quantile(vals, np.linspace(0.05, 0.95, 19))):
            for ge in (True, False):
                pred = (vals >= thr).astype(int) if ge else (vals <= thr).astype(int)
                ba = float(balanced_accuracy_score(y, pred))
                if ba > top:
                    top = ba
                    best = {
                        "best_single_feature": f,
                        "best_single_rule": f"{f} {'>=' if ge else '<='} {thr:.6g}",
                        "best_single_feature_ba": ba,
                    }
    return best


def search_existing_fallbacks(slots: set[tuple[str, str]], active_current: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    files: list[Path] = []
    for pattern in [
        "data/hybrid_active_modes_freeze_v*/tables/hybrid_active_models_30_modes.csv",
        "data/hybrid_operational_freeze_v*/tables/hybrid_operational_final_champions.csv",
        "data/hybrid_*/*/*selected_models.csv",
        "data/hybrid_*/*/*champions.csv",
    ]:
        files.extend(ROOT.glob(pattern))

    rows: list[pd.DataFrame] = []
    for path in sorted(set(files)):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        for c in [
            "domain",
            "mode",
            "role",
            "active_model_id",
            "source_campaign",
            "model_family",
            "feature_set_id",
            "config_id",
            "calibration",
            "threshold_policy",
            "threshold",
            "seed",
            "n_features",
            "precision",
            "recall",
            "specificity",
            "balanced_accuracy",
            "f1",
            "roc_auc",
            "pr_auc",
            "brier",
            "feature_list_pipe",
        ]:
            if c not in df.columns:
                df[c] = None
        df["source_file"] = str(path.relative_to(ROOT))
        rows.append(
            df[
                [
                    "domain",
                    "mode",
                    "role",
                    "active_model_id",
                    "source_campaign",
                    "model_family",
                    "feature_set_id",
                    "config_id",
                    "calibration",
                    "threshold_policy",
                    "threshold",
                    "seed",
                    "n_features",
                    "precision",
                    "recall",
                    "specificity",
                    "balanced_accuracy",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier",
                    "feature_list_pipe",
                    "source_file",
                ]
            ]
        )
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    pool = pd.concat(rows, ignore_index=True)
    pool["slot"] = list(zip(pool["domain"].astype(str), pool["mode"].astype(str)))
    pool = pool[pool["slot"].isin(slots)].copy()
    for c in ["n_features", "precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
        pool[c] = pd.to_numeric(pool[c], errors="coerce")
    pool["guard_ok"] = ~pool.apply(violates_guard, axis=1)
    pool["blacklisted_exact_id"] = pool["active_model_id"].astype(str).isin(BLACKLIST_MODEL_IDS)
    pool["non_degenerate"] = pool["n_features"].fillna(0) >= MIN_FEATURES
    old_idx = {
        (str(r.domain), str(getattr(r, "mode"))): r
        for r in active_current[["domain", "mode", "f1", "precision", "recall"]].itertuples(index=False)
    }
    compat_rows = []
    for _, row in pool.iterrows():
        slot = (str(row["domain"]), str(row["mode"]))
        old = old_idx.get(slot)
        old_f1 = safe_float(getattr(old, "f1", np.nan)) if old is not None else np.nan
        good = (
            bool(row["guard_ok"])
            and not bool(row["blacklisted_exact_id"])
            and bool(row["non_degenerate"])
            and safe_float(row["f1"], 0.0) >= max(0.78, old_f1 - 0.02 if pd.notna(old_f1) else 0.78)
            and safe_float(row["precision"], 0.0) >= 0.70
        )
        reason = []
        if not bool(row["guard_ok"]):
            reason.append("guard_violation")
        if bool(row["blacklisted_exact_id"]):
            reason.append("blacklisted_exact_id")
        if not bool(row["non_degenerate"]):
            reason.append("degenerate_or_too_few_features")
        if not good and not reason:
            reason.append("not_materially_better_or_precision_below_floor")
        compat_rows.append({"fallback_accepted_candidate": "yes" if good else "no", "fallback_rejection_reason": "|".join(reason) if reason else "none"})
    pool = pd.concat([pool.reset_index(drop=True), pd.DataFrame(compat_rows)], axis=1)
    accepted = pool[pool["fallback_accepted_candidate"] == "yes"].sort_values(
        ["domain", "mode", "f1", "recall", "precision", "balanced_accuracy", "brier"],
        ascending=[True, True, False, False, False, False, True],
    )
    return pool.drop(columns=["slot"]), accepted.groupby(["domain", "mode"], as_index=False).head(1)


def train_slot(
    domain: str,
    mode: str,
    role: str,
    old_row: pd.Series,
    tr_df: pd.DataFrame,
    va_df: pd.DataFrame,
    ho_df: pd.DataFrame,
    target_col: str,
    cand_sets: dict[str, list[str]],
) -> tuple[pd.DataFrame, pd.Series | None]:
    rows: list[dict[str, Any]] = []
    y_tr = tr_df[target_col].astype(int).to_numpy()
    y_va = va_df[target_col].astype(int).to_numpy()
    y_ho = ho_df[target_col].astype(int).to_numpy()
    old_precision = safe_float(old_row.get("precision"), 0.0)
    p_floor = precision_floor(mode, domain, old_precision)
    family_plan = [
        ("rf", "rf_structural_regularized_v1"),
        ("extra_trees", "extra_trees_structural_regularized_v1"),
        ("hgb", "hgb_ultra_conservative_v1"),
        ("hgb", "hgb_guard_mid_v1"),
        ("logreg", "logreg_guard_strong_v1"),
        ("logreg", "logreg_guard_mid_v1"),
    ]

    for fs_id, feats in list(cand_sets.items())[:5]:
        try:
            x_tr, x_va, x_ho, eff, _ = fit_numeric(tr_df, va_df, ho_df, feats)
        except Exception:
            continue
        w = sample_weight(y_tr, domain, mode)
        for family, model_config_id in family_plan:
            for seed in SEARCH_SEEDS:
                try:
                    model = build_model(family, seed, float(np.mean(y_tr)), model_config_id)
                    fit_with_optional_weights(model, family, x_tr, y_tr, w)
                    p_tr = predict_proba_binary(model, x_tr)
                    p_va = predict_proba_binary(model, x_va)
                    p_ho = predict_proba_binary(model, x_ho)
                except Exception:
                    continue
                thr, val_score = choose_threshold(mode, domain, y_va, p_va, p_floor)
                mt = compute_metrics(y_tr, p_tr, thr)
                mv = compute_metrics(y_va, p_va, thr)
                mh = compute_metrics(y_ho, p_ho, thr)
                overfit = float(mt["balanced_accuracy"] - mv["balanced_accuracy"])
                gen_gap = float(abs(mv["balanced_accuracy"] - mh["balanced_accuracy"]))
                row = {
                    "domain": domain,
                    "mode": mode,
                    "role": role,
                    "source_campaign": LINE,
                    "feature_set_id": fs_id,
                    "feature_list_pipe": "|".join(eff),
                    "model_family": family,
                    "config_id": model_config_id,
                    "calibration": "none",
                    "threshold_policy": "f1_recall_structural_target_band",
                    "threshold": float(thr),
                    "seed": int(seed),
                    "n_features": int(len(eff)),
                    "train_balanced_accuracy": float(mt["balanced_accuracy"]),
                    "val_balanced_accuracy": float(mv["balanced_accuracy"]),
                    "val_precision": float(mv["precision"]),
                    "val_recall": float(mv["recall"]),
                    "val_f1": float(mv["f1"]),
                    "val_score": float(val_score),
                    "precision": float(mh["precision"]),
                    "recall": float(mh["recall"]),
                    "specificity": float(mh["specificity"]),
                    "balanced_accuracy": float(mh["balanced_accuracy"]),
                    "f1": float(mh["f1"]),
                    "roc_auc": float(mh["roc_auc"]),
                    "pr_auc": float(mh["pr_auc"]),
                    "brier": float(mh["brier"]),
                    "overfit_gap_train_val_ba": overfit,
                    "generalization_gap_val_holdout_ba": gen_gap,
                }
                row["guard_ok"] = "yes" if not violates_guard(row) else "no"
                row["precision_floor_ok"] = "yes" if row["precision"] >= p_floor else "no"
                row["overfit_ok"] = "yes" if overfit <= 0.12 else "no"
                row["generalization_ok"] = "yes" if gen_gap <= 0.09 else "no"
                rows.append(row)

    trials = pd.DataFrame(rows)
    if trials.empty:
        return trials, None

    old_f1 = safe_float(old_row.get("f1"), 0.0)
    old_ba = safe_float(old_row.get("balanced_accuracy"), 0.0)
    valid = trials[
        (trials["guard_ok"] == "yes")
        & (trials["f1"] >= max(0.72, old_f1 - 0.08))
        & (trials["balanced_accuracy"] >= max(0.80, old_ba - 0.06))
        & (trials["precision"] >= max(0.52, p_floor - 0.06))
    ].copy()
    if valid.empty:
        valid = trials[trials["guard_ok"] == "yes"].copy()
    if valid.empty:
        return trials, None

    r_lo, r_hi = recall_target(mode)
    valid["recall_band_bonus"] = valid["recall"].apply(lambda x: 1.0 if r_lo <= x <= r_hi else 0.0)
    valid["selection_score"] = (
        0.52 * valid["f1"]
        + 0.18 * valid["recall"]
        + 0.16 * valid["precision"]
        + 0.10 * valid["balanced_accuracy"]
        + 0.02 * valid["recall_band_bonus"]
        + 0.02 * (1.0 - valid["brier"].clip(lower=0.0, upper=1.0))
        - 0.08 * valid["overfit_gap_train_val_ba"].clip(lower=0.0)
        - 0.06 * valid["generalization_gap_val_holdout_ba"].clip(lower=0.0)
    )
    winner = valid.sort_values(
        ["selection_score", "f1", "recall_band_bonus", "recall", "precision", "balanced_accuracy", "brier"],
        ascending=[False, False, False, False, False, False, True],
    ).iloc[0]
    return trials, winner


def refit_selected(
    row: pd.Series,
    tr_df: pd.DataFrame,
    va_df: pd.DataFrame,
    ho_df: pd.DataFrame,
    target_col: str,
) -> dict[str, Any]:
    features = [f for f in str(row["feature_list_pipe"]).split("|") if f]
    x_tr, x_va, x_ho, eff, medians = fit_numeric(tr_df, va_df, ho_df, features)
    y_tr = tr_df[target_col].astype(int).to_numpy()
    y_va = va_df[target_col].astype(int).to_numpy()
    y_ho = ho_df[target_col].astype(int).to_numpy()
    family = str(row["model_family"])
    seed = int(row["seed"])
    model = build_model(family, seed, float(np.mean(y_tr)), str(row.get("config_id", "")))
    fit_with_optional_weights(model, family, x_tr, y_tr, sample_weight(y_tr, str(row["domain"]), str(row["mode"])))
    threshold = float(row["threshold"])
    p_ho = predict_proba_binary(model, x_ho)
    p_va = predict_proba_binary(model, x_va)
    return {
        "model": model,
        "features": eff,
        "medians": medians,
        "x_ho": x_ho,
        "y_ho": y_ho,
        "x_va": x_va,
        "y_va": y_va,
        "p_ho": p_ho,
        "p_va": p_va,
        "threshold": threshold,
    }


def bootstrap_metrics(row: pd.Series, y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict[str, Any]:
    rng = np.random.default_rng(int(row["seed"]) + 17)
    rows = []
    n = len(y_true)
    for i in range(BOOTSTRAP_ROUNDS):
        idx = rng.integers(0, n, size=n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        m = compute_metrics(y_true[idx], probs[idx], threshold)
        rows.append({"round": i, **{k: m[k] for k in ["f1", "recall", "precision", "balanced_accuracy", "brier"]}})
    b = pd.DataFrame(rows)
    out: dict[str, Any] = {"bootstrap_rounds_effective": int(len(b))}
    for m in ["f1", "recall", "precision", "balanced_accuracy", "brier"]:
        out[f"bootstrap_{m}_mean"] = float(b[m].mean()) if not b.empty else np.nan
        out[f"bootstrap_{m}_std"] = float(b[m].std(ddof=0)) if not b.empty else np.nan
    return out


def stress_metrics(row: pd.Series, refit: dict[str, Any]) -> dict[str, Any]:
    model = refit["model"]
    x = np.asarray(refit["x_ho"], dtype=float)
    y = refit["y_ho"]
    threshold = float(refit["threshold"])
    baseline = compute_metrics(y, refit["p_ho"], threshold)
    rng = np.random.default_rng(int(row["seed"]) + 31)
    medians = refit["medians"]

    x_noise = x.copy()
    mask = rng.random(x_noise.shape) < 0.10
    if mask.any():
        x_noise[mask] = np.take(medians, np.where(mask)[1])
    p_noise = predict_proba_binary(model, x_noise)
    noise_m = compute_metrics(y, p_noise, threshold)

    x_drop = x.copy()
    if x_drop.shape[1] > 0:
        x_drop[:, 0] = medians[0]
    p_drop = predict_proba_binary(model, x_drop)
    drop_m = compute_metrics(y, p_drop, threshold)

    return {
        "baseline_f1": baseline["f1"],
        "baseline_balanced_accuracy": baseline["balanced_accuracy"],
        "stress_missing10_f1": noise_m["f1"],
        "stress_missing10_balanced_accuracy": noise_m["balanced_accuracy"],
        "stress_missing10_ba_drop": baseline["balanced_accuracy"] - noise_m["balanced_accuracy"],
        "stress_drop_top1_f1": drop_m["f1"],
        "stress_drop_top1_balanced_accuracy": drop_m["balanced_accuracy"],
        "stress_drop_top1_ba_drop": baseline["balanced_accuracy"] - drop_m["balanced_accuracy"],
    }


def confidence_band(score: float) -> str:
    if score >= 85:
        return "high"
    if score >= 70:
        return "moderate"
    if score >= 60:
        return "low"
    return "limited"


def confidence_score(row: pd.Series, norm_class: str, audits: dict[tuple[str, str], dict[str, Any]]) -> tuple[float, str, str]:
    f1 = safe_float(row.get("f1"), 0.0)
    rec = safe_float(row.get("recall"), 0.0)
    prec = safe_float(row.get("precision"), 0.0)
    ba = safe_float(row.get("balanced_accuracy"), 0.0)
    brier = safe_float(row.get("brier"), 1.0)
    score = 100.0 * (0.32 * f1 + 0.24 * rec + 0.18 * prec + 0.19 * ba + 0.07 * max(0.0, 1.0 - brier))
    key = (str(row.get("domain")), str(row.get("mode")))
    audit = audits.get(key, {})
    if any(safe_float(row.get(m), 0.0) > 0.98 for m in WATCH_METRICS):
        score -= 30.0
    if safe_float(audit.get("overfit_gap_train_val_ba"), 0.0) > 0.12:
        score -= 7.0
    if safe_float(audit.get("generalization_gap_val_holdout_ba"), 0.0) > 0.09:
        score -= 6.0
    if safe_float(audit.get("stress_missing10_ba_drop"), 0.0) > 0.06:
        score -= 4.0
    if safe_float(audit.get("best_single_feature_ba"), 0.0) >= safe_float(row.get("balanced_accuracy"), 0.0) - 0.015:
        score -= 4.0

    if norm_class in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"}:
        score = min(score, 59.0)
    elif norm_class == "PRIMARY_WITH_CAVEAT":
        score = min(score, 84.9)
    score = max(0.0, min(98.0, score))
    band = confidence_band(score)

    if norm_class in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"} or band == "limited":
        op_class = "ACTIVE_LIMITED_USE"
        score = min(score, 59.0)
        band = "limited"
    elif band == "high" and norm_class == "ROBUST_PRIMARY":
        op_class = "ACTIVE_HIGH_CONFIDENCE"
        score = max(85.0, min(score, 98.0))
        band = "high"
    elif band in {"high", "moderate"}:
        op_class = "ACTIVE_MODERATE_CONFIDENCE"
        score = min(max(score, 70.0), 84.9)
        band = "moderate"
    else:
        op_class = "ACTIVE_LOW_CONFIDENCE"
        score = min(max(score, 60.0), 69.9)
        band = "low"
    return round(score, 1), band, op_class


def update_active_and_operational(
    active: pd.DataFrame,
    op: pd.DataFrame,
    selected: pd.DataFrame,
    audit_by_slot: dict[tuple[str, str], dict[str, Any]],
    shortcut_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    active_new = active.copy()
    op_new = op.copy()
    comparison_rows = []
    selected_idx = {(str(r.domain), str(getattr(r, "mode"))): r for r in selected.itertuples(index=False)}

    for key, new in selected_idx.items():
        domain, mode = key
        mask_a = (active_new["domain"] == domain) & (active_new["mode"] == mode)
        mask_o = (op_new["domain"] == domain) & (op_new["mode"] == mode)
        if not mask_a.any() or not mask_o.any():
            continue
        old = active_new[mask_a].iloc[0].copy()
        feature_set_id = str(getattr(new, "feature_set_id"))
        model_family = str(getattr(new, "model_family"))
        new_active_id = f"{domain}__{mode}__{LINE}__{model_family}__{slug_token(feature_set_id)}"
        metrics = {m: safe_float(getattr(new, m), safe_float(old.get(m))) for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]}

        for col, val in {
            "active_model_id": new_active_id,
            "source_line": SOURCE_LINE,
            "source_campaign": LINE,
            "model_family": model_family,
            "feature_set_id": feature_set_id,
            "config_id": str(getattr(new, "config_id")),
            "calibration": str(getattr(new, "calibration")),
            "threshold_policy": str(getattr(new, "threshold_policy")),
            "threshold": safe_float(getattr(new, "threshold")),
            "seed": safe_int(getattr(new, "seed")),
            "n_features": safe_int(getattr(new, "n_features")),
            "feature_list_pipe": str(getattr(new, "feature_list_pipe")),
            "overfit_flag": "yes" if safe_float(getattr(new, "overfit_gap_train_val_ba"), 0.0) > 0.12 else "no",
            "generalization_flag": "yes" if safe_float(getattr(new, "generalization_gap_val_holdout_ba"), 1.0) <= 0.09 else "no",
            "dataset_ease_flag": "no",
            "notes": "structural_mode_rescue_v1:blacklist_replacement;mode_subset_from_role_full_ranked_universe",
        }.items():
            active_new.loc[mask_a, col] = val
        for m, val in metrics.items():
            active_new.loc[mask_a, m] = val

        for col, val in {
            "source_campaign": LINE,
            "model_family": model_family,
            "feature_set_id": feature_set_id,
            "config_id": str(getattr(new, "config_id")),
            "calibration": str(getattr(new, "calibration")),
            "threshold_policy": str(getattr(new, "threshold_policy")),
            "threshold": safe_float(getattr(new, "threshold")),
            "n_features": safe_int(getattr(new, "n_features")),
        }.items():
            if col in op_new.columns:
                op_new.loc[mask_o, col] = val
        for m, val in metrics.items():
            if m in op_new.columns:
                op_new.loc[mask_o, m] = val

        comparison_rows.append(
            {
                "domain": domain,
                "mode": mode,
                "role": str(old.get("role", "")),
                "old_active_model_id": str(old.get("active_model_id", "")),
                "new_active_model_id": new_active_id,
                "old_feature_set_id": str(old.get("feature_set_id", "")),
                "new_feature_set_id": feature_set_id,
                "old_n_features": safe_int(old.get("n_features")),
                "new_n_features": safe_int(getattr(new, "n_features")),
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

    save_csv(op_new, OP_OUT_BASE / "tables" / "hybrid_operational_final_champions.csv")
    save_csv(active_new, ACTIVE_OUT_BASE / "tables" / "hybrid_active_models_30_modes.csv")
    norm = build_normalized_table(
        PolicyInputs(
            operational_csv=OP_OUT_BASE / "tables" / "hybrid_operational_final_champions.csv",
            active_csv=ACTIVE_OUT_BASE / "tables" / "hybrid_active_models_30_modes.csv",
            shortcut_inventory_csv=SHORTCUT_OUT if SHORTCUT_OUT.exists() else None,
        )
    )
    norm_idx = {(str(r.domain), str(getattr(r, "mode"))): str(r.normalized_final_class) for r in norm.itertuples(index=False)}

    for i, row in active_new.iterrows():
        key = (str(row["domain"]), str(row["mode"]))
        norm_class = norm_idx.get(key, "HOLD_FOR_LIMITATION")
        score, band, op_class = confidence_score(row, norm_class, audit_by_slot)
        active_new.loc[i, "confidence_pct"] = score
        active_new.loc[i, "confidence_band"] = band
        active_new.loc[i, "final_operational_class"] = op_class
        active_new.loc[i, "recommended_for_default_use"] = "yes" if op_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"} else "no"
        caveat = []
        if op_class == "ACTIVE_LIMITED_USE":
            caveat.append("limited operational confidence")
        audit = audit_by_slot.get(key, {})
        if safe_float(audit.get("overfit_gap_train_val_ba"), 0.0) > 0.12:
            caveat.append("overfit gap requires caution")
        if safe_float(audit.get("generalization_gap_val_holdout_ba"), 0.0) > 0.09:
            caveat.append("holdout generalization gap requires caution")
        if safe_float(audit.get("stress_missing10_ba_drop"), 0.0) > 0.06:
            caveat.append("stress sensitivity")
        if caveat:
            active_new.loc[i, "operational_caveat"] = "; ".join(caveat)
        elif str(active_new.loc[i, "operational_caveat"]).strip() == "":
            active_new.loc[i, "operational_caveat"] = "none"
        mask_o = (op_new["domain"] == key[0]) & (op_new["mode"] == key[1])
        if mask_o.any() and "final_class" in op_new.columns:
            op_new.loc[mask_o, "final_class"] = norm_class

    save_csv(op_new, OP_OUT_BASE / "tables" / "hybrid_operational_final_champions.csv")
    save_csv(op_new[op_new["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])], OP_OUT_BASE / "tables" / "hybrid_operational_final_nonchampions.csv")
    save_csv(active_new, ACTIVE_OUT_BASE / "tables" / "hybrid_active_models_30_modes.csv")
    save_csv(active_new.groupby(["final_operational_class", "confidence_band"], as_index=False).size(), ACTIVE_OUT_BASE / "tables" / "hybrid_active_modes_summary.csv")
    save_csv(pd.read_csv(INPUTS_SRC), ACTIVE_OUT_BASE / "tables" / "hybrid_questionnaire_inputs_master.csv")

    norm = build_normalized_table(
        PolicyInputs(
            operational_csv=OP_OUT_BASE / "tables" / "hybrid_operational_final_champions.csv",
            active_csv=ACTIVE_OUT_BASE / "tables" / "hybrid_active_models_30_modes.csv",
            shortcut_inventory_csv=SHORTCUT_OUT if SHORTCUT_OUT.exists() else None,
        )
    )
    violations = policy_violations(norm)
    save_csv(norm, NORM_OUT)
    save_csv(violations, NORM_VIOL)
    return active_new, op_new, pd.DataFrame(comparison_rows)


def main() -> int:
    ensure_dirs()
    active = pd.read_csv(ACTIVE_SRC)
    op = pd.read_csv(OP_SRC)
    data = pd.read_csv(DATASET)
    reg_map = load_feature_registry()
    meta_map = load_input_meta()
    splits, split_df = split_by_domain(data)
    save_csv(split_df, BASE / "validation" / "split_registry.csv")

    data_cols = set(data.columns)
    active["role"] = active["role"].replace({"guardian": "caregiver"}).fillna("caregiver")
    blacklist_active = active[active["active_model_id"].astype(str).isin(BLACKLIST_MODEL_IDS)].copy()
    blacklist_active = blacklist_active.sort_values(["domain", "mode"]).reset_index(drop=True)
    extra_active = active[active["active_model_id"].astype(str).isin(STRUCTURAL_EXTRA_RESCUE_MODEL_IDS)].copy()
    extra_active = extra_active.sort_values(["domain", "mode"]).reset_index(drop=True)
    target_active = pd.concat([blacklist_active, extra_active], ignore_index=True).drop_duplicates(subset=["domain", "mode"]).reset_index(drop=True)
    save_csv(blacklist_active, BASE / "tables" / "initial_blacklist_active_audit.csv")
    save_csv(extra_active, BASE / "tables" / "initial_structural_extra_active_audit.csv")

    guard_initial = active[
        (active["recall"] > 0.98)
        | (active["specificity"] > 0.98)
        | (active["roc_auc"] > 0.98)
        | (active["pr_auc"] > 0.98)
    ].copy()
    save_csv(guard_initial, BASE / "tables" / "initial_guardrail_violations.csv")
    save_csv(active, BASE / "tables" / "initial_active_snapshot.csv")

    expected_slots = {(model_id.split("__")[0], model_id.split("__")[1]) for model_id in BLACKLIST_MODEL_IDS}
    detected_slots = {(str(r.domain), str(getattr(r, "mode"))) for r in blacklist_active.itertuples(index=False)}
    if detected_slots != expected_slots:
        missing = sorted(expected_slots - detected_slots)
        extra = sorted(detected_slots - expected_slots)
        raise RuntimeError(f"blacklist_state_mismatch missing={missing} extra={extra}")

    target_slots = expected_slots | {(str(r.domain), str(getattr(r, "mode"))) for r in extra_active.itertuples(index=False)}
    fallback_pool, fallback_best = search_existing_fallbacks(target_slots, active)
    save_csv(fallback_pool, BASE / "tables" / "existing_fallback_candidates_all.csv")
    save_csv(fallback_best, BASE / "tables" / "existing_fallback_candidates_accepted_by_screen.csv")

    duplicate_audit = pd.DataFrame(
        [
            {
                "dataset_rows": int(len(data)),
                "full_vector_duplicates_anywhere": int(
                    data.drop(columns=["participant_id"], errors="ignore").astype(str).agg("|".join, axis=1).duplicated(keep=False).sum()
                ),
            }
        ]
    )
    save_csv(duplicate_audit, BASE / "validation" / "duplicate_audit_global.csv")

    class_rows = []
    for d in DOMAINS:
        y = data[f"target_domain_{d}_final"].dropna().astype(int)
        class_rows.append({"domain": d, "n": int(len(y)), "positive": int(y.sum()), "negative": int((1 - y).sum()), "positive_rate": float(y.mean())})
    save_csv(pd.DataFrame(class_rows), BASE / "validation" / "class_balance_audit.csv")

    ranking_rows = []
    subset_rows = []
    subset_feature_rows = []
    rank_cache: dict[tuple[str, str], pd.DataFrame] = {}
    subset_cache: dict[tuple[str, str, str], dict[str, list[str]]] = {}

    for domain in sorted({d for d, _ in target_slots}):
        target_col = f"target_domain_{domain}_final"
        tr_df = subset(data, splits[domain]["train"])
        y_tr = tr_df[target_col].astype(int).to_numpy()
        for role in ROLES:
            full_feats = full_universe(domain, role, reg_map, data_cols)
            ranking = robust_feature_ranking(domain, role, full_feats, tr_df, y_tr, meta_map)
            rank_cache[(domain, role)] = ranking
            ranking_rows.extend(ranking.to_dict(orient="records"))
            full_n = len(ranking)
            for suffix in ["1_3", "2_3", "full"]:
                mode = f"{role}_{suffix}"
                if (domain, mode) not in expected_slots and not mode.endswith("_full"):
                    continue
                sets = structured_subset(domain, role, mode, ranking, reg_map, data_cols)
                subset_cache[(domain, role, mode)] = sets
                for fs_id, feats in sets.items():
                    subset_rows.append(
                        {
                            "domain": domain,
                            "role": role,
                            "mode": mode,
                            "feature_set_id": fs_id,
                            "full_universe_n": full_n,
                            "target_mode_ratio": mode_ratio(mode),
                            "target_n": target_feature_count(mode, full_n),
                            "n_features": len(feats),
                            "feature_list_pipe": "|".join(feats),
                        }
                    )
                    for pos, feature in enumerate(feats, start=1):
                        subset_feature_rows.append({"domain": domain, "role": role, "mode": mode, "feature_set_id": fs_id, "position": pos, "feature": feature})
    ranking_df = pd.DataFrame(ranking_rows)
    subset_df = pd.DataFrame(subset_rows)
    save_csv(ranking_df, BASE / "subsets" / "structural_feature_rankings.csv")
    save_csv(subset_df, BASE / "subsets" / "structural_mode_subsets.csv")
    save_csv(pd.DataFrame(subset_feature_rows), BASE / "subsets" / "structural_mode_subset_features.csv")

    all_trials: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    shortcut_rows: list[dict[str, Any]] = []
    audit_by_slot: dict[tuple[str, str], dict[str, Any]] = {}

    for _, old in target_active.iterrows():
        domain = str(old["domain"])
        mode = str(old["mode"])
        role = str(old["role"])
        target_col = f"target_domain_{domain}_final"
        tr_df = subset(data, splits[domain]["train"])
        va_df = subset(data, splits[domain]["val"])
        ho_df = subset(data, splits[domain]["holdout"])
        cand_sets = subset_cache.get((domain, role, mode), {})
        trials, winner = train_slot(domain, mode, role, old, tr_df, va_df, ho_df, target_col, cand_sets)
        if not trials.empty:
            all_trials.extend(trials.to_dict(orient="records"))
        if winner is None:
            raise RuntimeError(f"no_guard_compliant_structural_candidate:{domain}:{mode}")

        selected = winner.to_dict()
        selected["old_active_model_id"] = str(old["active_model_id"])
        selected["replacement_origin"] = "retrained_structural"
        selected_rows.append(selected)

        refit = refit_selected(pd.Series(selected), tr_df, va_df, ho_df, target_col)
        boot = bootstrap_metrics(pd.Series(selected), refit["y_ho"], refit["p_ho"], float(selected["threshold"]))
        stress = stress_metrics(pd.Series(selected), refit)
        sc = single_feature_rule(ho_df, target_col, refit["features"])
        shortcut_gap = safe_float(sc["best_single_feature_ba"], np.nan) - safe_float(selected["balanced_accuracy"], np.nan)
        shortcut_flag = "yes" if pd.notna(shortcut_gap) and safe_float(sc["best_single_feature_ba"], 0.0) >= safe_float(selected["balanced_accuracy"], 0.0) - 0.015 else "no"

        boot_row = {"domain": domain, "mode": mode, **boot}
        stress_row = {"domain": domain, "mode": mode, **stress}
        bootstrap_rows.append(boot_row)
        stress_rows.append(stress_row)
        shortcut_rows.append(
            {
                "domain": domain,
                "mode": mode,
                "best_single_feature": sc["best_single_feature"],
                "best_single_rule": sc["best_single_rule"],
                "best_single_feature_ba": sc["best_single_feature_ba"],
                "model_balanced_accuracy": selected["balanced_accuracy"],
                "shortcut_gap_vs_model_ba": shortcut_gap,
                "shortcut_dominance_flag": shortcut_flag,
            }
        )
        audit_by_slot[(domain, mode)] = {
            "overfit_gap_train_val_ba": selected["overfit_gap_train_val_ba"],
            "generalization_gap_val_holdout_ba": selected["generalization_gap_val_holdout_ba"],
            **boot,
            **stress,
            "best_single_feature_ba": sc["best_single_feature_ba"],
            "shortcut_gap_vs_model_ba": shortcut_gap,
        }

    # Preserve shortcut inventory rows for unchanged active slots, so policy normalization has 30-mode coverage.
    selected_slot_set = {(r["domain"], r["mode"]) for r in selected_rows}
    for _, row in active.iterrows():
        key = (str(row["domain"]), str(row["mode"]))
        if key in selected_slot_set:
            continue
        shortcut_rows.append(
            {
                "domain": key[0],
                "mode": key[1],
                "best_single_feature": "",
                "best_single_rule": "",
                "best_single_feature_ba": np.nan,
                "model_balanced_accuracy": safe_float(row.get("balanced_accuracy")),
                "shortcut_gap_vs_model_ba": np.nan,
                "shortcut_dominance_flag": "no",
            }
        )

    trials_df = pd.DataFrame(all_trials)
    selected_df = pd.DataFrame(selected_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    bootstrap_df = pd.DataFrame(bootstrap_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    stress_df = pd.DataFrame(stress_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    shortcut_df = pd.DataFrame(shortcut_rows).sort_values(["domain", "mode"]).reset_index(drop=True)

    save_csv(trials_df, BASE / "trials" / "structural_retrain_trials.csv")
    save_csv(selected_df, BASE / "tables" / "selected_structural_replacements.csv")
    save_csv(bootstrap_df, BASE / "bootstrap" / "selected_bootstrap_audit.csv")
    save_csv(stress_df, BASE / "stress" / "selected_stress_audit.csv")
    save_csv(shortcut_df, SHORTCUT_OUT)

    stability = []
    for r in selected_df.itertuples(index=False):
        sub = trials_df[
            (trials_df["domain"] == str(r.domain))
            & (trials_df["mode"] == str(getattr(r, "mode")))
            & (trials_df["feature_set_id"] == str(r.feature_set_id))
            & (trials_df["model_family"] == str(r.model_family))
        ]
        stability.append(
            {
                "domain": str(r.domain),
                "mode": str(getattr(r, "mode")),
                "feature_set_id": str(r.feature_set_id),
                "model_family": str(r.model_family),
                "seed_count": int(sub["seed"].nunique()) if not sub.empty else 0,
                "f1_std_across_seeds": float(sub.groupby("seed")["f1"].max().std(ddof=0)) if not sub.empty else np.nan,
                "balanced_accuracy_std_across_seeds": float(sub.groupby("seed")["balanced_accuracy"].max().std(ddof=0)) if not sub.empty else np.nan,
                "recall_std_across_seeds": float(sub.groupby("seed")["recall"].max().std(ddof=0)) if not sub.empty else np.nan,
            }
        )
    stability_df = pd.DataFrame(stability)
    save_csv(stability_df, BASE / "stability" / "selected_seed_stability_audit.csv")

    active_new, op_new, comp = update_active_and_operational(active, op, selected_df, audit_by_slot, shortcut_df)
    save_csv(comp.sort_values(["domain", "mode"]), BASE / "tables" / "final_old_vs_new_comparison.csv")

    final_guard = active_new[
        (active_new["recall"] > 0.98)
        | (active_new["specificity"] > 0.98)
        | (active_new["roc_auc"] > 0.98)
        | (active_new["pr_auc"] > 0.98)
    ].copy()
    final_blacklist = active_new[active_new["active_model_id"].astype(str).isin(BLACKLIST_MODEL_IDS)].copy()
    final_extra = active_new[active_new["active_model_id"].astype(str).isin(STRUCTURAL_EXTRA_RESCUE_MODEL_IDS)].copy()
    final_single_feature = active_new[pd.to_numeric(active_new["n_features"], errors="coerce").fillna(0) <= 1].copy()
    save_csv(final_guard, BASE / "validation" / "remaining_guardrail_violations.csv")
    save_csv(final_blacklist, BASE / "validation" / "remaining_blacklisted_champions.csv")
    save_csv(final_extra, BASE / "validation" / "remaining_structural_extra_degenerate_champions.csv")
    save_csv(final_single_feature, BASE / "validation" / "remaining_single_feature_champions.csv")

    demoted = blacklist_active.copy()
    demoted["demotion_reason"] = "blacklisted_structural_mode_rescue_v1"
    demoted["demoted_at_utc"] = now_iso()
    save_csv(demoted, BASE / "tables" / "blacklisted_models_demoted.csv")
    save_csv(demoted, OP_OUT_BASE / "tables" / "hybrid_operational_demoted_blacklisted_models.csv")
    extra_demoted = extra_active.copy()
    extra_demoted["demotion_reason"] = "extra_structural_degenerate_model_rescue_v1"
    extra_demoted["demoted_at_utc"] = now_iso()
    save_csv(extra_demoted, BASE / "tables" / "extra_structural_models_demoted.csv")
    save_csv(extra_demoted, OP_OUT_BASE / "tables" / "hybrid_operational_demoted_structural_extra_models.csv")

    overfit_audit = selected_df[
        [
            "domain",
            "mode",
            "role",
            "train_balanced_accuracy",
            "val_balanced_accuracy",
            "balanced_accuracy",
            "overfit_gap_train_val_ba",
            "generalization_gap_val_holdout_ba",
            "overfit_ok",
            "generalization_ok",
        ]
    ].merge(stability_df, on=["domain", "mode"], how="left")
    overfit_audit = overfit_audit.merge(stress_df, on=["domain", "mode"], how="left")
    save_csv(overfit_audit, BASE / "validation" / "overfit_generalization_stability_audit.csv")

    # Artifacts/manifests.
    save_csv(pd.read_csv(ACTIVE_SUMMARY_SRC), BASE / "tables" / "source_v6_hotfix_active_summary_snapshot.csv")
    save_csv(active_new.groupby(["final_operational_class", "confidence_band"], as_index=False).size(), BASE / "tables" / "final_active_modes_summary.csv")

    report_lines = [
        "# Hybrid Structural Mode Rescue v1",
        "",
        f"- generated_at_utc: {now_iso()}",
        f"- source_active: {ACTIVE_SRC.relative_to(ROOT)}",
        f"- source_operational: {OP_SRC.relative_to(ROOT)}",
        f"- output_active: {(ACTIVE_OUT_BASE / 'tables/hybrid_active_models_30_modes.csv').relative_to(ROOT)}",
        f"- output_operational: {(OP_OUT_BASE / 'tables/hybrid_operational_final_champions.csv').relative_to(ROOT)}",
        f"- blacklisted_active_initial: {len(blacklist_active)}",
        f"- blacklisted_active_final: {len(final_blacklist)}",
        f"- structural_extra_rescue_initial: {len(extra_active)}",
        f"- structural_extra_rescue_final: {len(final_extra)}",
        f"- single_feature_active_final: {len(final_single_feature)}",
        f"- guardrail_violations_initial: {len(guard_initial)}",
        f"- guardrail_violations_final: {len(final_guard)}",
        f"- retrained_structural_replacements: {len(selected_df)}",
        f"- accepted_existing_fallbacks: 0",
        "",
        "## Corrected Slots",
        md_table(comp[["domain", "mode", "old_active_model_id", "new_active_model_id", "old_f1", "new_f1", "old_recall", "new_recall", "old_precision", "new_precision", "old_balanced_accuracy", "new_balanced_accuracy"]]),
        "",
        "## Structural Subsets",
        md_table(subset_df[["domain", "role", "mode", "feature_set_id", "full_universe_n", "target_n", "n_features"]]),
        "",
        "## Overfit / Generalization",
        md_table(overfit_audit[["domain", "mode", "overfit_gap_train_val_ba", "generalization_gap_val_holdout_ba", "f1_std_across_seeds", "balanced_accuracy_std_across_seeds", "stress_missing10_ba_drop", "stress_drop_top1_ba_drop"]]),
    ]
    (BASE / "reports" / "structural_mode_rescue_summary.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest = {
        "line": LINE,
        "freeze_label": FREEZE_LABEL,
        "generated_at_utc": now_iso(),
        "source_truth_previous": {
            "active": str(ACTIVE_SRC.relative_to(ROOT)),
            "operational": str(OP_SRC.relative_to(ROOT)),
        },
        "source_truth_new": {
            "active": str((ACTIVE_OUT_BASE / "tables" / "hybrid_active_models_30_modes.csv").relative_to(ROOT)),
            "operational": str((OP_OUT_BASE / "tables" / "hybrid_operational_final_champions.csv").relative_to(ROOT)),
        },
        "stats": {
            "blacklisted_active_initial": int(len(blacklist_active)),
            "blacklisted_active_final": int(len(final_blacklist)),
            "structural_extra_rescue_initial": int(len(extra_active)),
            "structural_extra_rescue_final": int(len(final_extra)),
            "single_feature_active_final": int(len(final_single_feature)),
            "guardrail_violations_initial": int(len(guard_initial)),
            "guardrail_violations_final": int(len(final_guard)),
            "retrained_structural_replacements": int(len(selected_df)),
            "accepted_existing_fallbacks": 0,
        },
    }
    (ART / f"{LINE}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (ROOT / "artifacts" / f"hybrid_active_modes_freeze_{FREEZE_LABEL}" / f"hybrid_active_modes_freeze_{FREEZE_LABEL}_manifest.json").write_text(
        json.dumps({"run_id": f"hybrid_active_modes_freeze_{FREEZE_LABEL}", "replacement_line": LINE, "generated_at_utc": now_iso()}, indent=2),
        encoding="utf-8",
    )
    (ROOT / "artifacts" / f"hybrid_operational_freeze_{FREEZE_LABEL}" / f"hybrid_operational_freeze_{FREEZE_LABEL}_manifest.json").write_text(
        json.dumps({"run_id": f"hybrid_operational_freeze_{FREEZE_LABEL}", "replacement_line": LINE, "generated_at_utc": now_iso()}, indent=2),
        encoding="utf-8",
    )

    norm_final = pd.read_csv(NORM_VIOL) if NORM_VIOL.exists() else pd.DataFrame()
    result = {
        "status": "ok",
        "line": LINE,
        "freeze_label": FREEZE_LABEL,
        "blacklisted_active_initial": int(len(blacklist_active)),
        "blacklisted_active_final": int(len(final_blacklist)),
        "structural_extra_rescue_initial": int(len(extra_active)),
        "structural_extra_rescue_final": int(len(final_extra)),
        "single_feature_active_final": int(len(final_single_feature)),
        "guardrail_violations_final": int(len(final_guard)),
        "policy_violations_final": int(len(norm_final)),
        "retrained_structural_replacements": int(len(selected_df)),
    }
    print(json.dumps(result, ensure_ascii=False))
    if final_guard.empty and final_blacklist.empty and final_extra.empty and final_single_feature.empty and norm_final.empty:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
