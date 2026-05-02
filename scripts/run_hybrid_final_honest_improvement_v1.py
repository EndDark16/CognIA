#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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

LINE = "hybrid_final_honest_improvement_v1"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE

V2_BASE = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2"
V2_DATASET = V2_BASE / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
V2_FE_REGISTRY = V2_BASE / "feature_engineering" / "hybrid_no_external_scores_feature_engineering_registry.csv"

ACTIVE_V2_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v2"
OP_V2_BASE = ROOT / "data" / "hybrid_operational_freeze_v2"
ACTIVE_V2 = ACTIVE_V2_BASE / "tables" / "hybrid_active_models_30_modes.csv"
OP_V2 = OP_V2_BASE / "tables" / "hybrid_operational_final_champions.csv"
ACTIVE_INPUTS_V2 = ACTIVE_V2_BASE / "tables" / "hybrid_questionnaire_inputs_master.csv"

NORM_V2 = (
    ROOT
    / "data"
    / "hybrid_classification_normalization_v1"
    / "tables"
    / "hybrid_operational_classification_normalized_v2.csv"
)

ACTIVE_V4_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v4"
OP_V4_BASE = ROOT / "data" / "hybrid_operational_freeze_v4"

PRIORITY_DOMAINS = {"anxiety", "depression", "elimination"}
FOCUS_MODE_SUFFIX = ("_2_3", "_full")

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20261101
MARGIN_SEED = 20270421
SEARCH_SEEDS = [20270421]
STABILITY_SEEDS = [20270421, 20270439, 20270501]

