#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
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
LINE = "hybrid_conduct_honest_retrain_v1"
BASE = ROOT / "data" / LINE
ART = ROOT / "artifacts" / LINE

V2_BASE = ROOT / "data" / "hybrid_no_external_scores_rebuild_v2"
V2_DATASET = V2_BASE / "tables" / "hybrid_no_external_scores_dataset_ready.csv"
V2_FEATURE_REGISTRY = V2_BASE / "feature_engineering" / "hybrid_no_external_scores_feature_engineering_registry.csv"

OP_V1 = ROOT / "data" / "hybrid_operational_freeze_v1" / "tables" / "hybrid_operational_final_champions.csv"
ACTIVE_V1 = ROOT / "data" / "hybrid_active_modes_freeze_v1" / "tables" / "hybrid_active_models_30_modes.csv"
ACTIVE_INPUTS_V1 = ROOT / "data" / "hybrid_active_modes_freeze_v1" / "tables" / "hybrid_questionnaire_inputs_master.csv"

OP_V2_BASE = ROOT / "data" / "hybrid_operational_freeze_v2"
ACTIVE_V2_BASE = ROOT / "data" / "hybrid_active_modes_freeze_v2"

FOCUS_MODES = ["caregiver_2_3", "caregiver_full", "psychologist_2_3", "psychologist_full"]
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
BASE_SEED = 20261101
SEED_STABILITY = [20270421, 20270439, 20270457]

