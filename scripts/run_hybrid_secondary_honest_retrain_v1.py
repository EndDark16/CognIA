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
from sklearn.ensemble import RandomForestClassifier
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

LINE = "hybrid_secondary_honest_retrain_v1"
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

ACTIVE_V3_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v3"
OP_V3_BASE = ROOT / "data" / "hybrid_operational_freeze_v3"

EXPLICIT_PRIORITY_TARGETS = {
    ("depression", "caregiver_1_3"),
    ("depression", "psychologist_1_3"),
}

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20261101
SEARCH_SEEDS = [20270421]
STABILITY_SEEDS = [20270421, 20270439]

RF_CONFIGS: dict[str, dict[str, Any]] = {
    "rf_balanced_subsample_v2": {
        "n_estimators": 140,
        "max_depth": 20,
        "min_samples_split": 6,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    "rf_regularized_v2": {
        "n_estimators": 140,
        "max_depth": 12,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    "rf_precision_guard_v2": {
        "n_estimators": 130,
        "max_depth": 14,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.5,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": 0.9,
    },
}

CAL_METHODS = ["none", "isotonic"]
THRESH_POLICIES = ["balanced", "precision_min_recall"]


@dataclass
class RetrainTarget:
    domain: str
    mode: str
    role: str
    active_model_id: str
    source_campaign: str
    feature_set_id: str
    overfit_flag: str
    secondary_gt_098: str
    shortcut_dominance_flag: str
    best_single_feature: str


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
        OP_V3_BASE / "tables",
        OP_V3_BASE / "reports",
        OP_V3_BASE / "inventory",
        OP_V3_BASE / "validation",
        OP_V3_BASE / "bootstrap",
        OP_V3_BASE / "ablation",
        OP_V3_BASE / "stress",
        ACTIVE_V3_BASE / "tables",
        ACTIVE_V3_BASE / "reports",
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
        if m["recall"] < 0.68 or m["balanced_accuracy"] < 0.80:
            return -1e9
        return 0.62 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.12 * m["pr_auc"] + 0.06 * m["recall"]
    if policy == "recall_constrained":
        if m["recall"] < 0.70:
            return -1e9
        return 0.48 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["pr_auc"]
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
    return 0.40 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["recall"] - 0.08 * m["brier"]


def quality_label(m: dict[str, float]) -> str:
    if (
        m["precision"] >= 0.84
        and m["recall"] >= 0.75
        and m["balanced_accuracy"] >= 0.88
        and m["pr_auc"] >= 0.84
        and m["brier"] <= 0.065
    ):
        return "bueno"
    if (
        m["precision"] >= 0.78
        and m["recall"] >= 0.68
        and m["balanced_accuracy"] >= 0.84
        and m["pr_auc"] >= 0.78
        and m["brier"] <= 0.08
    ):
        return "aceptable"
    return "malo"


def secondary_max_metric(m: dict[str, float]) -> float:
    return float(max(m["specificity"], m["roc_auc"], m["pr_auc"]))


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


def fit_imputer_and_matrix(
    tr_df: pd.DataFrame, va_df: pd.DataFrame, ho_df: pd.DataFrame, features: list[str]
) -> tuple[SimpleImputer, np.ndarray, np.ndarray, np.ndarray]:
    x_tr = tr_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_va = va_df[features].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = ho_df[features].copy().apply(pd.to_numeric, errors="coerce")
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
        lr = LogisticRegression(max_iter=200, solver="lbfgs")
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


def quality_to_final_class(q: str, overfit_gap: float) -> str:
    if q in {"muy_bueno", "bueno"} and float(overfit_gap) <= 0.10:
        return "ROBUST_PRIMARY"
    if q == "aceptable":
        return "PRIMARY_WITH_CAVEAT"
    if q == "malo":
        return "HOLD_FOR_LIMITATION"
    return "REJECT_AS_PRIMARY"


def build_suspicion_inventory(
    active_v2: pd.DataFrame,
    reg_map: dict[tuple[str, str, str], list[str]],
    df_data: pd.DataFrame,
    split_ids: dict[str, dict[str, list[str]]],
) -> pd.DataFrame:
    rows = []
    for _, r in active_v2.iterrows():
        if str(r["domain"]) == "conduct":
            continue
        sec_max = max(float(r["specificity"]), float(r["roc_auc"]), float(r["pr_auc"]))
        sec_gt = sec_max > 0.98
        overfit_yes = str(r["overfit_flag"]).lower() == "yes"
        if not sec_gt and not overfit_yes:
            continue
        feat_list, feat_status = get_feature_list(r, reg_map)
        hold_df = subset_by_ids(df_data, split_ids[str(r["domain"])]["holdout"])
        target_col = f"target_domain_{r['domain']}_final"
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
        shortcut_flag = pd.notna(shortcut_gap) and shortcut_gap >= 0.05

        rows.append(
            {
                "domain": r["domain"],
                "mode": r["mode"],
                "role": r["role"],
                "active_model_id": r["active_model_id"],
                "source_campaign": r["source_campaign"],
                "feature_set_id": r["feature_set_id"],
                "final_operational_class": r["final_operational_class"],
                "overfit_flag": r["overfit_flag"],
                "generalization_flag": r["generalization_flag"],
                "operational_caveat": r["operational_caveat"],
                "secondary_max_metric": sec_max,
                "secondary_gt_098": "yes" if sec_gt else "no",
                "precision": float(r["precision"]),
                "recall": float(r["recall"]),
                "specificity": float(r["specificity"]),
                "balanced_accuracy": model_ba,
                "f1": float(r["f1"]),
                "roc_auc": float(r["roc_auc"]),
                "pr_auc": float(r["pr_auc"]),
                "brier": float(r["brier"]),
                "feature_audit_status": feat_status,
                "best_single_feature": shortcut["best_single_feature"],
                "best_single_rule": shortcut["best_single_rule"],
                "best_single_feature_ba": shortcut_ba,
                "shortcut_gap_vs_model_ba": shortcut_gap,
                "shortcut_dominance_flag": "yes" if shortcut_flag else "no",
            }
        )

    out = pd.DataFrame(rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    return out


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
        "stability_pruned_subset",
        "precision_oriented_subset",
        "compact_subset",
    ]:
        key = (domain, mode, fs)
        if key in reg_map and reg_map[key]:
            if fs not in cands and len(reg_map[key]) <= 35:
                cands[fs] = list(reg_map[key])

    return cands


def build_retrain_targets(suspicion: pd.DataFrame) -> list[RetrainTarget]:
    targets: list[RetrainTarget] = []
    for _, r in suspicion.iterrows():
        key = (str(r["domain"]), str(r["mode"]))
        retrain = False
        if key in EXPLICIT_PRIORITY_TARGETS:
            retrain = True
        elif (
            str(r["source_campaign"]) == "rebuild_v2"
            and str(r["secondary_gt_098"]) == "yes"
            and str(r["shortcut_dominance_flag"]) == "yes"
            and str(r["domain"]) != "conduct"
        ):
            retrain = True
        if not retrain:
            continue
        targets.append(
            RetrainTarget(
                domain=str(r["domain"]),
                mode=str(r["mode"]),
                role=str(r["role"]),
                active_model_id=str(r["active_model_id"]),
                source_campaign=str(r["source_campaign"]),
                feature_set_id=str(r["feature_set_id"]),
                overfit_flag=str(r["overfit_flag"]),
                secondary_gt_098=str(r["secondary_gt_098"]),
                shortcut_dominance_flag=str(r["shortcut_dominance_flag"]),
                best_single_feature=str(r["best_single_feature"]),
            )
        )
    return targets


def main() -> None:
    ensure_dirs()

    active_v2 = pd.read_csv(ACTIVE_V2)
    op_v2 = pd.read_csv(OP_V2)
    fe_reg = pd.read_csv(V2_FE_REGISTRY)
    fe_reg["feature_list"] = fe_reg["feature_list_pipe"].fillna("").apply(lambda s: [f for f in str(s).split("|") if f])
    reg_map = {
        (str(r.domain), str(r.mode), str(r.feature_set_id)): list(r.feature_list)
        for r in fe_reg.itertuples(index=False)
    }

    df_data = pd.read_csv(V2_DATASET)
    split_ids, split_registry = build_split_registry(df_data)
    save_csv(split_registry, BASE / "validation/split_registry.csv")

    # Duplicate audit (global)
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

    suspicion = build_suspicion_inventory(active_v2, reg_map, df_data, split_ids)
    save_csv(suspicion, BASE / "tables/non_conduct_suspect_inventory.csv")

    retrain_targets = build_retrain_targets(suspicion)
    save_csv(pd.DataFrame([t.__dict__ for t in retrain_targets]), BASE / "tables/retrain_targets.csv")

    trial_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []

    for t in retrain_targets:
        domain, mode = t.domain, t.mode
        target_col = f"target_domain_{domain}_final"
        split = split_ids[domain]
        tr_df = subset_by_ids(df_data, split["train"])
        va_df = subset_by_ids(df_data, split["val"])
        ho_df = subset_by_ids(df_data, split["holdout"])
        y_tr = tr_df[target_col].astype(int).to_numpy()
        y_va = va_df[target_col].astype(int).to_numpy()
        y_ho = ho_df[target_col].astype(int).to_numpy()

        old_row = active_v2[(active_v2["domain"] == domain) & (active_v2["mode"] == mode)].iloc[0]
        old_ba = float(old_row["balanced_accuracy"])

        cand_sets = candidate_feature_sets(domain, mode, t.feature_set_id, t.best_single_feature, reg_map)
        if not cand_sets:
            selected_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "role": t.role,
                    "active_model_id": t.active_model_id,
                    "source_campaign": t.source_campaign,
                    "feature_set_id_old": t.feature_set_id,
                    "promotion_decision": "HOLD_FOR_LIMITATION",
                    "hold_reason": "por_confirmar_missing_feature_set",
                }
            )
            continue

        local_trials: list[dict[str, Any]] = []

        for fs_id, feats in cand_sets.items():
            if not feats:
                continue
            _, x_tr, x_va, x_ho = fit_imputer_and_matrix(tr_df, va_df, ho_df, feats)
            for cfg_id in RF_CONFIGS:
                for seed in SEARCH_SEEDS:
                    model = build_rf(cfg_id, seed)
                    model.fit(x_tr, y_tr)
                    p_tr_raw = np.clip(model.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
                    p_va_raw = np.clip(model.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
                    p_ho_raw = np.clip(model.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
                    for cal in CAL_METHODS:
                        p_tr, p_va, p_ho = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, cal)
                        for pol in THRESH_POLICIES:
                            thr, thr_score = choose_threshold(pol, y_va, p_va)
                            m_tr = compute_metrics(y_tr, p_tr, thr)
                            m_va = compute_metrics(y_va, p_va, thr)
                            m_ho = compute_metrics(y_ho, p_ho, thr)
                            overfit_gap = float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                            gen_gap = float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]))
                            q = quality_label(m_ho)
                            sec_max = secondary_max_metric(m_ho)
                            val_sel = (
                                0.46 * m_va["balanced_accuracy"]
                                + 0.24 * m_va["precision"]
                                + 0.18 * m_va["pr_auc"]
                                + 0.12 * m_va["recall"]
                                - 0.12 * max(0.0, overfit_gap)
                                - 0.08 * max(0.0, gen_gap)
                            )
                            local_trials.append(
                                {
                                    "domain": domain,
                                    "mode": mode,
                                    "role": t.role,
                                    "feature_set_id": fs_id,
                                    "config_id": cfg_id,
                                    "model_family": "rf",
                                    "calibration": cal,
                                    "threshold_policy": pol,
                                    "threshold": float(thr),
                                    "seed": int(seed),
                                    "n_features": int(len(feats)),
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
                                    "overfit_warning": "yes" if overfit_gap > 0.10 else "no",
                                    "quality_label": q,
                                    "ranking_score": ranking_score(m_ho),
                                    "val_selection_score": float(val_sel),
                                    "threshold_policy_score": float(thr_score),
                                    "secondary_max_metric": sec_max,
                                    "secondary_cap_ok": "yes" if sec_max <= 0.98 else "no",
                                }
                            )

        if not local_trials:
            selected_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "role": t.role,
                    "active_model_id": t.active_model_id,
                    "source_campaign": t.source_campaign,
                    "feature_set_id_old": t.feature_set_id,
                    "promotion_decision": "HOLD_FOR_LIMITATION",
                    "hold_reason": "no_trials_generated",
                }
            )
            continue

        local_df = pd.DataFrame(local_trials)
        trial_rows.extend(local_trials)

        winner = (
            local_df.sort_values(
                ["val_selection_score", "val_balanced_accuracy", "val_precision", "n_features"],
                ascending=[False, False, False, True],
            )
            .iloc[0]
            .copy()
        )

        winner_feats = [f for f in str(winner["feature_list_pipe"]).split("|") if f]
        hold_df = ho_df.copy()
        shortcut_new = (
            best_single_feature_rule(hold_df, target_col, winner_feats)
            if winner_feats
            else {"best_single_feature": "", "best_single_rule": "", "best_single_feature_ba": np.nan}
        )
        winner["new_best_single_feature"] = shortcut_new["best_single_feature"]
        winner["new_best_single_rule"] = shortcut_new["best_single_rule"]
        winner["new_best_single_feature_ba"] = shortcut_new["best_single_feature_ba"]
        winner["new_shortcut_gap_vs_model_ba"] = (
            float(shortcut_new["best_single_feature_ba"] - float(winner["balanced_accuracy"]))
            if pd.notna(shortcut_new["best_single_feature_ba"])
            else np.nan
        )

        pass_generalization = (
            float(winner["overfit_gap_train_val_ba"]) <= 0.10
            and float(winner["generalization_gap_val_holdout_ba"]) <= 0.08
            and float(winner["balanced_accuracy"]) >= max(0.82, old_ba - 0.02)
            and float(winner["precision"]) >= 0.75
            and float(winner["recall"]) >= 0.68
            and float(winner["pr_auc"]) >= 0.76
        )
        secondary_gate = True
        if str(t.secondary_gt_098).lower() == "yes":
            secondary_gate = bool(
                float(winner["secondary_max_metric"]) <= 0.98
                and (
                    pd.isna(winner["new_shortcut_gap_vs_model_ba"])
                    or float(winner["new_shortcut_gap_vs_model_ba"]) <= 0.05
                )
            )

        promote = bool(pass_generalization and secondary_gate)
        winner["promotion_decision"] = "PROMOTE_NOW" if promote else "HOLD_FOR_LIMITATION"
        winner["generalization_ok"] = "yes" if pass_generalization else "no"
        winner["secondary_gate_ok"] = "yes" if secondary_gate else "no"

        _, x_tr, x_va, x_ho = fit_imputer_and_matrix(tr_df, va_df, ho_df, winner_feats)
        model0 = build_rf(str(winner["config_id"]), int(winner["seed"]))
        model0.fit(x_tr, y_tr)
        p_ho_raw = np.clip(model0.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
        p_tr_raw = np.clip(model0.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
        p_va_raw = np.clip(model0.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
        _, _, p_ho_cal = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, str(winner["calibration"]))
        base_thr = float(winner["threshold"])
        m0 = compute_metrics(y_ho, p_ho_cal, base_thr)

        for s in STABILITY_SEEDS:
            ms = build_rf(str(winner["config_id"]), int(s))
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
        for _ in range(80):
            sidx = rng.choice(idx, size=len(idx), replace=True)
            yb = y_ho[sidx]
            pb = p_ho_cal[sidx]
            mb = compute_metrics(yb, pb, base_thr)
            bootstrap_rows.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "metric": "balanced_accuracy",
                    "value": mb["balanced_accuracy"],
                }
            )

        if hasattr(model0, "feature_importances_"):
            imp_rank = pd.Series(model0.feature_importances_, index=winner_feats).sort_values(ascending=False)
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
                feats_ab = [f for f in winner_feats if f not in drop]
                if not feats_ab:
                    continue
                _, xtr_ab, xva_ab, xho_ab = fit_imputer_and_matrix(tr_df, va_df, ho_df, feats_ab)
                mab = build_rf(str(winner["config_id"]), int(winner["seed"]))
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

        x_ho_raw_df = ho_df[winner_feats].copy().apply(pd.to_numeric, errors="coerce")
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

        winner_row = {
            "domain": domain,
            "mode": mode,
            "role": t.role,
            "active_model_id": t.active_model_id,
            "source_campaign": t.source_campaign,
            "feature_set_id_old": t.feature_set_id,
            **winner.to_dict(),
            "old_overfit_flag": t.overfit_flag,
            "old_secondary_gt_098": t.secondary_gt_098,
            "old_shortcut_dominance_flag": t.shortcut_dominance_flag,
            "old_best_single_feature": t.best_single_feature,
        }
        selected_rows.append(winner_row)

    trial_df = pd.DataFrame(trial_rows)
    selected_df = pd.DataFrame(selected_rows)
    save_csv(trial_df, BASE / "trials/secondary_honest_retrain_trials.csv")
    save_csv(selected_df, BASE / "tables/secondary_honest_retrain_selected_models.csv")
    save_csv(pd.DataFrame(stability_rows), BASE / "stability/secondary_honest_seed_stability.csv")
    save_csv(pd.DataFrame(bootstrap_rows), BASE / "bootstrap/secondary_honest_bootstrap_intervals.csv")
    save_csv(pd.DataFrame(ablation_rows), BASE / "ablation/secondary_honest_ablation.csv")
    save_csv(pd.DataFrame(stress_rows), BASE / "stress/secondary_honest_stress.csv")

    comp_rows = []
    for _, r in selected_df.iterrows():
        old = active_v2[(active_v2["domain"] == r["domain"]) & (active_v2["mode"] == r["mode"])].iloc[0]
        comp_rows.append(
            {
                "domain": r["domain"],
                "mode": r["mode"],
                "active_model_id": old["active_model_id"],
                "source_campaign": old["source_campaign"],
                "feature_set_id_old": old["feature_set_id"],
                "config_id_old": old["config_id"],
                "calibration_old": old["calibration"],
                "threshold_policy_old": old["threshold_policy"],
                "threshold_old": float(old["threshold"]),
                "seed_old": int(old["seed"]),
                "n_features_old": int(old["n_features"]),
                "precision_old": float(old["precision"]),
                "recall_old": float(old["recall"]),
                "specificity_old": float(old["specificity"]),
                "balanced_accuracy_old": float(old["balanced_accuracy"]),
                "f1_old": float(old["f1"]),
                "roc_auc_old": float(old["roc_auc"]),
                "pr_auc_old": float(old["pr_auc"]),
                "brier_old": float(old["brier"]),
                "overfit_flag_old": str(old["overfit_flag"]),
                "generalization_flag_old": str(old["generalization_flag"]),
                "feature_set_id_new": r.get("feature_set_id", ""),
                "config_id_new": r.get("config_id", ""),
                "calibration_new": r.get("calibration", ""),
                "threshold_policy_new": r.get("threshold_policy", ""),
                "threshold_new": float(r.get("threshold", np.nan)) if pd.notna(r.get("threshold", np.nan)) else np.nan,
                "seed_new": int(r.get("seed", 0)) if pd.notna(r.get("seed", np.nan)) else np.nan,
                "n_features_new": int(r.get("n_features", 0)) if pd.notna(r.get("n_features", np.nan)) else np.nan,
                "precision_new": float(r.get("precision", np.nan)),
                "recall_new": float(r.get("recall", np.nan)),
                "specificity_new": float(r.get("specificity", np.nan)),
                "balanced_accuracy_new": float(r.get("balanced_accuracy", np.nan)),
                "f1_new": float(r.get("f1", np.nan)),
                "roc_auc_new": float(r.get("roc_auc", np.nan)),
                "pr_auc_new": float(r.get("pr_auc", np.nan)),
                "brier_new": float(r.get("brier", np.nan)),
                "quality_label_new": r.get("quality_label", ""),
                "overfit_gap_train_val_ba_new": float(r.get("overfit_gap_train_val_ba", np.nan)),
                "generalization_gap_val_holdout_ba_new": float(r.get("generalization_gap_val_holdout_ba", np.nan)),
                "secondary_max_metric_new": float(r.get("secondary_max_metric", np.nan)),
                "secondary_cap_ok": r.get("secondary_cap_ok", ""),
                "generalization_ok": r.get("generalization_ok", ""),
                "promotion_decision": r.get("promotion_decision", "HOLD_FOR_LIMITATION"),
                "delta_precision": float(r.get("precision", np.nan)) - float(old["precision"]),
                "delta_recall": float(r.get("recall", np.nan)) - float(old["recall"]),
                "delta_specificity": float(r.get("specificity", np.nan)) - float(old["specificity"]),
                "delta_balanced_accuracy": float(r.get("balanced_accuracy", np.nan)) - float(old["balanced_accuracy"]),
                "delta_f1": float(r.get("f1", np.nan)) - float(old["f1"]),
                "delta_roc_auc": float(r.get("roc_auc", np.nan)) - float(old["roc_auc"]),
                "delta_pr_auc": float(r.get("pr_auc", np.nan)) - float(old["pr_auc"]),
                "delta_brier": float(r.get("brier", np.nan)) - float(old["brier"]),
            }
        )

    comp_df = pd.DataFrame(comp_rows)
    save_csv(comp_df, BASE / "tables/secondary_old_vs_new_comparison.csv")

    demoted = comp_df[comp_df["promotion_decision"] == "PROMOTE_NOW"].copy()
    if not demoted.empty:
        demoted = demoted.assign(
            status="demoted_from_primary_due_overfit_or_secondary_metric_suspicion",
            reason="replaced_by_secondary_honest_retrain_v1",
        )
    save_csv(demoted, BASE / "inventory/models_demoted.csv")

    op_v3 = op_v2.copy()
    promoted_map = {
        (str(r["domain"]), str(r["mode"])): r
        for _, r in selected_df.iterrows()
        if str(r.get("promotion_decision", "")) == "PROMOTE_NOW"
    }

    for (d, m), r in promoted_map.items():
        mask = (op_v3["domain"] == d) & (op_v3["mode"] == m)
        if not mask.any():
            continue
        op_v3.loc[mask, "source_campaign"] = "secondary_honest_retrain_v1"
        op_v3.loc[mask, "model_family"] = "rf"
        op_v3.loc[mask, "feature_set_id"] = r["feature_set_id"]
        op_v3.loc[mask, "calibration"] = r["calibration"]
        op_v3.loc[mask, "threshold_policy"] = r["threshold_policy"]
        op_v3.loc[mask, "threshold"] = float(r["threshold"])
        op_v3.loc[mask, "precision"] = float(r["precision"])
        op_v3.loc[mask, "recall"] = float(r["recall"])
        op_v3.loc[mask, "specificity"] = float(r["specificity"])
        op_v3.loc[mask, "balanced_accuracy"] = float(r["balanced_accuracy"])
        op_v3.loc[mask, "f1"] = float(r["f1"])
        op_v3.loc[mask, "roc_auc"] = float(r["roc_auc"])
        op_v3.loc[mask, "pr_auc"] = float(r["pr_auc"])
        op_v3.loc[mask, "brier"] = float(r["brier"])
        op_v3.loc[mask, "quality_label"] = str(r["quality_label"])
        op_v3.loc[mask, "overfit_gap_train_val_ba"] = float(r["overfit_gap_train_val_ba"])
        op_v3.loc[mask, "final_class"] = quality_to_final_class(str(r["quality_label"]), float(r["overfit_gap_train_val_ba"]))

    save_csv(op_v3, OP_V3_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(op_v3[op_v3["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])], OP_V3_BASE / "tables/hybrid_operational_final_nonchampions.csv")

    overfit_rows = []
    for r in op_v3.itertuples(index=False):
        overfit_rows.append(
            {
                "domain": r.domain,
                "mode": r.mode,
                "source_campaign": r.source_campaign,
                "overfit_gap_train_val_ba": float(r.overfit_gap_train_val_ba),
                "overfit_flag": "yes" if float(r.overfit_gap_train_val_ba) > 0.10 else "no",
            }
        )
    save_csv(pd.DataFrame(overfit_rows), OP_V3_BASE / "validation/hybrid_operational_overfit_audit.csv")
    save_csv(
        op_v3[["domain", "mode", "source_campaign"]].assign(note="generalization metrics consolidated from source campaign"),
        OP_V3_BASE / "validation/hybrid_operational_generalization_audit.csv",
    )
    save_csv(
        op_v3[["domain", "mode", "source_campaign"]].assign(note="bootstrap from source campaign"),
        OP_V3_BASE / "bootstrap/hybrid_operational_bootstrap_intervals.csv",
    )
    save_csv(
        op_v3[["domain", "mode", "source_campaign"]].assign(note="ablation from source campaign"),
        OP_V3_BASE / "ablation/hybrid_operational_ablation.csv",
    )
    save_csv(
        op_v3[["domain", "mode", "source_campaign"]].assign(note="stress from source campaign"),
        OP_V3_BASE / "stress/hybrid_operational_stress.csv",
    )

    save_csv(
        comp_df[[
            "domain",
            "mode",
            "active_model_id",
            "promotion_decision",
            "feature_set_id_new",
            "delta_precision",
            "delta_recall",
            "delta_balanced_accuracy",
            "delta_pr_auc",
            "delta_brier",
        ]],
        OP_V3_BASE / "inventory/v2_to_v3_replacement_map.csv",
    )

    op_report = [
        "# Hybrid Operational Freeze v3 - Summary",
        "",
        "Targeted secondary audit/retrain over freeze_v2 (Conduct preserved).",
        "",
        "## Final class counts",
        op_v3["final_class"].value_counts().to_string(),
        "",
        "## Retrained comparison",
        md_table(comp_df[[
            "domain",
            "mode",
            "promotion_decision",
            "precision_old",
            "precision_new",
            "balanced_accuracy_old",
            "balanced_accuracy_new",
            "roc_auc_old",
            "roc_auc_new",
            "pr_auc_old",
            "pr_auc_new",
        ]]),
    ]
    write_md(OP_V3_BASE / "reports/hybrid_operational_freeze_summary.md", "\n".join(op_report))

    active_v3 = active_v2.copy()
    op_idx = {(r.domain, r.mode): r for r in op_v3.itertuples(index=False)}

    for (d, m), r in promoted_map.items():
        mask = (active_v3["domain"] == d) & (active_v3["mode"] == m)
        if not mask.any():
            continue
        active_v3.loc[mask, "active_model_id"] = f"{d}__{m}__secondary_honest_retrain_v1__rf__{r['feature_set_id']}"
        active_v3.loc[mask, "source_line"] = "hybrid_secondary_honest_retrain_v1"
        active_v3.loc[mask, "source_campaign"] = "secondary_honest_retrain_v1"
        active_v3.loc[mask, "model_family"] = "rf"
        active_v3.loc[mask, "feature_set_id"] = r["feature_set_id"]
        active_v3.loc[mask, "config_id"] = r["config_id"]
        active_v3.loc[mask, "calibration"] = r["calibration"]
        active_v3.loc[mask, "threshold_policy"] = r["threshold_policy"]
        active_v3.loc[mask, "threshold"] = float(r["threshold"])
        active_v3.loc[mask, "seed"] = int(r["seed"])
        active_v3.loc[mask, "n_features"] = int(r["n_features"])
        active_v3.loc[mask, "precision"] = float(r["precision"])
        active_v3.loc[mask, "recall"] = float(r["recall"])
        active_v3.loc[mask, "specificity"] = float(r["specificity"])
        active_v3.loc[mask, "balanced_accuracy"] = float(r["balanced_accuracy"])
        active_v3.loc[mask, "f1"] = float(r["f1"])
        active_v3.loc[mask, "roc_auc"] = float(r["roc_auc"])
        active_v3.loc[mask, "pr_auc"] = float(r["pr_auc"])
        active_v3.loc[mask, "brier"] = float(r["brier"])
        active_v3.loc[mask, "overfit_flag"] = "yes" if float(r["overfit_gap_train_val_ba"]) > 0.10 else "no"
        active_v3.loc[mask, "generalization_flag"] = str(r["generalization_ok"]).lower()
        active_v3.loc[mask, "dataset_ease_flag"] = "no"
        active_v3.loc[mask, "notes"] = "secondary_honest_retrain_v1_replacement"

    src_class = []
    qlabels = []
    for r in active_v3.itertuples(index=False):
        k = (r.domain, r.mode)
        src_class.append(getattr(op_idx[k], "final_class", "HOLD_FOR_LIMITATION"))
        qlabels.append(getattr(op_idx[k], "quality_label", "malo"))
    active_v3["src_class_v3"] = src_class
    active_v3["quality_label_v3"] = qlabels

    def nrm(x: float, lo: float, hi: float) -> float:
        x = float(x)
        if x <= lo:
            return 0.0
        if x >= hi:
            return 1.0
        return (x - lo) / (hi - lo)

    def conf_score(row: pd.Series) -> float:
        s = 0.0
        s += 18 * nrm(row["precision"], 0.5, 0.95)
        s += 14 * nrm(row["recall"], 0.5, 0.95)
        s += 22 * nrm(row["balanced_accuracy"], 0.5, 0.98)
        s += 22 * nrm(row["pr_auc"], 0.5, 0.98)
        s += 10 * nrm(0.12 - float(row["brier"]), 0, 0.12)
        s += {"muy_bueno": 10, "bueno": 7, "aceptable": 4, "malo": 0}.get(str(row["quality_label_v3"]).lower(), 0)
        s += {
            "ROBUST_PRIMARY": 8,
            "PRIMARY_WITH_CAVEAT": 2,
            "HOLD_FOR_LIMITATION": -8,
            "SUSPECT_EASY_DATASET_NEEDS_CAUTION": -4,
            "REJECT_AS_PRIMARY": -10,
        }.get(str(row["src_class_v3"]), 0)
        if str(row["overfit_flag"]).lower() == "yes":
            s -= 12
        if str(row["generalization_flag"]).lower() == "no":
            s -= 10
        if str(row["dataset_ease_flag"]).lower() == "yes":
            s -= 8
        return round(max(0.0, min(100.0, s)), 1)

    def conf_band(x: float) -> str:
        if x >= 85:
            return "high"
        if x >= 70:
            return "moderate"
        if x >= 55:
            return "low"
        return "limited"

    active_v3["confidence_pct"] = active_v3.apply(conf_score, axis=1)
    active_v3["confidence_band"] = active_v3["confidence_pct"].apply(conf_band)

    def operational_class(row: pd.Series) -> str:
        if row["src_class_v3"] == "HOLD_FOR_LIMITATION" or row["confidence_band"] == "limited":
            return "ACTIVE_LIMITED_USE"
        if row["dataset_ease_flag"] == "yes" and row["confidence_band"] == "high":
            return "ACTIVE_MODERATE_CONFIDENCE"
        if row["confidence_band"] == "high":
            return "ACTIVE_HIGH_CONFIDENCE"
        if row["confidence_band"] == "moderate":
            return "ACTIVE_MODERATE_CONFIDENCE"
        return "ACTIVE_LOW_CONFIDENCE"

    active_v3["final_operational_class"] = active_v3.apply(operational_class, axis=1)

    caveats = []
    recs = []
    for r in active_v3.itertuples(index=False):
        c = []
        if r.final_operational_class == "ACTIVE_LIMITED_USE":
            c.append("limited reliability; escalate to richer mode")
        if r.overfit_flag == "yes":
            c.append("overfit risk")
        if r.dataset_ease_flag == "yes":
            c.append("possible easy-dataset inflation")
        if float(r.precision) < 0.80:
            c.append("low precision")
        if float(r.recall) < 0.70:
            c.append("low recall")
        if "1_3" in str(r.mode) and r.final_operational_class in {"ACTIVE_LOW_CONFIDENCE", "ACTIVE_LIMITED_USE"}:
            c.append("short mode fragile")
        caveats.append("; ".join(c) if c else "none")
        recs.append("yes" if r.final_operational_class in {"ACTIVE_HIGH_CONFIDENCE", "ACTIVE_MODERATE_CONFIDENCE"} else "no")

    active_v3["operational_caveat"] = caveats
    active_v3["recommended_for_default_use"] = recs
    active_v3 = active_v3.drop(columns=["src_class_v3", "quality_label_v3"])

    save_csv(active_v3, ACTIVE_V3_BASE / "tables/hybrid_active_models_30_modes.csv")
    save_csv(
        active_v3.groupby(["final_operational_class", "confidence_band"], as_index=False).size(),
        ACTIVE_V3_BASE / "tables/hybrid_active_modes_summary.csv",
    )
    save_csv(pd.read_csv(ACTIVE_INPUTS_V2), ACTIVE_V3_BASE / "tables/hybrid_questionnaire_inputs_master.csv")

    active_report = [
        "# Hybrid Active Modes Freeze v3 - Summary",
        "",
        "Targeted secondary audit/retrain over freeze_v2 with contract-preserving replacements only where promoted.",
        "",
        "## Active class counts",
        active_v3["final_operational_class"].value_counts().to_string(),
        "",
        "## Replaced active rows",
        md_table(
            active_v3[active_v3["source_campaign"].isin(["secondary_honest_retrain_v1"])][
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
                    "final_operational_class",
                ]
            ]
        ),
    ]
    write_md(ACTIVE_V3_BASE / "reports/hybrid_active_modes_freeze_summary.md", "\n".join(active_report))

    summary = [
        "# Hybrid Secondary Honest Retrain v1 - Executive Summary",
        "",
        "Focused on remaining suspicious slots after Conduct retrain (priority: depression short modes).",
        "",
        "## Suspicion inventory (outside conduct)",
        md_table(
            suspicion[
                [
                    "domain",
                    "mode",
                    "source_campaign",
                    "secondary_max_metric",
                    "secondary_gt_098",
                    "overfit_flag",
                    "shortcut_dominance_flag",
                    "best_single_feature",
                    "best_single_feature_ba",
                    "feature_audit_status",
                ]
            ]
        ),
        "",
        "## Retrain targets",
        md_table(pd.DataFrame([t.__dict__ for t in retrain_targets])),
        "",
        "## Selection result",
        md_table(
            selected_df[
                [
                    "domain",
                    "mode",
                    "feature_set_id",
                    "config_id",
                    "calibration",
                    "threshold_policy",
                    "threshold",
                    "precision",
                    "recall",
                    "specificity",
                    "balanced_accuracy",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier",
                    "quality_label",
                    "secondary_max_metric",
                    "secondary_cap_ok",
                    "generalization_ok",
                    "promotion_decision",
                ]
            ]
        ),
    ]
    write_md(BASE / "reports/hybrid_secondary_honest_retrain_summary.md", "\n".join(summary))

    demotion_report = [
        "# Secondary Demotion Decisions",
        "",
        "Legacy slots replaced in v3 are demoted with explicit reason.",
        "",
        md_table(demoted),
    ]
    write_md(BASE / "reports/secondary_demotion_decision.md", "\n".join(demotion_report))

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
        "priority_targets": sorted([f"{d}/{m}" for d, m in EXPLICIT_PRIORITY_TARGETS]),
        "source_truth_updates": {
            "operational": "data/hybrid_operational_freeze_v3/tables/hybrid_operational_final_champions.csv",
            "active": "data/hybrid_active_modes_freeze_v3/tables/hybrid_active_models_30_modes.csv",
        },
        "generated_files": manifest_files,
    }
    (ART / "hybrid_secondary_honest_retrain_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    op_manifest = {
        "run_id": "hybrid_operational_freeze_v3",
        "base_line": "hybrid_operational_freeze_v2",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_operational_freeze_v3/tables/hybrid_operational_final_champions.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_operational_freeze_v3").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_operational_freeze_v3/hybrid_operational_freeze_v3_manifest.json").write_text(
        json.dumps(op_manifest, indent=2), encoding="utf-8"
    )

    active_manifest = {
        "run_id": "hybrid_active_modes_freeze_v3",
        "base_line": "hybrid_active_modes_freeze_v2",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df.get("promotion_decision", pd.Series([], dtype=str)) == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_active_modes_freeze_v3/tables/hybrid_active_models_30_modes.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_active_modes_freeze_v3").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_active_modes_freeze_v3/hybrid_active_modes_freeze_v3_manifest.json").write_text(
        json.dumps(active_manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