RF_CONFIGS: dict[str, dict[str, Any]] = {
    "rf_balanced_subsample_v2": {
        "n_estimators": 110,
        "max_depth": 20,
        "min_samples_split": 6,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    "rf_regularized_v2": {
        "n_estimators": 100,
        "max_depth": 12,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    "rf_precision_guard_v2": {
        "n_estimators": 100,
        "max_depth": 14,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.5,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": 0.9,
    },
}

EXTRA_CONFIGS: dict[str, dict[str, Any]] = {
    "extra_balanced_v1": {
        "n_estimators": 140,
        "max_depth": None,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": "balanced",
    },
    "extra_regularized_v1": {
        "n_estimators": 120,
        "max_depth": 14,
        "min_samples_split": 6,
        "min_samples_leaf": 2,
        "max_features": 0.55,
        "class_weight": "balanced",
    },
}

HGB_CONFIGS: dict[str, dict[str, Any]] = {
    "hgb_regularized_v1": {
        "max_depth": 5,
        "learning_rate": 0.05,
        "max_iter": 180,
        "l2_regularization": 0.2,
    },
    "hgb_conservative_v1": {
        "max_depth": 4,
        "learning_rate": 0.035,
        "max_iter": 200,
        "l2_regularization": 0.35,
    },
}

LOGREG_CONFIGS: dict[str, dict[str, Any]] = {
    "logreg_balanced_v1": {
        "max_iter": 2500,
        "C": 0.8,
        "solver": "liblinear",
        "class_weight": "balanced",
    },
    "logreg_regularized_v1": {
        "max_iter": 2500,
        "C": 0.45,
        "solver": "liblinear",
        "class_weight": "balanced",
    },
}

CAL_METHODS_MARGIN = ["none"]
CAL_METHODS_DEEP = ["none"]
THRESH_POLICIES = ["balanced", "precision_min_recall"]


@dataclass
class FocusSlot:
    domain: str
    mode: str
    role: str
    active_model_id: str
    source_campaign: str
    feature_set_id: str
    final_operational_class: str
    confidence_pct: float
    confidence_band: str
    overfit_flag: str
    generalization_flag: str
    dataset_ease_flag: str
    normalized_final_class: str
    secondary_metric_anomaly_flag: str
    secondary_metric_peak: float
    old_best_single_feature: str
    old_best_single_feature_ba: float
    old_shortcut_gap_vs_model_ba: float


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [
        BASE / "tables",
        BASE / "reports",
        BASE / "inventory",
        BASE / "validation",
        BASE / "bootstrap",
        BASE / "stability",
        BASE / "ablation",
        BASE / "stress",
        BASE / "trials",
        ART,
        OP_V4_BASE / "tables",
        OP_V4_BASE / "reports",
        OP_V4_BASE / "inventory",
        OP_V4_BASE / "validation",
        OP_V4_BASE / "bootstrap",
        OP_V4_BASE / "ablation",
        OP_V4_BASE / "stress",
        ACTIVE_V4_BASE / "tables",
        ACTIVE_V4_BASE / "reports",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


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


def threshold_score(policy: str, m: dict[str, float]) -> float:
    if policy == "balanced":
        return 0.50 * m["balanced_accuracy"] + 0.20 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
    if policy == "precision_min_recall":
        if m["recall"] < 0.70 or m["balanced_accuracy"] < 0.82:
            return -1e9
        return 0.64 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.10 * m["pr_auc"] + 0.06 * m["recall"]
    if policy == "recall_constrained":
        if m["precision"] < 0.76:
            return -1e9
        return 0.52 * m["recall"] + 0.20 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["precision"]
    return 0.40 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["recall"] - 0.08 * m["brier"]


def choose_threshold(policy: str, y_true: np.ndarray, probs: np.ndarray) -> tuple[float, float]:
    best_thr = 0.5
    best_score = -1e9
    for thr in np.linspace(0.05, 0.95, 181):
        m = compute_metrics(y_true, probs, float(thr))
        s = threshold_score(policy, m)
        if s > best_score:
            best_score = s
            best_thr = float(thr)
    return best_thr, best_score


def ranking_score(m: dict[str, float]) -> float:
    return 0.36 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.20 * m["pr_auc"] + 0.12 * m["recall"] - 0.08 * m["brier"]


def quality_label(m: dict[str, float]) -> str:
    if (
        m["precision"] >= 0.84
        and m["recall"] >= 0.78
        and m["balanced_accuracy"] >= 0.90
        and m["pr_auc"] >= 0.84
        and m["brier"] <= 0.055
    ):
        return "bueno"
    if (
        m["precision"] >= 0.78
        and m["recall"] >= 0.70
        and m["balanced_accuracy"] >= 0.86
        and m["pr_auc"] >= 0.80
        and m["brier"] <= 0.07
    ):
        return "aceptable"
    return "malo"


def secondary_max_metric(m: dict[str, float]) -> float:
    return float(max(m["specificity"], m["roc_auc"], m["pr_auc"]))


def secondary_anomaly_from_metrics(m: dict[str, float]) -> str:
    sec = secondary_max_metric(m)
    suspicious_combo = sec > 0.985 and float(m["brier"]) <= 0.03
    return "yes" if sec > 0.98 or suspicious_combo else "no"


def build_rf(config_id: str, seed: int) -> RandomForestClassifier:
    cfg = RF_CONFIGS[config_id]
    return RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cfg["class_weight"],
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        random_state=int(seed),
        n_jobs=-1,
    )


def build_extra(config_id: str, seed: int) -> ExtraTreesClassifier:
    cfg = EXTRA_CONFIGS[config_id]
    return ExtraTreesClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cfg["class_weight"],
        random_state=int(seed),
        n_jobs=-1,
    )


def build_hgb(config_id: str, seed: int) -> HistGradientBoostingClassifier:
    cfg = HGB_CONFIGS[config_id]
    return HistGradientBoostingClassifier(
        max_depth=int(cfg["max_depth"]),
        learning_rate=float(cfg["learning_rate"]),
        max_iter=int(cfg["max_iter"]),
        l2_regularization=float(cfg["l2_regularization"]),
        random_state=int(seed),
    )


def build_logreg(config_id: str, seed: int) -> LogisticRegression:
    del seed
    cfg = LOGREG_CONFIGS[config_id]
    return LogisticRegression(
        max_iter=int(cfg["max_iter"]),
        C=float(cfg["C"]),
        solver=str(cfg["solver"]),
        class_weight=cfg["class_weight"],
    )


def build_model(family: str, config_id: str, seed: int):
    if family == "rf":
        return build_rf(config_id, seed)
    if family == "extra_trees":
        return build_extra(config_id, seed)
    if family == "hgb":
        return build_hgb(config_id, seed)
    if family == "logreg":
        return build_logreg(config_id, seed)
    raise ValueError(f"Unsupported family: {family}")


def fit_imputer_and_matrix(
    tr_df: pd.DataFrame, va_df: pd.DataFrame, ho_df: pd.DataFrame, features: list[str]
) -> tuple[SimpleImputer, np.ndarray, np.ndarray, np.ndarray]:
    x_tr = tr_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_va = va_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = ho_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_tr = x_tr.dropna(axis=1, how="all")
    x_va = x_va[x_tr.columns]
    x_ho = x_ho[x_tr.columns]
    imp = SimpleImputer(strategy="median")
    return imp, imp.fit_transform(x_tr), imp.transform(x_va), imp.transform(x_ho)


def calibrate_probs(
    y_val: np.ndarray,
    p_tr_raw: np.ndarray,
    p_va_raw: np.ndarray,
    p_ho_raw: np.ndarray,
    method: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if method == "none":
        return p_tr_raw, p_va_raw, p_ho_raw
    if len(np.unique(y_val)) < 2:
        return p_tr_raw, p_va_raw, p_ho_raw
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p_va_raw, y_val)
        return (
            np.clip(iso.predict(p_tr_raw), 1e-6, 1 - 1e-6),
            np.clip(iso.predict(p_va_raw), 1e-6, 1 - 1e-6),
            np.clip(iso.predict(p_ho_raw), 1e-6, 1 - 1e-6),
        )
    if method == "sigmoid":
        lr = LogisticRegression(max_iter=300, solver="lbfgs")
        lr.fit(p_va_raw.reshape(-1, 1), y_val)
        return (
            np.clip(lr.predict_proba(p_tr_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
            np.clip(lr.predict_proba(p_va_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
            np.clip(lr.predict_proba(p_ho_raw.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6),
        )
    return p_tr_raw, p_va_raw, p_ho_raw


def build_split_registry(df: pd.DataFrame) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    split_ids: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []
    ids = df["participant_id"].astype(str).tolist()
    for i, d in enumerate(DOMAINS):
        y = df[f"target_domain_{d}_final"].astype(int)
        seed = BASE_SEED + i * 23
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(
            np.array(ids, dtype=object), y, test_size=0.40, random_state=seed, stratify=strat
        )
        strat_tmp = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids, va_y, ho_y = train_test_split(
            tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=strat_tmp
        )
        split_ids[d] = {
            "train": [str(x) for x in tr_ids],
            "val": [str(x) for x in va_ids],
            "holdout": [str(x) for x in ho_ids],
        }
        rows.append(
            {
                "domain": d,
                "target": f"target_domain_{d}_final",
                "seed": seed,
                "train_n": len(tr_ids),
                "val_n": len(va_ids),
                "holdout_n": len(ho_ids),
                "train_pos_rate": float(np.mean(tr_y)),
                "val_pos_rate": float(np.mean(va_y)),
                "holdout_pos_rate": float(np.mean(ho_y)),
            }
        )
    return split_ids, pd.DataFrame(rows)


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def md_table(df: pd.DataFrame, max_rows: int = 200) -> str:
    if df is None or df.empty:
        return "(sin filas)"
    x = df.copy().head(max_rows)
    cols = list(x.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in x.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def best_single_feature_rule(
    hold_df: pd.DataFrame,
    target_col: str,
    features: list[str],
) -> dict[str, Any]:
    y = hold_df[target_col].astype(int).to_numpy()
    best = {
        "best_single_feature": "",
        "best_single_rule": "",
        "best_single_feature_ba": -1.0,
    }
    for f in features:
        if f not in hold_df.columns:
            continue
        x = pd.to_numeric(hold_df[f], errors="coerce")
        if x.isna().all():
            continue
        med = float(x.median()) if not x.dropna().empty else 0.0
        x = x.fillna(med).to_numpy()
        if len(np.unique(x)) < 2:
            continue
        thr_grid = np.unique(np.quantile(x, np.linspace(0.05, 0.95, 19)))
        for thr in thr_grid:
            for ge in (True, False):
                pred = (x >= thr).astype(int) if ge else (x <= thr).astype(int)
                ba = float(balanced_accuracy_score(y, pred))
                if ba > best["best_single_feature_ba"]:
                    best = {
                        "best_single_feature": f,
                        "best_single_rule": f"{f} {'>=' if ge else '<='} {float(thr):.6g}",
                        "best_single_feature_ba": ba,
                    }
    return best


def get_feature_list(
    active_row: pd.Series,
    reg_map: dict[tuple[str, str, str], list[str]],
) -> tuple[list[str], str]:
    d, m, fs = str(active_row["domain"]), str(active_row["mode"]), str(active_row["feature_set_id"])
    src = str(active_row["source_campaign"])
    key = (d, m, fs)
    if src == "rebuild_v2" and key in reg_map:
        return list(reg_map[key]), "exact_v2"
    if src == "boosted_v3":
        base_map = {
            "boosted_eng_full": "full_eligible",
            "boosted_eng_compact": "compact_subset",
            "boosted_eng_pruned": "stability_pruned_subset",
        }
        if fs in base_map and (d, m, base_map[fs]) in reg_map:
            return list(reg_map[(d, m, base_map[fs])]), "base_only_por_confirmar_engv3"
        if key in reg_map:
            return list(reg_map[key]), "mapped_v2_by_name_por_confirmar"
    if key in reg_map:
        return list(reg_map[key]), "fallback_v2_by_name"
    return [], "por_confirmar_missing_feature_set"


def quality_to_final_class(metrics: dict[str, float], overfit_gap: float, secondary_anomaly: str) -> str:
    robust_gate = (
        metrics["balanced_accuracy"] >= 0.90
        and metrics["f1"] >= 0.85
        and metrics["precision"] >= 0.82
        and metrics["recall"] >= 0.80
        and metrics["brier"] <= 0.06
        and overfit_gap <= 0.10
    )
    caveat_gate = (
        metrics["balanced_accuracy"] >= 0.84
        and metrics["f1"] >= 0.78
        and metrics["precision"] >= 0.74
        and metrics["recall"] >= 0.68
        and metrics["brier"] <= 0.08
    )
    if robust_gate and secondary_anomaly == "no":
        return "ROBUST_PRIMARY"
    if caveat_gate:
        return "PRIMARY_WITH_CAVEAT"
    return "HOLD_FOR_LIMITATION"


def candidate_feature_sets(
    domain: str,
    mode: str,
    old_feature_set_id: str,
    dominant_feature: str,
    reg_map: dict[tuple[str, str, str], list[str]],
) -> dict[str, list[str]]:
    cands: dict[str, list[str]] = {}
    old_key = (domain, mode, old_feature_set_id)
    old_feats = reg_map.get(old_key, [])
    if old_feats:
        cands[old_feature_set_id] = list(old_feats)
    if old_feats and dominant_feature and dominant_feature in old_feats:
        fs_id = f"{old_feature_set_id}_no_shortcut_v1"
        cands[fs_id] = [f for f in old_feats if f != dominant_feature]

    for fs in [
        "full_eligible",
        "precision_oriented_subset",
        "compact_subset",
        "stability_pruned_subset",
        "engineered_compact",
        "engineered_pruned",
    ]:
        key = (domain, mode, fs)
        if key in reg_map and reg_map[key] and fs not in cands:
            cands[fs] = list(reg_map[key])

    out: dict[str, list[str]] = {}
    for fs, feats in cands.items():
        if len(out) >= 6:
            break
        out[fs] = feats
    return out


def build_focus_inventory(
    active_v2: pd.DataFrame,
    norm_v2: pd.DataFrame,
    reg_map: dict[tuple[str, str, str], list[str]],
    df_data: pd.DataFrame,
    split_ids: dict[str, dict[str, list[str]]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    norm_idx = {(str(r.domain), str(r.mode)): r for r in norm_v2.itertuples(index=False)}

    for _, r in active_v2.iterrows():
        d = str(r["domain"])
        m = str(r["mode"])
        if d not in PRIORITY_DOMAINS:
            continue
        if not m.endswith(FOCUS_MODE_SUFFIX):
            continue
        feat_list, feat_status = get_feature_list(r, reg_map)
        hold_df = subset_by_ids(df_data, split_ids[d]["holdout"])
        target_col = f"target_domain_{d}_final"
        shortcut = {
            "best_single_feature": "",
            "best_single_rule": "",
            "best_single_feature_ba": np.nan,
        }
        if feat_list:
            shortcut = best_single_feature_rule(hold_df, target_col, feat_list)
        shortcut_ba = float(shortcut["best_single_feature_ba"]) if pd.notna(shortcut["best_single_feature_ba"]) else np.nan
        model_ba = float(r["balanced_accuracy"])
        shortcut_gap = float(shortcut_ba - model_ba) if pd.notna(shortcut_ba) else np.nan

        nrow = norm_idx.get((d, m), None)
        rows.append(
            {
                "domain": d,
                "mode": m,
                "role": str(r["role"]),
                "active_model_id": str(r["active_model_id"]),
                "source_campaign": str(r["source_campaign"]),
                "feature_set_id": str(r["feature_set_id"]),
                "final_operational_class": str(r["final_operational_class"]),
                "confidence_pct": float(r["confidence_pct"]),
                "confidence_band": str(r["confidence_band"]),
                "overfit_flag": str(r["overfit_flag"]),
                "generalization_flag": str(r["generalization_flag"]),
                "dataset_ease_flag": str(r["dataset_ease_flag"]),
                "precision": float(r["precision"]),
                "recall": float(r["recall"]),
                "specificity": float(r["specificity"]),
                "balanced_accuracy": float(r["balanced_accuracy"]),
                "f1": float(r["f1"]),
                "roc_auc": float(r["roc_auc"]),
                "pr_auc": float(r["pr_auc"]),
                "brier": float(r["brier"]),
                "secondary_metric_peak": float(max(float(r["specificity"]), float(r["roc_auc"]), float(r["pr_auc"]))),
                "secondary_metric_anomaly_flag": "yes"
                if max(float(r["specificity"]), float(r["roc_auc"]), float(r["pr_auc"])) > 0.98
                else "no",
                "feature_audit_status": feat_status,
                "old_best_single_feature": shortcut["best_single_feature"],
                "old_best_single_rule": shortcut["best_single_rule"],
                "old_best_single_feature_ba": shortcut_ba,
                "old_shortcut_gap_vs_model_ba": shortcut_gap,
                "shortcut_dominance_flag": "yes" if pd.notna(shortcut_gap) and shortcut_gap >= 0.05 else "no",
                "normalized_final_class": str(getattr(nrow, "normalized_final_class", "por_confirmar")),
                "classification_reason_code": str(getattr(nrow, "classification_reason_code", "por_confirmar")),
            }
        )

    return pd.DataFrame(rows).sort_values(["domain", "mode"]).reset_index(drop=True)


def run_search_for_slot(
    *,
    domain: str,
    mode: str,
    role: str,
    tr_df: pd.DataFrame,
    va_df: pd.DataFrame,
    ho_df: pd.DataFrame,
    target_col: str,
    feature_sets: dict[str, list[str]],
    seeds: list[int],
    family_scope: str,
) -> tuple[pd.DataFrame, pd.Series | None]:
    y_tr = tr_df[target_col].astype(int).to_numpy()
    y_va = va_df[target_col].astype(int).to_numpy()
    y_ho = ho_df[target_col].astype(int).to_numpy()

    rows: list[dict[str, Any]] = []

    families: list[tuple[str, list[str]]] = []
    if family_scope == "margin":
        families = [
            ("rf", ["rf_regularized_v2"]),
            ("hgb", ["hgb_regularized_v1"]),
        ]
        cal_methods = CAL_METHODS_MARGIN
    else:
        families = [
            ("rf", ["rf_regularized_v2", "rf_precision_guard_v2"]),
            ("hgb", ["hgb_regularized_v1"]),
        ]
        cal_methods = CAL_METHODS_DEEP

    for fs_id, feats in feature_sets.items():
        if not feats:
            continue
        try:
            _, x_tr, x_va, x_ho = fit_imputer_and_matrix(tr_df, va_df, ho_df, feats)
        except Exception:
            continue
        n_effective_features = int(x_tr.shape[1])
        if n_effective_features < 5:
            continue

        for fam, cfg_list in families:
            for cfg_id in cfg_list:
                for seed in seeds:
                    try:
                        model = build_model(fam, cfg_id, seed)
                        model.fit(x_tr, y_tr)
                    except Exception:
                        continue

                    if not hasattr(model, "predict_proba"):
                        continue

                    p_tr_raw = np.clip(model.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
                    p_va_raw = np.clip(model.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
                    p_ho_raw = np.clip(model.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)

                    for cal in cal_methods:
                        p_tr, p_va, p_ho = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, cal)
                        for pol in THRESH_POLICIES:
                            thr, thr_score = choose_threshold(pol, y_va, p_va)
                            m_tr = compute_metrics(y_tr, p_tr, thr)
                            m_va = compute_metrics(y_va, p_va, thr)
                            m_ho = compute_metrics(y_ho, p_ho, thr)
                            overfit_gap = float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                            gen_gap = float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]))
                            sec_max = secondary_max_metric(m_ho)
                            val_sel = (
                                0.46 * m_va["balanced_accuracy"]
                                + 0.20 * m_va["precision"]
                                + 0.18 * m_va["pr_auc"]
                                + 0.16 * m_va["recall"]
                                - 0.12 * max(0.0, overfit_gap)
                                - 0.10 * max(0.0, gen_gap)
                            )
                            rows.append(
                                {
                                    "domain": domain,
                                    "mode": mode,
                                    "role": role,
                                    "feature_set_id": fs_id,
                                    "config_id": cfg_id,
                                    "model_family": fam,
                                    "calibration": cal,
                                    "threshold_policy": pol,
                                    "threshold": float(thr),
                                    "seed": int(seed),
                                    "n_features": int(n_effective_features),
                                    "feature_list_pipe": "|".join(feats),
                                    "train_precision": m_tr["precision"],
                                    "train_recall": m_tr["recall"],
                                    "train_balanced_accuracy": m_tr["balanced_accuracy"],
                                    "val_precision": m_va["precision"],
                                    "val_recall": m_va["recall"],
                                    "val_balanced_accuracy": m_va["balanced_accuracy"],
                                    "precision": m_ho["precision"],
                                    "recall": m_ho["recall"],
                                    "specificity": m_ho["specificity"],
                                    "balanced_accuracy": m_ho["balanced_accuracy"],
                                    "f1": m_ho["f1"],
                                    "roc_auc": m_ho["roc_auc"],
                                    "pr_auc": m_ho["pr_auc"],
                                    "brier": m_ho["brier"],
                                    "overfit_gap_train_val_ba": overfit_gap,
                                    "generalization_gap_val_holdout_ba": gen_gap,
                                    "quality_label": quality_label(m_ho),
                                    "ranking_score": ranking_score(m_ho),
                                    "val_selection_score": float(val_sel),
                                    "threshold_policy_score": float(thr_score),
                                    "secondary_max_metric": sec_max,
                                    "secondary_metric_anomaly_flag": secondary_anomaly_from_metrics(m_ho),
                                    "overfit_warning": "yes" if overfit_gap > 0.10 else "no",
                                }
                            )

    if not rows:
        return pd.DataFrame(), None

    trial_df = pd.DataFrame(rows)
    winner = (
        trial_df.sort_values(
            ["val_selection_score", "val_balanced_accuracy", "val_precision", "n_features"],
            ascending=[False, False, False, True],
        )
        .iloc[0]
        .copy()
    )
    return trial_df, winner


def mode_focus_priority(mode: str) -> int:
    if mode.endswith("_full"):
        return 1
    if mode.endswith("_2_3"):
        return 2
    return 9


def should_target_for_deep_retrain(row: pd.Series) -> bool:
    domain = str(row.get("domain", ""))
    mode = str(row.get("mode", ""))
    if domain not in PRIORITY_DOMAINS:
        return False
    if not mode.endswith(FOCUS_MODE_SUFFIX):
        return False
    if str(row.get("margin_status", "")) == "no_candidate_trials":
        return False
    return True


def nrm(x: float, lo: float, hi: float) -> float:
    x = float(x)
    if x <= lo:
        return 0.0
    if x >= hi:
        return 1.0
    return (x - lo) / (hi - lo)


def main() -> None:
    ensure_dirs()

    active_v2 = pd.read_csv(ACTIVE_V2)
    op_v2 = pd.read_csv(OP_V2)
    norm_v2 = pd.read_csv(NORM_V2) if NORM_V2.exists() else pd.DataFrame()
    fe_reg = pd.read_csv(V2_FE_REGISTRY)
    fe_reg["feature_list"] = fe_reg["feature_list_pipe"].fillna("").apply(lambda s: [f for f in str(s).split("|") if f])
    reg_map = {
        (str(r.domain), str(r.mode), str(r.feature_set_id)): list(r.feature_list)
        for r in fe_reg.itertuples(index=False)
    }

    df_data = pd.read_csv(V2_DATASET)
    split_ids, split_registry = build_split_registry(df_data)
    save_csv(split_registry, BASE / "validation/split_registry.csv")

    dup = pd.DataFrame(
        [
            {
                "dataset_rows": int(len(df_data)),
                "full_vector_duplicates_anywhere": int(
                    df_data.drop(columns=["participant_id"], errors="ignore")
                    .astype(str)
                    .agg("|".join, axis=1)
                    .duplicated(keep=False)
                    .sum()
                ),
            }
        ]
    )
    save_csv(dup, BASE / "validation/duplicate_audit_global.csv")

    focus = build_focus_inventory(active_v2, norm_v2, reg_map, df_data, split_ids)
    save_csv(focus, BASE / "tables/focus_slots_inventory.csv")

    margin_rows: list[dict[str, Any]] = []
    margin_trial_rows: list[dict[str, Any]] = []

    for r in focus.itertuples(index=False):
        domain = str(r.domain)
        mode = str(r.mode)
        target_col = f"target_domain_{domain}_final"
        split = split_ids[domain]
        tr_df = subset_by_ids(df_data, split["train"])
        va_df = subset_by_ids(df_data, split["val"])
        ho_df = subset_by_ids(df_data, split["holdout"])

        cands = candidate_feature_sets(
            domain=domain,
            mode=mode,
            old_feature_set_id=str(r.feature_set_id),
            dominant_feature=str(r.old_best_single_feature),
            reg_map=reg_map,
        )

        trial_df, winner = run_search_for_slot(
            domain=domain,
            mode=mode,
            role=str(r.role),
            tr_df=tr_df,
            va_df=va_df,
            ho_df=ho_df,
            target_col=target_col,
            feature_sets=cands,
            seeds=[MARGIN_SEED],
            family_scope="margin",
        )

        if not trial_df.empty:
            trial_df["search_scope"] = "margin"
            margin_trial_rows.extend(trial_df.to_dict(orient="records"))

        if winner is None:
            margin_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "role": str(r.role),
                    "active_model_id": str(r.active_model_id),
                    "normalized_final_class": str(r.normalized_final_class),
                    "confidence_pct": float(r.confidence_pct),
                    "margin_status": "no_candidate_trials",
                }
            )
            continue

        margin_rows.append(
            {
                "domain": domain,
                "mode": mode,
                "role": str(r.role),
                "active_model_id": str(r.active_model_id),
                "normalized_final_class": str(r.normalized_final_class),
                "confidence_pct": float(r.confidence_pct),
                "old_balanced_accuracy": float(r.balanced_accuracy),
                "old_f1": float(r.f1),
                "old_precision": float(r.precision),
                "old_recall": float(r.recall),
                "old_roc_auc": float(r.roc_auc),
                "old_pr_auc": float(r.pr_auc),
                "old_brier": float(r.brier),
                "old_secondary_max_metric": float(r.secondary_metric_peak),
                "old_secondary_metric_anomaly_flag": str(r.secondary_metric_anomaly_flag),
                "winner_model_family": str(winner["model_family"]),
                "winner_feature_set_id": str(winner["feature_set_id"]),
                "winner_config_id": str(winner["config_id"]),
                "winner_calibration": str(winner["calibration"]),
                "winner_threshold_policy": str(winner["threshold_policy"]),
                "winner_threshold": float(winner["threshold"]),
                "new_balanced_accuracy": float(winner["balanced_accuracy"]),
                "new_f1": float(winner["f1"]),
                "new_precision": float(winner["precision"]),
                "new_recall": float(winner["recall"]),
                "new_roc_auc": float(winner["roc_auc"]),
                "new_pr_auc": float(winner["pr_auc"]),
                "new_brier": float(winner["brier"]),
                "new_secondary_max_metric": float(winner["secondary_max_metric"]),
                "new_secondary_metric_anomaly_flag": str(winner["secondary_metric_anomaly_flag"]),
                "delta_balanced_accuracy": float(winner["balanced_accuracy"]) - float(r.balanced_accuracy),
                "delta_f1": float(winner["f1"]) - float(r.f1),
                "delta_precision": float(winner["precision"]) - float(r.precision),
                "delta_recall": float(winner["recall"]) - float(r.recall),
                "delta_roc_auc": float(winner["roc_auc"]) - float(r.roc_auc),
                "delta_pr_auc": float(winner["pr_auc"]) - float(r.pr_auc),
                "delta_brier": float(winner["brier"]) - float(r.brier),
                "margin_status": "material_candidate"
                if (
                    float(winner["balanced_accuracy"]) - float(r.balanced_accuracy) >= 0.010
                    or float(winner["f1"]) - float(r.f1) >= 0.015
                    or float(winner["pr_auc"]) - float(r.pr_auc) >= 0.015
                )
                else "near_ceiling_or_minor_gain",
            }
        )

    margin_df = pd.DataFrame(margin_rows)
    margin_trial_df = pd.DataFrame(margin_trial_rows)
    save_csv(margin_df, BASE / "tables/focus_margin_audit.csv")
    save_csv(margin_trial_df, BASE / "trials/focus_margin_trials.csv")

    deep_targets = margin_df[margin_df.apply(should_target_for_deep_retrain, axis=1)].copy()
    deep_targets = deep_targets.sort_values(
        by=["domain", "mode"],
        key=lambda s: s.map(lambda x: f"{x}") if s.name != "mode" else s.map(mode_focus_priority),
    )
    save_csv(deep_targets, BASE / "tables/deep_retrain_targets.csv")

    deep_trial_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []

    for t in deep_targets.itertuples(index=False):
        domain = str(t.domain)
        mode = str(t.mode)
        role = str(t.role)
        old_row = active_v2[(active_v2["domain"] == domain) & (active_v2["mode"] == mode)].iloc[0]

        target_col = f"target_domain_{domain}_final"
        split = split_ids[domain]
        tr_df = subset_by_ids(df_data, split["train"])
        va_df = subset_by_ids(df_data, split["val"])
        ho_df = subset_by_ids(df_data, split["holdout"])
        y_tr = tr_df[target_col].astype(int).to_numpy()
        y_va = va_df[target_col].astype(int).to_numpy()
        y_ho = ho_df[target_col].astype(int).to_numpy()

        cands = candidate_feature_sets(
            domain=domain,
            mode=mode,
            old_feature_set_id=str(old_row["feature_set_id"]),
            dominant_feature=str(getattr(t, "old_best_single_feature", "")),
            reg_map=reg_map,
        )

        trial_df, winner = run_search_for_slot(
            domain=domain,
            mode=mode,
            role=role,
            tr_df=tr_df,
            va_df=va_df,
            ho_df=ho_df,
            target_col=target_col,
            feature_sets=cands,
            seeds=SEARCH_SEEDS,
            family_scope="deep",
        )

        if trial_df.empty or winner is None:
            selected_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "role": role,
                    "active_model_id": str(old_row["active_model_id"]),
                    "promotion_decision": "HOLD_FOR_LIMITATION",
                    "hold_reason": "no_deep_trials_generated",
                }
            )
            continue

        trial_df["search_scope"] = "deep"
        deep_trial_rows.extend(trial_df.to_dict(orient="records"))

        winner_feats = [f for f in str(winner["feature_list_pipe"]).split("|") if f]
        shortcut_new = best_single_feature_rule(ho_df, target_col, winner_feats) if winner_feats else {
            "best_single_feature": "",
            "best_single_rule": "",
            "best_single_feature_ba": np.nan,
        }
        winner["new_best_single_feature"] = shortcut_new["best_single_feature"]
        winner["new_best_single_rule"] = shortcut_new["best_single_rule"]
        winner["new_best_single_feature_ba"] = shortcut_new["best_single_feature_ba"]
        winner["new_shortcut_gap_vs_model_ba"] = (
            float(shortcut_new["best_single_feature_ba"] - float(winner["balanced_accuracy"]))
            if pd.notna(shortcut_new["best_single_feature_ba"])
            else np.nan
        )

        old_metrics = {
            "precision": float(old_row["precision"]),
            "recall": float(old_row["recall"]),
            "balanced_accuracy": float(old_row["balanced_accuracy"]),
            "f1": float(old_row["f1"]),
            "pr_auc": float(old_row["pr_auc"]),
            "brier": float(old_row["brier"]),
            "specificity": float(old_row["specificity"]),
            "roc_auc": float(old_row["roc_auc"]),
        }

        new_metrics = {
            "precision": float(winner["precision"]),
            "recall": float(winner["recall"]),
            "balanced_accuracy": float(winner["balanced_accuracy"]),
            "f1": float(winner["f1"]),
            "pr_auc": float(winner["pr_auc"]),
            "brier": float(winner["brier"]),
            "specificity": float(winner["specificity"]),
            "roc_auc": float(winner["roc_auc"]),
        }

        delta_ba = new_metrics["balanced_accuracy"] - old_metrics["balanced_accuracy"]
        delta_f1 = new_metrics["f1"] - old_metrics["f1"]
        delta_pr_auc = new_metrics["pr_auc"] - old_metrics["pr_auc"]
        ranking_gain = float(winner["ranking_score"]) - ranking_score(old_metrics)

        pass_generalization = (
            float(winner["overfit_gap_train_val_ba"]) <= 0.10
            and float(winner["generalization_gap_val_holdout_ba"]) <= 0.08
            and new_metrics["precision"] >= 0.78
            and new_metrics["recall"] >= 0.70
            and new_metrics["balanced_accuracy"] >= 0.86
            and new_metrics["pr_auc"] >= 0.80
            and new_metrics["brier"] <= 0.07
        )

        class_upgrade_candidate = (
            str(old_row["final_operational_class"]) == "ACTIVE_LIMITED_USE"
            and new_metrics["balanced_accuracy"] >= 0.89
            and new_metrics["f1"] >= 0.83
            and new_metrics["precision"] >= 0.80
            and new_metrics["recall"] >= 0.80
            and new_metrics["brier"] <= 0.055
        )

        material_gain = bool(
            delta_ba >= 0.010
            or delta_f1 >= 0.015
            or delta_pr_auc >= 0.015
            or (new_metrics["recall"] - old_metrics["recall"] >= 0.035 and new_metrics["precision"] >= old_metrics["precision"] - 0.02)
            or ranking_gain >= 0.02
        )

        old_secondary_anomaly = "yes" if max(float(old_row["specificity"]), float(old_row["roc_auc"]), float(old_row["pr_auc"])) > 0.98 else "no"
        anomaly_guard = True
        if old_secondary_anomaly == "yes" and float(winner["secondary_max_metric"]) > 0.98:
            anomaly_guard = bool(
                pd.isna(winner["new_shortcut_gap_vs_model_ba"]) or float(winner["new_shortcut_gap_vs_model_ba"]) <= 0.05
            )

        promote = bool(pass_generalization and anomaly_guard and (material_gain or class_upgrade_candidate))

        winner["promotion_decision"] = "PROMOTE_NOW" if promote else "HOLD_FOR_LIMITATION"
        winner["generalization_ok"] = "yes" if pass_generalization else "no"
        winner["material_gain_ok"] = "yes" if material_gain else "no"
        winner["class_upgrade_candidate"] = "yes" if class_upgrade_candidate else "no"
        winner["anomaly_guard_ok"] = "yes" if anomaly_guard else "no"

        selected_payload = {
            "domain": domain,
            "mode": mode,
            "role": role,
            "active_model_id": str(old_row["active_model_id"]),
            "source_campaign_old": str(old_row["source_campaign"]),
            "feature_set_id_old": str(old_row["feature_set_id"]),
            **winner.to_dict(),
            "old_precision": old_metrics["precision"],
            "old_recall": old_metrics["recall"],
            "old_specificity": old_metrics["specificity"],
            "old_balanced_accuracy": old_metrics["balanced_accuracy"],
            "old_f1": old_metrics["f1"],
            "old_roc_auc": old_metrics["roc_auc"],
            "old_pr_auc": old_metrics["pr_auc"],
            "old_brier": old_metrics["brier"],
            "old_final_operational_class": str(old_row["final_operational_class"]),
            "old_confidence_pct": float(old_row["confidence_pct"]),
            "delta_precision": new_metrics["precision"] - old_metrics["precision"],
            "delta_recall": new_metrics["recall"] - old_metrics["recall"],
            "delta_balanced_accuracy": delta_ba,
            "delta_f1": delta_f1,
            "delta_pr_auc": delta_pr_auc,
            "delta_brier": new_metrics["brier"] - old_metrics["brier"],
            "old_secondary_anomaly": old_secondary_anomaly,
            "ranking_gain": ranking_gain,
        }

        if not promote:
            selected_rows.append(selected_payload)
            continue

        _, x_tr, x_va, x_ho = fit_imputer_and_matrix(tr_df, va_df, ho_df, winner_feats)
        model0 = build_model(str(winner["model_family"]), str(winner["config_id"]), int(winner["seed"]))
        model0.fit(x_tr, y_tr)
        effective_feats = [f for f in winner_feats if f in tr_df.columns and not pd.to_numeric(tr_df[f], errors="coerce").isna().all()]
        p_ho_raw = np.clip(model0.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
        p_tr_raw = np.clip(model0.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
        p_va_raw = np.clip(model0.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
        _, _, p_ho_cal = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, str(winner["calibration"]))
        base_thr = float(winner["threshold"])
        m0 = compute_metrics(y_ho, p_ho_cal, base_thr)

        for s in STABILITY_SEEDS:
            ms = build_model(str(winner["model_family"]), str(winner["config_id"]), int(s))
            ms.fit(x_tr, y_tr)
            ps_raw = np.clip(ms.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
            ps_tr_raw = np.clip(ms.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
            ps_va_raw = np.clip(ms.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
            _, _, ps = calibrate_probs(y_va, ps_tr_raw, ps_va_raw, ps_raw, str(winner["calibration"]))
            mm = compute_metrics(y_ho, ps, base_thr)
            stability_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "seed": int(s),
                    "model_family": str(winner["model_family"]),
                    "precision": mm["precision"],
                    "recall": mm["recall"],
                    "balanced_accuracy": mm["balanced_accuracy"],
                    "pr_auc": mm["pr_auc"],
                    "brier": mm["brier"],
                    "threshold": base_thr,
                }
            )

        rng = np.random.default_rng(20270421)
        idx = np.arange(len(y_ho))
        for _ in range(100):
            sidx = rng.choice(idx, size=len(idx), replace=True)
            yb = y_ho[sidx]
            pb = p_ho_cal[sidx]
            mb = compute_metrics(yb, pb, base_thr)
            bootstrap_rows.extend(
                [
                    {"domain": domain, "mode": mode, "metric": "balanced_accuracy", "value": mb["balanced_accuracy"]},
                    {"domain": domain, "mode": mode, "metric": "pr_auc", "value": mb["pr_auc"]},
                ]
            )

        if hasattr(model0, "feature_importances_") and len(model0.feature_importances_) == len(effective_feats):
            imp_rank = pd.Series(model0.feature_importances_, index=effective_feats).sort_values(ascending=False)
            ablation_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "ablation_case": "baseline",
                    "k": 0,
                    "delta_ba": 0.0,
                    "delta_pr_auc": 0.0,
                }
            )
            for k in [3, 5]:
                drop = imp_rank.head(min(k, len(imp_rank))).index.tolist()
                feats_ab = [f for f in effective_feats if f not in drop]
                if not feats_ab:
                    continue
                _, xtr_ab, xva_ab, xho_ab = fit_imputer_and_matrix(tr_df, va_df, ho_df, feats_ab)
                mab = build_model(str(winner["model_family"]), str(winner["config_id"]), int(winner["seed"]))
                mab.fit(xtr_ab, y_tr)
                pab = np.clip(mab.predict_proba(xho_ab)[:, 1], 1e-6, 1 - 1e-6)
                mab_m = compute_metrics(y_ho, pab, base_thr)
                ablation_rows.append(
                    {
                        "domain": domain,
                        "mode": mode,
                        "ablation_case": f"drop_top{k}",
                        "k": k,
                        "removed_features": "|".join(drop),
                        "delta_ba": float(mab_m["balanced_accuracy"] - m0["balanced_accuracy"]),
                        "delta_pr_auc": float(mab_m["pr_auc"] - m0["pr_auc"]),
                    }
                )

        for dthr in [-0.10, -0.05, 0.05, 0.10]:
            thr2 = float(np.clip(base_thr + dthr, 0.05, 0.95))
            mt = compute_metrics(y_ho, p_ho_cal, thr2)
            stress_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "stress_type": "threshold",
                    "scenario": f"threshold_shift_{dthr:+.2f}",
                    "balanced_accuracy": mt["balanced_accuracy"],
                    "delta_ba": float(mt["balanced_accuracy"] - m0["balanced_accuracy"]),
                }
            )

        x_ho_raw_df = ho_df[effective_feats].copy().apply(pd.to_numeric, errors="coerce")
        medians = x_ho_raw_df.median(numeric_only=True)
        for ratio in [0.10, 0.20]:
            xm = x_ho_raw_df.copy()
            mask = np.random.default_rng(20270421 + int(100 * ratio)).random(xm.shape) < ratio
            xm = xm.mask(mask)
            xm = xm.fillna(medians)
            pm = np.clip(model0.predict_proba(xm.to_numpy())[:, 1], 1e-6, 1 - 1e-6)
            mm = compute_metrics(y_ho, pm, base_thr)
            stress_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "stress_type": "missingness",
                    "scenario": f"missing_{int(100*ratio)}pct",
                    "balanced_accuracy": mm["balanced_accuracy"],
                    "delta_ba": float(mm["balanced_accuracy"] - m0["balanced_accuracy"]),
                }
            )

        selected_rows.append(selected_payload)

    deep_trial_df = pd.DataFrame(deep_trial_rows)
    selected_df = pd.DataFrame(selected_rows)
    save_csv(deep_trial_df, BASE / "trials/final_honest_improvement_trials.csv")
    save_csv(selected_df, BASE / "tables/final_honest_improvement_selected_models.csv")
    save_csv(pd.DataFrame(stability_rows), BASE / "stability/final_honest_seed_stability.csv")
    save_csv(pd.DataFrame(bootstrap_rows), BASE / "bootstrap/final_honest_bootstrap_intervals.csv")
    save_csv(pd.DataFrame(ablation_rows), BASE / "ablation/final_honest_ablation.csv")
    save_csv(pd.DataFrame(stress_rows), BASE / "stress/final_honest_stress.csv")

    comp_df = selected_df.copy()
    if not comp_df.empty:
        keep_cols = [
            "domain",
            "mode",
            "active_model_id",
            "promotion_decision",
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
            "generalization_ok",
            "material_gain_ok",
            "anomaly_guard_ok",
            "class_upgrade_candidate",
            "new_shortcut_gap_vs_model_ba",
        ]
        comp_df = comp_df[[c for c in keep_cols if c in comp_df.columns]].copy()
    save_csv(comp_df, BASE / "tables/final_old_vs_new_comparison.csv")

    demoted = selected_df[selected_df.get("promotion_decision", "") == "PROMOTE_NOW"].copy()
    if not demoted.empty:
        demoted = demoted.assign(
            status="demoted_from_primary_due_replacement",
            reason="replaced_by_hybrid_final_honest_improvement_v1",
        )
    save_csv(demoted, BASE / "inventory/models_demoted.csv")

    op_v4 = op_v2.copy()
    promoted_map = {
        (str(r["domain"]), str(r["mode"])): r
        for _, r in selected_df.iterrows()
        if str(r.get("promotion_decision", "")) == "PROMOTE_NOW"
    }

    for (d, m), r in promoted_map.items():
        mask = (op_v4["domain"] == d) & (op_v4["mode"] == m)
        if not mask.any():
            continue
        new_metrics = {
            "precision": float(r["precision"]),
            "recall": float(r["recall"]),
            "specificity": float(r["specificity"]),
            "balanced_accuracy": float(r["balanced_accuracy"]),
            "f1": float(r["f1"]),
            "roc_auc": float(r["roc_auc"]),
            "pr_auc": float(r["pr_auc"]),
            "brier": float(r["brier"]),
        }
        overfit_gap = float(r["overfit_gap_train_val_ba"])
        sec_anom = secondary_anomaly_from_metrics(new_metrics)
        op_v4.loc[mask, "source_campaign"] = "final_honest_improvement_v1"
        op_v4.loc[mask, "model_family"] = str(r["model_family"])
        op_v4.loc[mask, "feature_set_id"] = str(r["feature_set_id"])
        op_v4.loc[mask, "calibration"] = str(r["calibration"])
        op_v4.loc[mask, "threshold_policy"] = str(r["threshold_policy"])
        op_v4.loc[mask, "threshold"] = float(r["threshold"])
        for k, v in new_metrics.items():
            op_v4.loc[mask, k] = v
        op_v4.loc[mask, "quality_label"] = quality_label(new_metrics)
        op_v4.loc[mask, "overfit_gap_train_val_ba"] = overfit_gap
        op_v4.loc[mask, "final_class"] = quality_to_final_class(new_metrics, overfit_gap, sec_anom)

    save_csv(op_v4, OP_V4_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(
        op_v4[op_v4["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])],
        OP_V4_BASE / "tables/hybrid_operational_final_nonchampions.csv",
    )

    save_csv(
        op_v4[["domain", "mode", "source_campaign", "final_class", "quality_label", "overfit_gap_train_val_ba"]],
        OP_V4_BASE / "validation/hybrid_operational_overfit_audit.csv",
    )
    save_csv(
        op_v4[["domain", "mode", "source_campaign"]].assign(note="generalization metrics consolidated from source campaign"),
        OP_V4_BASE / "validation/hybrid_operational_generalization_audit.csv",
    )
    save_csv(
        op_v4[["domain", "mode", "source_campaign"]].assign(note="bootstrap from source campaign"),
        OP_V4_BASE / "bootstrap/hybrid_operational_bootstrap_intervals.csv",
    )
    save_csv(
        op_v4[["domain", "mode", "source_campaign"]].assign(note="ablation from source campaign"),
        OP_V4_BASE / "ablation/hybrid_operational_ablation.csv",
    )
    save_csv(
        op_v4[["domain", "mode", "source_campaign"]].assign(note="stress from source campaign"),
        OP_V4_BASE / "stress/hybrid_operational_stress.csv",
    )

    replacement_rows = []
    for _, r in selected_df.iterrows():
        replacement_rows.append(
            {
                "domain": r.get("domain"),
                "mode": r.get("mode"),
                "old_active_model_id": r.get("active_model_id"),
                "promotion_decision": r.get("promotion_decision"),
                "new_model_family": r.get("model_family"),
                "new_feature_set_id": r.get("feature_set_id"),
                "delta_balanced_accuracy": r.get("delta_balanced_accuracy"),
                "delta_f1": r.get("delta_f1"),
                "delta_pr_auc": r.get("delta_pr_auc"),
                "delta_brier": r.get("delta_brier"),
            }
        )
    save_csv(pd.DataFrame(replacement_rows), OP_V4_BASE / "inventory/v2_to_v4_replacement_map.csv")

    op_report = [
        "# Hybrid Operational Freeze v4 - Summary",
        "",
        "Final honest improvement campaign focused on anxiety/depression/elimination in full and 2_3 modes.",
        "",
        "## Final class counts",
        op_v4["final_class"].value_counts().to_string(),
        "",
        "## Compared slots (old vs new)",
        md_table(comp_df),
    ]
    write_md(OP_V4_BASE / "reports/hybrid_operational_freeze_summary.md", "\n".join(op_report))

    active_v4 = active_v2.copy()
    op_idx = {(r.domain, r.mode): r for r in op_v4.itertuples(index=False)}

    for (d, m), r in promoted_map.items():
        mask = (active_v4["domain"] == d) & (active_v4["mode"] == m)
        if not mask.any():
            continue
        new_model_id = f"{d}__{m}__final_honest_improvement_v1__{r['model_family']}__{r['feature_set_id']}"
        active_v4.loc[mask, "active_model_id"] = new_model_id
        active_v4.loc[mask, "source_line"] = LINE
        active_v4.loc[mask, "source_campaign"] = "final_honest_improvement_v1"
        active_v4.loc[mask, "model_family"] = str(r["model_family"])
        active_v4.loc[mask, "feature_set_id"] = str(r["feature_set_id"])
        active_v4.loc[mask, "config_id"] = str(r["config_id"])
        active_v4.loc[mask, "calibration"] = str(r["calibration"])
        active_v4.loc[mask, "threshold_policy"] = str(r["threshold_policy"])
        active_v4.loc[mask, "threshold"] = float(r["threshold"])
        active_v4.loc[mask, "seed"] = int(r["seed"])
        active_v4.loc[mask, "n_features"] = int(r["n_features"])
        for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
            active_v4.loc[mask, k] = float(r[k])
        active_v4.loc[mask, "overfit_flag"] = "yes" if float(r["overfit_gap_train_val_ba"]) > 0.10 else "no"
        active_v4.loc[mask, "generalization_flag"] = str(r["generalization_ok"]).lower()
        active_v4.loc[mask, "dataset_ease_flag"] = "no"
        active_v4.loc[mask, "notes"] = "final_honest_improvement_v1_replacement"

    def conf_score_from_vals(row: pd.Series, src_class: str, qlabel: str) -> float:
        s = 0.0
        s += 20 * nrm(row["precision"], 0.5, 0.95)
        s += 16 * nrm(row["recall"], 0.5, 0.95)
        s += 22 * nrm(row["balanced_accuracy"], 0.5, 0.98)
        s += 20 * nrm(row["pr_auc"], 0.5, 0.98)
        s += 10 * nrm(0.12 - float(row["brier"]), 0, 0.12)
        s += {"muy_bueno": 10, "bueno": 7, "aceptable": 4, "malo": 0}.get(str(qlabel).lower(), 0)
        s += {
            "ROBUST_PRIMARY": 8,
            "PRIMARY_WITH_CAVEAT": 2,
            "HOLD_FOR_LIMITATION": -8,
            "REJECT_AS_PRIMARY": -12,
        }.get(str(src_class), 0)
        if str(row["overfit_flag"]).lower() == "yes":
            s -= 12
        if str(row["generalization_flag"]).lower() != "yes":
            s -= 10
        if str(row["dataset_ease_flag"]).lower() == "yes":
            s -= 8
        if max(float(row["specificity"]), float(row["roc_auc"]), float(row["pr_auc"])) > 0.98:
            s -= 8
        return round(max(0.0, min(100.0, s)), 1)

    def conf_band(x: float) -> str:
        if x >= 88:
            return "high"
        if x >= 74:
            return "moderate"
        if x >= 62:
            return "low"
        return "limited"

    def operational_class(src_class: str, confidence_band: str) -> str:
        if src_class in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"} or confidence_band == "limited":
            return "ACTIVE_LIMITED_USE"
        if confidence_band == "high":
            return "ACTIVE_HIGH_CONFIDENCE"
        if confidence_band == "moderate":
            return "ACTIVE_MODERATE_CONFIDENCE"
        return "ACTIVE_LOW_CONFIDENCE"

    # Preserve v2 confidence/class for unchanged rows. Recompute only promoted rows.
    for (d, m), _r in promoted_map.items():
        mask = (active_v4["domain"] == d) & (active_v4["mode"] == m)
        if not mask.any():
            continue
        idx = active_v4[mask].index[0]
        row = active_v4.loc[idx]
        op_row = op_idx.get((d, m), None)
        src_class = str(getattr(op_row, "final_class", "HOLD_FOR_LIMITATION"))
        qlabel = str(getattr(op_row, "quality_label", "malo"))
        conf = conf_score_from_vals(row, src_class, qlabel)
        band = conf_band(conf)
        op_class = operational_class(src_class, band)
        caveats: list[str] = []
        if op_class == "ACTIVE_LIMITED_USE":
            caveats.append("limited reliability; escalate to richer mode")
        if str(row["overfit_flag"]) == "yes":
            caveats.append("overfit risk")
        if max(float(row["specificity"]), float(row["roc_auc"]), float(row["pr_auc"])) > 0.98:
            caveats.append("secondary metric anomaly; requires caveat")
        if float(row["precision"]) < 0.80:
            caveats.append("low precision")
        if float(row["recall"]) < 0.70:
            caveats.append("low recall")
        active_v4.loc[idx, "confidence_pct"] = conf
        active_v4.loc[idx, "confidence_band"] = band
        active_v4.loc[idx, "final_operational_class"] = op_class
        active_v4.loc[idx, "operational_caveat"] = "; ".join(caveats) if caveats else "none"
        active_v4.loc[idx, "recommended_for_default_use"] = (
            "yes"
            if op_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"}
            and src_class not in {"HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"}
            else "no"
        )

    save_csv(active_v4, ACTIVE_V4_BASE / "tables/hybrid_active_models_30_modes.csv")
    save_csv(
        active_v4.groupby(["final_operational_class", "confidence_band"], as_index=False).size(),
        ACTIVE_V4_BASE / "tables/hybrid_active_modes_summary.csv",
    )
    save_csv(pd.read_csv(ACTIVE_INPUTS_V2), ACTIVE_V4_BASE / "tables/hybrid_questionnaire_inputs_master.csv")

    active_report = [
        "# Hybrid Active Modes Freeze v4 - Summary",
        "",
        "Final honest improvement campaign focused on full and 2_3 modes.",
        "",
        "## Active class counts",
        active_v4["final_operational_class"].value_counts().to_string(),
        "",
        "## Replaced active rows",
        md_table(
            active_v4[active_v4["source_campaign"].isin(["final_honest_improvement_v1"])][
                [
                    "domain",
                    "mode",
                    "active_model_id",
                    "source_campaign",
                    "feature_set_id",
                    "precision",
                    "recall",
                    "specificity",
                    "balanced_accuracy",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier",
                    "confidence_pct",
                    "confidence_band",
                    "final_operational_class",
                ]
            ]
        ),
    ]
    write_md(ACTIVE_V4_BASE / "reports/hybrid_active_modes_freeze_summary.md", "\n".join(active_report))

    reviewed_ceiling = margin_df[
        (margin_df["domain"].isin(["anxiety", "elimination"]))
        & (margin_df["margin_status"] != "material_candidate")
    ][["domain", "mode", "margin_status", "old_secondary_metric_anomaly_flag", "new_secondary_metric_anomaly_flag"]]

    summary = [
        "# Hybrid Final Honest Improvement v1 - Executive Summary",
        "",
        "Campaign objective: verify real residual margin and only promote replacements with material, honest gains.",
        "",
        "## Focus slots inventory",
        md_table(focus),
        "",
        "## Margin audit",
        md_table(margin_df),
        "",
        "## Deep retrain targets",
        md_table(deep_targets),
        "",
        "## Selection result",
        md_table(selected_df),
        "",
        "## Practical ceiling confirmed (no promotion)",
        md_table(reviewed_ceiling),
    ]
    write_md(BASE / "reports/hybrid_final_honest_improvement_summary.md", "\n".join(summary))

    manifest_files = []
    for p in sorted([x for x in BASE.rglob("*") if x.is_file()]):
        rel = p.relative_to(ROOT).as_posix()
        manifest_files.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": int(p.stat().st_size),
            }
        )

    manifest = {
        "line": LINE,
        "generated_at_utc": now_iso(),
        "focus": {
            "domains": sorted(PRIORITY_DOMAINS),
            "mode_suffix": list(FOCUS_MODE_SUFFIX),
            "source_operational": "data/hybrid_operational_freeze_v2/tables/hybrid_operational_final_champions.csv",
            "source_active": "data/hybrid_active_modes_freeze_v2/tables/hybrid_active_models_30_modes.csv",
        },
        "source_truth_updates": {
            "operational": "data/hybrid_operational_freeze_v4/tables/hybrid_operational_final_champions.csv",
            "active": "data/hybrid_active_modes_freeze_v4/tables/hybrid_active_models_30_modes.csv",
        },
        "stats": {
            "focus_slots": int(len(focus)),
            "deep_targets": int(len(deep_targets)),
            "promoted": int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum()),
        },
        "generated_files": manifest_files,
    }
    (ART / "hybrid_final_honest_improvement_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    op_manifest = {
        "run_id": "hybrid_operational_freeze_v4",
        "base_line": "hybrid_operational_freeze_v2",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_operational_freeze_v4/tables/hybrid_operational_final_champions.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_operational_freeze_v4").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_operational_freeze_v4/hybrid_operational_freeze_v4_manifest.json").write_text(
        json.dumps(op_manifest, indent=2), encoding="utf-8"
    )

    active_manifest = {
        "run_id": "hybrid_active_modes_freeze_v4",
        "base_line": "hybrid_active_modes_freeze_v2",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_active_modes_freeze_v4/tables/hybrid_active_models_30_modes.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_active_modes_freeze_v4").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_active_modes_freeze_v4/hybrid_active_modes_freeze_v4_manifest.json").write_text(
        json.dumps(active_manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
