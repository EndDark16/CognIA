#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import math
import re
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
LINE = "hybrid_no_external_scores_rebuild_v2"
BASE = ROOT / "data" / LINE
INV = BASE / "inventory"
MODES_DIR = BASE / "modes"
TABLES = BASE / "tables"
TRIALS = BASE / "trials"
FE = BASE / "feature_engineering"
CAL = BASE / "calibration"
THR = BASE / "thresholds"
BOOT = BASE / "bootstrap"
STAB = BASE / "stability"
ABL = BASE / "ablation"
STRESS = BASE / "stress"
REPORTS = BASE / "reports"
ART = ROOT / "artifacts" / LINE

HBASE = ROOT / "data" / "hybrid_dsm5_rebuild_v1"
DATASET_PATH = HBASE / "hybrid_dataset_synthetic_complete_final.csv"
RESP_PATH = HBASE / "hybrid_model_input_respondability_final.csv"
MODE_MATRIX_PATH = HBASE / "questionnaire_modes_priority_matrix_final.csv"
DSM_PATH = HBASE / "dsm5_quant_feature_template_final.csv"

FROZEN_BASE = ROOT / "data" / "hybrid_final_freeze_v1"
FROZEN_CHAMPIONS = FROZEN_BASE / "tables" / "frozen_hybrid_champions_master.csv"
FROZEN_INPUTS = FROZEN_BASE / "tables" / "frozen_hybrid_champions_inputs_master.csv"

PREV_LINES = [
    "hybrid_rf_ceiling_push_v1",
    "hybrid_rf_consolidation_v2",
    "hybrid_rf_final_ceiling_push_v3",
    "hybrid_rf_targeted_fix_v4",
    "hybrid_final_freeze_v1",
]

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
MODES = [
    "caregiver_1_3",
    "caregiver_2_3",
    "caregiver_full",
    "psychologist_1_3",
    "psychologist_2_3",
    "psychologist_full",
]

EXTERNAL_SCORE_COLUMNS = [
    "swan_hyperactive_impulsive_total", "swan_inattention_total", "swan_total",
    "sdq_conduct_problems", "sdq_emotional_symptoms", "sdq_hyperactivity_inattention", "sdq_impact", "sdq_peer_problems", "sdq_prosocial_behavior", "sdq_total_difficulties",
    "icut_total",
    "ari_p_symptom_total", "ari_sr_symptom_total",
    "scared_p_generalized_anxiety", "scared_p_panic_somatic", "scared_p_possible_anxiety_disorder_cut25", "scared_p_school_avoidance", "scared_p_separation_anxiety", "scared_p_social_anxiety", "scared_p_total",
    "scared_sr_generalized_anxiety", "scared_sr_panic_somatic", "scared_sr_possible_anxiety_disorder_cut25", "scared_sr_school_avoidance", "scared_sr_separation_anxiety", "scared_sr_social_anxiety", "scared_sr_total",
    "mfq_p_total",
]

LEAK_PATTERNS = (
    "_threshold_met",
    "final_dsm5_threshold_met",
    "any_module_threshold_met",
    "target_domain_",
)
LEAK_EXACT = {
    "elimination_type_code",
    "adhd_presentation_code",
    "anxiety_module_count_positive",
    "dmdd_age_6_to_18",
}

BASE_SEED = 20261101
STAGE2_SEEDS = [20261101, 20261119]
STAB_SEEDS = [20261101, 20261119, 20261137]

FIT_COUNTER = {"fits": 0, "trees": 0}