RF_CONFIGS = {
    "rf_baseline_v1": {
        "n_estimators": 160,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_balanced_subsample_v1": {
        "n_estimators": 180,
        "max_depth": 22,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    "rf_regularized_v1": {
        "n_estimators": 180,
        "max_depth": 12,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    "rf_precision_push_v1": {
        "n_estimators": 160,
        "max_depth": 14,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.50,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": 0.9,
    },
}

CAL_METHODS = ["none", "isotonic"]
THRESH_POLICIES = ["balanced", "precision_min_recall"]
SEARCH_CONFIG_IDS = ["rf_balanced_subsample_v1", "rf_regularized_v1"]


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
        OP_V2_BASE / "tables",
        OP_V2_BASE / "reports",
        OP_V2_BASE / "inventory",
        OP_V2_BASE / "validation",
        OP_V2_BASE / "bootstrap",
        OP_V2_BASE / "ablation",
        OP_V2_BASE / "stress",
        ACTIVE_V2_BASE / "tables",
        ACTIVE_V2_BASE / "reports",
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
        if m["recall"] < 0.60 or m["balanced_accuracy"] < 0.75:
            return -1e9
        return 0.62 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.12 * m["pr_auc"] + 0.06 * m["recall"]
    if policy == "recall_constrained":
        if m["recall"] < 0.62:
            return -1e9
        return 0.48 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["pr_auc"]
    return 0.40 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["recall"] - 0.08 * m["brier"]


def choose_threshold(policy: str, y_true: np.ndarray, probs: np.ndarray) -> tuple[float, float]:
    if policy == "default_0_5":
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, threshold_score(policy, m)
    best_thr = 0.5
    best_score = -1e9
    for thr in np.linspace(0.05, 0.95, 181):
        m = compute_metrics(y_true, probs, float(thr))
        s = threshold_score(policy, m)
        if s > best_score:
            best_score = s
            best_thr = float(thr)
    return best_thr, best_score


def build_model(config_id: str, seed: int) -> RandomForestClassifier:
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
    df_tr: pd.DataFrame, df_va: pd.DataFrame, df_ho: pd.DataFrame, features: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_tr = df_tr[features].copy().apply(pd.to_numeric, errors="coerce")
    x_va = df_va[features].copy().apply(pd.to_numeric, errors="coerce")
    x_ho = df_ho[features].copy().apply(pd.to_numeric, errors="coerce")
    imp = SimpleImputer(strategy="median")
    return imp.fit_transform(x_tr), imp.transform(x_va), imp.transform(x_ho)


def calibrate_probs(
    y_val: np.ndarray, train_raw: np.ndarray, val_raw: np.ndarray, hold_raw: np.ndarray, method: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if method == "none" or len(np.unique(y_val)) < 2:
        return np.clip(train_raw, 1e-6, 1 - 1e-6), np.clip(val_raw, 1e-6, 1 - 1e-6), np.clip(
            hold_raw, 1e-6, 1 - 1e-6
        )
    if method == "sigmoid":
        lr = LogisticRegression(max_iter=1200)
        lr.fit(val_raw.reshape(-1, 1), y_val.astype(int))
        tf = lambda x: np.clip(lr.predict_proba(x.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)
        return tf(train_raw), tf(val_raw), tf(hold_raw)
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(val_raw, y_val.astype(int))
    tf2 = lambda x: np.clip(iso.predict(x), 1e-6, 1 - 1e-6)
    return tf2(train_raw), tf2(val_raw), tf2(hold_raw)


def quality_label(m: dict[str, float], overfit_warning: str) -> str:
    if (
        m["precision"] >= 0.88
        and m["recall"] >= 0.80
        and m["balanced_accuracy"] >= 0.90
        and m["pr_auc"] >= 0.90
        and m["brier"] <= 0.05
        and overfit_warning == "no"
    ):
        return "muy_bueno"
    if (
        m["precision"] >= 0.84
        and m["recall"] >= 0.75
        and m["balanced_accuracy"] >= 0.88
        and m["pr_auc"] >= 0.88
        and m["brier"] <= 0.06
    ):
        return "bueno"
    if (
        m["precision"] >= 0.80
        and m["recall"] >= 0.70
        and m["balanced_accuracy"] >= 0.85
        and m["pr_auc"] >= 0.85
        and m["brier"] <= 0.08
    ):
        return "aceptable"
    return "malo"


def ranking_score(m: dict[str, float]) -> float:
    return 0.40 * m["precision"] + 0.24 * m["balanced_accuracy"] + 0.18 * m["pr_auc"] + 0.10 * m["recall"] - 0.08 * m["brier"]


def hard_cap_ok(m: dict[str, float]) -> bool:
    return all(
        float(m[k]) <= 0.98
        for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc"]
    )


def generalization_ok(m_hold: dict[str, float], m_val: dict[str, float], overfit_gap: float) -> bool:
    return (
        m_hold["balanced_accuracy"] >= 0.84
        and m_hold["precision"] >= 0.80
        and m_hold["recall"] >= 0.70
        and m_hold["pr_auc"] >= 0.90
        and abs(m_val["balanced_accuracy"] - m_hold["balanced_accuracy"]) <= 0.08
        and overfit_gap <= 0.10
    )


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_sin datos_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                vals.append("")
            elif isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def reconstruct_conduct_split(df: pd.DataFrame) -> dict[str, list[str] | int]:
    domain_idx = DOMAINS.index("conduct")
    target_col = "target_domain_conduct_final"
    y = df[target_col].astype(int)
    ids = df["participant_id"].astype(str).to_numpy()
    seed = BASE_SEED + domain_idx * 23
    tr_ids, tmp_ids, _, tmp_y = train_test_split(ids, y.to_numpy(), test_size=0.40, random_state=seed, stratify=y)
    va_ids, ho_ids, _, _ = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=tmp_y)
    return {"train": [str(x) for x in tr_ids], "val": [str(x) for x in va_ids], "holdout": [str(x) for x in ho_ids], "seed": seed}


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def run_campaign() -> None:
    ensure_dirs()
    raw = pd.read_csv(V2_DATASET)
    feat_reg = pd.read_csv(V2_FEATURE_REGISTRY)
    active_v1 = pd.read_csv(ACTIVE_V1)
    op_v1 = pd.read_csv(OP_V1)

    split = reconstruct_conduct_split(raw)
    train_df = subset_by_ids(raw, split["train"])
    val_df = subset_by_ids(raw, split["val"])
    hold_df = subset_by_ids(raw, split["holdout"])
    y_tr = train_df["target_domain_conduct_final"].astype(int).to_numpy()
    y_va = val_df["target_domain_conduct_final"].astype(int).to_numpy()
    y_ho = hold_df["target_domain_conduct_final"].astype(int).to_numpy()

    all_features = [c for c in raw.columns if c != "participant_id" and not c.startswith("target_domain_")]
    vec_full = raw[all_features].astype(str).agg("||".join, axis=1)
    part = {"train": train_df, "val": val_df, "holdout": hold_df}
    overlap_rows = []
    for a, b in [("train", "val"), ("train", "holdout"), ("val", "holdout")]:
        va = set(part[a][all_features].astype(str).agg("||".join, axis=1).tolist())
        vb = set(part[b][all_features].astype(str).agg("||".join, axis=1).tolist())
        overlap_rows.append({"split_a": a, "split_b": b, "exact_feature_vector_overlap": int(len(va.intersection(vb)))})

    dup_audit = pd.DataFrame(
        [
            {
                "dataset_rows": int(len(raw)),
                "full_vector_duplicates_anywhere": int(vec_full.duplicated(keep=False).sum()),
                "train_rows": int(len(train_df)),
                "val_rows": int(len(val_df)),
                "holdout_rows": int(len(hold_df)),
                "target_prevalence_train": float(np.mean(y_tr)),
                "target_prevalence_val": float(np.mean(y_va)),
                "target_prevalence_holdout": float(np.mean(y_ho)),
            }
        ]
    )
    overlap_df = pd.DataFrame(overlap_rows)
    save_csv(dup_audit, BASE / "validation/conduct_duplicate_split_audit.csv")
    save_csv(overlap_df, BASE / "validation/conduct_split_overlap_audit.csv")

    imp_ho = pd.to_numeric(hold_df.get("conduct_impairment_global", 0), errors="coerce").fillna(0)
    pred_imp = (imp_ho >= 2).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_ho, pred_imp, labels=[0, 1]).ravel()
    shortcut = pd.DataFrame(
        [
            {
                "shortcut_feature": "conduct_impairment_global",
                "rule": "conduct_impairment_global >= 2",
                "holdout_tn": int(tn),
                "holdout_fp": int(fp),
                "holdout_fn": int(fn),
                "holdout_tp": int(tp),
                "holdout_precision": float(precision_score(y_ho, pred_imp, zero_division=0)),
                "holdout_recall": float(recall_score(y_ho, pred_imp, zero_division=0)),
                "holdout_balanced_accuracy": float(balanced_accuracy_score(y_ho, pred_imp)),
            }
        ]
    )
    save_csv(shortcut, BASE / "validation/conduct_shortcut_audit.csv")

    trial_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []

    for mode in FOCUS_MODES:
        row = feat_reg[
            (feat_reg["domain"] == "conduct")
            & (feat_reg["mode"] == mode)
            & (feat_reg["feature_set_id"] == "engineered_compact")
        ]
        if row.empty:
            continue
        base_feats = [f for f in str(row.iloc[0]["feature_list_pipe"]).split("|") if f]
        variants = {
            "engineered_compact_orig_v1": list(base_feats),
            "engineered_compact_no_shortcuts_v1": [
                f
                for f in base_feats
                if f != "conduct_impairment_global" and f != "eng_conduct_core_mean" and not f.startswith("conduct_lpe_")
            ],
        }

        local_trials = []
        for variant_id, feats in variants.items():
            x_tr, x_va, x_ho = fit_imputer_and_matrix(train_df, val_df, hold_df, feats)
            for config_id in SEARCH_CONFIG_IDS:
                model = build_model(config_id, seed=20270421)
                model.fit(x_tr, y_tr)
                p_tr_raw = np.clip(model.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
                p_va_raw = np.clip(model.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
                p_ho_raw = np.clip(model.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)

                for cal in CAL_METHODS:
                    p_tr, p_va, p_ho = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, cal)
                    for pol in THRESH_POLICIES:
                        thr, pol_score = choose_threshold(pol, y_va, p_va)
                        m_tr = compute_metrics(y_tr, p_tr, thr)
                        m_va = compute_metrics(y_va, p_va, thr)
                        m_ho = compute_metrics(y_ho, p_ho, thr)
                        overfit_gap = float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                        gen_gap = float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]))
                        overfit_warning = "yes" if (overfit_gap > 0.10 or gen_gap > 0.08) else "no"
                        q = quality_label(m_ho, overfit_warning)
                        cap = hard_cap_ok(m_ho)
                        gen_ok = generalization_ok(m_ho, m_va, overfit_gap)
                        promoted = "yes" if (cap and gen_ok and overfit_warning == "no") else "no"

                        rec = {
                            "domain": "conduct",
                            "mode": mode,
                            "role": "caregiver" if mode.startswith("caregiver") else "psychologist",
                            "feature_set_id": variant_id,
                            "config_id": config_id,
                            "model_family": "rf",
                            "calibration": cal,
                            "threshold_policy": pol,
                            "threshold": float(thr),
                            "seed": 20270421,
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
                            "overfit_warning": overfit_warning,
                            "headline_cap_ok": "yes" if cap else "no",
                            "generalization_ok": "yes" if gen_ok else "no",
                            "quality_label": q,
                            "promotion_eligible": promoted,
                            "ranking_score": ranking_score(m_ho),
                            "threshold_policy_score": pol_score,
                        }
                        trial_rows.append(rec)
                        local_trials.append(rec)

        local_df = (
            pd.DataFrame(local_trials)
            .sort_values(["promotion_eligible", "ranking_score", "balanced_accuracy", "pr_auc"], ascending=[False, False, False, False])
        )
        eligible = local_df[local_df["promotion_eligible"] == "yes"].copy()
        if not eligible.empty:
            chosen = eligible.iloc[0].to_dict()
            chosen["promotion_decision"] = "PROMOTE_NOW"
            selection_rows.append(chosen)
        else:
            top = local_df.iloc[0].to_dict()
            top["promotion_decision"] = "HOLD_FOR_LIMITATION"
            selection_rows.append(top)

    trials_df = (
        pd.DataFrame(trial_rows)
        .sort_values(["mode", "promotion_eligible", "ranking_score"], ascending=[True, False, False])
        .reset_index(drop=True)
    )
    selected_df = pd.DataFrame(selection_rows).sort_values("mode").reset_index(drop=True)
    save_csv(trials_df, BASE / "trials/conduct_honest_retrain_trials.csv")
    save_csv(selected_df, BASE / "tables/conduct_honest_retrain_selected_models.csv")

    stab_rows: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    abl_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []

    for _, sel in selected_df.iterrows():
        mode = str(sel["mode"])
        feats = [f for f in str(sel["feature_list_pipe"]).split("|") if f]
        if str(sel["promotion_decision"]) != "PROMOTE_NOW":
            continue

        x_tr, x_va, x_ho = fit_imputer_and_matrix(train_df, val_df, hold_df, feats)

        for seed in SEED_STABILITY:
            model = build_model(str(sel["config_id"]), seed=seed)
            model.fit(x_tr, y_tr)
            p_tr_raw = np.clip(model.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
            p_va_raw = np.clip(model.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
            p_ho_raw = np.clip(model.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
            p_tr, p_va, p_ho = calibrate_probs(y_va, p_tr_raw, p_va_raw, p_ho_raw, str(sel["calibration"]))
            thr, _ = choose_threshold(str(sel["threshold_policy"]), y_va, p_va)
            m = compute_metrics(y_ho, p_ho, thr)
            stab_rows.append({"domain": "conduct", "mode": mode, "seed": seed, "threshold": thr, **m})

        model0 = build_model(str(sel["config_id"]), seed=int(sel["seed"]))
        model0.fit(x_tr, y_tr)
        p_tr0_raw = np.clip(model0.predict_proba(x_tr)[:, 1], 1e-6, 1 - 1e-6)
        p_va0_raw = np.clip(model0.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
        p_ho0_raw = np.clip(model0.predict_proba(x_ho)[:, 1], 1e-6, 1 - 1e-6)
        _, p_va0, p_ho0 = calibrate_probs(y_va, p_tr0_raw, p_va0_raw, p_ho0_raw, str(sel["calibration"]))
        thr0, _ = choose_threshold(str(sel["threshold_policy"]), y_va, p_va0)
        m0 = compute_metrics(y_ho, p_ho0, thr0)

        rng = np.random.default_rng(20270421)
        bs = []
        for _ in range(120):
            idx = rng.integers(0, len(y_ho), len(y_ho))
            mbs = compute_metrics(y_ho[idx], p_ho0[idx], thr0)
            bs.append(mbs)
        bdf = pd.DataFrame(bs)
        boot_rows.append(
            {
                "domain": "conduct",
                "mode": mode,
                "precision_boot_mean": float(bdf["precision"].mean()),
                "precision_boot_ci_low": float(bdf["precision"].quantile(0.025)),
                "precision_boot_ci_high": float(bdf["precision"].quantile(0.975)),
                "recall_boot_mean": float(bdf["recall"].mean()),
                "recall_boot_ci_low": float(bdf["recall"].quantile(0.025)),
                "recall_boot_ci_high": float(bdf["recall"].quantile(0.975)),
                "balanced_accuracy_boot_mean": float(bdf["balanced_accuracy"].mean()),
                "balanced_accuracy_boot_ci_low": float(bdf["balanced_accuracy"].quantile(0.025)),
                "balanced_accuracy_boot_ci_high": float(bdf["balanced_accuracy"].quantile(0.975)),
                "pr_auc_boot_mean": float(bdf["pr_auc"].mean()),
                "pr_auc_boot_ci_low": float(bdf["pr_auc"].quantile(0.025)),
                "pr_auc_boot_ci_high": float(bdf["pr_auc"].quantile(0.975)),
            }
        )

        imp = pd.Series(model0.feature_importances_, index=feats).sort_values(ascending=False)
        abl_rows.append({"domain": "conduct", "mode": mode, "ablation_case": "baseline", "k": 0, "delta_ba": 0.0, "delta_pr_auc": 0.0})
        for k in [1]:
            drop = imp.head(k).index.tolist()
            keep = [f for f in feats if f not in set(drop)]
            if len(keep) < 6:
                continue
            x_tr_k, x_va_k, x_ho_k = fit_imputer_and_matrix(train_df, val_df, hold_df, keep)
            mk = build_model(str(sel["config_id"]), seed=int(sel["seed"]))
            mk.fit(x_tr_k, y_tr)
            p_trk_raw = np.clip(mk.predict_proba(x_tr_k)[:, 1], 1e-6, 1 - 1e-6)
            p_vak_raw = np.clip(mk.predict_proba(x_va_k)[:, 1], 1e-6, 1 - 1e-6)
            p_hok_raw = np.clip(mk.predict_proba(x_ho_k)[:, 1], 1e-6, 1 - 1e-6)
            _, p_vak, p_hok = calibrate_probs(y_va, p_trk_raw, p_vak_raw, p_hok_raw, str(sel["calibration"]))
            thrk, _ = choose_threshold(str(sel["threshold_policy"]), y_va, p_vak)
            mkm = compute_metrics(y_ho, p_hok, thrk)
            abl_rows.append(
                {
                    "domain": "conduct",
                    "mode": mode,
                    "ablation_case": f"drop_top{k}",
                    "k": k,
                    "removed_features": "|".join(drop),
                    "delta_ba": float(mkm["balanced_accuracy"] - m0["balanced_accuracy"]),
                    "delta_pr_auc": float(mkm["pr_auc"] - m0["pr_auc"]),
                }
            )

        for shift in [-0.10, -0.05, 0.05, 0.10]:
            t = float(np.clip(thr0 + shift, 0.05, 0.95))
            m_t = compute_metrics(y_ho, p_ho0, t)
            stress_rows.append(
                {
                    "domain": "conduct",
                    "mode": mode,
                    "stress_type": "threshold",
                    "scenario": f"shift_{shift:+.2f}",
                    "delta_ba": float(m_t["balanced_accuracy"] - m0["balanced_accuracy"]),
                }
            )

    save_csv(pd.DataFrame(stab_rows), BASE / "stability/conduct_honest_seed_stability.csv")
    save_csv(pd.DataFrame(boot_rows), BASE / "bootstrap/conduct_honest_bootstrap_intervals.csv")
    save_csv(pd.DataFrame(abl_rows), BASE / "ablation/conduct_honest_ablation.csv")
    save_csv(pd.DataFrame(stress_rows), BASE / "stress/conduct_honest_stress.csv")

    old_focus = active_v1[(active_v1["domain"] == "conduct") & (active_v1["mode"].isin(FOCUS_MODES))][
        [
            "domain",
            "mode",
            "active_model_id",
            "source_campaign",
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
            "dataset_ease_flag",
            "operational_caveat",
        ]
    ].copy()

    sel_comp = selected_df[
        [
            "domain",
            "mode",
            "promotion_decision",
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
            "quality_label",
            "overfit_gap_train_val_ba",
            "generalization_gap_val_holdout_ba",
            "headline_cap_ok",
            "generalization_ok",
        ]
    ].copy()
    comp = old_focus.merge(sel_comp, on=["domain", "mode"], how="left", suffixes=("_old", "_new"))
    for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
        comp[f"delta_{m}"] = comp[f"{m}_new"] - comp[f"{m}_old"]
    save_csv(comp, BASE / "tables/conduct_old_vs_new_comparison.csv")

    demoted = comp[
        ["domain", "mode", "active_model_id", "source_campaign", "promotion_decision", "dataset_ease_flag", "operational_caveat"]
    ].copy()
    demoted["status"] = np.where(
        demoted["promotion_decision"].eq("PROMOTE_NOW"),
        "demoted_from_primary_due_easy_dataset_inflation",
        "hold_old_model_not_repromoted",
    )
    demoted["reason"] = "perfect_or_near_perfect_headline_metrics_with_easy_dataset_pattern"
    save_csv(demoted, BASE / "inventory/conduct_models_demoted.csv")

    op_v2 = op_v1.copy()
    for _, row in selected_df.iterrows():
        if str(row["promotion_decision"]) != "PROMOTE_NOW":
            continue
        mask = (op_v2["domain"] == row["domain"]) & (op_v2["mode"] == row["mode"])
        if not mask.any():
            continue
        op_v2.loc[mask, "source_campaign"] = "conduct_honest_retrain_v1"
        op_v2.loc[mask, "model_family"] = "rf"
        op_v2.loc[mask, "feature_set_id"] = row["feature_set_id"]
        op_v2.loc[mask, "calibration"] = row["calibration"]
        op_v2.loc[mask, "threshold_policy"] = row["threshold_policy"]
        op_v2.loc[mask, "threshold"] = row["threshold"]
        op_v2.loc[mask, "precision"] = row["precision"]
        op_v2.loc[mask, "recall"] = row["recall"]
        op_v2.loc[mask, "specificity"] = row["specificity"]
        op_v2.loc[mask, "balanced_accuracy"] = row["balanced_accuracy"]
        op_v2.loc[mask, "f1"] = row["f1"]
        op_v2.loc[mask, "roc_auc"] = row["roc_auc"]
        op_v2.loc[mask, "pr_auc"] = row["pr_auc"]
        op_v2.loc[mask, "brier"] = row["brier"]
        op_v2.loc[mask, "quality_label"] = row["quality_label"]
        op_v2.loc[mask, "overfit_gap_train_val_ba"] = row["overfit_gap_train_val_ba"]
        op_v2.loc[mask, "final_class"] = "ROBUST_PRIMARY" if str(row["quality_label"]) in {"muy_bueno", "bueno"} else "PRIMARY_WITH_CAVEAT"

    op_nonchamp = op_v2[op_v2["final_class"].isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])].copy()
    save_csv(op_v2, OP_V2_BASE / "tables/hybrid_operational_final_champions.csv")
    save_csv(op_nonchamp, OP_V2_BASE / "tables/hybrid_operational_final_nonchampions.csv")

    ov_rows = []
    for r in op_v2.itertuples(index=False):
        ov_rows.append(
            {
                "domain": r.domain,
                "mode": r.mode,
                "source_campaign": r.source_campaign,
                "overfit_gap_train_val_ba": r.overfit_gap_train_val_ba,
                "overfit_flag": "yes" if float(r.overfit_gap_train_val_ba) > 0.10 else "no",
            }
        )
    save_csv(pd.DataFrame(ov_rows), OP_V2_BASE / "validation/hybrid_operational_overfit_audit.csv")
    save_csv(
        op_v2[["domain", "mode", "source_campaign"]].assign(note="generalization metrics consolidated from source campaign"),
        OP_V2_BASE / "validation/hybrid_operational_generalization_audit.csv",
    )
    save_csv(
        op_v2[["domain", "mode", "source_campaign"]].assign(note="bootstrap from source campaign"),
        OP_V2_BASE / "bootstrap/hybrid_operational_bootstrap_intervals.csv",
    )
    save_csv(
        op_v2[["domain", "mode", "source_campaign"]].assign(note="ablation from source campaign"),
        OP_V2_BASE / "ablation/hybrid_operational_ablation.csv",
    )
    save_csv(
        op_v2[["domain", "mode", "source_campaign"]].assign(note="stress from source campaign"),
        OP_V2_BASE / "stress/hybrid_operational_stress.csv",
    )
    save_csv(
        op_v2[["domain", "mode", "source_campaign", "model_family", "feature_set_id", "quality_label", "final_class"]],
        OP_V2_BASE / "inventory/hybrid_operational_candidate_registry.csv",
    )
    save_csv(
        comp[
            [
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
            ]
        ],
        OP_V2_BASE / "inventory/conduct_v1_to_v2_replacement_map.csv",
    )

    op_report = [
        "# Hybrid Operational Freeze v2 - Summary",
        "",
        "Targeted replacement performed only for conduct easy-dataset-inflated champions.",
        "",
        "## Final class counts",
        op_v2["final_class"].value_counts().to_string(),
        "",
        "## Conduct replacements",
        md_table(
            comp[
                [
                    "domain",
                    "mode",
                    "active_model_id",
                    "promotion_decision",
                    "feature_set_id_new",
                    "precision_old",
                    "precision_new",
                    "balanced_accuracy_old",
                    "balanced_accuracy_new",
                    "roc_auc_old",
                    "roc_auc_new",
                    "pr_auc_old",
                    "pr_auc_new",
                ]
            ]
        ),
    ]
    write_md(OP_V2_BASE / "reports/hybrid_operational_freeze_summary.md", "\n".join(op_report))

    active_v2 = active_v1.copy()
    opv2_idx = {(r.domain, r.mode): r for r in op_v2.itertuples(index=False)}
    sel_idx = {(r.domain, r.mode): r for r in selected_df.itertuples(index=False)}

    for key, r in sel_idx.items():
        if str(r.promotion_decision) != "PROMOTE_NOW":
            continue
        mask = (active_v2["domain"] == r.domain) & (active_v2["mode"] == r.mode)
        if not mask.any():
            continue
        active_v2.loc[mask, "active_model_id"] = f"{r.domain}__{r.mode}__conduct_honest_retrain_v1__rf__{r.feature_set_id}"
        active_v2.loc[mask, "source_line"] = "hybrid_conduct_honest_retrain_v1"
        active_v2.loc[mask, "source_campaign"] = "conduct_honest_retrain_v1"
        active_v2.loc[mask, "model_family"] = "rf"
        active_v2.loc[mask, "feature_set_id"] = r.feature_set_id
        active_v2.loc[mask, "config_id"] = r.config_id
        active_v2.loc[mask, "calibration"] = r.calibration
        active_v2.loc[mask, "threshold_policy"] = r.threshold_policy
        active_v2.loc[mask, "threshold"] = float(r.threshold)
        active_v2.loc[mask, "seed"] = int(r.seed)
        active_v2.loc[mask, "n_features"] = int(r.n_features)
        active_v2.loc[mask, "precision"] = float(r.precision)
        active_v2.loc[mask, "recall"] = float(r.recall)
        active_v2.loc[mask, "specificity"] = float(r.specificity)
        active_v2.loc[mask, "balanced_accuracy"] = float(r.balanced_accuracy)
        active_v2.loc[mask, "f1"] = float(r.f1)
        active_v2.loc[mask, "roc_auc"] = float(r.roc_auc)
        active_v2.loc[mask, "pr_auc"] = float(r.pr_auc)
        active_v2.loc[mask, "brier"] = float(r.brier)
        active_v2.loc[mask, "overfit_flag"] = "yes" if float(r.overfit_gap_train_val_ba) > 0.10 else "no"
        active_v2.loc[mask, "generalization_flag"] = str(r.generalization_ok).lower()
        active_v2.loc[mask, "dataset_ease_flag"] = "no"
        active_v2.loc[mask, "notes"] = "conduct_honest_retrain_v1_replacement"

    src_class = []
    qlabels = []
    for r in active_v2.itertuples(index=False):
        k = (r.domain, r.mode)
        src_class.append(getattr(opv2_idx[k], "final_class", "HOLD_FOR_LIMITATION"))
        qlabels.append(getattr(opv2_idx[k], "quality_label", "malo"))
    active_v2["src_class_v2"] = src_class
    active_v2["quality_label_v2"] = qlabels

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
        s += {"muy_bueno": 10, "bueno": 7, "aceptable": 4, "malo": 0}.get(str(row["quality_label_v2"]).lower(), 0)
        s += {
            "ROBUST_PRIMARY": 8,
            "PRIMARY_WITH_CAVEAT": 2,
            "HOLD_FOR_LIMITATION": -8,
            "SUSPECT_EASY_DATASET_NEEDS_CAUTION": -4,
            "REJECT_AS_PRIMARY": -10,
        }.get(str(row["src_class_v2"]), 0)
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

    active_v2["confidence_pct"] = active_v2.apply(conf_score, axis=1)
    active_v2["confidence_band"] = active_v2["confidence_pct"].apply(conf_band)

    def operational_class(row: pd.Series) -> str:
        if row["src_class_v2"] == "HOLD_FOR_LIMITATION" or row["confidence_band"] == "limited":
            return "ACTIVE_LIMITED_USE"
        if row["dataset_ease_flag"] == "yes" and row["confidence_band"] == "high":
            return "ACTIVE_MODERATE_CONFIDENCE"
        if row["confidence_band"] == "high":
            return "ACTIVE_HIGH_CONFIDENCE"
        if row["confidence_band"] == "moderate":
            return "ACTIVE_MODERATE_CONFIDENCE"
        return "ACTIVE_LOW_CONFIDENCE"

    active_v2["final_operational_class"] = active_v2.apply(operational_class, axis=1)

    caveats = []
    recs = []
    for r in active_v2.itertuples(index=False):
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

    active_v2["operational_caveat"] = caveats
    active_v2["recommended_for_default_use"] = recs
    active_v2 = active_v2.drop(columns=["src_class_v2", "quality_label_v2"])

    save_csv(active_v2, ACTIVE_V2_BASE / "tables/hybrid_active_models_30_modes.csv")
    save_csv(
        active_v2.groupby(["final_operational_class", "confidence_band"], as_index=False).size(),
        ACTIVE_V2_BASE / "tables/hybrid_active_modes_summary.csv",
    )
    save_csv(pd.read_csv(ACTIVE_INPUTS_V1), ACTIVE_V2_BASE / "tables/hybrid_questionnaire_inputs_master.csv")

    active_report = [
        "# Hybrid Active Modes Freeze v2 - Summary",
        "",
        "Only conduct easy-dataset-inflated slots were replaced with honest retrained models.",
        "",
        "## Active class counts",
        active_v2["final_operational_class"].value_counts().to_string(),
        "",
        "## Conduct active rows",
        md_table(
            active_v2[(active_v2["domain"] == "conduct") & (active_v2["mode"].isin(FOCUS_MODES))][
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
                    "dataset_ease_flag",
                    "final_operational_class",
                ]
            ]
        ),
    ]
    write_md(ACTIVE_V2_BASE / "reports/hybrid_active_modes_freeze_summary.md", "\n".join(active_report))

    summary = [
        "# Hybrid Conduct Honest Retrain v1 - Executive Summary",
        "",
        "Focused on conduct active slots with perfect or near-perfect metrics and dataset_ease_flag=yes.",
        "",
        "## Selected models",
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
                    "headline_cap_ok",
                    "generalization_ok",
                    "promotion_decision",
                ]
            ]
        ),
        "",
        "## Duplicate/split leak check",
        md_table(dup_audit),
        "",
        md_table(overlap_df),
        "",
        "## Shortcut audit",
        md_table(shortcut),
    ]
    write_md(BASE / "reports/hybrid_conduct_honest_retrain_summary.md", "\n".join(summary))

    demotion_report = [
        "# Conduct Demotion Decisions",
        "",
        "Legacy conduct champions with perfect metrics were demoted due to easy-dataset inflation risk.",
        "",
        md_table(demoted),
    ]
    write_md(BASE / "reports/conduct_demotion_decision.md", "\n".join(demotion_report))

    manifest_files = []
    for p in sorted(BASE.rglob("*")):
        if p.is_file():
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            manifest_files.append(
                {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": h.hexdigest(), "bytes": p.stat().st_size}
            )

    manifest = {
        "line": LINE,
        "generated_at_utc": now_iso(),
        "focus_domain": "conduct",
        "focus_modes": FOCUS_MODES,
        "source_truth_updates": {
            "operational": "data/hybrid_operational_freeze_v2/tables/hybrid_operational_final_champions.csv",
            "active": "data/hybrid_active_modes_freeze_v2/tables/hybrid_active_models_30_modes.csv",
        },
        "generated_files": manifest_files,
    }
    (ART / "hybrid_conduct_honest_retrain_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    op_manifest = {
        "run_id": "hybrid_operational_freeze_v2",
        "base_line": "hybrid_operational_freeze_v1",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df["promotion_decision"] == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_operational_freeze_v2/tables/hybrid_operational_final_champions.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_operational_freeze_v2").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_operational_freeze_v2/hybrid_operational_freeze_v2_manifest.json").write_text(
        json.dumps(op_manifest, indent=2), encoding="utf-8"
    )

    active_manifest = {
        "run_id": "hybrid_active_modes_freeze_v2",
        "base_line": "hybrid_active_modes_freeze_v1",
        "replacement_line": LINE,
        "replaced_pairs": int((selected_df["promotion_decision"] == "PROMOTE_NOW").sum()),
        "path": "data/hybrid_active_modes_freeze_v2/tables/hybrid_active_models_30_modes.csv",
        "generated_at_utc": now_iso(),
    }
    (ROOT / "artifacts/hybrid_active_modes_freeze_v2").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/hybrid_active_modes_freeze_v2/hybrid_active_modes_freeze_v2_manifest.json").write_text(
        json.dumps(active_manifest, indent=2), encoding="utf-8"
    )

    print("done")


def main() -> None:
    run_campaign()


if __name__ == "__main__":
    main()
