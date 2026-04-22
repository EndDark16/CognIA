#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
LINE = "hybrid_rf_targeted_fix_v4"
BASE = ROOT / "data" / LINE
INV = BASE / "inventory"
TRIALS = BASE / "trials"
FEAT = BASE / "feature_selection"
CAL = BASE / "calibration"
THR = BASE / "thresholds"
BOOT = BASE / "bootstrap"
STAB = BASE / "stability"
ABL = BASE / "ablation"
STRESS = BASE / "stress"
TABLES = BASE / "tables"
REPORTS = BASE / "reports"
ART = ROOT / "artifacts" / LINE

DATASET_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "hybrid_dataset_synthetic_complete_final.csv"
RESPOND_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "hybrid_model_input_respondability_final.csv"
MODE_MATRIX_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "questionnaire_modes_priority_matrix_final.csv"
DSM_TEMPLATE_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "dsm5_quant_feature_template_final.csv"

V3_BASE = ROOT / "data" / "hybrid_rf_final_ceiling_push_v3"
V3_WINNERS = V3_BASE / "tables" / "hybrid_rf_mode_domain_winners.csv"
V3_FINAL_METRICS = V3_BASE / "tables" / "hybrid_rf_mode_domain_final_metrics.csv"
V3_DECISIONS = V3_BASE / "tables" / "hybrid_rf_final_promotion_decisions.csv"
V3_FEATURESETS = V3_BASE / "trials" / "hybrid_rf_final_trial_feature_sets.csv"
V3_SPLITS = V3_BASE / "splits"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]

CAL_METHODS = ["none", "sigmoid", "isotonic"]
THRESH_POLICIES = [
    "default_0_5",
    "balanced",
    "precision_oriented",
    "recall_guard",
    "recall_constrained",
    "precision_min_recall",
]

TARGETED_CANDIDATES = [
    ("depression", "caregiver_1_3"),
    ("depression", "caregiver_2_3"),
    ("depression", "caregiver_full"),
    ("depression", "psychologist_1_3"),
    ("depression", "psychologist_2_3"),
    ("depression", "psychologist_full"),
    ("adhd", "caregiver_1_3"),
    ("adhd", "caregiver_2_3"),
    ("adhd", "psychologist_1_3"),
    ("adhd", "psychologist_2_3"),
    ("elimination", "caregiver_1_3"),
    ("elimination", "psychologist_1_3"),
    ("elimination", "caregiver_2_3"),
    ("elimination", "psychologist_2_3"),
    ("anxiety", "caregiver_1_3"),
    ("anxiety", "caregiver_2_3"),
    ("anxiety", "caregiver_full"),
]

FIT_COUNTER = {"fits": 0, "trees": 0}


@dataclass
class Candidate:
    candidate_id: str
    domain: str
    mode: str
    v3_feature_set_id: str
    v3_config_id: str
    v3_calibration: str
    v3_threshold_policy: str
    v3_threshold: float
    v3_seed: int
    v3_holdout_precision: float
    v3_holdout_recall: float
    v3_holdout_ba: float
    v3_holdout_pr_auc: float
    v3_holdout_brier: float


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_progress(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_dirs() -> None:
    for p in [BASE, INV, TRIALS, FEAT, CAL, THR, BOOT, STAB, ABL, STRESS, TABLES, REPORTS, ART]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


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


def normalize_flag(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip().lower()


def safe_roc_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, probs))