RF_CONFIGS = [
    {"config_id": "rf_baseline", "n_estimators": 220, "max_depth": None, "min_samples_split": 4, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": None, "bootstrap": True, "max_samples": None},
    {"config_id": "rf_balanced_subsample", "n_estimators": 260, "max_depth": 22, "min_samples_split": 4, "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.9},
    {"config_id": "rf_precision_push", "n_estimators": 240, "max_depth": 18, "min_samples_split": 8, "min_samples_leaf": 3, "max_features": 0.55, "class_weight": {0: 1.0, 1: 1.4}, "bootstrap": True, "max_samples": None},
    {"config_id": "rf_recall_guard", "n_estimators": 260, "max_depth": None, "min_samples_split": 4, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": {0: 1.0, 1: 1.9}, "bootstrap": True, "max_samples": 0.95},
    {"config_id": "rf_regularized", "n_estimators": 240, "max_depth": 14, "min_samples_split": 10, "min_samples_leaf": 4, "max_features": 0.45, "class_weight": "balanced", "bootstrap": True, "max_samples": 0.85},
    {"config_id": "rf_pos_weight_mid", "n_estimators": 280, "max_depth": 20, "min_samples_split": 6, "min_samples_leaf": 2, "max_features": 0.60, "class_weight": {0: 1.0, 1: 2.1}, "bootstrap": True, "max_samples": 0.9},
]
RF_CFG = {c["config_id"]: c for c in RF_CONFIGS}

CAL_METHODS = ["none", "sigmoid", "isotonic"]
THRESH_POLICIES = ["default_0_5", "balanced", "precision_oriented", "recall_guard", "precision_min_recall", "recall_constrained"]


@dataclass
class Winner:
    mode: str
    role: str
    domain: str
    feature_set_id: str
    config_id: str
    calibration: str
    threshold_policy: str
    threshold: float
    seed: int
    n_features: int
    precision: float
    recall: float
    specificity: float
    ba: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier: float
    overfit_gap_train_val_ba: float
    generalization_gap_val_holdout_ba: float
    quality_label: str
    ceiling_status: str
    should_keep_improving: str
    final_status: str
    notes: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    for p in [BASE, INV, MODES_DIR, TABLES, TRIALS, FE, CAL, THR, BOOT, STAB, ABL, STRESS, REPORTS, ART]:
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


def print_progress(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def yesno(x: Any) -> str:
    if pd.isna(x):
        return "no"
    s = str(x).strip().lower()
    return "si" if s in {"si", "sí", "yes", "true", "1", "y"} else "no"

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
    return 0.40 * metrics["precision"] + 0.24 * metrics["balanced_accuracy"] + 0.18 * metrics["pr_auc"] + 0.10 * metrics["recall"] - 0.08 * metrics["brier"]


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
            if m["recall"] < max(0.5, recall_floor):
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


def calibrate_probabilities(y_val: np.ndarray, train_raw: np.ndarray, val_raw: np.ndarray, hold_raw: np.ndarray) -> tuple[dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], dict[str, dict[str, float]], dict[str, Callable[[np.ndarray], np.ndarray]]]:
    out_probs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    out_diag: dict[str, dict[str, float]] = {}
    transforms: dict[str, Callable[[np.ndarray], np.ndarray]] = {}

    def ident(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 1e-6, 1 - 1e-6)

    out_probs["none"] = (ident(train_raw), ident(val_raw), ident(hold_raw))
    out_diag["none"] = {"val_brier": float(brier_score_loss(y_val, ident(val_raw))), "val_ece": float(expected_calibration_error(y_val, ident(val_raw)))}
    transforms["none"] = ident

    if len(np.unique(y_val)) >= 2:
        lr = LogisticRegression(max_iter=1200)
        lr.fit(val_raw.reshape(-1, 1), y_val.astype(int))

        def tf_sigmoid(x: np.ndarray) -> np.ndarray:
            return np.clip(lr.predict_proba(x.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)

        out_probs["sigmoid"] = (tf_sigmoid(train_raw), tf_sigmoid(val_raw), tf_sigmoid(hold_raw))
        out_diag["sigmoid"] = {"val_brier": float(brier_score_loss(y_val, out_probs["sigmoid"][1])), "val_ece": float(expected_calibration_error(y_val, out_probs["sigmoid"][1]))}
        transforms["sigmoid"] = tf_sigmoid

        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(val_raw, y_val.astype(int))

        def tf_iso(x: np.ndarray) -> np.ndarray:
            return np.clip(iso.predict(x), 1e-6, 1 - 1e-6)

        out_probs["isotonic"] = (tf_iso(train_raw), tf_iso(val_raw), tf_iso(hold_raw))
        out_diag["isotonic"] = {"val_brier": float(brier_score_loss(y_val, out_probs["isotonic"][1])), "val_ece": float(expected_calibration_error(y_val, out_probs["isotonic"][1]))}
        transforms["isotonic"] = tf_iso

    return out_probs, out_diag, transforms


def choose_targets(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    w = df.copy()
    if all(c in w.columns for c in ["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]):
        w["target_domain_depression_final"] = (
            w[["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]].apply(pd.to_numeric, errors="coerce").fillna(0).max(axis=1).astype(int)
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

def leakage_like_feature(feature: str) -> bool:
    low = feature.lower()
    if feature in LEAK_EXACT:
        return True
    return any(tok in low for tok in LEAK_PATTERNS)


def parse_role(mode: str) -> str:
    return "caregiver" if mode.startswith("caregiver") else "psychologist"


def prepare_X(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for c in X.columns:
        if c == "sex_assigned_at_birth":
            X[c] = X[c].fillna("Unknown").astype(str)
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    return X


def make_pipeline(features: list[str], cfg: dict[str, Any], seed: int) -> Pipeline:
    cat_cols = [c for c in features if c == "sex_assigned_at_birth"]
    num_cols = [c for c in features if c not in cat_cols]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat_cols),
        ],
        remainder="drop",
    )
    model = RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cfg["class_weight"],
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        random_state=seed,
        n_jobs=1,
    )
    return Pipeline([("pre", pre), ("rf", model)])


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
    agg: dict[str, float] = {f: 0.0 for f in feature_names}
    for t_name, val in zip(transformed, imp):
        clean = str(t_name)
        orig = clean
        if clean.startswith("num__"):
            orig = clean.split("num__", 1)[1]
        elif clean.startswith("cat__"):
            tail = clean.split("cat__", 1)[1]
            if tail.startswith("sex_assigned_at_birth"):
                orig = "sex_assigned_at_birth"
            else:
                orig = tail.split("_", 1)[0]
        if orig in agg:
            agg[orig] += float(val)
    return pd.Series(agg).sort_values(ascending=False)


def effect_size_rank(train_df: pd.DataFrame, features: list[str], target_col: str) -> pd.Series:
    y = train_df[target_col].astype(int)
    out: dict[str, float] = {}
    for f in features:
        s = train_df[f]
        if not pd.api.types.is_numeric_dtype(s):
            s = s.astype(str).fillna("Unknown").astype("category").cat.codes.astype(float)
        else:
            s = pd.to_numeric(s, errors="coerce")
        pos = s[y == 1]
        neg = s[y == 0]
        denom = float(np.nanstd(s.values)) + 1e-9
        out[f] = float(abs(np.nanmean(pos.values) - np.nanmean(neg.values)) / denom)
    return pd.Series(out).sort_values(ascending=False)


def bootstrap_metric_ci(y_true: np.ndarray, probs: np.ndarray, threshold: float, n_boot: int = 220, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx_all = np.arange(len(y_true))
    metrics_names = ["precision", "recall", "balanced_accuracy", "pr_auc", "brier"]
    history: dict[str, list[float]] = {m: [] for m in metrics_names}
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        m = compute_metrics(y_true[idx], probs[idx], threshold)
        for name in metrics_names:
            history[name].append(float(m[name]))
    out: dict[str, float] = {}
    for name in metrics_names:
        arr = np.array(history[name], dtype=float)
        out[f"{name}_boot_mean"] = float(np.mean(arr))
        out[f"{name}_boot_ci_low"] = float(np.quantile(arr, 0.025))
        out[f"{name}_boot_ci_high"] = float(np.quantile(arr, 0.975))
    return out


def inject_missing(X: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = X.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f not in out.columns:
            continue
        if f != "sex_assigned_at_birth":
            out[f] = pd.to_numeric(out[f], errors="coerce").astype(float)
        mask = rng.random(len(out)) < ratio
        out.loc[mask, f] = np.nan
    return out

def build_engineered_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    rows: list[dict[str, Any]] = []

    def add_feature(name: str, cols: list[str], kind: str, formula: str) -> None:
        use = [c for c in cols if c in out.columns]
        if not use:
            return
        x = out[use].apply(pd.to_numeric, errors="coerce")
        if kind == "mean":
            out[name] = x.mean(axis=1)
        elif kind == "sum":
            out[name] = x.sum(axis=1)
        elif kind == "nonzero_ratio":
            out[name] = (x > 0).sum(axis=1) / max(1, len(use))
        elif kind == "max":
            out[name] = x.max(axis=1)
        elif kind == "std":
            out[name] = x.std(axis=1)
        rows.append({"engineered_feature": name, "source_features_pipe": "|".join(use), "formula_kind": kind, "formula_description": formula, "n_sources": len(use)})

    add_feature("eng_adhd_core_mean", [f"adhd_inatt_{i:02d}_{s}" for i, s in [
        (1,"attention_to_detail_errors"),(2,"sustained_attention_difficulty"),(3,"seems_not_listening"),(4,"fails_to_finish_tasks"),(5,"organization_difficulty"),(6,"avoids_sustained_effort"),(7,"loses_things"),(8,"easily_distracted"),(9,"forgetful_daily_activities")
    ]] + [f"adhd_hypimp_{i:02d}_{s}" for i, s in [
        (1,"fidgets"),(2,"leaves_seat"),(3,"runs_or_climbs_inappropriately"),(4,"cannot_play_quietly"),(5,"driven_by_motor"),(6,"talks_excessively"),(7,"blurts_out"),(8,"difficulty_waiting_turn"),(9,"interrupts_intrudes")
    ]], "mean", "mean of explicit DSM5 ADHD symptom items")

    add_feature("eng_conduct_core_mean", [f"conduct_{i:02d}_{s}" for i, s in [
        (1,"bullies_threatens_intimidates"),(2,"initiates_fights"),(3,"weapon_use"),(4,"physical_cruelty_people"),(5,"physical_cruelty_animals"),(6,"steals_confronting_victim"),(7,"forced_sex"),(8,"fire_setting"),(9,"property_destruction"),(10,"breaks_into_house_building_car"),(11,"lies_to_obtain_or_avoid"),(12,"steals_without_confrontation"),(13,"stays_out_at_night_before_13"),(14,"runs_away_overnight"),(15,"truancy_before_13")
    ]], "mean", "mean of explicit DSM5 Conduct symptom items")

    add_feature("eng_anxiety_core_mean", [
        "sep_anx_01_distress_on_separation","sep_anx_02_worry_losing_attachment_figures","sep_anx_03_worry_event_causing_separation","sep_anx_04_refuses_leaving_home_school","sep_anx_05_fear_being_alone_without_attachment","sep_anx_06_refuses_sleep_away_or_alone","sep_anx_07_separation_nightmares","sep_anx_08_physical_complaints_on_separation",
        "social_anxiety_fear_interactions","social_anxiety_fear_being_observed","social_anxiety_fear_performance","social_anxiety_fear_negative_evaluation","social_anxiety_almost_always_triggered","social_anxiety_avoid_or_endure_intense",
        "gad_excessive_worry_multiple_areas","gad_difficulty_controlling_worry","gad_assoc_01_restlessness","gad_assoc_02_fatigue","gad_assoc_03_concentration_difficulty","gad_assoc_04_irritability","gad_assoc_05_muscle_tension","gad_assoc_06_sleep_problems",
        "agor_fear_01_public_transport","agor_fear_02_open_spaces","agor_fear_03_enclosed_spaces","agor_fear_04_crowds_queues","agor_fear_05_outside_home_alone",
    ], "mean", "mean of explicit DSM5 anxiety module items")

    add_feature("eng_depression_core_mean", [
        "mdd_01_depressed_or_irritable_mood","mdd_02_loss_of_interest_or_pleasure","mdd_03_weight_or_appetite_change","mdd_04_sleep_change","mdd_05_psychomotor_change","mdd_06_fatigue_or_low_energy","mdd_07_worthlessness_or_excessive_guilt","mdd_08_concentration_or_decision_difficulty","mdd_09_death_or_suicidal_thoughts",
        "dmdd_outbursts_severity","dmdd_outbursts_frequency_per_week","dmdd_developmentally_inappropriate","dmdd_irritable_between_outbursts",
        "pdd_depressed_or_irritable_mood","pdd_01_appetite_change","pdd_02_sleep_change","pdd_03_low_energy","pdd_04_low_self_esteem","pdd_05_concentration_difficulty","pdd_06_hopelessness",
    ], "mean", "mean of explicit DSM5 depression module items")

    add_feature("eng_elimination_intensity", [
        "enuresis_event_frequency_per_week","enuresis_duration_months_consecutive","enuresis_distress_impairment",
        "encopresis_event_frequency_per_month","encopresis_duration_months_consecutive",
    ], "mean", "mean of elimination frequency/duration/distress quantities")

    add_feature("eng_internalizing_index", ["eng_anxiety_core_mean", "eng_depression_core_mean"], "mean", "mean of engineered anxiety and depression indices")
    add_feature("eng_externalizing_index", ["eng_adhd_core_mean", "eng_conduct_core_mean"], "mean", "mean of engineered adhd and conduct indices")
    add_feature("eng_adhd_context_spread", ["adhd_context_home", "adhd_context_school", "adhd_context_other"], "mean", "mean ADHD context spread")
    add_feature("eng_mood_discrepancy", ["mdd_symptom_count", "pdd_symptom_count"], "std", "std between MDD and PDD symptom counts")

    reg = pd.DataFrame(rows).drop_duplicates(subset=["engineered_feature"]).reset_index(drop=True)
    return out, reg


def build_split_registry(df: pd.DataFrame, target_map: dict[str, str]) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    split_ids: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []
    ids = df["participant_id"].astype(str).tolist()
    for i, d in enumerate(DOMAINS):
        y = df[target_map[d]].astype(int)
        seed = BASE_SEED + i * 23
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(np.array(ids, dtype=object), y, test_size=0.40, random_state=seed, stratify=strat)
        strat_tmp = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids, va_y, ho_y = train_test_split(tmp_ids, tmp_y, test_size=0.50, random_state=seed + 1, stratify=strat_tmp)
        split_ids[d] = {"train": [str(x) for x in tr_ids], "val": [str(x) for x in va_ids], "holdout": [str(x) for x in ho_ids]}
        rows.append({"domain": d, "target": target_map[d], "seed": seed, "train_n": len(tr_ids), "val_n": len(va_ids), "holdout_n": len(ho_ids), "train_pos_rate": float(np.mean(tr_y)), "val_pos_rate": float(np.mean(va_y)), "holdout_pos_rate": float(np.mean(ho_y))})
    return split_ids, pd.DataFrame(rows)


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()

def build_mode_feature_maps(df: pd.DataFrame, respond: pd.DataFrame, mode_matrix: pd.DataFrame, engineered_features: list[str]) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    direct_keep = set(respond[(respond["is_direct_input"].astype(str).str.lower().eq("yes")) & (respond["keep_for_model_v1"].astype(str).str.lower().eq("yes"))]["feature"].astype(str))
    derived_keep = set(respond[(respond["is_transparent_derived"].astype(str).str.lower().eq("yes")) & (respond["keep_for_model_v1"].astype(str).str.lower().eq("yes"))]["feature"].astype(str))

    mode_map: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []
    frozen_inputs = pd.read_csv(FROZEN_INPUTS) if FROZEN_INPUTS.exists() else pd.DataFrame()

    for mode in MODES:
        include_col = f"include_{mode}"
        role = parse_role(mode)
        direct_from_matrix = set(mode_matrix[mode_matrix[include_col].map(yesno).eq("si")]["feature"].astype(str).tolist()) if include_col in mode_matrix.columns else set()
        direct_usable = sorted([f for f in direct_from_matrix if f in direct_keep and f in df.columns and f not in EXTERNAL_SCORE_COLUMNS])
        derived_usable = sorted([f for f in direct_from_matrix if f in derived_keep and f in df.columns and f not in EXTERNAL_SCORE_COLUMNS])

        eng_for_mode = []
        for ef in engineered_features:
            if ef.startswith("eng_internalizing") and role in {"caregiver", "psychologist"}:
                eng_for_mode.append(ef)
            elif ef.startswith("eng_externalizing") and role in {"caregiver", "psychologist"}:
                eng_for_mode.append(ef)
            elif ef.startswith("eng_"):
                eng_for_mode.append(ef)
        eng_for_mode = sorted(set([e for e in eng_for_mode if e in df.columns]))

        eligible = sorted(set(direct_usable) | set(derived_usable))
        mode_map[mode] = {
            "role": [role],
            "direct": direct_usable,
            "derived": derived_usable,
            "engineered": eng_for_mode,
            "eligible": eligible,
        }

        prev_count = None
        if not frozen_inputs.empty and include_col in frozen_inputs.columns:
            prev_count = int((frozen_inputs[include_col].astype(str).str.lower() == "si").sum())
        rows.append({
            "mode": mode,
            "role": role,
            "direct_features": len(direct_usable),
            "derived_features": len(derived_usable),
            "engineered_features": len(eng_for_mode),
            "eligible_base_features": len(eligible),
            "previous_freeze_mode_count": prev_count if prev_count is not None else np.nan,
            "features_lost_vs_freeze": (prev_count - len(eligible)) if prev_count is not None else np.nan,
            "severely_impoverished_mode": "yes" if len(eligible) < 35 else "no",
        })
    return mode_map, pd.DataFrame(rows)


def select_stage1_combos(stage1_df: pd.DataFrame) -> list[tuple[str, str]]:
    grouped = stage1_df.groupby(["feature_set_id", "config_id"], as_index=False).agg(
        val_precision=("val_precision", "mean"),
        val_recall=("val_recall", "mean"),
        val_ba=("val_balanced_accuracy", "mean"),
        val_pr_auc=("val_pr_auc", "mean"),
        val_brier=("val_brier", "mean"),
        stage_score=("stage_score", "mean"),
    )
    grouped["guard_ok"] = (grouped["val_recall"] >= 0.40) & (grouped["val_ba"] >= 0.65)
    grouped["rank_score"] = 0.42 * grouped["val_precision"] + 0.24 * grouped["val_ba"] + 0.18 * grouped["val_pr_auc"] + 0.10 * grouped["val_recall"] - 0.06 * grouped["val_brier"]
    valid = grouped[grouped["guard_ok"]].sort_values("rank_score", ascending=False)
    if valid.empty:
        valid = grouped.sort_values("rank_score", ascending=False)
    combos = [(str(r["feature_set_id"]), str(r["config_id"])) for _, r in valid.head(2).iterrows()]
    if ("full_eligible", "rf_baseline") not in combos and ((grouped["feature_set_id"] == "full_eligible") & (grouped["config_id"] == "rf_baseline")).any():
        combos.append(("full_eligible", "rf_baseline"))
    return list(dict.fromkeys(combos))[:2]


def build_feature_sets(train_df: pd.DataFrame, base_features: list[str], engineered_features: list[str], target_col: str, mode: str, domain: str) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    if len(base_features) < 8:
        raise RuntimeError(f"Not enough features for {mode}/{domain}: {len(base_features)}")

    proxy = make_pipeline(base_features, RF_CFG["rf_baseline"], BASE_SEED)
    Xtr = prepare_X(train_df, base_features)
    ytr = train_df[target_col].astype(int).to_numpy()
    fit_with_count(proxy, Xtr, ytr, int(RF_CFG["rf_baseline"]["n_estimators"]))
    imp = aggregate_importance(proxy, base_features)
    eff = effect_size_rank(train_df, base_features, target_col)

    n = len(base_features)
    compact_n = min(n, max(10, int(round(n * 0.45))))
    precision_n = min(n, max(10, int(round(n * 0.40))))
    balanced_n = min(n, max(12, int(round(n * 0.55))))
    stable_n = min(n, max(12, int(round(n * 0.50))))

    corr_df = train_df[base_features].copy()
    for c in corr_df.columns:
        if not pd.api.types.is_numeric_dtype(corr_df[c]):
            corr_df[c] = corr_df[c].astype(str).fillna("Unknown").astype("category").cat.codes.astype(float)
    corr_df = corr_df.apply(pd.to_numeric, errors="coerce").fillna(corr_df.median(numeric_only=True))
    corr = corr_df.corr().abs()
    balanced = []
    for f in imp.index.tolist():
        if len(balanced) >= balanced_n:
            break
        keep = True
        for prev in balanced:
            if f in corr.index and prev in corr.columns and float(corr.loc[f, prev]) >= 0.92:
                keep = False
                break
        if keep:
            balanced.append(f)
    if len(balanced) < 8:
        balanced = imp.head(balanced_n).index.tolist()

    stability_scores: dict[str, float] = {f: 0.0 for f in base_features}
    for s in [BASE_SEED, BASE_SEED + 17, BASE_SEED + 33]:
        p = make_pipeline(base_features, RF_CFG["rf_baseline"], s)
        fit_with_count(p, Xtr, ytr, int(RF_CFG["rf_baseline"]["n_estimators"]))
        rk = aggregate_importance(p, base_features)
        for pos, feat in enumerate(rk.index.tolist(), start=1):
            stability_scores[feat] += 1.0 / float(pos)
    stable_rank = pd.Series(stability_scores).sort_values(ascending=False)

    eng = [f for f in engineered_features if f in train_df.columns]
    feature_sets = {
        "full_eligible": sorted(set(base_features)),
        "compact_subset": sorted(set(imp.head(compact_n).index.tolist())),
        "balanced_subset": sorted(set(balanced)),
        "precision_oriented_subset": sorted(set(eff.head(precision_n).index.tolist())),
        "stability_pruned_subset": sorted(set(stable_rank.head(stable_n).index.tolist())),
        "engineered_full": sorted(set(base_features + eng)),
        "engineered_pruned": sorted(set(imp.head(max(12, int(round(n * 0.60)))).index.tolist() + eng)),
        "engineered_compact": sorted(set(imp.head(max(10, int(round(n * 0.35)))).index.tolist() + eng)),
    }

    rows = []
    for fsid, feats in feature_sets.items():
        rows.append({"mode": mode, "domain": domain, "feature_set_id": fsid, "n_features": len(feats), "feature_list_pipe": "|".join(feats), "construction_rule": fsid})
    return feature_sets, rows

def run_campaign() -> None:
    ensure_dirs()
    print_progress("Loading base tables and building strict clean universe")
    raw = pd.read_csv(DATASET_PATH)
    respond = pd.read_csv(RESP_PATH)
    mode_matrix = pd.read_csv(MODE_MATRIX_PATH)
    dsm = pd.read_csv(DSM_PATH)
    frozen = pd.read_csv(FROZEN_CHAMPIONS)

    raw, target_map = choose_targets(raw)
    target_cols = list(target_map.values())

    allowed_by_resp = set(
        respond[
            (respond["keep_for_model_v1"].astype(str).str.lower() == "yes")
            & (
                (respond["is_direct_input"].astype(str).str.lower() == "yes")
                | (respond["is_transparent_derived"].astype(str).str.lower() == "yes")
            )
        ]["feature"].astype(str)
    )

    gov_rows = []
    for c in raw.columns:
        if c == "participant_id":
            continue
        layer = "dsm5" if (c in set(dsm["feature_name"].astype(str))) or c.startswith(("adhd_", "conduct_", "enuresis_", "encopresis_", "sep_anx_", "social_anxiety_", "gad_", "agor_", "mdd_", "dmdd_", "pdd_")) else "clean_base"
        is_direct = "yes" if c in set(respond[respond["is_direct_input"].astype(str).str.lower().eq("yes")]["feature"].astype(str)) else "no"
        is_derived = "yes" if c in set(respond[respond["is_transparent_derived"].astype(str).str.lower().eq("yes")]["feature"].astype(str)) else "no"
        in_mode = "yes" if c in set(mode_matrix["feature"].astype(str)) else "no"
        reason = ""
        keep = "yes"
        depends_external = "yes" if c in EXTERNAL_SCORE_COLUMNS else "no"
        if c in EXTERNAL_SCORE_COLUMNS:
            keep = "no"
            reason = "explicit_external_score_or_subscale_excluded"
        elif c in target_cols:
            keep = "no"
            reason = "target_column"
        elif leakage_like_feature(c):
            keep = "no"
            reason = "potential_leakage_or_target_proxy"
        elif c not in allowed_by_resp:
            keep = "no"
            reason = "not_in_allowed_respondability_universe"

        gov_rows.append({
            "feature": c,
            "keep_for_new_primary_line": keep,
            "removal_reason": reason if reason else "retained",
            "layer": layer,
            "is_direct_input": is_direct,
            "is_transparent_derived": is_derived,
            "visible_in_modes_matrix": in_mode,
            "depends_on_external_instrument_or_score": depends_external,
        })

    gov = pd.DataFrame(gov_rows)
    removed = gov[gov["keep_for_new_primary_line"] == "no"].copy()
    retained = gov[gov["keep_for_new_primary_line"] == "yes"].copy()

    save_csv(removed.sort_values("feature"), INV / "no_external_scores_removed_features.csv")
    save_csv(retained.sort_values("feature"), INV / "no_external_scores_retained_features.csv")
    save_csv(gov.sort_values("feature"), INV / "no_external_scores_feature_governance.csv")

    demoted_rows = []
    for line in PREV_LINES:
        demoted_rows.append({
            "line": line,
            "status_1": "historical_trace_only",
            "status_2": "not_functional_for_new_primary_line",
            "updated_at_utc": now_iso(),
        })
    save_csv(pd.DataFrame(demoted_rows), INV / "previous_models_status_demoted.csv")

    base_features_clean = sorted(retained["feature"].tolist())
    df_clean = raw[["participant_id"] + base_features_clean + target_cols].copy()

    df_eng, eng_registry = build_engineered_features(df_clean)
    engineered_features = [f for f in eng_registry.get("engineered_feature", pd.Series([], dtype=str)).tolist() if f in df_eng.columns]

    dataset_ready_cols = ["participant_id"] + base_features_clean + engineered_features + target_cols
    dataset_ready = df_eng[dataset_ready_cols].copy()
    save_csv(dataset_ready, TABLES / "hybrid_no_external_scores_dataset_ready.csv")

    ds_audit = pd.DataFrame(
        [
            {"item": "rows", "value": int(len(dataset_ready))},
            {"item": "columns_total_dataset_ready", "value": int(len(dataset_ready.columns))},
            {"item": "base_features_clean", "value": int(len(base_features_clean))},
            {"item": "engineered_features", "value": int(len(engineered_features))},
            {"item": "removed_features", "value": int(len(removed))},
            {"item": "retained_features", "value": int(len(retained))},
            {"item": "explicit_external_score_columns_found_and_removed", "value": int(sum([1 for c in EXTERNAL_SCORE_COLUMNS if c in raw.columns]))},
        ]
    )
    save_csv(ds_audit, TABLES / "hybrid_no_external_scores_dataset_audit.csv")

    mode_map, mode_cov = build_mode_feature_maps(df_eng, respond, mode_matrix, engineered_features)
    save_csv(mode_cov.sort_values("mode"), MODES_DIR / "no_external_scores_mode_coverage.csv")

    split_ids, split_registry = build_split_registry(df_eng, target_map)

    mode_count_rows = []
    for mode in MODES:
        for d in DOMAINS:
            mode_count_rows.append({
                "mode": mode,
                "domain": d,
                "role": parse_role(mode),
                "direct_features": len(mode_map[mode]["direct"]),
                "derived_features": len(mode_map[mode]["derived"]),
                "engineered_features": len(mode_map[mode]["engineered"]),
                "eligible_base_features": len(mode_map[mode]["eligible"]),
                "severely_impoverished_mode": "yes" if len(mode_map[mode]["eligible"]) < 35 else "no",
            })
    save_csv(pd.DataFrame(mode_count_rows), MODES_DIR / "no_external_scores_mode_feature_counts.csv")

    print_progress("Training 30 domain-mode pairs on clean universe")
    trial_rows: list[dict[str, Any]] = []
    trial_metric_rows: list[dict[str, Any]] = []
    feature_set_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    stab_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    fe_result_rows: list[dict[str, Any]] = []

    trial_id = 0
    for mode in MODES:
        role = parse_role(mode)
        for domain in DOMAINS:
            target_col = target_map[domain]
            split = split_ids[domain]
            tr_df = subset_by_ids(df_eng, split["train"])
            va_df = subset_by_ids(df_eng, split["val"])
            ho_df = subset_by_ids(df_eng, split["holdout"])
            y_tr = tr_df[target_col].astype(int).to_numpy()
            y_va = va_df[target_col].astype(int).to_numpy()
            y_ho = ho_df[target_col].astype(int).to_numpy()

            forbidden = set(target_cols + ["participant_id"]) | set(EXTERNAL_SCORE_COLUMNS)
            base_pool = [f for f in mode_map[mode]["eligible"] if f in df_eng.columns and f not in forbidden and not leakage_like_feature(f)]
            base_pool = sorted(set(base_pool))
            if len(base_pool) < 8:
                raise RuntimeError(f"Insufficient clean features for {mode}/{domain}: {len(base_pool)}")

            eng_pool = [f for f in mode_map[mode]["engineered"] if f in df_eng.columns]
            feat_sets, fs_rows = build_feature_sets(tr_df, base_pool, eng_pool, target_col, mode, domain)
            feature_set_rows.extend(fs_rows)

            stage1_local = []
            for fs_id, feats in feat_sets.items():
                Xtr = prepare_X(tr_df, feats)
                Xva = prepare_X(va_df, feats)
                for cfg in RF_CONFIGS:
                    pipe = make_pipeline(feats, cfg, BASE_SEED)
                    fit_with_count(pipe, Xtr, y_tr, int(cfg["n_estimators"]))
                    tr_raw = np.clip(pipe.predict_proba(Xtr)[:, 1], 1e-6, 1 - 1e-6)
                    va_raw = np.clip(pipe.predict_proba(Xva)[:, 1], 1e-6, 1 - 1e-6)
                    m_tr = compute_metrics(y_tr, tr_raw, 0.5)
                    m_va = compute_metrics(y_va, va_raw, 0.5)
                    score = objective(m_va) - 0.10 * max(0.0, m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                    trial_id += 1
                    rec = {
                        "trial_id": trial_id, "stage": "stage1", "mode": mode, "role": role, "domain": domain,
                        "feature_set_id": fs_id, "config_id": cfg["config_id"], "seed": BASE_SEED,
                        "calibration": "none", "threshold_policy": "default_0_5", "threshold": 0.5, "n_features": len(feats),
                        "stage_score": score, "selected_for_stage2": "no",
                    }
                    for k, v in m_tr.items():
                        rec[f"train_{k}"] = v
                    for k, v in m_va.items():
                        rec[f"val_{k}"] = v
                    rec["val_objective"] = score
                    rec["overfit_gap_ba"] = m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]
                    trial_rows.append({k: rec.get(k) for k in ["trial_id", "stage", "mode", "role", "domain", "feature_set_id", "config_id", "seed", "calibration", "threshold_policy", "threshold", "n_features", "selected_for_stage2", "val_objective", "overfit_gap_ba"]})
                    trial_metric_rows.append(rec)
                    stage1_local.append(rec)

            stage1_df = pd.DataFrame(stage1_local)
            combos = select_stage1_combos(stage1_df)
            combo_set = set(combos)
            for tr in trial_rows:
                if tr["stage"] == "stage1" and tr["mode"] == mode and tr["domain"] == domain and (tr["feature_set_id"], tr["config_id"]) in combo_set:
                    tr["selected_for_stage2"] = "yes"

            stage2_local = []
            for fs_id, cfg_id in combos:
                feats = feat_sets[fs_id]
                cfg = RF_CFG[cfg_id]
                Xtr = prepare_X(tr_df, feats)
                Xva = prepare_X(va_df, feats)
                Xho = prepare_X(ho_df, feats)

                for seed in STAGE2_SEEDS:
                    pipe = make_pipeline(feats, cfg, seed)
                    fit_with_count(pipe, Xtr, y_tr, int(cfg["n_estimators"]))
                    tr_raw = np.clip(pipe.predict_proba(Xtr)[:, 1], 1e-6, 1 - 1e-6)
                    va_raw = np.clip(pipe.predict_proba(Xva)[:, 1], 1e-6, 1 - 1e-6)
                    ho_raw = np.clip(pipe.predict_proba(Xho)[:, 1], 1e-6, 1 - 1e-6)
                    calibrated, cal_diag, _ = calibrate_probabilities(y_va, tr_raw, va_raw, ho_raw)

                    for cal in CAL_METHODS:
                        if cal not in calibrated:
                            continue
                        tr_p, va_p, ho_p = calibrated[cal]
                        calibration_rows.append({"mode": mode, "domain": domain, "feature_set_id": fs_id, "config_id": cfg_id, "seed": seed, "calibration_method": cal, "val_brier": cal_diag[cal]["val_brier"], "val_ece": cal_diag[cal]["val_ece"]})
                        for pol in THRESH_POLICIES:
                            thr, pol_score = choose_threshold(pol, y_va, va_p, recall_floor=0.50)
                            m_tr = compute_metrics(y_tr, tr_p, thr)
                            m_va = compute_metrics(y_va, va_p, thr)
                            m_ho = compute_metrics(y_ho, ho_p, thr)
                            val_obj = objective(m_va) - 0.08 * max(0.0, m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
                            trial_id += 1
                            rec = {
                                "trial_id": trial_id, "stage": "stage2", "mode": mode, "role": role, "domain": domain,
                                "feature_set_id": fs_id, "config_id": cfg_id, "seed": seed, "calibration": cal,
                                "threshold_policy": pol, "threshold": thr, "n_features": len(feats),
                                "val_objective": val_obj, "overfit_gap_ba": m_tr["balanced_accuracy"] - m_va["balanced_accuracy"],
                                "selected_for_stage2": "yes", "threshold_policy_score": pol_score,
                            }
                            for k, v in m_tr.items():
                                rec[f"train_{k}"] = v
                            for k, v in m_va.items():
                                rec[f"val_{k}"] = v
                            for k, v in m_ho.items():
                                rec[f"holdout_{k}"] = v
                            trial_rows.append({k: rec.get(k) for k in ["trial_id", "stage", "mode", "role", "domain", "feature_set_id", "config_id", "seed", "calibration", "threshold_policy", "threshold", "n_features", "selected_for_stage2", "val_objective", "overfit_gap_ba"]})
                            trial_metric_rows.append(rec)
                            stage2_local.append(rec)

            stage2_df = pd.DataFrame(stage2_local)
            if stage2_df.empty:
                raise RuntimeError(f"Stage2 empty for {mode}/{domain}")

            grouped = stage2_df.groupby(["feature_set_id", "config_id", "calibration", "threshold_policy"], as_index=False).agg(
                val_precision_mean=("val_precision", "mean"),
                val_recall_mean=("val_recall", "mean"),
                val_ba_mean=("val_balanced_accuracy", "mean"),
                val_pr_auc_mean=("val_pr_auc", "mean"),
                val_brier_mean=("val_brier", "mean"),
                val_obj_mean=("val_objective", "mean"),
                val_obj_std=("val_objective", "std"),
                n_features=("n_features", "max"),
            ).fillna(0.0)
            grouped["selection_score"] = 0.42 * grouped["val_precision_mean"] + 0.24 * grouped["val_ba_mean"] + 0.18 * grouped["val_pr_auc_mean"] + 0.10 * grouped["val_recall_mean"] - 0.06 * grouped["val_brier_mean"] - 0.05 * grouped["val_obj_std"]
            winner_group = grouped.sort_values(["selection_score", "val_ba_mean", "val_precision_mean", "n_features"], ascending=[False, False, False, True]).iloc[0]
            wkey = (str(winner_group["feature_set_id"]), str(winner_group["config_id"]), str(winner_group["calibration"]), str(winner_group["threshold_policy"]))
            seed_row = stage2_df[(stage2_df["feature_set_id"] == wkey[0]) & (stage2_df["config_id"] == wkey[1]) & (stage2_df["calibration"] == wkey[2]) & (stage2_df["threshold_policy"] == wkey[3])].sort_values("val_objective", ascending=False).iloc[0]
            wseed = int(seed_row["seed"])
            feats_w = feat_sets[wkey[0]]
            cfg_w = RF_CFG[wkey[1]]
            Xtr = prepare_X(tr_df, feats_w)
            Xva = prepare_X(va_df, feats_w)
            Xho = prepare_X(ho_df, feats_w)
            wp = make_pipeline(feats_w, cfg_w, wseed)
            fit_with_count(wp, Xtr, y_tr, int(cfg_w["n_estimators"]))
            tr_raw = np.clip(wp.predict_proba(Xtr)[:, 1], 1e-6, 1 - 1e-6)
            va_raw = np.clip(wp.predict_proba(Xva)[:, 1], 1e-6, 1 - 1e-6)
            ho_raw = np.clip(wp.predict_proba(Xho)[:, 1], 1e-6, 1 - 1e-6)
            cal_probs, _, cal_transforms = calibrate_probabilities(y_va, tr_raw, va_raw, ho_raw)
            sel_cal = wkey[2] if wkey[2] in cal_probs else "none"
            tr_p, va_p, ho_p = cal_probs[sel_cal]
            sel_thr, _ = choose_threshold(wkey[3], y_va, va_p, recall_floor=0.50)
            m_tr = compute_metrics(y_tr, tr_p, sel_thr)
            m_va = compute_metrics(y_va, va_p, sel_thr)
            m_ho = compute_metrics(y_ho, ho_p, sel_thr)

            # baseline for material-gain reference
            b_feats = feat_sets["full_eligible"]
            b_cfg = RF_CFG["rf_baseline"]
            Xtr_b, Xva_b, Xho_b = prepare_X(tr_df, b_feats), prepare_X(va_df, b_feats), prepare_X(ho_df, b_feats)
            bp = make_pipeline(b_feats, b_cfg, BASE_SEED)
            fit_with_count(bp, Xtr_b, y_tr, int(b_cfg["n_estimators"]))
            ho_b = np.clip(bp.predict_proba(Xho_b)[:, 1], 1e-6, 1 - 1e-6)
            m_ho_b = compute_metrics(y_ho, ho_b, 0.5)

            for pol in THRESH_POLICIES:
                thr, pscore = choose_threshold(pol, y_va, va_p, recall_floor=0.50)
                mvo = compute_metrics(y_va, va_p, thr)
                mho = compute_metrics(y_ho, ho_p, thr)
                threshold_rows.append({
                    "mode": mode, "role": role, "domain": domain,
                    "winner_feature_set_id": wkey[0], "winner_config_id": wkey[1], "winner_seed": wseed,
                    "calibration": sel_cal, "threshold_policy": pol, "threshold": thr, "policy_score": pscore,
                    "is_selected_policy": "yes" if pol == wkey[3] else "no",
                    "val_precision": mvo["precision"], "val_recall": mvo["recall"], "val_balanced_accuracy": mvo["balanced_accuracy"], "val_pr_auc": mvo["pr_auc"], "val_brier": mvo["brier"],
                    "holdout_precision": mho["precision"], "holdout_recall": mho["recall"], "holdout_balanced_accuracy": mho["balanced_accuracy"], "holdout_pr_auc": mho["pr_auc"], "holdout_brier": mho["brier"],
                })

            boot = bootstrap_metric_ci(y_ho, ho_p, sel_thr, n_boot=220, seed=wseed + 5)
            boot_rows.append({
                "mode": mode, "domain": domain, "feature_set_id": wkey[0], "config_id": wkey[1],
                "calibration": sel_cal, "threshold_policy": wkey[3], "threshold": sel_thr, **boot
            })

            # seed stability
            for s in STAB_SEEDS:
                sp = make_pipeline(feats_w, cfg_w, s)
                fit_with_count(sp, Xtr, y_tr, int(cfg_w["n_estimators"]))
                trs = np.clip(sp.predict_proba(Xtr)[:, 1], 1e-6, 1 - 1e-6)
                vas = np.clip(sp.predict_proba(Xva)[:, 1], 1e-6, 1 - 1e-6)
                hos = np.clip(sp.predict_proba(Xho)[:, 1], 1e-6, 1 - 1e-6)
                cal_s, _, _ = calibrate_probabilities(y_va, trs, vas, hos)
                _, vas_p, hos_p = cal_s[sel_cal] if sel_cal in cal_s else cal_s["none"]
                thr_s, _ = choose_threshold(wkey[3], y_va, vas_p, recall_floor=0.50)
                ms = compute_metrics(y_ho, hos_p, thr_s)
                stab_rows.append({"mode": mode, "domain": domain, "seed": s, "precision": ms["precision"], "recall": ms["recall"], "balanced_accuracy": ms["balanced_accuracy"], "pr_auc": ms["pr_auc"], "brier": ms["brier"], "threshold": thr_s})

            # ablation
            imp = aggregate_importance(wp, feats_w)
            top_feats = imp.head(8).index.tolist()
            ablation_rows.append({"mode": mode, "domain": domain, "ablation": "baseline", "k": 0, "removed_features": "", "precision": m_ho["precision"], "recall": m_ho["recall"], "balanced_accuracy": m_ho["balanced_accuracy"], "pr_auc": m_ho["pr_auc"], "brier": m_ho["brier"]})
            for k in [1, 3]:
                rem = top_feats[:k]
                feats_ab = [f for f in feats_w if f not in set(rem)]
                if len(feats_ab) < 5:
                    continue
                Xtr_ab, Xva_ab, Xho_ab = prepare_X(tr_df, feats_ab), prepare_X(va_df, feats_ab), prepare_X(ho_df, feats_ab)
                abp = make_pipeline(feats_ab, cfg_w, wseed)
                fit_with_count(abp, Xtr_ab, y_tr, int(cfg_w["n_estimators"]))
                tr_ab = np.clip(abp.predict_proba(Xtr_ab)[:, 1], 1e-6, 1 - 1e-6)
                va_ab = np.clip(abp.predict_proba(Xva_ab)[:, 1], 1e-6, 1 - 1e-6)
                ho_ab = np.clip(abp.predict_proba(Xho_ab)[:, 1], 1e-6, 1 - 1e-6)
                cal_ab, _, _ = calibrate_probabilities(y_va, tr_ab, va_ab, ho_ab)
                _, va_abp, ho_abp = cal_ab[sel_cal] if sel_cal in cal_ab else cal_ab["none"]
                thr_ab, _ = choose_threshold(wkey[3], y_va, va_abp, recall_floor=0.50)
                mab = compute_metrics(y_ho, ho_abp, thr_ab)
                ablation_rows.append({"mode": mode, "domain": domain, "ablation": "drop_topk", "k": k, "removed_features": "|".join(rem), "precision": mab["precision"], "recall": mab["recall"], "balanced_accuracy": mab["balanced_accuracy"], "pr_auc": mab["pr_auc"], "brier": mab["brier"], "delta_ba": mab["balanced_accuracy"] - m_ho["balanced_accuracy"], "delta_pr_auc": mab["pr_auc"] - m_ho["pr_auc"]})

            # stress
            for ratio in [0.10, 0.20]:
                Xmiss = inject_missing(Xho, feats_w, ratio=ratio, seed=wseed + int(100 * ratio))
                ho_miss_raw = np.clip(wp.predict_proba(Xmiss)[:, 1], 1e-6, 1 - 1e-6)
                ho_miss = cal_transforms[sel_cal](ho_miss_raw) if sel_cal in cal_transforms else ho_miss_raw
                mm = compute_metrics(y_ho, ho_miss, sel_thr)
                stress_rows.append({"mode": mode, "domain": domain, "stress_type": "missingness", "scenario": f"missing_{int(100*ratio)}pct", "precision": mm["precision"], "recall": mm["recall"], "balanced_accuracy": mm["balanced_accuracy"], "pr_auc": mm["pr_auc"], "brier": mm["brier"], "delta_ba": mm["balanced_accuracy"] - m_ho["balanced_accuracy"]})

            for dthr in [-0.10, -0.05, 0.05, 0.10]:
                t = float(np.clip(sel_thr + dthr, 0.05, 0.95))
                mt = compute_metrics(y_ho, ho_p, t)
                stress_rows.append({"mode": mode, "domain": domain, "stress_type": "threshold", "scenario": f"threshold_shift_{dthr:+.2f}", "precision": mt["precision"], "recall": mt["recall"], "balanced_accuracy": mt["balanced_accuracy"], "pr_auc": mt["pr_auc"], "brier": mt["brier"], "delta_ba": mt["balanced_accuracy"] - m_ho["balanced_accuracy"]})

            # engineered material help signal by stage1
            st1_pair = stage1_df.copy()
            eng_best = st1_pair[st1_pair["feature_set_id"].str.startswith("engineered_")]["stage_score"].max() if not st1_pair[st1_pair["feature_set_id"].str.startswith("engineered_")].empty else np.nan
            non_best = st1_pair[~st1_pair["feature_set_id"].str.startswith("engineered_")]["stage_score"].max() if not st1_pair[~st1_pair["feature_set_id"].str.startswith("engineered_")].empty else np.nan
            fe_delta = (eng_best - non_best) if (not pd.isna(eng_best) and not pd.isna(non_best)) else np.nan
            fe_result_rows.append({"mode": mode, "domain": domain, "best_stage1_engineered_score": eng_best, "best_stage1_non_engineered_score": non_best, "delta_engineered_minus_non": fe_delta, "engineered_help_material": "yes" if (not pd.isna(fe_delta) and fe_delta >= 0.01) else "no"})
            overfit_gap = float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"])
            gen_gap = float(abs(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]))
            overfit_warning = "yes" if (overfit_gap > 0.07 or gen_gap > 0.06) else "no"

            if m_ho["precision"] >= 0.88 and m_ho["recall"] >= 0.80 and m_ho["balanced_accuracy"] >= 0.90 and m_ho["pr_auc"] >= 0.90 and m_ho["brier"] <= 0.05 and overfit_warning == "no":
                q = "muy_bueno"
            elif m_ho["precision"] >= 0.84 and m_ho["recall"] >= 0.75 and m_ho["balanced_accuracy"] >= 0.88 and m_ho["pr_auc"] >= 0.88 and m_ho["brier"] <= 0.06 and overfit_warning == "no":
                q = "bueno"
            elif m_ho["precision"] >= 0.80 and m_ho["recall"] >= 0.70 and m_ho["balanced_accuracy"] >= 0.85 and m_ho["pr_auc"] >= 0.85 and m_ho["brier"] <= 0.08:
                q = "aceptable"
            else:
                q = "malo"

            d_ba = m_ho["balanced_accuracy"] - m_ho_b["balanced_accuracy"]
            d_pr = m_ho["pr_auc"] - m_ho_b["pr_auc"]
            d_prec = m_ho["precision"] - m_ho_b["precision"]
            d_brier = m_ho["brier"] - m_ho_b["brier"]
            material_gain = (d_ba >= 0.01) or (d_pr >= 0.01) or ((d_prec >= 0.01) and (m_ho["recall"] >= (m_ho_b["recall"] - 0.03))) or (d_brier <= -0.01)

            if (not material_gain) and q in {"muy_bueno", "bueno"} and overfit_warning == "no":
                ceiling = "ceiling_confirmed"
            elif material_gain:
                ceiling = "marginal_room_left"
            else:
                ceiling = "near_ceiling"

            if ceiling == "ceiling_confirmed":
                keep = "no_practical_ceiling_confirmed"
            elif q == "malo":
                keep = "only_if_new_signal"
            elif material_gain and overfit_warning == "no":
                keep = "yes"
            else:
                keep = "no"

            if q in {"muy_bueno", "bueno"} and overfit_warning == "no":
                final_status = "FROZEN_PRIMARY"
            elif q == "aceptable":
                final_status = "FROZEN_WITH_CAVEAT"
            else:
                final_status = "HOLD_FOR_LIMITATION"

            final_rows.append({
                "mode": mode, "role": role, "domain": domain,
                "feature_set_id": wkey[0], "config_id": wkey[1], "calibration": sel_cal, "threshold_policy": wkey[3], "threshold": sel_thr, "seed": wseed,
                "n_features": len(feats_w),
                "precision": m_ho["precision"], "recall": m_ho["recall"], "specificity": m_ho["specificity"], "balanced_accuracy": m_ho["balanced_accuracy"], "f1": m_ho["f1"], "roc_auc": m_ho["roc_auc"], "pr_auc": m_ho["pr_auc"], "brier": m_ho["brier"],
                "train_precision": m_tr["precision"], "train_recall": m_tr["recall"], "train_balanced_accuracy": m_tr["balanced_accuracy"], "val_precision": m_va["precision"], "val_recall": m_va["recall"], "val_balanced_accuracy": m_va["balanced_accuracy"],
                "overfit_gap_train_val_ba": overfit_gap, "generalization_gap_val_holdout_ba": gen_gap, "overfit_warning": overfit_warning,
                "baseline_holdout_precision": m_ho_b["precision"], "baseline_holdout_recall": m_ho_b["recall"], "baseline_holdout_ba": m_ho_b["balanced_accuracy"], "baseline_holdout_pr_auc": m_ho_b["pr_auc"], "baseline_holdout_brier": m_ho_b["brier"],
                "delta_vs_baseline_precision": d_prec, "delta_vs_baseline_ba": d_ba, "delta_vs_baseline_pr_auc": d_pr, "delta_vs_baseline_brier": d_brier,
                "material_gain_vs_baseline": "yes" if material_gain else "no",
                "quality_label": q, "ceiling_status": ceiling, "should_keep_improving": keep, "final_status": final_status,
                "notes": "clean_universe_no_external_scores",
            })

    print_progress("Saving trial-level outputs")
    feature_set_df = pd.DataFrame(feature_set_rows).drop_duplicates(subset=["mode", "domain", "feature_set_id"]).sort_values(["mode", "domain", "feature_set_id"]).reset_index(drop=True)
    trial_registry_df = pd.DataFrame(trial_rows).sort_values("trial_id").reset_index(drop=True)
    trial_metrics_df = pd.DataFrame(trial_metric_rows).sort_values("trial_id").reset_index(drop=True)
    calibration_df = pd.DataFrame(calibration_rows)
    threshold_df = pd.DataFrame(threshold_rows)
    boot_df = pd.DataFrame(boot_rows)
    stab_df = pd.DataFrame(stab_rows)
    ablation_df = pd.DataFrame(ablation_rows)
    stress_df = pd.DataFrame(stress_rows)
    final_df = pd.DataFrame(final_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    fe_results_df = pd.DataFrame(fe_result_rows).sort_values(["domain", "mode"]).reset_index(drop=True)

    save_csv(trial_registry_df, TRIALS / "hybrid_no_external_scores_trial_registry.csv")
    save_csv(trial_metrics_df, TRIALS / "hybrid_no_external_scores_trial_metrics_full.csv")
    save_csv(feature_set_df, FE / "hybrid_no_external_scores_feature_engineering_registry.csv")
    save_csv(fe_results_df, FE / "hybrid_no_external_scores_feature_engineering_results.csv")
    save_csv(calibration_df, CAL / "hybrid_no_external_scores_calibration_results.csv")
    save_csv(threshold_df, THR / "hybrid_no_external_scores_threshold_results.csv")
    save_csv(boot_df, BOOT / "hybrid_no_external_scores_bootstrap_intervals.csv")
    save_csv(stab_df, STAB / "hybrid_no_external_scores_seed_stability.csv")
    save_csv(ablation_df, ABL / "hybrid_no_external_scores_ablation_results.csv")
    save_csv(stress_df, STRESS / "hybrid_no_external_scores_stress_results.csv")
    save_csv(final_df, TABLES / "hybrid_no_external_scores_final_models.csv")
    print_progress("Comparing against frozen previous line")
    comp = final_df.merge(
        frozen[["domain", "mode", "feature_set_id", "config_id", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "quality_label", "final_status"]].rename(columns={
            "feature_set_id": "prev_feature_set_id", "config_id": "prev_config_id", "precision": "prev_precision", "recall": "prev_recall", "balanced_accuracy": "prev_balanced_accuracy", "pr_auc": "prev_pr_auc", "brier": "prev_brier", "quality_label": "prev_quality_label", "final_status": "prev_final_status"
        }),
        on=["domain", "mode"],
        how="left",
    )
    comp["delta_precision"] = comp["precision"] - comp["prev_precision"]
    comp["delta_recall"] = comp["recall"] - comp["prev_recall"]
    comp["delta_balanced_accuracy"] = comp["balanced_accuracy"] - comp["prev_balanced_accuracy"]
    comp["delta_pr_auc"] = comp["pr_auc"] - comp["prev_pr_auc"]
    comp["delta_brier"] = comp["brier"] - comp["prev_brier"]
    comp["comparison_result"] = np.where(comp["delta_balanced_accuracy"] >= 0.01, "improves", np.where(comp["delta_balanced_accuracy"] <= -0.01, "worse", "tie_noise"))
    comp["drop_methodologically_acceptable"] = np.where(comp["delta_balanced_accuracy"] < -0.01, "yes_alignment_gain", "na_or_not_drop")
    comp["new_replaces_previous_as_primary"] = np.where(
        (comp["quality_label"].isin(["muy_bueno", "bueno"])) & (comp["overfit_warning"] == "no"),
        "yes",
        np.where(comp["quality_label"] == "aceptable", "yes_with_caveat", "no"),
    )
    save_csv(comp.sort_values(["domain", "mode"]), TABLES / "hybrid_no_external_scores_vs_frozen_comparison.csv")

    ranked = final_df.copy()
    ranked["ranking_score"] = 0.40 * ranked["precision"] + 0.24 * ranked["balanced_accuracy"] + 0.18 * ranked["pr_auc"] + 0.10 * ranked["recall"] - 0.08 * ranked["brier"]
    ranked["stability_penalty"] = 0.60 * ranked["overfit_gap_train_val_ba"].clip(lower=0) + 0.60 * ranked["generalization_gap_val_holdout_ba"].clip(lower=0)
    ranked["ranking_score_adj"] = ranked["ranking_score"] - ranked["stability_penalty"]
    ranked = ranked.sort_values(["ranking_score_adj", "balanced_accuracy"], ascending=False).reset_index(drop=True)
    save_csv(ranked, TABLES / "hybrid_no_external_scores_final_ranked_models.csv")

    champions = []
    for d in DOMAINS:
        ddf = ranked[ranked["domain"] == d].copy()
        if ddf.empty:
            continue
        ddf = ddf.sort_values(["ranking_score_adj", "balanced_accuracy", "precision"], ascending=False)
        best = ddf.iloc[0].copy()
        if str(best["mode"]).endswith("full"):
            m23 = str(best["mode"]).replace("_full", "_2_3")
            alt = ddf[ddf["mode"] == m23]
            if not alt.empty:
                a = alt.iloc[0]
                if (best["balanced_accuracy"] - a["balanced_accuracy"] < 0.01) and (best["pr_auc"] - a["pr_auc"] < 0.01) and (best["precision"] - a["precision"] < 0.015):
                    best = a
        champions.append({
            "domain": d,
            "champion_mode": best["mode"],
            "champion_feature_set_id": best["feature_set_id"],
            "champion_config_id": best["config_id"],
            "champion_calibration": best["calibration"],
            "champion_threshold_policy": best["threshold_policy"],
            "champion_final_status": best["final_status"],
            "precision": best["precision"], "recall": best["recall"], "balanced_accuracy": best["balanced_accuracy"], "pr_auc": best["pr_auc"], "brier": best["brier"],
            "ceiling_status": best["ceiling_status"], "should_keep_improving": best["should_keep_improving"],
        })
    champions_df = pd.DataFrame(champions).sort_values("domain").reset_index(drop=True)
    save_csv(champions_df, TABLES / "hybrid_no_external_scores_final_champions.csv")

    print_progress("Writing reports")
    qcounts = final_df["quality_label"].value_counts().to_dict()
    ccounts = final_df["ceiling_status"].value_counts().to_dict()
    icounts = final_df["should_keep_improving"].value_counts().to_dict()

    summary = [
        "# Hybrid No External Scores Rebuild v2 - Summary",
        "",
        "## Final models (30)",
        md_table(final_df[["domain", "mode", "precision", "recall", "balanced_accuracy", "pr_auc", "brier", "quality_label", "ceiling_status", "final_status"]]),
        "",
        f"- quality_counts: {qcounts}",
        f"- ceiling_counts: {ccounts}",
        f"- keep_improving_counts: {icounts}",
        f"- fits_total: {FIT_COUNTER['fits']}",
        f"- trees_total: {FIT_COUNTER['trees']}",
    ]
    write_md(REPORTS / "hybrid_no_external_scores_rebuild_summary.md", "\n".join(summary))

    dec = [
        "# Hybrid No External Scores - Modeling Decision",
        "",
        "## Champions",
        md_table(champions_df),
        "",
        "## Viability",
        "- This line is strictly aligned with product reality (no external scores/subscales).",
        "- Promote as new primary only where quality and stability are defendable.",
        "- Keep explicit caveats where quality dropped materially versus frozen historical line.",
    ]
    write_md(REPORTS / "hybrid_no_external_scores_modeling_decision.md", "\n".join(dec))

    align = [
        "# Hybrid No External Scores - Questionnaire Alignment",
        "",
        "## Governance",
        "- External score/subscale/cutoff columns explicitly excluded from new primary line.",
        "- Only questionnaire-answerable direct inputs + transparent derived + demography + internal engineered features are used.",
        "",
        "## Mode coverage",
        md_table(mode_cov[["mode", "direct_features", "derived_features", "engineered_features", "eligible_base_features", "features_lost_vs_freeze", "severely_impoverished_mode"]]),
    ]
    write_md(REPORTS / "hybrid_no_external_scores_questionnaire_alignment.md", "\n".join(align))

    ceil = [
        "# Hybrid No External Scores - Ceiling Decision",
        "",
        md_table(final_df[["domain", "mode", "quality_label", "ceiling_status", "should_keep_improving", "overfit_warning"]]),
    ]
    write_md(REPORTS / "hybrid_no_external_scores_ceiling_decision.md", "\n".join(ceil))

    cmp_md = [
        "# Hybrid No External Scores - Comparison vs Previous Frozen",
        "",
        md_table(comp[["domain", "mode", "prev_balanced_accuracy", "balanced_accuracy", "delta_balanced_accuracy", "prev_pr_auc", "pr_auc", "delta_pr_auc", "comparison_result", "new_replaces_previous_as_primary"]]),
    ]
    write_md(REPORTS / "hybrid_no_external_scores_comparison_vs_previous.md", "\n".join(cmp_md))
    generated_files = []
    for p in sorted(BASE.rglob("*")):
        if p.is_file():
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            generated_files.append({"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": h.hexdigest(), "bytes": p.stat().st_size})

    manifest = {
        "line": LINE,
        "generated_at_utc": now_iso(),
        "fits_total": FIT_COUNTER["fits"],
        "trees_total": FIT_COUNTER["trees"],
        "removed_columns_explicit_external": [c for c in EXTERNAL_SCORE_COLUMNS if c in raw.columns],
        "removed_columns_count": int(len(removed)),
        "retained_columns_count": int(len(retained)),
        "engineered_features_count": int(len(engineered_features)),
        "generated_files": generated_files,
    }
    (ART / "hybrid_no_external_scores_rebuild_v2_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print_progress("Campaign completed")


def main() -> None:
    run_campaign()


if __name__ == "__main__":
    main()