def safe_pr_auc(y_true: np.ndarray, probs: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float(np.mean(y_true))
    return float(average_precision_score(y_true, probs))


def expected_calibration_error(y_true: np.ndarray, probs: np.ndarray, bins: int = 10) -> float:
    probs = np.clip(probs, 1e-6, 1 - 1e-6)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.digitize(probs, edges[1:-1], right=False)
    n = len(y_true)
    ece = 0.0
    for b in range(bins):
        m = idx == b
        if not np.any(m):
            continue
        conf = float(np.mean(probs[m]))
        acc = float(np.mean(y_true[m]))
        ece += (np.sum(m) / n) * abs(acc - conf)
    return float(ece)


def compute_metrics(y_true: np.ndarray, probs: np.ndarray, thr: float) -> dict[str, float]:
    pred = (probs >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": spec,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": safe_roc_auc(y_true, probs),
        "pr_auc": safe_pr_auc(y_true, probs),
        "brier": float(brier_score_loss(y_true, np.clip(probs, 1e-6, 1 - 1e-6))),
        "accuracy": float(accuracy_score(y_true, pred)),
    }


def objective(metrics: dict[str, float]) -> float:
    return (
        0.40 * metrics["precision"]
        + 0.24 * metrics["balanced_accuracy"]
        + 0.18 * metrics["pr_auc"]
        + 0.10 * metrics["recall"]
        - 0.08 * metrics["brier"]
    )


def choose_threshold(policy: str, y_true: np.ndarray, probs: np.ndarray, recall_floor: float = 0.55) -> tuple[float, float]:
    if policy == "default_0_5":
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective(m)
    grid = np.linspace(0.05, 0.95, 181)
    best_thr = 0.5
    best_score = -1e9
    for thr in grid:
        m = compute_metrics(y_true, probs, float(thr))
        if policy == "balanced":
            score = 0.50 * m["balanced_accuracy"] + 0.20 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
        elif policy == "precision_oriented":
            if m["recall"] < max(0.50, recall_floor):
                continue
            score = 0.62 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.12 * m["pr_auc"] + 0.06 * m["recall"]
        elif policy == "recall_guard":
            if m["recall"] < max(0.72, recall_floor):
                continue
            score = 0.38 * m["precision"] + 0.26 * m["balanced_accuracy"] + 0.28 * m["recall"] + 0.08 * m["pr_auc"]
        elif policy == "recall_constrained":
            if m["recall"] < max(0.62, recall_floor):
                continue
            score = 0.48 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["pr_auc"]
        elif policy == "precision_min_recall":
            if m["recall"] < max(0.58, recall_floor):
                continue
            if m["balanced_accuracy"] < 0.75:
                continue
            score = 0.66 * m["precision"] + 0.16 * m["balanced_accuracy"] + 0.10 * m["pr_auc"] + 0.08 * m["recall"]
        else:
            score = objective(m)
        if score > best_score:
            best_score = float(score)
            best_thr = float(thr)
    if best_score < -1e8:
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective(m)
    return best_thr, best_score


def choose_targets(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    w = df.copy()
    if all(c in w.columns for c in ["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]):
        w["target_domain_depression_final"] = (
            w[["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .max(axis=1)
            .astype(int)
        )
    target_source = {
        "adhd": "adhd_final_dsm5_threshold_met",
        "conduct": "conduct_final_dsm5_threshold_met",
        "elimination": "elimination_any_threshold_met",
        "anxiety": "anxiety_any_module_threshold_met",
        "depression": "target_domain_depression_final",
    }
    for d, c in target_source.items():
        out = f"target_domain_{d}_final"
        w[out] = pd.to_numeric(w[c], errors="coerce").fillna(0).astype(int)
        w[out] = (w[out] > 0).astype(int)
        target_source[d] = out
    return w, target_source


def load_ids(path: Path) -> list[str]:
    x = pd.read_csv(path)
    col = "participant_id" if "participant_id" in x.columns else x.columns[0]
    return x[col].astype(str).tolist()


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def build_alt_splits(df: pd.DataFrame, target_col: str, seeds: list[int]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    ids = df["participant_id"].astype(str).to_numpy()
    y = df[target_col].astype(int).to_numpy()
    for i, seed in enumerate(seeds, start=1):
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(ids, y, test_size=0.40, random_state=seed, stratify=strat)
        strat_tmp = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids = train_test_split(tmp_ids, test_size=0.50, random_state=seed + 1, stratify=strat_tmp)
        out[f"alt_split_{i}"] = {"train": [str(x) for x in tr_ids], "val": [str(x) for x in va_ids], "holdout": [str(x) for x in ho_ids]}
    return out


BASE_SEED = 20260712
STAGE2_SEEDS = [20260712, 20260729]
STABILITY_SEEDS = [20260712, 20260729, 20260811, 20260837]
ALT_SPLIT_SEEDS = [20260901, 20260919]

RF_CONFIG_LIBRARY: dict[str, dict[str, Any]] = {
    "rf_baseline": {
        "config_id": "rf_baseline",
        "n_estimators": 240,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": None,
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_balanced_subsample": {
        "config_id": "rf_balanced_subsample",
        "n_estimators": 300,
        "max_depth": 22,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    "rf_precision_push": {
        "config_id": "rf_precision_push",
        "n_estimators": 280,
        "max_depth": 18,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.55,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_recall_guard": {
        "config_id": "rf_recall_guard",
        "n_estimators": 300,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": {0: 1.0, 1: 1.8},
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_regularized": {
        "config_id": "rf_regularized",
        "n_estimators": 260,
        "max_depth": 14,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    "rf_positive_push_strong": {
        "config_id": "rf_positive_push_strong",
        "n_estimators": 320,
        "max_depth": 20,
        "min_samples_split": 6,
        "min_samples_leaf": 2,
        "max_features": 0.6,
        "class_weight": {0: 1.0, 1: 2.2},
        "bootstrap": True,
        "max_samples": 0.9,
    },
}


def safe_float(x: Any, fallback: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return fallback
        return float(x)
    except Exception:
        return fallback


def parse_role(mode: str) -> str:
    return "caregiver" if str(mode).startswith("caregiver") else "psychologist"


def parse_feature_pipe(s: Any) -> list[str]:
    if pd.isna(s):
        return []
    out = [x.strip() for x in str(s).split("|") if str(x).strip()]
    return sorted(set(out))


def prepare_X(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].copy()
    for c in x.columns:
        if c == "sex_assigned_at_birth":
            x[c] = x[c].fillna("Unknown").astype(str)
        else:
            x[c] = pd.to_numeric(x[c], errors="coerce").astype(float)
    return x


def make_pipeline(features: list[str], cfg: dict[str, Any], seed: int) -> Pipeline:
    cat_cols = [c for c in features if c == "sex_assigned_at_birth"]
    num_cols = [c for c in features if c not in cat_cols]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cat_cols,
            ),
        ],
        remainder="drop",
    )
    rf = RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cfg["class_weight"],
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        random_state=int(seed),
        n_jobs=1,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def fit_with_count(pipe: Pipeline, x: pd.DataFrame, y: np.ndarray, n_trees: int) -> Pipeline:
    pipe.fit(x, y)
    FIT_COUNTER["fits"] += 1
    FIT_COUNTER["trees"] += int(n_trees)
    return pipe


def aggregate_importance(pipe: Pipeline, feature_names: list[str]) -> pd.Series:
    pre = pipe.named_steps["pre"]
    rf = pipe.named_steps["rf"]
    transformed = pre.get_feature_names_out()
    imp = rf.feature_importances_
    agg = {f: 0.0 for f in feature_names}
    for t_name, val in zip(transformed, imp):
        s = str(t_name)
        original = s
        if s.startswith("num__"):
            original = s.split("num__", 1)[1]
        elif s.startswith("cat__"):
            tail = s.split("cat__", 1)[1]
            original = "sex_assigned_at_birth" if tail.startswith("sex_assigned_at_birth") else tail.split("_", 1)[0]
        if original in agg:
            agg[original] += float(val)
    return pd.Series(agg).sort_values(ascending=False)


def calibrate_probabilities(
    y_val: np.ndarray,
    train_raw: np.ndarray,
    val_raw: np.ndarray,
    hold_raw: np.ndarray,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], dict[str, dict[str, float]], dict[str, Callable[[np.ndarray], np.ndarray]]]:
    def ident(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 1e-6, 1 - 1e-6)

    out_probs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {
        "none": (ident(train_raw), ident(val_raw), ident(hold_raw))
    }
    out_diag: dict[str, dict[str, float]] = {
        "none": {
            "val_brier": float(brier_score_loss(y_val, ident(val_raw))),
            "val_ece": float(expected_calibration_error(y_val, ident(val_raw))),
        }
    }
    transforms: dict[str, Callable[[np.ndarray], np.ndarray]] = {"none": ident}

    if len(np.unique(y_val)) < 2:
        return out_probs, out_diag, transforms

    lr = LogisticRegression(max_iter=1200)
    lr.fit(val_raw.reshape(-1, 1), y_val.astype(int))

    def tf_sigmoid(x: np.ndarray) -> np.ndarray:
        return np.clip(lr.predict_proba(x.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)

    out_probs["sigmoid"] = (tf_sigmoid(train_raw), tf_sigmoid(val_raw), tf_sigmoid(hold_raw))
    out_diag["sigmoid"] = {
        "val_brier": float(brier_score_loss(y_val, out_probs["sigmoid"][1])),
        "val_ece": float(expected_calibration_error(y_val, out_probs["sigmoid"][1])),
    }
    transforms["sigmoid"] = tf_sigmoid

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(val_raw, y_val.astype(int))

    def tf_iso(x: np.ndarray) -> np.ndarray:
        return np.clip(iso.predict(x), 1e-6, 1 - 1e-6)

    out_probs["isotonic"] = (tf_iso(train_raw), tf_iso(val_raw), tf_iso(hold_raw))
    out_diag["isotonic"] = {
        "val_brier": float(brier_score_loss(y_val, out_probs["isotonic"][1])),
        "val_ece": float(expected_calibration_error(y_val, out_probs["isotonic"][1])),
    }
    transforms["isotonic"] = tf_iso
    return out_probs, out_diag, transforms


def bootstrap_metric_ci(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float,
    n_boot: int = 300,
    seed: int = 42,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx_all = np.arange(len(y_true))
    metric_names = ["precision", "recall", "balanced_accuracy", "pr_auc", "brier"]
    hist: dict[str, list[float]] = {m: [] for m in metric_names}
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        m = compute_metrics(y_true[idx], probs[idx], threshold)
        for name in metric_names:
            hist[name].append(float(m[name]))
    out: dict[str, float] = {}
    for name in metric_names:
        arr = np.array(hist[name], dtype=float)
        out[f"{name}_boot_mean"] = float(np.mean(arr))
        out[f"{name}_boot_ci_low"] = float(np.quantile(arr, 0.025))
        out[f"{name}_boot_ci_high"] = float(np.quantile(arr, 0.975))
    return out


def inject_missing(x: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = x.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f not in out.columns:
            continue
        if f != "sex_assigned_at_birth":
            out[f] = pd.to_numeric(out[f], errors="coerce").astype(float)
        mask = rng.random(len(out)) < ratio
        out.loc[mask, f] = np.nan
    return out


def inject_light_noise(x: pd.DataFrame, features: list[str], noise_scale: float, seed: int) -> pd.DataFrame:
    out = x.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f == "sex_assigned_at_birth" or f not in out.columns:
            continue
        s = pd.to_numeric(out[f], errors="coerce").astype(float)
        sd = float(np.nanstd(s.values))
        if sd <= 0:
            continue
        noise = rng.normal(0.0, noise_scale * sd, size=len(out))
        out[f] = s + noise
    return out


def load_v3_ids(domain: str) -> dict[str, list[str]]:
    d = V3_SPLITS / f"domain_{domain}"
    return {
        "train": load_ids(d / "ids_train.csv"),
        "val": load_ids(d / "ids_val.csv"),
        "holdout": load_ids(d / "ids_holdout.csv"),
    }


def select_stage1_combos(stage1_df: pd.DataFrame, baseline_recall: float, baseline_ba: float) -> list[tuple[str, str]]:
    if stage1_df.empty:
        return []
    grouped = (
        stage1_df.groupby(["feature_set_id", "config_id"], as_index=False)
        .agg(
            val_precision=("val_precision", "mean"),
            val_recall=("val_recall", "mean"),
            val_ba=("val_balanced_accuracy", "mean"),
            val_pr_auc=("val_pr_auc", "mean"),
            val_brier=("val_brier", "mean"),
            stage_score=("stage_score", "mean"),
        )
        .copy()
    )
    grouped["guard_ok"] = (
        (grouped["val_recall"] >= max(0.40, baseline_recall - 0.14))
        & (grouped["val_ba"] >= max(0.70, baseline_ba - 0.06))
    )
    grouped["rank_score"] = (
        0.42 * grouped["val_precision"]
        + 0.24 * grouped["val_ba"]
        + 0.18 * grouped["val_pr_auc"]
        + 0.10 * grouped["val_recall"]
        - 0.06 * grouped["val_brier"]
    )
    valid = grouped[grouped["guard_ok"]].sort_values("rank_score", ascending=False)
    if valid.empty:
        valid = grouped.sort_values("rank_score", ascending=False)
    combos = [(str(r["feature_set_id"]), str(r["config_id"])) for _, r in valid.head(2).iterrows()]
    return list(dict.fromkeys(combos))


def is_dsm5_feature(feature: str, dsm_template_set: set[str]) -> bool:
    f = str(feature).lower()
    if feature in dsm_template_set:
        return True
    if f in {"age_years", "sex_assigned_at_birth"}:
        return False
    if f.startswith(("swan_", "sdq_", "icut_", "ari_", "scared_", "mfq_")):
        return False
    dsm_prefixes = (
        "adhd_",
        "conduct_",
        "enuresis_",
        "encopresis_",
        "elimination_",
        "sep_anx_",
        "social_anxiety_",
        "gad_",
        "agor_",
        "anxiety_",
        "mdd_",
        "dmdd_",
        "pdd_",
    )
    return f.startswith(dsm_prefixes) or any(tok in f for tok in ["symptom", "criterion", "impairment", "duration", "onset"])


def build_local_configs(domain: str, winner_cfg_id: str) -> list[dict[str, Any]]:
    base = RF_CONFIG_LIBRARY.get(winner_cfg_id, RF_CONFIG_LIBRARY["rf_baseline"]).copy()
    n0 = int(base["n_estimators"])
    d0 = base["max_depth"]
    msplit = int(base["min_samples_split"])
    mleaf = int(base["min_samples_leaf"])
    mfeat = base["max_features"]
    msamp = base["max_samples"]
    bootstrap = bool(base["bootstrap"])

    domain_weights = {
        "depression": [1.4, 1.8, 2.2],
        "adhd": [1.2, 1.45, 1.7],
        "elimination": [1.1, 1.25, 1.45],
        "anxiety": [1.3, 1.6, 1.9],
        "conduct": [1.3, 1.7, 2.0],
    }.get(domain, [1.3, 1.6, 1.9])

    if isinstance(mfeat, float):
        feat_up = float(min(0.9, mfeat + 0.1))
        feat_dn = float(max(0.35, mfeat - 0.1))
    else:
        feat_up = 0.7
        feat_dn = 0.5

    d_mid = 18 if d0 is None else int(d0)
    configs: list[dict[str, Any]] = [
        {
            "config_id": winner_cfg_id,
            "n_estimators": n0,
            "max_depth": d0,
            "min_samples_split": msplit,
            "min_samples_leaf": mleaf,
            "max_features": mfeat,
            "class_weight": base["class_weight"],
            "bootstrap": bootstrap,
            "max_samples": msamp,
        },
        {
            "config_id": f"{winner_cfg_id}__trees_plus",
            "n_estimators": min(520, n0 + 80),
            "max_depth": d0,
            "min_samples_split": msplit,
            "min_samples_leaf": mleaf,
            "max_features": mfeat,
            "class_weight": base["class_weight"],
            "bootstrap": bootstrap,
            "max_samples": msamp,
        },
        {
            "config_id": f"{winner_cfg_id}__regularized",
            "n_estimators": max(180, n0 - 20),
            "max_depth": max(10, d_mid - 4),
            "min_samples_split": max(4, msplit + 2),
            "min_samples_leaf": max(2, mleaf + 1),
            "max_features": feat_dn,
            "class_weight": "balanced",
            "bootstrap": True,
            "max_samples": 0.85,
        },
        {
            "config_id": f"{winner_cfg_id}__balanced_subsample",
            "n_estimators": min(480, n0 + 40),
            "max_depth": d0,
            "min_samples_split": msplit,
            "min_samples_leaf": max(1, mleaf),
            "max_features": mfeat,
            "class_weight": "balanced_subsample",
            "bootstrap": True,
            "max_samples": 0.9,
        },
        {
            "config_id": f"{winner_cfg_id}__pos_weight_low",
            "n_estimators": n0,
            "max_depth": d0,
            "min_samples_split": msplit,
            "min_samples_leaf": max(1, mleaf),
            "max_features": mfeat,
            "class_weight": {0: 1.0, 1: domain_weights[0]},
            "bootstrap": bootstrap,
            "max_samples": msamp,
        },
        {
            "config_id": f"{winner_cfg_id}__pos_weight_mid",
            "n_estimators": min(500, n0 + 40),
            "max_depth": d0,
            "min_samples_split": msplit,
            "min_samples_leaf": max(1, mleaf),
            "max_features": feat_up,
            "class_weight": {0: 1.0, 1: domain_weights[1]},
            "bootstrap": True,
            "max_samples": 0.9,
        },
        {
            "config_id": f"{winner_cfg_id}__pos_weight_high",
            "n_estimators": min(520, n0 + 80),
            "max_depth": d0,
            "min_samples_split": max(4, msplit),
            "min_samples_leaf": max(1, mleaf),
            "max_features": feat_dn,
            "class_weight": {0: 1.0, 1: domain_weights[2]},
            "bootstrap": True,
            "max_samples": 0.9,
        },
        {
            "config_id": f"{winner_cfg_id}__shallow_precision",
            "n_estimators": min(480, n0 + 20),
            "max_depth": max(8, d_mid - 6),
            "min_samples_split": max(6, msplit + 2),
            "min_samples_leaf": max(2, mleaf + 1),
            "max_features": feat_dn,
            "class_weight": {0: 1.0, 1: domain_weights[0]},
            "bootstrap": True,
            "max_samples": 0.8,
        },
    ]

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cfg in configs:
        sig = json.dumps(
            {
                "n_estimators": cfg["n_estimators"],
                "max_depth": cfg["max_depth"],
                "min_samples_split": cfg["min_samples_split"],
                "min_samples_leaf": cfg["min_samples_leaf"],
                "max_features": cfg["max_features"],
                "class_weight": cfg["class_weight"],
                "bootstrap": cfg["bootstrap"],
                "max_samples": cfg["max_samples"],
            },
            sort_keys=True,
            default=str,
        )
        if sig in seen:
            continue
        seen.add(sig)
        cleaned.append(cfg)
    return cleaned


def config_hash(cfg: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_target_candidates(
    winners_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
) -> list[Candidate]:
    out: list[Candidate] = []
    for domain, mode in TARGETED_CANDIDATES:
        w = winners_df[(winners_df["domain"] == domain) & (winners_df["mode"] == mode)]
        m = metrics_df[(metrics_df["domain"] == domain) & (metrics_df["mode"] == mode)]
        if w.empty or m.empty:
            continue
        wr = w.iloc[0]
        mr = m.iloc[0]
        out.append(
            Candidate(
                candidate_id=f"{domain}__{mode}",
                domain=domain,
                mode=mode,
                v3_feature_set_id=str(wr["winner_feature_set_id"]),
                v3_config_id=str(wr["winner_config_id"]),
                v3_calibration=str(wr["winner_calibration"]),
                v3_threshold_policy=str(wr["winner_threshold_policy"]),
                v3_threshold=safe_float(wr["winner_threshold"], 0.5),
                v3_seed=int(safe_float(wr["winner_seed"], BASE_SEED)),
                v3_holdout_precision=safe_float(mr["holdout_precision"], 0.0),
                v3_holdout_recall=safe_float(mr["holdout_recall"], 0.0),
                v3_holdout_ba=safe_float(mr["holdout_balanced_accuracy"], 0.0),
                v3_holdout_pr_auc=safe_float(mr["holdout_pr_auc"], 0.0),
                v3_holdout_brier=safe_float(mr["holdout_brier"], 1.0),
            )
        )
    return out


def run_campaign() -> None:
    ensure_dirs()
    print_progress("Loading dataset and reference artifacts")
    df = pd.read_csv(DATASET_PATH)
    respondability = pd.read_csv(RESPOND_PATH)
    mode_matrix = pd.read_csv(MODE_MATRIX_PATH)
    dsm_template = pd.read_csv(DSM_TEMPLATE_PATH)

    v3_winners = pd.read_csv(V3_WINNERS)
    v3_metrics = pd.read_csv(V3_FINAL_METRICS)
    v3_decisions = pd.read_csv(V3_DECISIONS)
    v3_featuresets = pd.read_csv(V3_FEATURESETS)

    print_progress("Detecting target columns for current hybrid dataset")
    df, target_by_domain = choose_targets(df)
    target_registry_rows: list[dict[str, Any]] = []
    for d in DOMAINS:
        col = target_by_domain[d]
        target_registry_rows.append(
            {
                "domain": d,
                "target_column": col,
                "n_pos": int(df[col].sum()),
                "n_neg": int((1 - df[col]).sum()),
                "positive_rate": float(df[col].mean()),
            }
        )
    save_csv(pd.DataFrame(target_registry_rows), TABLES / "domain_target_registry.csv")

    print_progress("Building candidate inventory from v3 winners")
    candidates = load_target_candidates(v3_winners, v3_metrics)
    if not candidates:
        raise RuntimeError("No targeted candidates found from v3 artifacts")

    # Build mode feature coverage matrix from matrix/respondability.
    cov_rows: list[dict[str, Any]] = []
    for mode in sorted({m for _, m in TARGETED_CANDIDATES}):
        include_col = f"include_{mode}"
        if include_col not in mode_matrix.columns:
            continue
        mode_feats = set(
            mode_matrix[mode_matrix[include_col].map(normalize_flag).eq("si")]["feature"].astype(str).tolist()
        )
        direct_keep = set(
            respondability[
                respondability["is_direct_input"].astype(str).str.lower().eq("yes")
                & respondability["keep_for_model_v1"].astype(str).str.lower().eq("yes")
            ]["feature"].astype(str)
        )
        derived_keep = set(
            respondability[
                respondability["is_transparent_derived"].astype(str).str.lower().eq("yes")
                & respondability["keep_for_model_v1"].astype(str).str.lower().eq("yes")
            ]["feature"].astype(str)
        )
        direct = sorted([f for f in mode_feats if f in direct_keep and f in df.columns])
        derived = sorted([f for f in mode_feats if f in derived_keep and f in df.columns])
        cov_rows.append(
            {
                "mode": mode,
                "role": parse_role(mode),
                "mode_features_in_matrix": int(len(mode_feats)),
                "direct_usable": int(len(direct)),
                "transparent_derived_usable": int(len(derived)),
                "eligible_union": int(len(set(direct) | set(derived))),
            }
        )
    save_csv(pd.DataFrame(cov_rows).sort_values("mode"), TABLES / "mode_feature_coverage_matrix.csv")

    # Split registry (v3 untouched holdout + alternative splits for stability checks).
    split_registry_rows: list[dict[str, Any]] = []
    alt_splits_by_domain: dict[str, dict[str, dict[str, list[str]]]] = {}
    for domain in sorted({c.domain for c in candidates}):
        base_split = load_v3_ids(domain)
        for part in ["train", "val", "holdout"]:
            split_registry_rows.append(
                {
                    "split_version": "v4_reuse_v3_holdout",
                    "domain": domain,
                    "split_name": part,
                    "n": len(base_split[part]),
                    "source": str((V3_SPLITS / f"domain_{domain}" / f"ids_{part}.csv").relative_to(ROOT)).replace("\\", "/"),
                }
            )
        alt = build_alt_splits(df, target_by_domain[domain], ALT_SPLIT_SEEDS)
        alt_splits_by_domain[domain] = alt
        for split_name, split_map in alt.items():
            for part in ["train", "val", "holdout"]:
                split_registry_rows.append(
                    {
                        "split_version": "v4_alt_seeded",
                        "domain": domain,
                        "split_name": f"{split_name}_{part}",
                        "n": len(split_map[part]),
                        "source": "generated_in_script",
                    }
                )
    save_csv(pd.DataFrame(split_registry_rows), TABLES / "split_registry.csv")

    # Candidate inventory.
    inventory_rows: list[dict[str, Any]] = []
    for c in candidates:
        inventory_rows.append(
            {
                "candidate_id": c.candidate_id,
                "domain": c.domain,
                "mode": c.mode,
                "role": parse_role(c.mode),
                "v3_feature_set_id": c.v3_feature_set_id,
                "v3_config_id": c.v3_config_id,
                "v3_calibration": c.v3_calibration,
                "v3_threshold_policy": c.v3_threshold_policy,
                "v3_threshold": c.v3_threshold,
                "v3_holdout_precision": c.v3_holdout_precision,
                "v3_holdout_recall": c.v3_holdout_recall,
                "v3_holdout_ba": c.v3_holdout_ba,
                "v3_holdout_pr_auc": c.v3_holdout_pr_auc,
                "v3_holdout_brier": c.v3_holdout_brier,
            }
        )
    inventory_df = pd.DataFrame(inventory_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(inventory_df, INV / "hybrid_rf_targeted_fix_inventory.csv")
    inv_md = [
        "# Hybrid RF Targeted Fix v4 - Inventory",
        "",
        "## Candidates",
        md_table(inventory_df),
        "",
        "## Scope Notes",
        "- Campaign is surgical: only fragile/insufficient pairs from v3 were attacked.",
        "- Holdout split is reused from v3 and remains untouched for tuning.",
        "- RandomForest remains the principal and only model family.",
    ]
    write_md(INV / "hybrid_rf_targeted_fix_inventory.md", "\n".join(inv_md))

    print_progress(f"Running targeted training for {len(candidates)} candidates")

    feature_selection_rows: list[dict[str, Any]] = []
    trial_registry_rows: list[dict[str, Any]] = []
    trial_metrics_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    operating_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    seed_stability_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    dsm_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []

    dsm_template_set = set(dsm_template["feature_name"].astype(str).tolist())
    trial_id = 0

    for cand in candidates:
        print_progress(f"Candidate loop: {cand.candidate_id}")
        target_col = target_by_domain[cand.domain]
        split = load_v3_ids(cand.domain)
        train_df = subset_by_ids(df, split["train"])
        val_df = subset_by_ids(df, split["val"])
        hold_df = subset_by_ids(df, split["holdout"])
        y_train = train_df[target_col].astype(int).to_numpy()
        y_val = val_df[target_col].astype(int).to_numpy()
        y_hold = hold_df[target_col].astype(int).to_numpy()

        fs_rows = v3_featuresets[
            (v3_featuresets["domain"] == cand.domain) & (v3_featuresets["mode"] == cand.mode)
        ].copy()
        if fs_rows.empty:
            raise RuntimeError(f"No v3 feature sets found for {cand.candidate_id}")
        fs_map = {str(r["feature_set_id"]): [f for f in parse_feature_pipe(r["feature_list_pipe"]) if f in df.columns] for _, r in fs_rows.iterrows()}
        order = [
            cand.v3_feature_set_id,
            "full_eligible",
            "precision_oriented_subset",
            "balanced_subset",
            "stability_pruned_subset",
            "compact_robust_subset",
            "top_importance_filtered",
        ]
        selected_fs_ids: list[str] = []
        for fsid in order:
            if fsid in fs_map and fsid not in selected_fs_ids and len(fs_map[fsid]) >= 5:
                selected_fs_ids.append(fsid)
        selected_fs_ids = selected_fs_ids[:5]
        if cand.v3_feature_set_id not in selected_fs_ids and cand.v3_feature_set_id in fs_map and len(fs_map[cand.v3_feature_set_id]) >= 5:
            selected_fs_ids = [cand.v3_feature_set_id] + selected_fs_ids
            selected_fs_ids = selected_fs_ids[:5]
        selected_fs = {fsid: fs_map[fsid] for fsid in selected_fs_ids}

        for fsid, feats in selected_fs.items():
            feature_selection_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "feature_set_id": fsid,
                    "n_features": len(feats),
                    "feature_list_pipe": "|".join(feats),
                    "source": "v3_feature_set_reused",
                }
            )

        local_cfgs = build_local_configs(cand.domain, cand.v3_config_id)
        cfg_by_id = {c["config_id"]: c for c in local_cfgs}

        stage1_rows: list[dict[str, Any]] = []
        for fsid, feats in selected_fs.items():
            x_train = prepare_X(train_df, feats)
            x_val = prepare_X(val_df, feats)
            for cfg in local_cfgs:
                pipe = make_pipeline(feats, cfg, cand.v3_seed)
                fit_with_count(pipe, x_train, y_train, int(cfg["n_estimators"]))
                tr_raw = np.clip(pipe.predict_proba(x_train)[:, 1], 1e-6, 1 - 1e-6)
                va_raw = np.clip(pipe.predict_proba(x_val)[:, 1], 1e-6, 1 - 1e-6)
                m_tr = compute_metrics(y_train, tr_raw, 0.5)
                m_va = compute_metrics(y_val, va_raw, 0.5)
                stage_score = objective(m_va) - 0.10 * max(0.0, m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                trial_id += 1
                row = {
                    "trial_id": trial_id,
                    "candidate_id": cand.candidate_id,
                    "stage": "stage1_local_search",
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "role": parse_role(cand.mode),
                    "feature_set_id": fsid,
                    "config_id": cfg["config_id"],
                    "config_hash": config_hash(cfg),
                    "seed": cand.v3_seed,
                    "calibration": "none",
                    "threshold_policy": "default_0_5",
                    "threshold": 0.5,
                    "n_features": len(feats),
                    "stage_score": stage_score,
                    "selected_for_stage2": "no",
                }
                for k, v in m_tr.items():
                    row[f"train_{k}"] = v
                for k, v in m_va.items():
                    row[f"val_{k}"] = v
                row["val_objective"] = stage_score
                row["overfit_gap_ba"] = m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]
                stage1_rows.append(row)
                trial_registry_rows.append(
                    {
                        "trial_id": trial_id,
                        "candidate_id": cand.candidate_id,
                        "stage": "stage1_local_search",
                        "domain": cand.domain,
                        "mode": cand.mode,
                        "role": parse_role(cand.mode),
                        "feature_set_id": fsid,
                        "config_id": cfg["config_id"],
                        "config_hash": config_hash(cfg),
                        "seed": cand.v3_seed,
                        "calibration": "none",
                        "threshold_policy": "default_0_5",
                        "threshold": 0.5,
                        "n_features": len(feats),
                        "selected_for_stage2": "no",
                        "val_objective": stage_score,
                        "overfit_gap_ba": row["overfit_gap_ba"],
                    }
                )
                trial_metrics_rows.append(row.copy())

        stage1_df = pd.DataFrame(stage1_rows)
        stage2_combos = select_stage1_combos(stage1_df, cand.v3_holdout_recall, cand.v3_holdout_ba)
        if (cand.v3_feature_set_id, cand.v3_config_id) not in stage2_combos and cand.v3_config_id in cfg_by_id and cand.v3_feature_set_id in selected_fs:
            stage2_combos.append((cand.v3_feature_set_id, cand.v3_config_id))
        stage2_combos = list(dict.fromkeys(stage2_combos))[:3]

        for combo in stage2_combos:
            mask = (stage1_df["feature_set_id"] == combo[0]) & (stage1_df["config_id"] == combo[1])
            stage1_df.loc[mask, "selected_for_stage2"] = "yes"
        selected_trial_ids = set(stage1_df[stage1_df["selected_for_stage2"] == "yes"]["trial_id"].tolist())
        for row in trial_registry_rows:
            if row["trial_id"] in selected_trial_ids:
                row["selected_for_stage2"] = "yes"

        stage2_rows: list[dict[str, Any]] = []
        per_candidate_seeds = sorted(set([cand.v3_seed] + STAGE2_SEEDS))
        for fsid, cfgid in stage2_combos:
            if fsid not in selected_fs or cfgid not in cfg_by_id:
                continue
            feats = selected_fs[fsid]
            cfg = cfg_by_id[cfgid]
            x_train = prepare_X(train_df, feats)
            x_val = prepare_X(val_df, feats)
            x_hold = prepare_X(hold_df, feats)
            for seed in per_candidate_seeds:
                pipe = make_pipeline(feats, cfg, seed)
                fit_with_count(pipe, x_train, y_train, int(cfg["n_estimators"]))
                tr_raw = np.clip(pipe.predict_proba(x_train)[:, 1], 1e-6, 1 - 1e-6)
                va_raw = np.clip(pipe.predict_proba(x_val)[:, 1], 1e-6, 1 - 1e-6)
                ho_raw = np.clip(pipe.predict_proba(x_hold)[:, 1], 1e-6, 1 - 1e-6)
                calibrated, cal_diag, _ = calibrate_probabilities(y_val, tr_raw, va_raw, ho_raw)
                for cal_method in CAL_METHODS:
                    if cal_method not in calibrated:
                        continue
                    tr_p, va_p, ho_p = calibrated[cal_method]
                    calibration_rows.append(
                        {
                            "candidate_id": cand.candidate_id,
                            "domain": cand.domain,
                            "mode": cand.mode,
                            "feature_set_id": fsid,
                            "config_id": cfgid,
                            "seed": seed,
                            "calibration_method": cal_method,
                            "val_brier": cal_diag[cal_method]["val_brier"],
                            "val_ece": cal_diag[cal_method]["val_ece"],
                            "stage": "stage2",
                        }
                    )
                    for policy in THRESH_POLICIES:
                        thr, pscore = choose_threshold(
                            policy=policy,
                            y_true=y_val,
                            probs=va_p,
                            recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
                        )
                        m_tr = compute_metrics(y_train, tr_p, thr)
                        m_va = compute_metrics(y_val, va_p, thr)
                        m_ho = compute_metrics(y_hold, ho_p, thr)
                        val_obj = objective(m_va) - 0.08 * max(0.0, m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                        trial_id += 1
                        row = {
                            "trial_id": trial_id,
                            "candidate_id": cand.candidate_id,
                            "stage": "stage2_focused",
                            "domain": cand.domain,
                            "mode": cand.mode,
                            "role": parse_role(cand.mode),
                            "feature_set_id": fsid,
                            "config_id": cfgid,
                            "config_hash": config_hash(cfg),
                            "seed": seed,
                            "calibration": cal_method,
                            "threshold_policy": policy,
                            "threshold": thr,
                            "threshold_policy_score": pscore,
                            "n_features": len(feats),
                            "val_objective": val_obj,
                            "overfit_gap_ba": m_tr["balanced_accuracy"] - m_va["balanced_accuracy"],
                            "selected_for_stage2": "yes",
                        }
                        for k, v in m_tr.items():
                            row[f"train_{k}"] = v
                        for k, v in m_va.items():
                            row[f"val_{k}"] = v
                        for k, v in m_ho.items():
                            row[f"holdout_{k}"] = v
                        stage2_rows.append(row)
                        trial_metrics_rows.append(row.copy())
                        trial_registry_rows.append(
                            {
                                "trial_id": trial_id,
                                "candidate_id": cand.candidate_id,
                                "stage": "stage2_focused",
                                "domain": cand.domain,
                                "mode": cand.mode,
                                "role": parse_role(cand.mode),
                                "feature_set_id": fsid,
                                "config_id": cfgid,
                                "config_hash": config_hash(cfg),
                                "seed": seed,
                                "calibration": cal_method,
                                "threshold_policy": policy,
                                "threshold": thr,
                                "n_features": len(feats),
                                "selected_for_stage2": "yes",
                                "val_objective": val_obj,
                                "overfit_gap_ba": row["overfit_gap_ba"],
                            }
                        )

        stage2_df = pd.DataFrame(stage2_rows)
        if stage2_df.empty:
            raise RuntimeError(f"No stage2 results for {cand.candidate_id}")

        grouped = (
            stage2_df.groupby(["feature_set_id", "config_id", "calibration", "threshold_policy"], as_index=False)
            .agg(
                val_precision_mean=("val_precision", "mean"),
                val_recall_mean=("val_recall", "mean"),
                val_ba_mean=("val_balanced_accuracy", "mean"),
                val_pr_auc_mean=("val_pr_auc", "mean"),
                val_brier_mean=("val_brier", "mean"),
                val_ba_std=("val_balanced_accuracy", "std"),
                val_obj_mean=("val_objective", "mean"),
                val_obj_std=("val_objective", "std"),
                n_features=("n_features", "max"),
            )
            .fillna(0.0)
        )
        grouped["guard_ok"] = (
            (grouped["val_recall_mean"] >= max(0.45, cand.v3_holdout_recall - 0.12))
            & (grouped["val_ba_mean"] >= max(0.72, cand.v3_holdout_ba - 0.05))
        )
        grouped["selection_score"] = (
            0.42 * grouped["val_precision_mean"]
            + 0.24 * grouped["val_ba_mean"]
            + 0.18 * grouped["val_pr_auc_mean"]
            + 0.10 * grouped["val_recall_mean"]
            - 0.06 * grouped["val_brier_mean"]
            - 0.06 * grouped["val_ba_std"]
            - 0.05 * grouped["val_obj_std"]
        )
        cand_groups = grouped[grouped["guard_ok"]].copy()
        if cand_groups.empty:
            cand_groups = grouped.copy()
        best_group = cand_groups.sort_values(
            ["selection_score", "val_ba_mean", "val_precision_mean", "n_features"],
            ascending=[False, False, False, True],
        ).iloc[0]
        winner_key = (
            str(best_group["feature_set_id"]),
            str(best_group["config_id"]),
            str(best_group["calibration"]),
            str(best_group["threshold_policy"]),
        )
        winner_seed_rows = stage2_df[
            (stage2_df["feature_set_id"] == winner_key[0])
            & (stage2_df["config_id"] == winner_key[1])
            & (stage2_df["calibration"] == winner_key[2])
            & (stage2_df["threshold_policy"] == winner_key[3])
        ].copy()
        winner_seed = int(winner_seed_rows.sort_values("val_objective", ascending=False).iloc[0]["seed"])
        winner_feats = selected_fs[winner_key[0]]
        winner_cfg = cfg_by_id[winner_key[1]]
        x_train_w = prepare_X(train_df, winner_feats)
        x_val_w = prepare_X(val_df, winner_feats)
        x_hold_w = prepare_X(hold_df, winner_feats)
        winner_pipe = make_pipeline(winner_feats, winner_cfg, winner_seed)
        fit_with_count(winner_pipe, x_train_w, y_train, int(winner_cfg["n_estimators"]))
        tr_raw_w = np.clip(winner_pipe.predict_proba(x_train_w)[:, 1], 1e-6, 1 - 1e-6)
        va_raw_w = np.clip(winner_pipe.predict_proba(x_val_w)[:, 1], 1e-6, 1 - 1e-6)
        ho_raw_w = np.clip(winner_pipe.predict_proba(x_hold_w)[:, 1], 1e-6, 1 - 1e-6)
        cal_probs, cal_diag, cal_transforms = calibrate_probabilities(y_val, tr_raw_w, va_raw_w, ho_raw_w)
        selected_cal = winner_key[2] if winner_key[2] in cal_probs else "none"
        tr_p_w, va_p_w, ho_p_w = cal_probs[selected_cal]
        selected_thr, selected_thr_score = choose_threshold(
            policy=winner_key[3],
            y_true=y_val,
            probs=va_p_w,
            recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
        )
        m_tr_w = compute_metrics(y_train, tr_p_w, selected_thr)
        m_va_w = compute_metrics(y_val, va_p_w, selected_thr)
        m_ho_w = compute_metrics(y_hold, ho_p_w, selected_thr)

        overfit_gap = float(m_tr_w["balanced_accuracy"] - m_va_w["balanced_accuracy"])
        gen_gap = float(abs(m_va_w["balanced_accuracy"] - m_ho_w["balanced_accuracy"]))
        delta_precision = float(m_ho_w["precision"] - cand.v3_holdout_precision)
        delta_recall = float(m_ho_w["recall"] - cand.v3_holdout_recall)
        delta_ba = float(m_ho_w["balanced_accuracy"] - cand.v3_holdout_ba)
        delta_pr = float(m_ho_w["pr_auc"] - cand.v3_holdout_pr_auc)
        delta_brier = float(m_ho_w["brier"] - cand.v3_holdout_brier)
        material_gain = bool(
            (delta_ba >= 0.01)
            or (delta_pr >= 0.01)
            or ((delta_precision >= 0.015) and (delta_recall > -0.03))
            or (delta_brier <= -0.008)
        )
        # Calibration comparison for selected winner.
        for cal_method, (_, va_probs_c, ho_probs_c) in cal_probs.items():
            m_val_05 = compute_metrics(y_val, va_probs_c, 0.5)
            m_ho_05 = compute_metrics(y_hold, ho_probs_c, 0.5)
            calibration_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "feature_set_id": winner_key[0],
                    "config_id": winner_key[1],
                    "seed": winner_seed,
                    "calibration_method": cal_method,
                    "val_brier": cal_diag[cal_method]["val_brier"],
                    "val_ece": cal_diag[cal_method]["val_ece"],
                    "val_precision_at_0_5": m_val_05["precision"],
                    "val_recall_at_0_5": m_val_05["recall"],
                    "val_balanced_accuracy_at_0_5": m_val_05["balanced_accuracy"],
                    "holdout_precision_at_0_5": m_ho_05["precision"],
                    "holdout_recall_at_0_5": m_ho_05["recall"],
                    "holdout_balanced_accuracy_at_0_5": m_ho_05["balanced_accuracy"],
                    "stage": "winner_eval",
                }
            )

        # Operating points over threshold policies.
        for policy in THRESH_POLICIES:
            thr, score = choose_threshold(
                policy=policy,
                y_true=y_val,
                probs=va_p_w,
                recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
            )
            m_val_op = compute_metrics(y_val, va_p_w, thr)
            m_ho_op = compute_metrics(y_hold, ho_p_w, thr)
            operating_row = {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "role": parse_role(cand.mode),
                "winner_feature_set_id": winner_key[0],
                "winner_config_id": winner_key[1],
                "winner_seed": winner_seed,
                "calibration": selected_cal,
                "threshold_policy": policy,
                "threshold": thr,
                "policy_score": score,
                "is_selected_policy": "yes" if policy == winner_key[3] else "no",
                "val_precision": m_val_op["precision"],
                "val_recall": m_val_op["recall"],
                "val_specificity": m_val_op["specificity"],
                "val_balanced_accuracy": m_val_op["balanced_accuracy"],
                "val_f1": m_val_op["f1"],
                "val_roc_auc": m_val_op["roc_auc"],
                "val_pr_auc": m_val_op["pr_auc"],
                "val_brier": m_val_op["brier"],
                "holdout_precision": m_ho_op["precision"],
                "holdout_recall": m_ho_op["recall"],
                "holdout_specificity": m_ho_op["specificity"],
                "holdout_balanced_accuracy": m_ho_op["balanced_accuracy"],
                "holdout_f1": m_ho_op["f1"],
                "holdout_roc_auc": m_ho_op["roc_auc"],
                "holdout_pr_auc": m_ho_op["pr_auc"],
                "holdout_brier": m_ho_op["brier"],
            }
            operating_rows.append(operating_row)
            threshold_rows.append(operating_row.copy())

        # Bootstrap CI on holdout.
        boot = bootstrap_metric_ci(y_hold, ho_p_w, selected_thr, n_boot=300, seed=winner_seed + 11)
        bootstrap_rows.append(
            {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "feature_set_id": winner_key[0],
                "config_id": winner_key[1],
                "calibration": selected_cal,
                "threshold_policy": winner_key[3],
                "threshold": selected_thr,
                **boot,
            }
        )
        # Seed stability for selected configuration.
        seed_metric_rows_local: list[dict[str, Any]] = []
        for s in STABILITY_SEEDS:
            pipe_s = make_pipeline(winner_feats, winner_cfg, s)
            fit_with_count(pipe_s, x_train_w, y_train, int(winner_cfg["n_estimators"]))
            tr_raw_s = np.clip(pipe_s.predict_proba(x_train_w)[:, 1], 1e-6, 1 - 1e-6)
            va_raw_s = np.clip(pipe_s.predict_proba(x_val_w)[:, 1], 1e-6, 1 - 1e-6)
            ho_raw_s = np.clip(pipe_s.predict_proba(x_hold_w)[:, 1], 1e-6, 1 - 1e-6)
            cal_s, _, _ = calibrate_probabilities(y_val, tr_raw_s, va_raw_s, ho_raw_s)
            tr_ps, va_ps, ho_ps = cal_s[selected_cal] if selected_cal in cal_s else cal_s["none"]
            thr_s, _ = choose_threshold(
                policy=winner_key[3],
                y_true=y_val,
                probs=va_ps,
                recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
            )
            m_ho_s = compute_metrics(y_hold, ho_ps, thr_s)
            row_s = {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "stability_type": "seed",
                "seed_or_split": f"seed_{s}",
                "precision": m_ho_s["precision"],
                "recall": m_ho_s["recall"],
                "balanced_accuracy": m_ho_s["balanced_accuracy"],
                "pr_auc": m_ho_s["pr_auc"],
                "brier": m_ho_s["brier"],
                "threshold": thr_s,
            }
            seed_metric_rows_local.append(row_s)
            seed_stability_rows.append(row_s)

        # Split sensitivity.
        alt_splits = alt_splits_by_domain[cand.domain]
        for split_name, split_map in alt_splits.items():
            tr_df_alt = subset_by_ids(df, split_map["train"])
            va_df_alt = subset_by_ids(df, split_map["val"])
            ho_df_alt = subset_by_ids(df, split_map["holdout"])
            y_tr_alt = tr_df_alt[target_col].astype(int).to_numpy()
            y_va_alt = va_df_alt[target_col].astype(int).to_numpy()
            y_ho_alt = ho_df_alt[target_col].astype(int).to_numpy()
            x_tr_alt = prepare_X(tr_df_alt, winner_feats)
            x_va_alt = prepare_X(va_df_alt, winner_feats)
            x_ho_alt = prepare_X(ho_df_alt, winner_feats)
            pipe_alt = make_pipeline(winner_feats, winner_cfg, winner_seed)
            fit_with_count(pipe_alt, x_tr_alt, y_tr_alt, int(winner_cfg["n_estimators"]))
            tr_raw_alt = np.clip(pipe_alt.predict_proba(x_tr_alt)[:, 1], 1e-6, 1 - 1e-6)
            va_raw_alt = np.clip(pipe_alt.predict_proba(x_va_alt)[:, 1], 1e-6, 1 - 1e-6)
            ho_raw_alt = np.clip(pipe_alt.predict_proba(x_ho_alt)[:, 1], 1e-6, 1 - 1e-6)
            cal_alt, _, _ = calibrate_probabilities(y_va_alt, tr_raw_alt, va_raw_alt, ho_raw_alt)
            tr_p_alt, va_p_alt, ho_p_alt = cal_alt[selected_cal] if selected_cal in cal_alt else cal_alt["none"]
            thr_alt, _ = choose_threshold(
                policy=winner_key[3],
                y_true=y_va_alt,
                probs=va_p_alt,
                recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
            )
            m_ho_alt = compute_metrics(y_ho_alt, ho_p_alt, thr_alt)
            seed_stability_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stability_type": "split",
                    "seed_or_split": split_name,
                    "precision": m_ho_alt["precision"],
                    "recall": m_ho_alt["recall"],
                    "balanced_accuracy": m_ho_alt["balanced_accuracy"],
                    "pr_auc": m_ho_alt["pr_auc"],
                    "brier": m_ho_alt["brier"],
                    "threshold": thr_alt,
                }
            )
        # Feature importances and ablation.
        imp_rank = aggregate_importance(winner_pipe, winner_feats)
        top_features = imp_rank.head(10).index.tolist()
        dom_share = float(imp_rank.iloc[0]) if not imp_rank.empty else 0.0
        ablation_rows.append(
            {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "ablation_type": "winner_top_features",
                "k": 0,
                "removed_features": "",
                "remaining_features": len(winner_feats),
                "precision": m_ho_w["precision"],
                "recall": m_ho_w["recall"],
                "balanced_accuracy": m_ho_w["balanced_accuracy"],
                "pr_auc": m_ho_w["pr_auc"],
                "brier": m_ho_w["brier"],
                "delta_ba_vs_winner": 0.0,
                "delta_pr_auc_vs_winner": 0.0,
                "top10_features_pipe": "|".join(top_features),
                "dominant_feature_share": dom_share,
            }
        )
        for k in [1, 3, 5]:
            removed = top_features[:k]
            if not removed:
                continue
            rem_feats = [f for f in winner_feats if f not in set(removed)]
            if len(rem_feats) < 5:
                continue
            x_tr_ab = prepare_X(train_df, rem_feats)
            x_va_ab = prepare_X(val_df, rem_feats)
            x_ho_ab = prepare_X(hold_df, rem_feats)
            pipe_ab = make_pipeline(rem_feats, winner_cfg, winner_seed)
            fit_with_count(pipe_ab, x_tr_ab, y_train, int(winner_cfg["n_estimators"]))
            tr_raw_ab = np.clip(pipe_ab.predict_proba(x_tr_ab)[:, 1], 1e-6, 1 - 1e-6)
            va_raw_ab = np.clip(pipe_ab.predict_proba(x_va_ab)[:, 1], 1e-6, 1 - 1e-6)
            ho_raw_ab = np.clip(pipe_ab.predict_proba(x_ho_ab)[:, 1], 1e-6, 1 - 1e-6)
            cal_ab, _, _ = calibrate_probabilities(y_val, tr_raw_ab, va_raw_ab, ho_raw_ab)
            _, va_p_ab, ho_p_ab = cal_ab[selected_cal] if selected_cal in cal_ab else cal_ab["none"]
            thr_ab, _ = choose_threshold(
                policy=winner_key[3],
                y_true=y_val,
                probs=va_p_ab,
                recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
            )
            m_ab = compute_metrics(y_hold, ho_p_ab, thr_ab)
            ablation_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "ablation_type": "drop_topk",
                    "k": k,
                    "removed_features": "|".join(removed),
                    "remaining_features": len(rem_feats),
                    "precision": m_ab["precision"],
                    "recall": m_ab["recall"],
                    "balanced_accuracy": m_ab["balanced_accuracy"],
                    "pr_auc": m_ab["pr_auc"],
                    "brier": m_ab["brier"],
                    "delta_ba_vs_winner": float(m_ab["balanced_accuracy"] - m_ho_w["balanced_accuracy"]),
                    "delta_pr_auc_vs_winner": float(m_ab["pr_auc"] - m_ho_w["pr_auc"]),
                    "top10_features_pipe": "|".join(top_features),
                    "dominant_feature_share": dom_share,
                }
            )
        # Stress tests.
        stress_scenarios: list[tuple[str, str, np.ndarray, float]] = []
        for ratio in [0.05, 0.10, 0.20]:
            x_miss = inject_missing(x_hold_w, winner_feats, ratio=ratio, seed=winner_seed + int(ratio * 1000))
            ho_raw_miss = np.clip(winner_pipe.predict_proba(x_miss)[:, 1], 1e-6, 1 - 1e-6)
            ho_p_miss = cal_transforms[selected_cal](ho_raw_miss) if selected_cal in cal_transforms else ho_raw_miss
            stress_scenarios.append(("missingness", f"missing_{int(ratio*100)}pct", ho_p_miss, selected_thr))

        for ratio in [0.05, 0.10]:
            x_noise = inject_light_noise(x_hold_w, winner_feats, noise_scale=ratio, seed=winner_seed + int(ratio * 1000) + 55)
            ho_raw_noise = np.clip(winner_pipe.predict_proba(x_noise)[:, 1], 1e-6, 1 - 1e-6)
            ho_p_noise = cal_transforms[selected_cal](ho_raw_noise) if selected_cal in cal_transforms else ho_raw_noise
            stress_scenarios.append(("light_noise", f"noise_{int(ratio*100)}pct_std", ho_p_noise, selected_thr))

        for dthr in [-0.10, -0.05, 0.05, 0.10]:
            stress_scenarios.append(("threshold_sensitivity", f"threshold_shift_{dthr:+.2f}", ho_p_w, float(np.clip(selected_thr + dthr, 0.05, 0.95))))

        for s_type, scenario, probs_sc, thr_sc in stress_scenarios:
            m_sc = compute_metrics(y_hold, probs_sc, thr_sc)
            stress_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stress_type": s_type,
                    "scenario": scenario,
                    "threshold": thr_sc,
                    "precision": m_sc["precision"],
                    "recall": m_sc["recall"],
                    "balanced_accuracy": m_sc["balanced_accuracy"],
                    "pr_auc": m_sc["pr_auc"],
                    "brier": m_sc["brier"],
                    "delta_precision_vs_winner": float(m_sc["precision"] - m_ho_w["precision"]),
                    "delta_recall_vs_winner": float(m_sc["recall"] - m_ho_w["recall"]),
                    "delta_ba_vs_winner": float(m_sc["balanced_accuracy"] - m_ho_w["balanced_accuracy"]),
                    "delta_pr_auc_vs_winner": float(m_sc["pr_auc"] - m_ho_w["pr_auc"]),
                    "delta_brier_vs_winner": float(m_sc["brier"] - m_ho_w["brier"]),
                }
            )
        # DSM5 vs clean-base decomposition for targeted candidate winner.
        dsm_feats = [f for f in winner_feats if is_dsm5_feature(f, dsm_template_set)]
        clean_feats = [f for f in winner_feats if f not in set(dsm_feats)]
        variants = [("clean_base_only", clean_feats), ("dsm5_only", dsm_feats), ("hybrid_full", winner_feats)]
        variant_metrics: dict[str, dict[str, float]] = {}
        for variant, feats in variants:
            if len(feats) < 5:
                dsm_rows.append(
                    {
                        "candidate_id": cand.candidate_id,
                        "domain": cand.domain,
                        "mode": cand.mode,
                        "variant": variant,
                        "n_features": len(feats),
                        "status": "insufficient_features",
                    }
                )
                continue
            x_tr_v = prepare_X(train_df, feats)
            x_va_v = prepare_X(val_df, feats)
            x_ho_v = prepare_X(hold_df, feats)
            pipe_v = make_pipeline(feats, winner_cfg, winner_seed)
            fit_with_count(pipe_v, x_tr_v, y_train, int(winner_cfg["n_estimators"]))
            tr_raw_v = np.clip(pipe_v.predict_proba(x_tr_v)[:, 1], 1e-6, 1 - 1e-6)
            va_raw_v = np.clip(pipe_v.predict_proba(x_va_v)[:, 1], 1e-6, 1 - 1e-6)
            ho_raw_v = np.clip(pipe_v.predict_proba(x_ho_v)[:, 1], 1e-6, 1 - 1e-6)
            cal_v, _, _ = calibrate_probabilities(y_val, tr_raw_v, va_raw_v, ho_raw_v)
            _, va_p_v, ho_p_v = cal_v[selected_cal] if selected_cal in cal_v else cal_v["none"]
            thr_v, _ = choose_threshold(
                policy=winner_key[3],
                y_true=y_val,
                probs=va_p_v,
                recall_floor=max(0.45, cand.v3_holdout_recall - 0.12),
            )
            m_v = compute_metrics(y_hold, ho_p_v, thr_v)
            variant_metrics[variant] = m_v
            dsm_rows.append(
                {
                    "candidate_id": cand.candidate_id,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "variant": variant,
                    "n_features": len(feats),
                    "status": "ok",
                    "precision": m_v["precision"],
                    "recall": m_v["recall"],
                    "balanced_accuracy": m_v["balanced_accuracy"],
                    "pr_auc": m_v["pr_auc"],
                    "brier": m_v["brier"],
                }
            )

        hybrid_minus_clean_ba = np.nan
        hybrid_minus_clean_pr = np.nan
        hybrid_minus_clean_prec = np.nan
        hybrid_minus_clean_brier = np.nan
        if "hybrid_full" in variant_metrics and "clean_base_only" in variant_metrics:
            hybrid_minus_clean_ba = float(variant_metrics["hybrid_full"]["balanced_accuracy"] - variant_metrics["clean_base_only"]["balanced_accuracy"])
            hybrid_minus_clean_pr = float(variant_metrics["hybrid_full"]["pr_auc"] - variant_metrics["clean_base_only"]["pr_auc"])
            hybrid_minus_clean_prec = float(variant_metrics["hybrid_full"]["precision"] - variant_metrics["clean_base_only"]["precision"])
            hybrid_minus_clean_brier = float(variant_metrics["hybrid_full"]["brier"] - variant_metrics["clean_base_only"]["brier"])

        # Seed stability summary for decision.
        seed_df_local = pd.DataFrame(seed_metric_rows_local)
        seed_ba_std = float(seed_df_local["balanced_accuracy"].std()) if not seed_df_local.empty else np.nan
        seed_prec_std = float(seed_df_local["precision"].std()) if not seed_df_local.empty else np.nan
        seed_recall_std = float(seed_df_local["recall"].std()) if not seed_df_local.empty else np.nan
        seed_pr_std = float(seed_df_local["pr_auc"].std()) if not seed_df_local.empty else np.nan
        seed_brier_std = float(seed_df_local["brier"].std()) if not seed_df_local.empty else np.nan

        cand_stress = pd.DataFrame([r for r in stress_rows if r["candidate_id"] == cand.candidate_id])
        worst_ba_drop = float(cand_stress["delta_ba_vs_winner"].min()) if not cand_stress.empty else 0.0
        worst_prec_drop = float(cand_stress["delta_precision_vs_winner"].min()) if not cand_stress.empty else 0.0

        final_rows.append(
            {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "role": parse_role(cand.mode),
                "winner_feature_set_id": winner_key[0],
                "winner_config_id": winner_key[1],
                "winner_calibration": selected_cal,
                "winner_threshold_policy": winner_key[3],
                "winner_threshold": selected_thr,
                "winner_threshold_policy_score": selected_thr_score,
                "winner_seed": winner_seed,
                "n_features": len(winner_feats),
                "top_features": "|".join(top_features[:8]),
                "train_precision": m_tr_w["precision"],
                "train_recall": m_tr_w["recall"],
                "train_specificity": m_tr_w["specificity"],
                "train_balanced_accuracy": m_tr_w["balanced_accuracy"],
                "train_f1": m_tr_w["f1"],
                "train_roc_auc": m_tr_w["roc_auc"],
                "train_pr_auc": m_tr_w["pr_auc"],
                "train_brier": m_tr_w["brier"],
                "val_precision": m_va_w["precision"],
                "val_recall": m_va_w["recall"],
                "val_specificity": m_va_w["specificity"],
                "val_balanced_accuracy": m_va_w["balanced_accuracy"],
                "val_f1": m_va_w["f1"],
                "val_roc_auc": m_va_w["roc_auc"],
                "val_pr_auc": m_va_w["pr_auc"],
                "val_brier": m_va_w["brier"],
                "holdout_precision": m_ho_w["precision"],
                "holdout_recall": m_ho_w["recall"],
                "holdout_specificity": m_ho_w["specificity"],
                "holdout_balanced_accuracy": m_ho_w["balanced_accuracy"],
                "holdout_f1": m_ho_w["f1"],
                "holdout_roc_auc": m_ho_w["roc_auc"],
                "holdout_pr_auc": m_ho_w["pr_auc"],
                "holdout_brier": m_ho_w["brier"],
                "overfit_gap_train_val_ba": overfit_gap,
                "generalization_gap_val_holdout_ba": gen_gap,
                "seed_ba_std": seed_ba_std,
                "seed_precision_std": seed_prec_std,
                "seed_recall_std": seed_recall_std,
                "seed_pr_auc_std": seed_pr_std,
                "seed_brier_std": seed_brier_std,
                "worst_stress_ba_drop": worst_ba_drop,
                "worst_stress_precision_drop": worst_prec_drop,
                "dominant_feature_share": dom_share,
                "hybrid_minus_clean_balanced_accuracy": hybrid_minus_clean_ba,
                "hybrid_minus_clean_pr_auc": hybrid_minus_clean_pr,
                "hybrid_minus_clean_precision": hybrid_minus_clean_prec,
                "hybrid_minus_clean_brier": hybrid_minus_clean_brier,
                "v3_holdout_precision": cand.v3_holdout_precision,
                "v3_holdout_recall": cand.v3_holdout_recall,
                "v3_holdout_balanced_accuracy": cand.v3_holdout_ba,
                "v3_holdout_pr_auc": cand.v3_holdout_pr_auc,
                "v3_holdout_brier": cand.v3_holdout_brier,
                "delta_precision_vs_v3": delta_precision,
                "delta_recall_vs_v3": delta_recall,
                "delta_balanced_accuracy_vs_v3": delta_ba,
                "delta_pr_auc_vs_v3": delta_pr,
                "delta_brier_vs_v3": delta_brier,
                "material_improvement_vs_v3": "yes" if material_gain else "no",
            }
        )
    # Persist core tables.
    trials_registry_df = pd.DataFrame(trial_registry_rows).sort_values(["trial_id"]).reset_index(drop=True)
    trials_metrics_df = pd.DataFrame(trial_metrics_rows).sort_values(["trial_id"]).reset_index(drop=True)
    feature_selection_df = pd.DataFrame(feature_selection_rows).sort_values(["candidate_id", "feature_set_id"]).reset_index(drop=True)
    calibration_df = pd.DataFrame(calibration_rows).sort_values(["candidate_id", "stage", "seed"]).reset_index(drop=True)
    threshold_df = pd.DataFrame(threshold_rows).sort_values(["candidate_id", "threshold_policy"]).reset_index(drop=True)
    operating_df = pd.DataFrame(operating_rows).sort_values(["candidate_id", "threshold_policy"]).reset_index(drop=True)
    bootstrap_df = pd.DataFrame(bootstrap_rows).sort_values(["candidate_id"]).reset_index(drop=True)
    stability_df = pd.DataFrame(seed_stability_rows).sort_values(["candidate_id", "stability_type", "seed_or_split"]).reset_index(drop=True)
    ablation_df = pd.DataFrame(ablation_rows).sort_values(["candidate_id", "ablation_type", "k"]).reset_index(drop=True)
    stress_df = pd.DataFrame(stress_rows).sort_values(["candidate_id", "stress_type", "scenario"]).reset_index(drop=True)
    dsm_df = pd.DataFrame(dsm_rows).sort_values(["candidate_id", "variant"]).reset_index(drop=True)
    final_df = pd.DataFrame(final_rows).sort_values(["domain", "mode"]).reset_index(drop=True)

    save_csv(trials_registry_df, TRIALS / "hybrid_rf_targeted_fix_trial_registry.csv")
    save_csv(trials_metrics_df, TRIALS / "hybrid_rf_targeted_fix_trial_metrics_full.csv")
    save_csv(feature_selection_df, FEAT / "hybrid_rf_targeted_feature_selection.csv")
    save_csv(calibration_df, CAL / "hybrid_rf_targeted_calibration.csv")
    save_csv(threshold_df, THR / "hybrid_rf_targeted_thresholds.csv")
    save_csv(operating_df, TABLES / "hybrid_rf_targeted_operating_points.csv")
    save_csv(bootstrap_df, BOOT / "hybrid_rf_targeted_bootstrap_intervals.csv")
    save_csv(stability_df, STAB / "hybrid_rf_targeted_seed_stability.csv")
    save_csv(ablation_df, ABL / "hybrid_rf_targeted_ablation.csv")
    save_csv(stress_df, STRESS / "hybrid_rf_targeted_stress.csv")
    save_csv(dsm_df, TABLES / "hybrid_rf_targeted_dsm5_vs_cleanbase.csv")

    # Stability summary matrix.
    stability_summary_rows: list[dict[str, Any]] = []
    for cid, grp in stability_df.groupby("candidate_id"):
        g_seed = grp[grp["stability_type"] == "seed"]
        g_split = grp[grp["stability_type"] == "split"]
        stability_summary_rows.append(
            {
                "candidate_id": cid,
                "seed_ba_std": float(g_seed["balanced_accuracy"].std()) if not g_seed.empty else np.nan,
                "seed_precision_std": float(g_seed["precision"].std()) if not g_seed.empty else np.nan,
                "seed_recall_std": float(g_seed["recall"].std()) if not g_seed.empty else np.nan,
                "split_ba_std": float(g_split["balanced_accuracy"].std()) if not g_split.empty else np.nan,
                "split_precision_std": float(g_split["precision"].std()) if not g_split.empty else np.nan,
                "split_recall_std": float(g_split["recall"].std()) if not g_split.empty else np.nan,
                "seed_ba_min": float(g_seed["balanced_accuracy"].min()) if not g_seed.empty else np.nan,
                "seed_ba_max": float(g_seed["balanced_accuracy"].max()) if not g_seed.empty else np.nan,
            }
        )
    stability_summary_df = pd.DataFrame(stability_summary_rows).sort_values("candidate_id").reset_index(drop=True)
    save_csv(stability_summary_df, TABLES / "hybrid_rf_candidate_stability_summary.csv")
    # Decisions.
    ranked = final_df.copy()
    ranked["ranking_score"] = (
        0.40 * ranked["holdout_precision"]
        + 0.24 * ranked["holdout_balanced_accuracy"]
        + 0.18 * ranked["holdout_pr_auc"]
        + 0.10 * ranked["holdout_recall"]
        - 0.08 * ranked["holdout_brier"]
    )
    ranked = ranked.sort_values(["ranking_score", "holdout_balanced_accuracy"], ascending=False).reset_index(drop=True)

    overfit_flag = ranked["overfit_gap_train_val_ba"] > 0.07
    gen_flag = ranked["generalization_gap_val_holdout_ba"] > 0.06
    seed_fragile = (ranked["seed_ba_std"] > 0.03) | (ranked["seed_precision_std"] > 0.04)
    stress_fragile = (ranked["worst_stress_ba_drop"] < -0.08) | (ranked["worst_stress_precision_drop"] < -0.08)
    severe_drop_vs_v3 = (
        (ranked["delta_balanced_accuracy_vs_v3"] <= -0.015)
        | (ranked["delta_pr_auc_vs_v3"] <= -0.015)
        | ((ranked["delta_precision_vs_v3"] <= -0.03) & (ranked["delta_recall_vs_v3"] <= -0.03))
    )
    strong_metrics = (
        (ranked["holdout_precision"] >= 0.84)
        & (ranked["holdout_balanced_accuracy"] >= 0.86)
        & (ranked["holdout_pr_auc"] >= 0.84)
        & (ranked["holdout_recall"] >= 0.62)
    )
    reasonable_metrics = (
        (ranked["holdout_precision"] >= 0.78)
        & (ranked["holdout_balanced_accuracy"] >= 0.82)
        & (ranked["holdout_pr_auc"] >= 0.78)
        & (ranked["holdout_recall"] >= 0.55)
    )
    material = ranked["material_improvement_vs_v3"] == "yes"

    decisions = ranked.copy()
    decisions["promotion_decision"] = "PROMOTE_WITH_CAVEAT"
    decisions.loc[severe_drop_vs_v3, "promotion_decision"] = "REJECT_AS_PRIMARY"
    decisions.loc[
        (~severe_drop_vs_v3)
        & (overfit_flag | gen_flag | seed_fragile | stress_fragile)
        & ~strong_metrics,
        "promotion_decision",
    ] = "HOLD_FOR_FINAL_LIMITATION"
    decisions.loc[
        (~severe_drop_vs_v3)
        & (~overfit_flag)
        & (~gen_flag)
        & (~seed_fragile)
        & (~stress_fragile)
        & strong_metrics
        & material,
        "promotion_decision",
    ] = "PROMOTE_NOW"
    decisions.loc[
        (~severe_drop_vs_v3)
        & (~overfit_flag)
        & (~gen_flag)
        & (~seed_fragile)
        & (~stress_fragile)
        & (~material)
        & reasonable_metrics,
        "promotion_decision",
    ] = "CEILING_CONFIRMED_NO_MATERIAL_GAIN"
    decisions.loc[
        (~severe_drop_vs_v3)
        & (~material)
        & (~reasonable_metrics),
        "promotion_decision",
    ] = "HOLD_FOR_FINAL_LIMITATION"

    decisions["decision_reason"] = np.where(
        decisions["promotion_decision"] == "PROMOTE_NOW",
        "material_gain_plus_stability",
        np.where(
            decisions["promotion_decision"] == "PROMOTE_WITH_CAVEAT",
            "usable_but_with_limitations",
            np.where(
                decisions["promotion_decision"] == "CEILING_CONFIRMED_NO_MATERIAL_GAIN",
                "stable_no_material_gain_vs_v3",
                np.where(
                    decisions["promotion_decision"] == "HOLD_FOR_FINAL_LIMITATION",
                    "fragility_or_metric_limit_without_safe_gain",
                    "worse_than_v3_or_unstable",
                ),
            ),
        ),
    )

    save_csv(ranked, TABLES / "hybrid_rf_targeted_ranked_candidates.csv")
    save_csv(decisions, TABLES / "hybrid_rf_targeted_decisions.csv")

    # Final champions by domain (merge attacked candidates + carry-forward v3 for untouched domain/modes).
    v3_full = pd.read_csv(V3_FINAL_METRICS)
    v3_full["source_line"] = "v3_carry_forward"
    v3_full["promotion_decision"] = "CARRY_FORWARD_V3"
    attacked_lookup = {(r["domain"], r["mode"]): r for _, r in decisions.iterrows()}
    merged_rows: list[dict[str, Any]] = []
    for _, row in v3_full.iterrows():
        key = (str(row["domain"]), str(row["mode"]))
        if key in attacked_lookup:
            r = attacked_lookup[key]
            merged_rows.append(
                {
                    "domain": r["domain"],
                    "mode": r["mode"],
                    "role": r["role"],
                    "precision": r["holdout_precision"],
                    "recall": r["holdout_recall"],
                    "balanced_accuracy": r["holdout_balanced_accuracy"],
                    "pr_auc": r["holdout_pr_auc"],
                    "brier": r["holdout_brier"],
                    "promotion_decision": r["promotion_decision"],
                    "source_line": "v4_targeted",
                }
            )
        else:
            merged_rows.append(
                {
                    "domain": row["domain"],
                    "mode": row["mode"],
                    "role": row["role"],
                    "precision": row["holdout_precision"],
                    "recall": row["holdout_recall"],
                    "balanced_accuracy": row["holdout_balanced_accuracy"],
                    "pr_auc": row["holdout_pr_auc"],
                    "brier": row["holdout_brier"],
                    "promotion_decision": "CARRY_FORWARD_V3",
                    "source_line": "v3_carry_forward",
                }
            )
    merged_df = pd.DataFrame(merged_rows)
    rank_map = {
        "PROMOTE_NOW": 5,
        "PROMOTE_WITH_CAVEAT": 4,
        "CEILING_CONFIRMED_NO_MATERIAL_GAIN": 3,
        "HOLD_FOR_FINAL_LIMITATION": 2,
        "REJECT_AS_PRIMARY": 1,
        "CARRY_FORWARD_V3": 3,
    }
    merged_df["decision_rank"] = merged_df["promotion_decision"].map(rank_map).fillna(1)
    champions_rows: list[dict[str, Any]] = []
    for domain in DOMAINS:
        ddf = merged_df[merged_df["domain"] == domain].copy()
        if ddf.empty:
            continue
        ddf["score"] = (
            0.40 * ddf["precision"]
            + 0.24 * ddf["balanced_accuracy"]
            + 0.18 * ddf["pr_auc"]
            + 0.10 * ddf["recall"]
            - 0.08 * ddf["brier"]
        )
        ddf = ddf.sort_values(["decision_rank", "score", "balanced_accuracy", "precision"], ascending=False)
        best = ddf.iloc[0].copy()
        if str(best["mode"]).endswith("full"):
            mode23 = str(best["mode"]).replace("_full", "_2_3")
            alt = ddf[ddf["mode"] == mode23]
            if not alt.empty:
                a = alt.iloc[0]
                if (
                    float(best["balanced_accuracy"] - a["balanced_accuracy"]) < 0.01
                    and float(best["pr_auc"] - a["pr_auc"]) < 0.01
                    and float(best["precision"] - a["precision"]) < 0.015
                ):
                    best = a
        champions_rows.append(
            {
                "domain": domain,
                "champion_mode": best["mode"],
                "champion_role": best["role"],
                "champion_decision": best["promotion_decision"],
                "champion_source_line": best["source_line"],
                "precision": best["precision"],
                "recall": best["recall"],
                "balanced_accuracy": best["balanced_accuracy"],
                "pr_auc": best["pr_auc"],
                "brier": best["brier"],
            }
        )
    champions_df = pd.DataFrame(champions_rows).sort_values("domain").reset_index(drop=True)
    save_csv(champions_df, TABLES / "hybrid_rf_targeted_final_champions.csv")
    # Reports.
    overfit_yes = bool(((decisions["overfit_gap_train_val_ba"] > 0.07) | (decisions["generalization_gap_val_holdout_ba"] > 0.06)).any())
    generalization_yes = bool(
        (
            (decisions["holdout_balanced_accuracy"] >= 0.80)
            & (decisions["holdout_precision"] >= 0.78)
            & (decisions["holdout_recall"] >= 0.55)
        ).mean()
        >= 0.70
    )

    overfit_report = [
        "# Hybrid RF Targeted v4 - Overfitting Audit",
        "",
        "## Candidate gaps",
        md_table(
            decisions[
                [
                    "candidate_id",
                    "overfit_gap_train_val_ba",
                    "generalization_gap_val_holdout_ba",
                    "seed_ba_std",
                    "worst_stress_ba_drop",
                    "promotion_decision",
                ]
            ].sort_values("candidate_id")
        ),
        "",
        f"- overfitting_evidence: {'yes' if overfit_yes else 'no'}",
        "- thresholds: train-val BA gap > 0.07 or val-holdout BA gap > 0.06.",
    ]
    write_md(REPORTS / "hybrid_rf_targeted_overfitting_audit.md", "\n".join(overfit_report))

    gen_report = [
        "# Hybrid RF Targeted v4 - Generalization Audit",
        "",
        "## Holdout metrics and stability",
        md_table(
            decisions[
                [
                    "candidate_id",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "seed_ba_std",
                    "seed_precision_std",
                    "promotion_decision",
                ]
            ].sort_values("candidate_id")
        ),
        "",
        f"- generalization_evidence: {'yes' if generalization_yes else 'no'}",
    ]
    write_md(REPORTS / "hybrid_rf_targeted_generalization_audit.md", "\n".join(gen_report))

    fs_report = [
        "# Hybrid RF Targeted v4 - Feature Strategy",
        "",
        "## Feature sets explored",
        md_table(
            feature_selection_df[
                ["candidate_id", "feature_set_id", "n_features"]
            ].sort_values(["candidate_id", "n_features"])
        ),
        "",
        "## Ablation highlights",
        md_table(
            ablation_df[
                [
                    "candidate_id",
                    "ablation_type",
                    "k",
                    "delta_ba_vs_winner",
                    "delta_pr_auc_vs_winner",
                    "dominant_feature_share",
                ]
            ].sort_values(["candidate_id", "ablation_type", "k"])
        ),
    ]
    write_md(REPORTS / "hybrid_rf_targeted_feature_strategy.md", "\n".join(fs_report))

    ceiling_rows = decisions[
        [
            "candidate_id",
            "material_improvement_vs_v3",
            "delta_balanced_accuracy_vs_v3",
            "delta_pr_auc_vs_v3",
            "delta_precision_vs_v3",
            "delta_recall_vs_v3",
            "promotion_decision",
        ]
    ].sort_values("candidate_id")
    ceiling_report = [
        "# Hybrid RF Targeted v4 - Ceiling Decision",
        "",
        "## Material gain vs v3",
        md_table(ceiling_rows),
        "",
        f"- candidates_material_gain_count: {int((decisions['material_improvement_vs_v3'] == 'yes').sum())}",
        f"- candidates_no_material_gain_count: {int((decisions['material_improvement_vs_v3'] == 'no').sum())}",
        "- CEILING_CONFIRMED_NO_MATERIAL_GAIN is assigned when stability is acceptable and no material gain appears.",
    ]
    write_md(REPORTS / "hybrid_rf_targeted_ceiling_decision.md", "\n".join(ceiling_report))

    # 2/3 vs full comparison focused table in report.
    compare_rows: list[dict[str, Any]] = []
    decision_lookup = decisions.set_index(["domain", "mode"])
    for domain in sorted(set(decisions["domain"])):
        for role in ["caregiver", "psychologist"]:
            m23 = f"{role}_2_3"
            mfull = f"{role}_full"
            k23 = (domain, m23)
            kf = (domain, mfull)
            if k23 in decision_lookup.index and kf in decision_lookup.index:
                r23 = decision_lookup.loc[k23]
                rf = decision_lookup.loc[kf]
                compare_rows.append(
                    {
                        "domain": domain,
                        "role": role,
                        "ba_full_minus_2_3": float(rf["holdout_balanced_accuracy"] - r23["holdout_balanced_accuracy"]),
                        "pr_auc_full_minus_2_3": float(rf["holdout_pr_auc"] - r23["holdout_pr_auc"]),
                        "precision_full_minus_2_3": float(rf["holdout_precision"] - r23["holdout_precision"]),
                        "preferred_mode_operational": m23
                        if (
                            float(rf["holdout_balanced_accuracy"] - r23["holdout_balanced_accuracy"]) < 0.01
                            and float(rf["holdout_pr_auc"] - r23["holdout_pr_auc"]) < 0.01
                            and float(rf["holdout_precision"] - r23["holdout_precision"]) < 0.015
                        )
                        else mfull,
                    }
                )
    compare_df = pd.DataFrame(compare_rows)

    exec_report = [
        "# Hybrid RF Targeted v4 - Executive Summary",
        "",
        "## Final decisions by candidate",
        md_table(
            decisions[
                [
                    "candidate_id",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "material_improvement_vs_v3",
                    "promotion_decision",
                ]
            ].sort_values("candidate_id")
        ),
        "",
        "## 2/3 vs full (targeted comparisons)",
        md_table(compare_df) if not compare_df.empty else "_sin comparaciones disponibles_",
        "",
        "## DSM-5 contribution snapshot",
        md_table(
            dsm_df[
                [
                    "candidate_id",
                    "variant",
                    "status",
                    "n_features",
                    "precision",
                    "recall",
                    "balanced_accuracy",
                    "pr_auc",
                    "brier",
                ]
            ].sort_values(["candidate_id", "variant"])
        ),
        "",
        f"- overfitting_evidence: {'yes' if overfit_yes else 'no'}",
        f"- good_generalization_evidence: {'yes' if generalization_yes else 'no'}",
        f"- fits_total: {FIT_COUNTER['fits']}",
        f"- trees_total: {FIT_COUNTER['trees']}",
    ]
    write_md(REPORTS / "hybrid_rf_targeted_executive_summary.md", "\n".join(exec_report))
    analysis_report = [
        "# Hybrid RF Targeted v4 - Consolidated Analysis",
        "",
        "## Ranked candidates",
        md_table(
            ranked[
                [
                    "candidate_id",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "ranking_score",
                ]
            ]
        ),
        "",
        "## Final champions by domain",
        md_table(champions_df),
    ]
    write_md(REPORTS / "hybrid_rf_targeted_consolidated_analysis.md", "\n".join(analysis_report))

    # Required file names in this campaign.
    write_md(REPORTS / "hybrid_rf_targeted_overfitting_audit.md", (REPORTS / "hybrid_rf_targeted_overfitting_audit.md").read_text(encoding="utf-8"))
    write_md(REPORTS / "hybrid_rf_targeted_generalization_audit.md", (REPORTS / "hybrid_rf_targeted_generalization_audit.md").read_text(encoding="utf-8"))
    write_md(REPORTS / "hybrid_rf_targeted_feature_strategy.md", (REPORTS / "hybrid_rf_targeted_feature_strategy.md").read_text(encoding="utf-8"))
    write_md(REPORTS / "hybrid_rf_targeted_ceiling_decision.md", (REPORTS / "hybrid_rf_targeted_ceiling_decision.md").read_text(encoding="utf-8"))
    write_md(REPORTS / "hybrid_rf_targeted_executive_summary.md", (REPORTS / "hybrid_rf_targeted_executive_summary.md").read_text(encoding="utf-8"))

    # Manifest.
    generated_files: list[dict[str, Any]] = []
    for p in sorted(BASE.rglob("*")):
        if p.is_file():
            generated_files.append(
                {
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": file_sha256(p),
                    "bytes": p.stat().st_size,
                }
            )
    manifest = {
        "campaign_line": LINE,
        "generated_at_utc": now_iso(),
        "dataset_path": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "targeted_candidates": [f"{d}/{m}" for d, m in TARGETED_CANDIDATES],
        "candidates_audited_count": len(candidates),
        "fits_total": FIT_COUNTER["fits"],
        "trees_total": FIT_COUNTER["trees"],
        "generated_files": generated_files,
    }
    (ART / "hybrid_rf_targeted_fix_v4_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print_progress("v4 targeted campaign completed")


def main() -> None:
    run_campaign()


if __name__ == "__main__":
    main()
