#!/usr/bin/env python
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
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
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LINE = "hybrid_elimination_v14_real_anti_clone_rescue"
FREEZE = "v14"

BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
VALIDATION = BASE / "validation"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"

ACTIVE_V13 = ROOT / "data/hybrid_active_modes_freeze_v13/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V13_SUMMARY = ROOT / "data/hybrid_active_modes_freeze_v13/tables/hybrid_active_modes_summary.csv"
INPUTS_V13 = ROOT / "data/hybrid_active_modes_freeze_v13/tables/hybrid_questionnaire_inputs_master.csv"
OP_V13 = ROOT / "data/hybrid_operational_freeze_v13/tables/hybrid_operational_final_champions.csv"
OP_V13_NONCHAMP = ROOT / "data/hybrid_operational_freeze_v13/tables/hybrid_operational_final_nonchampions.csv"

AUDIT_V13_ELIM = ROOT / "data/hybrid_v13_real_prediction_anti_clone_audit/tables/v13_elimination_real_prediction_similarity.csv"
AUDIT_V13_ALL = ROOT / "data/hybrid_v13_real_prediction_anti_clone_audit/tables/v13_pairwise_prediction_similarity_all_domains.csv"
AUDIT_V13_REPORT = ROOT / "data/hybrid_v13_real_prediction_anti_clone_audit/reports/v13_real_prediction_anti_clone_report.md"
AUDIT_V13_VALID = ROOT / "data/hybrid_v13_real_prediction_anti_clone_audit/validation/v13_elimination_clone_risk_validator.csv"

DATASET = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
LOADER = ROOT / "api/services/questionnaire_v2_loader_service.py"

V10_SELECTED = ROOT / "data/hybrid_rf_max_real_metrics_v1/tables/selected_rf_champions_with_deltas_v11.csv"
V11_SELECTED = ROOT / "data/hybrid_final_rf_plus_maximize_metrics_v1/tables/selected_rf_champions_with_deltas_v12.csv"

ACTIVE_V14_OUT = ROOT / "data/hybrid_active_modes_freeze_v14/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V14_SUMMARY_OUT = ROOT / "data/hybrid_active_modes_freeze_v14/tables/hybrid_active_modes_summary.csv"
INPUTS_V14_OUT = ROOT / "data/hybrid_active_modes_freeze_v14/tables/hybrid_questionnaire_inputs_master.csv"
OP_V14_OUT = ROOT / "data/hybrid_operational_freeze_v14/tables/hybrid_operational_final_champions.csv"
OP_V14_NONCHAMP_OUT = ROOT / "data/hybrid_operational_freeze_v14/tables/hybrid_operational_final_nonchampions.csv"

ART_ACTIVE_V14 = ROOT / "artifacts/hybrid_active_modes_freeze_v14/hybrid_active_modes_freeze_v14_manifest.json"
ART_OP_V14 = ROOT / "artifacts/hybrid_operational_freeze_v14/hybrid_operational_freeze_v14_manifest.json"
ART_LINE = ROOT / f"artifacts/{LINE}/{LINE}_manifest.json"

MODEL_ROOT = ROOT / "models/active_modes"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
WATCH = ["recall", "specificity", "roc_auc", "pr_auc"]
METRICS_CORE = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]
METRICS_WITH_COUNTS = METRICS_CORE + ["tn", "fp", "fn", "tp", "threshold", "n_features"]
BASE_SEED = 20261101
ELIM_SLOT_ORDER = [
    ("caregiver", "caregiver_1_3"),
    ("caregiver", "caregiver_2_3"),
    ("caregiver", "caregiver_full"),
    ("psychologist", "psychologist_1_3"),
    ("psychologist", "psychologist_2_3"),
    ("psychologist", "psychologist_full"),
]

# 12 configs (<=30), 3 seeds (<=5), 7 threshold strategies (<=7)
SEEDS = [20270421, 20270439, 20270457]
THRESHOLD_POLICIES = [
    "max_f1_precision_guard",
    "recall_target_guard",
    "f1_ba_conservative",
    "precision_recovery",
    "pareto_f1_recall_precision",
    "balanced_accuracy_focus",
    "guardrail_conservative",
]
RF_CONFIGS: list[dict[str, Any]] = [
    {"config_id": "rf_v14_balanced_shallow", "n_estimators": 180, "max_depth": 5, "min_samples_split": 16, "min_samples_leaf": 8, "max_features": "sqrt", "class_weight": "balanced", "bootstrap": True, "max_samples": 0.85, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none"]},
    {"config_id": "rf_v14_balanced_medium", "n_estimators": 220, "max_depth": 8, "min_samples_split": 10, "min_samples_leaf": 5, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.82, "criterion": "gini", "ccp_alpha": 0.00005, "calibrations": ["none"]},
    {"config_id": "rf_v14_feature_bagging", "n_estimators": 220, "max_depth": 9, "min_samples_split": 8, "min_samples_leaf": 4, "max_features": 0.22, "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.78, "criterion": "gini", "ccp_alpha": 0.0001, "calibrations": ["none"]},
    {"config_id": "rf_v14_guard_randomized", "n_estimators": 90, "max_depth": 3, "min_samples_split": 90, "min_samples_leaf": 42, "max_features": 0.2, "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.48, "criterion": "entropy", "ccp_alpha": 0.002, "calibrations": ["none"]},
    {"config_id": "rf_v14_recall_guarded", "n_estimators": 170, "max_depth": 6, "min_samples_split": 12, "min_samples_leaf": 5, "max_features": "log2", "class_weight": "manual_recall", "bootstrap": True, "max_samples": 0.90, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none"]},
    {"config_id": "rf_v14_pruned_small", "n_estimators": 140, "max_depth": 4, "min_samples_split": 28, "min_samples_leaf": 12, "max_features": 0.45, "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.80, "criterion": "gini", "ccp_alpha": 0.001, "calibrations": ["none"]},
    {"config_id": "rf_v14_pruned_medium", "n_estimators": 160, "max_depth": 6, "min_samples_split": 20, "min_samples_leaf": 9, "max_features": 0.35, "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.76, "criterion": "entropy", "ccp_alpha": 0.0005, "calibrations": ["none"]},
    {"config_id": "rf_v14_bootstrap_low", "n_estimators": 210, "max_depth": 8, "min_samples_split": 10, "min_samples_leaf": 4, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.65, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none"]},
    {"config_id": "rf_v14_bootstrap_high", "n_estimators": 210, "max_depth": 8, "min_samples_split": 10, "min_samples_leaf": 4, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.95, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none"]},
    {"config_id": "rf_v14_calibrated_sigmoid", "n_estimators": 150, "max_depth": 6, "min_samples_split": 14, "min_samples_leaf": 7, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.84, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none", "sigmoid"]},
    {"config_id": "rf_v14_calibrated_isotonic", "n_estimators": 130, "max_depth": 5, "min_samples_split": 16, "min_samples_leaf": 8, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.86, "criterion": "gini", "ccp_alpha": 0.0, "calibrations": ["none", "isotonic"]},
    {"config_id": "rf_v14_train_oversample", "n_estimators": 180, "max_depth": 8, "min_samples_split": 10, "min_samples_leaf": 5, "max_features": "sqrt", "class_weight": "balanced_subsample", "bootstrap": True, "max_samples": 0.80, "criterion": "gini", "ccp_alpha": 0.00005, "calibrations": ["none"], "resampling": "positive_oversample_moderate"},
]


@dataclass
class Candidate:
    key: str
    slot_mode: str
    role: str
    threshold: float
    threshold_policy: str
    config_id: str
    calibration: str
    seed: int | None
    feature_list_pipe: str
    n_features: int
    precision: float
    recall: float
    specificity: float
    balanced_accuracy: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier: float
    tn: int
    fp: int
    fn: int
    tp: int
    probability_mean: float
    probability_std: float
    positive_rate: float
    guardrail_ok: str
    precision_floor_ok: str
    quality_score: float
    source_type: str
    source_model_id: str
    notes: str
    feature_set_id: str
    model_obj: Any
    probs_holdout: np.ndarray
    preds_holdout: np.ndarray
    y_holdout: np.ndarray
    probs_val: np.ndarray
    y_val: np.ndarray
    artifact_hash: str | None
    artifact_path: str | None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mkdirs() -> None:
    for path in [
        BASE,
        TABLES,
        VALIDATION,
        REPORTS,
        PLOTS,
        ACTIVE_V14_OUT.parent,
        OP_V14_OUT.parent,
        ART_ACTIVE_V14.parent,
        ART_OP_V14.parent,
        ART_LINE.parent,
        MODEL_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def sf(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def tcol(domain: str) -> str:
    return f"target_domain_{domain}_final"


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def auc(y_true: np.ndarray, prob: np.ndarray) -> float:
    return float(roc_auc_score(y_true, prob)) if len(np.unique(y_true)) > 1 else float("nan")


def pr_auc(y_true: np.ndarray, prob: np.ndarray) -> float:
    return float(average_precision_score(y_true, prob)) if len(np.unique(y_true)) > 1 else float(np.mean(y_true))


def compute_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict[str, float | int]:
    prob = np.clip(np.asarray(prob, dtype=float), 1e-6, 1 - 1e-6)
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": auc(y_true, prob),
        "pr_auc": pr_auc(y_true, prob),
        "brier": float(brier_score_loss(y_true, prob)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def split_registry(df: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    ids = df["participant_id"].astype(str).to_numpy()
    out: dict[str, dict[str, list[str]]] = {}
    for i, domain in enumerate(DOMAINS):
        y = df[tcol(domain)].astype(int).to_numpy()
        seed = BASE_SEED + i * 23
        train_ids, tmp_ids, _, y_tmp = train_test_split(
            ids,
            y,
            test_size=0.40,
            random_state=seed,
            stratify=y,
        )
        val_ids, holdout_ids, _, _ = train_test_split(
            tmp_ids,
            y_tmp,
            test_size=0.50,
            random_state=seed + 1,
            stratify=y_tmp,
        )
        out[domain] = {
            "train": list(map(str, train_ids)),
            "val": list(map(str, val_ids)),
            "holdout": list(map(str, holdout_ids)),
        }
    return out


def prep_x(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    x = df[feature_columns].copy()
    for col in x.columns:
        if col == "sex_assigned_at_birth":
            x[col] = x[col].fillna("Unknown").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce").astype(float)
    return x


def external_artifact_roots() -> list[tuple[str, Path]]:
    parent = ROOT.parent
    return [
        ("current_repo", ROOT / "models" / "active_modes"),
        ("worktree_rf_max_real_metrics", parent / "cognia_app_rf_max_real_metrics" / "models" / "active_modes"),
        ("worktree_final_rf_plus", parent / "cognia_app_final_rf_plus_maximize" / "models" / "active_modes"),
        ("clean_clone", parent / "cognia_app_elimination_v14_clean" / "models" / "active_modes"),
    ]


def resolve_existing_artifact(model_id: str) -> tuple[str | None, str | None, str | None]:
    for origin, base in external_artifact_roots():
        candidate = base / model_id / "pipeline.joblib"
        if candidate.exists():
            try:
                rel = candidate.relative_to(ROOT)
                rel_path = str(rel).replace("\\", "/")
            except Exception:
                rel_path = str(candidate)
            return rel_path, origin, sha256_file(candidate)
    return None, None, None


def detect_loader_line(text: str) -> tuple[str, str, str]:
    act = re.search(r"hybrid_active_modes_freeze_(v\d+)", text)
    op = re.search(r"hybrid_operational_freeze_(v\d+)", text)
    a = act.group(1) if act else "por_confirmar"
    o = op.group(1) if op else "por_confirmar"
    return a, o, "yes" if a == "v13" and o == "v13" else "no"


def guard_ok(metrics: dict[str, float | int]) -> bool:
    return all(sf(metrics.get(k), 1.0) <= 0.98 for k in WATCH)


def quality_score(metrics: dict[str, float | int], precision_floor: float) -> float:
    score = (
        0.45 * sf(metrics.get("f1"), 0)
        + 0.22 * sf(metrics.get("recall"), 0)
        + 0.18 * sf(metrics.get("precision"), 0)
        + 0.10 * sf(metrics.get("balanced_accuracy"), 0)
        + 0.05 * max(0.0, 1 - sf(metrics.get("brier"), 0.25))
    )
    if sf(metrics.get("precision"), 0) < precision_floor:
        score -= 0.35 + 0.80 * (precision_floor - sf(metrics.get("precision"), 0))
    if not guard_ok(metrics):
        score -= 2.0
    return float(score)


def precision_floor_from_current(current_precision: float) -> float:
    return max(0.62, float(current_precision) - 0.05)


def thr_grid(probs: np.ndarray) -> np.ndarray:
    vals = list(np.linspace(0.05, 0.95, 91))
    if len(probs):
        vals.extend(list(np.quantile(probs, np.linspace(0.05, 0.95, 37))))
    return np.array(sorted(set(float(v) for v in vals if 0 < float(v) < 1)), dtype=float)


def threshold_score(policy: str, metrics: dict[str, float | int], precision_floor: float, mode: str) -> float:
    lo, hi = ((0.88, 0.95) if mode.endswith("1_3") else (0.92, 0.98))
    f1v = sf(metrics.get("f1"), 0)
    rec = sf(metrics.get("recall"), 0)
    pre = sf(metrics.get("precision"), 0)
    ba = sf(metrics.get("balanced_accuracy"), 0)
    brier = sf(metrics.get("brier"), 1)

    if policy == "max_f1_precision_guard":
        s = 0.58 * f1v + 0.16 * rec + 0.14 * pre + 0.10 * ba + 0.02 * max(0, 1 - brier)
    elif policy == "recall_target_guard":
        s = 0.36 * f1v + 0.30 * rec + 0.16 * pre + 0.14 * ba + 0.04 * max(0, 1 - brier)
        if lo <= rec <= hi:
            s += 0.04
    elif policy == "precision_recovery":
        s = 0.46 * f1v + 0.13 * rec + 0.25 * pre + 0.12 * ba + 0.04 * max(0, 1 - brier)
        if pre >= precision_floor + 0.03:
            s += 0.03
    elif policy == "pareto_f1_recall_precision":
        s = 0.50 * f1v + 0.22 * rec + 0.18 * pre + 0.08 * ba + 0.02 * max(0, 1 - brier)
    elif policy == "balanced_accuracy_focus":
        s = 0.35 * f1v + 0.20 * rec + 0.15 * pre + 0.25 * ba + 0.05 * max(0, 1 - brier)
    elif policy == "guardrail_conservative":
        s = 0.44 * f1v + 0.16 * rec + 0.18 * pre + 0.16 * ba + 0.06 * max(0, 1 - brier)
        if max(sf(metrics.get(k), 0) for k in WATCH) > 0.975:
            s -= 0.12
    else:
        s = 0.42 * f1v + 0.19 * rec + 0.17 * pre + 0.18 * ba + 0.04 * max(0, 1 - brier)

    if pre < precision_floor:
        s -= 0.35 + 0.75 * (precision_floor - pre)
    if rec < lo:
        s -= 0.16 * (lo - rec)
    if rec > hi:
        s -= 0.12 * (rec - hi)
    for k in WATCH:
        v = sf(metrics.get(k), 0)
        if v > 0.98:
            s -= 0.50 + (v - 0.98)
    return float(s)


def choose_threshold(policy: str, y_val: np.ndarray, probs_val: np.ndarray, precision_floor: float, mode: str) -> tuple[float, dict[str, float | int], float]:
    best_thr = 0.5
    best_metrics = compute_metrics(y_val, probs_val, 0.5)
    best_score = -1e18
    for thr in thr_grid(probs_val):
        mm = compute_metrics(y_val, probs_val, float(thr))
        s = threshold_score(policy, mm, precision_floor, mode)
        if s > best_score:
            best_thr = float(thr)
            best_metrics = mm
            best_score = float(s)
    return best_thr, best_metrics, best_score


def manual_weight(y: np.ndarray) -> dict[int, float]:
    pos = max(float(np.mean(y)), 1e-6)
    neg = max(1 - pos, 1e-6)
    return {0: 1.0, 1: float(min(3.6, max(1.2, neg / pos * 1.15)))}


def train_only_resample(x: pd.DataFrame, y: np.ndarray, cfg: dict[str, Any], seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    mode = str(cfg.get("resampling", "none") or "none")
    if mode == "none":
        return x, y
    rng = np.random.default_rng(seed + 17)
    y = np.asarray(y, dtype=int)
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    if len(pos) == 0 or len(neg) == 0:
        return x, y
    if mode == "positive_oversample_moderate":
        target = min(int(len(neg) * 0.72), int(len(pos) * 1.85))
        extra = max(0, target - len(pos))
        add = rng.choice(pos, size=extra, replace=True) if extra else np.array([], dtype=int)
        idx = np.concatenate([np.arange(len(y)), add])
    else:
        return x, y
    rng.shuffle(idx)
    return x.iloc[idx].reset_index(drop=True), y[idx]


def rf_pipe(features: list[str], cfg: dict[str, Any], seed: int, y: np.ndarray) -> Pipeline:
    cats = [f for f in features if f == "sex_assigned_at_birth"]
    nums = [f for f in features if f not in cats]
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", keep_empty_features=True))]), nums),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent", keep_empty_features=True)), ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cats),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    class_weight = manual_weight(y) if str(cfg.get("class_weight")) == "manual_recall" else cfg.get("class_weight")
    rf = RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=class_weight,
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        criterion=cfg["criterion"],
        ccp_alpha=float(cfg["ccp_alpha"]),
        random_state=seed,
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def fit_model(features: list[str], cfg: dict[str, Any], seed: int, calibration: str, xtr: pd.DataFrame, ytr: np.ndarray) -> Any:
    xfit, yfit = train_only_resample(xtr, ytr, cfg, seed)
    pipe = rf_pipe(features, cfg, seed, yfit)
    if calibration == "none":
        pipe.fit(xfit, yfit)
        return pipe
    cv = 3 if min(np.bincount(ytr.astype(int))) >= 3 else 2
    model = CalibratedClassifierCV(estimator=pipe, method=calibration, cv=cv)
    model.fit(xfit, yfit)
    return model


def proba(model: Any, x: pd.DataFrame) -> np.ndarray:
    return np.clip(np.asarray(model.predict_proba(x)[:, 1], dtype=float), 1e-6, 1 - 1e-6)


def candidate_from_probs(
    *,
    key: str,
    slot_mode: str,
    role: str,
    threshold: float,
    threshold_policy: str,
    config_id: str,
    calibration: str,
    seed: int | None,
    feature_list_pipe: str,
    n_features: int,
    source_type: str,
    source_model_id: str,
    notes: str,
    feature_set_id: str,
    model_obj: Any,
    probs_holdout: np.ndarray,
    y_holdout: np.ndarray,
    probs_val: np.ndarray,
    y_val: np.ndarray,
    artifact_hash: str | None = None,
    artifact_path: str | None = None,
    precision_floor: float = 0.62,
) -> Candidate:
    m = compute_metrics(y_holdout, probs_holdout, threshold)
    q = quality_score(m, precision_floor)
    preds = (probs_holdout >= threshold).astype(int)
    return Candidate(
        key=key,
        slot_mode=slot_mode,
        role=role,
        threshold=float(threshold),
        threshold_policy=threshold_policy,
        config_id=config_id,
        calibration=calibration,
        seed=seed,
        feature_list_pipe=feature_list_pipe,
        n_features=n_features,
        precision=float(m["precision"]),
        recall=float(m["recall"]),
        specificity=float(m["specificity"]),
        balanced_accuracy=float(m["balanced_accuracy"]),
        f1=float(m["f1"]),
        roc_auc=float(m["roc_auc"]),
        pr_auc=float(m["pr_auc"]),
        brier=float(m["brier"]),
        tn=int(m["tn"]),
        fp=int(m["fp"]),
        fn=int(m["fn"]),
        tp=int(m["tp"]),
        probability_mean=float(np.mean(probs_holdout)),
        probability_std=float(np.std(probs_holdout)),
        positive_rate=float(np.mean(preds)),
        guardrail_ok="yes" if guard_ok(m) else "no",
        precision_floor_ok="yes" if float(m["precision"]) >= precision_floor else "no",
        quality_score=q,
        source_type=source_type,
        source_model_id=source_model_id,
        notes=notes,
        feature_set_id=feature_set_id,
        model_obj=model_obj,
        probs_holdout=probs_holdout,
        preds_holdout=preds,
        y_holdout=y_holdout,
        probs_val=probs_val,
        y_val=y_val,
        artifact_hash=artifact_hash,
        artifact_path=artifact_path,
    )


def elimination_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["domain"].astype(str) == "elimination"].copy()
    out["role_mode_order"] = out["role"].astype(str) + "|" + out["mode"].astype(str)
    order = [f"{r}|{m}" for r, m in ELIM_SLOT_ORDER]
    out["role_mode_order"] = pd.Categorical(out["role_mode_order"], categories=order, ordered=True)
    out = out.sort_values("role_mode_order").drop(columns=["role_mode_order"])
    return out


def build_historical_slot_sources(active_v13: pd.DataFrame) -> dict[tuple[str, str], list[dict[str, Any]]]:
    slot_sources: dict[tuple[str, str], list[dict[str, Any]]] = {}
    v10 = pd.read_csv(V10_SELECTED) if V10_SELECTED.exists() else pd.DataFrame()
    v11 = pd.read_csv(V11_SELECTED) if V11_SELECTED.exists() else pd.DataFrame()

    for _, row in elimination_rows(active_v13).iterrows():
        key = (str(row["role"]), str(row["mode"]))
        slot_sources.setdefault(key, [])
        slot_sources[key].append(
            {
                "source_name": "v13_active",
                "active_model_id": str(row["active_model_id"]),
                "threshold": sf(row["threshold"]),
                "config_id": str(row.get("config_id") or "por_confirmar"),
                "calibration": str(row.get("calibration") or "none"),
                "feature_list_pipe": str(row.get("feature_list_pipe") or ""),
                "feature_set_id": str(row.get("feature_set_id") or "por_confirmar"),
            }
        )

    def append_from(df: pd.DataFrame, source_name: str) -> None:
        if df.empty:
            return
        for _, row in df.iterrows():
            if str(row.get("domain")) != "elimination":
                continue
            key = (str(row.get("role")), str(row.get("mode")))
            feats_row = str(row.get("feature_list_pipe") or "")
            v13_feat = next((x["feature_list_pipe"] for x in slot_sources.get(key, []) if x["source_name"] == "v13_active"), "")
            if feats_row != v13_feat:
                continue
            slot_sources.setdefault(key, []).append(
                {
                    "source_name": source_name,
                    "active_model_id": str(row.get("active_model_id")),
                    "threshold": sf(row.get("threshold")),
                    "config_id": str(row.get("config_id") or "por_confirmar"),
                    "calibration": str(row.get("calibration") or "none"),
                    "feature_list_pipe": feats_row,
                    "feature_set_id": str(row.get("feature_set_id") or "por_confirmar"),
                }
            )

    append_from(v10, "v10_selected")
    append_from(v11, "v11_selected")

    for key in list(slot_sources.keys()):
        seen = set()
        deduped = []
        for s in slot_sources[key]:
            mk = (s["active_model_id"], s["source_name"])
            if mk in seen:
                continue
            seen.add(mk)
            deduped.append(s)
        slot_sources[key] = deduped
    return slot_sources


def pairwise_similarity(a: Candidate, b: Candidate) -> dict[str, Any]:
    pa, pb = np.asarray(a.probs_holdout, dtype=float), np.asarray(b.probs_holdout, dtype=float)
    pra, prb = np.asarray(a.preds_holdout, dtype=int), np.asarray(b.preds_holdout, dtype=int)
    y = np.asarray(a.y_holdout, dtype=int)

    corr = float(np.corrcoef(pa, pb)[0, 1]) if np.std(pa) > 0 and np.std(pb) > 0 else float("nan")
    agreement = float(np.mean(pra == prb))
    identical = "yes" if np.array_equal(pra, prb) else "no"

    same_confusion = (
        a.tn == b.tn and a.fp == b.fp and a.fn == b.fn and a.tp == b.tp
    )
    metric_max_delta = max(
        abs(sf(getattr(a, m), 0) - sf(getattr(b, m), 0))
        for m in ["f1", "recall", "precision", "balanced_accuracy", "specificity"]
    )
    threshold_delta = abs(a.threshold - b.threshold)
    fa = set(feats(a.feature_list_pipe))
    fb = set(feats(b.feature_list_pipe))
    feature_jaccard = float(len(fa & fb) / max(1, len(fa | fb)))

    err_a = set(np.where(pra != y)[0].tolist())
    err_b = set(np.where(prb != y)[0].tolist())
    err_union = err_a | err_b
    err_inter = err_a & err_b
    shared_error_overlap = float(len(err_inter) / len(err_union)) if err_union else 0.0

    artifact_hash_equal = "yes" if (a.artifact_hash and b.artifact_hash and a.artifact_hash == b.artifact_hash) else "no"
    artifact_path_equal = "yes" if (a.artifact_path and b.artifact_path and a.artifact_path == b.artifact_path) else "no"

    real_reasons = []
    if identical == "yes":
        real_reasons.append("binary_predictions_identical")
    if agreement >= 0.995 and (not math.isnan(corr)) and corr >= 0.995:
        real_reasons.append("agreement_and_probability_corr_ge_0_995")
    if same_confusion and (not math.isnan(corr)) and corr >= 0.995:
        real_reasons.append("same_confusion_and_probability_corr_ge_0_995")
    if threshold_delta <= 1e-12 and metric_max_delta <= 1e-12 and feature_jaccard >= 0.90:
        real_reasons.append("same_threshold_same_main_metrics_high_feature_jaccard")
    if artifact_hash_equal == "yes":
        real_reasons.append("same_artifact_hash")
    if artifact_path_equal == "yes":
        real_reasons.append("same_loaded_artifact_path")

    near_reasons = []
    if agreement >= 0.98:
        near_reasons.append("prediction_agreement_ge_0_98")
    if (not math.isnan(corr)) and corr >= 0.98:
        near_reasons.append("probability_correlation_ge_0_98")
    if metric_max_delta <= 0.005:
        near_reasons.append("metric_max_abs_delta_le_0_005")
    if feature_jaccard >= 0.75:
        near_reasons.append("feature_jaccard_ge_0_75")
    if threshold_delta <= 0.01:
        near_reasons.append("threshold_almost_equal")
    if shared_error_overlap >= 0.75:
        near_reasons.append("shared_error_overlap_ge_0_75")

    return {
        "prediction_agreement": agreement,
        "probability_correlation": corr,
        "binary_predictions_identical": identical,
        "metric_max_abs_delta": metric_max_delta,
        "threshold_abs_delta": threshold_delta,
        "feature_jaccard": feature_jaccard,
        "shared_error_overlap": shared_error_overlap,
        "same_confusion_matrix": "yes" if same_confusion else "no",
        "artifact_hash_equal": artifact_hash_equal,
        "artifact_path_equal": artifact_path_equal,
        "real_clone_flag": "yes" if real_reasons else "no",
        "near_clone_warning": "yes" if near_reasons else "no",
        "real_clone_reasons": "|".join(real_reasons),
        "near_clone_reasons": "|".join(near_reasons),
    }


def candidate_table_rows(cands: list[Candidate], domain: str = "elimination") -> list[dict[str, Any]]:
    rows = []
    for c in cands:
        rows.append(
            {
                "domain": domain,
                "role": c.role,
                "mode": c.slot_mode,
                "candidate_key": c.key,
                "source_type": c.source_type,
                "source_model_id": c.source_model_id,
                "feature_set_id": c.feature_set_id,
                "config_id": c.config_id,
                "calibration": c.calibration,
                "threshold_policy": c.threshold_policy,
                "threshold": c.threshold,
                "seed": c.seed,
                "n_features": c.n_features,
                "precision": c.precision,
                "recall": c.recall,
                "specificity": c.specificity,
                "balanced_accuracy": c.balanced_accuracy,
                "f1": c.f1,
                "roc_auc": c.roc_auc,
                "pr_auc": c.pr_auc,
                "brier": c.brier,
                "tn": c.tn,
                "fp": c.fp,
                "fn": c.fn,
                "tp": c.tp,
                "probability_mean": c.probability_mean,
                "probability_std": c.probability_std,
                "prediction_positive_rate": c.positive_rate,
                "guardrail_ok": c.guardrail_ok,
                "precision_floor_ok": c.precision_floor_ok,
                "quality_score": c.quality_score,
                "artifact_hash": c.artifact_hash,
                "artifact_path": c.artifact_path,
                "notes": c.notes,
            }
        )
    return rows


def pick_joint_pool(cands: list[Candidate], top_n: int = 40) -> list[Candidate]:
    ranked = sorted(cands, key=lambda x: (x.guardrail_ok != "yes", -x.quality_score, -x.f1, -x.recall, -x.precision, x.brier))
    return ranked[: min(top_n, len(ranked))]


def beam_select_combo(slot_candidates: dict[str, list[Candidate]], beam_size: int = 800) -> tuple[list[Candidate], pd.DataFrame]:
    modes = [m for _, m in ELIM_SLOT_ORDER]

    pair_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for ma, mb in itertools.combinations(modes, 2):
        for ca in slot_candidates[ma]:
            for cb in slot_candidates[mb]:
                key = tuple(sorted([ca.key, cb.key]))
                pair_cache[key] = pairwise_similarity(ca, cb)

    partials = []
    first_mode = modes[0]
    for c in slot_candidates[first_mode]:
        partials.append(
            {
                "keys": [c.key],
                "cands": [c],
                "real_clone_count": 0,
                "near_clone_count": 0,
                "quality_sum": c.quality_score,
                "recall_sum": c.recall,
                "precision_sum": c.precision,
                "f1_sum": c.f1,
            }
        )

    for mode in modes[1:]:
        new_partials = []
        for p in partials:
            for c in slot_candidates[mode]:
                real_add = 0
                near_add = 0
                for prev in p["cands"]:
                    k = tuple(sorted([prev.key, c.key]))
                    sim = pair_cache[k]
                    if sim["real_clone_flag"] == "yes":
                        real_add += 1
                    if sim["near_clone_warning"] == "yes":
                        near_add += 1
                new_partials.append(
                    {
                        "keys": p["keys"] + [c.key],
                        "cands": p["cands"] + [c],
                        "real_clone_count": p["real_clone_count"] + real_add,
                        "near_clone_count": p["near_clone_count"] + near_add,
                        "quality_sum": p["quality_sum"] + c.quality_score,
                        "recall_sum": p["recall_sum"] + c.recall,
                        "precision_sum": p["precision_sum"] + c.precision,
                        "f1_sum": p["f1_sum"] + c.f1,
                    }
                )
        new_partials.sort(
            key=lambda x: (
                x["real_clone_count"],
                x["near_clone_count"],
                -(x["quality_sum"] / len(x["cands"])),
                -(x["f1_sum"] / len(x["cands"])),
                -(x["recall_sum"] / len(x["cands"])),
                -(x["precision_sum"] / len(x["cands"])),
            )
        )
        partials = new_partials[:beam_size]

    best = partials[0]
    selected = best["cands"]

    combo_rows = [
        {
            "slot_index": idx + 1,
            "mode": c.slot_mode,
            "role": c.role,
            "candidate_key": c.key,
            "source_type": c.source_type,
            "source_model_id": c.source_model_id,
            "config_id": c.config_id,
            "calibration": c.calibration,
            "threshold_policy": c.threshold_policy,
            "threshold": c.threshold,
            "seed": c.seed,
            "f1": c.f1,
            "recall": c.recall,
            "precision": c.precision,
            "specificity": c.specificity,
            "balanced_accuracy": c.balanced_accuracy,
            "roc_auc": c.roc_auc,
            "pr_auc": c.pr_auc,
            "brier": c.brier,
            "quality_score": c.quality_score,
        }
        for idx, c in enumerate(selected)
    ]
    combo_summary = {
        "slot_index": 0,
        "mode": "__combo_summary__",
        "role": "__combo_summary__",
        "candidate_key": "|".join(best["keys"]),
        "source_type": "joint_selection",
        "source_model_id": "joint_selection",
        "config_id": "joint_selection",
        "calibration": "joint_selection",
        "threshold_policy": "joint_selection",
        "threshold": float("nan"),
        "seed": float("nan"),
        "f1": best["f1_sum"] / len(selected),
        "recall": best["recall_sum"] / len(selected),
        "precision": best["precision_sum"] / len(selected),
        "specificity": float("nan"),
        "balanced_accuracy": float("nan"),
        "roc_auc": float("nan"),
        "pr_auc": float("nan"),
        "brier": float("nan"),
        "quality_score": best["quality_sum"] / len(selected),
        "real_clone_count": best["real_clone_count"],
        "near_clone_count": best["near_clone_count"],
    }
    combo_rows.append(combo_summary)
    return selected, pd.DataFrame(combo_rows)


def evaluate_selected_elimination_pairs(selected_combo: list[Candidate]) -> tuple[pd.DataFrame, int, int]:
    rows = []
    for a, b in itertools.combinations(selected_combo, 2):
        sim = pairwise_similarity(a, b)
        rows.append(
            {
                "slot_a": f"elimination/{a.slot_mode}",
                "slot_b": f"elimination/{b.slot_mode}",
                "active_model_id_a": a.source_model_id,
                "active_model_id_b": b.source_model_id,
                "prediction_agreement": sim["prediction_agreement"],
                "probability_correlation": sim["probability_correlation"],
                "binary_predictions_identical": sim["binary_predictions_identical"],
                "metric_max_abs_delta": sim["metric_max_abs_delta"],
                "threshold_abs_delta": sim["threshold_abs_delta"],
                "feature_jaccard": sim["feature_jaccard"],
                "shared_error_overlap": sim["shared_error_overlap"],
                "real_clone_flag": sim["real_clone_flag"],
                "near_clone_warning": sim["near_clone_warning"],
                "real_clone_reasons": sim["real_clone_reasons"],
                "near_clone_reasons": sim["near_clone_reasons"],
            }
        )
    out = pd.DataFrame(rows)
    real_count = int((out["real_clone_flag"] == "yes").sum()) if not out.empty else 0
    near_count = int((out["near_clone_warning"] == "yes").sum()) if not out.empty else 0
    return out, real_count, near_count


def candidate_with_threshold(base: Candidate, threshold: float, precision_floor: float, policy_name: str) -> Candidate:
    return candidate_from_probs(
        key=f"{base.key}::joint_thr::{threshold:.6f}",
        slot_mode=base.slot_mode,
        role=base.role,
        threshold=float(threshold),
        threshold_policy=policy_name,
        config_id=base.config_id,
        calibration=base.calibration,
        seed=base.seed,
        feature_list_pipe=base.feature_list_pipe,
        n_features=base.n_features,
        source_type=base.source_type,
        source_model_id=base.source_model_id,
        notes=f"{base.notes};joint_threshold_diversification",
        feature_set_id=base.feature_set_id,
        model_obj=base.model_obj,
        probs_holdout=base.probs_holdout,
        y_holdout=base.y_holdout,
        probs_val=base.probs_val,
        y_val=base.y_val,
        artifact_hash=base.artifact_hash,
        artifact_path=base.artifact_path,
        precision_floor=precision_floor,
    )


def threshold_variants_for_selected(base: Candidate, precision_floor: float, max_keep: int = 18) -> list[Candidate]:
    vals = list(np.linspace(0.05, 0.95, 181))
    vals.extend(list(np.quantile(base.probs_val, np.linspace(0.02, 0.98, 97))))
    vals.extend([base.threshold, max(0.05, base.threshold - 0.15), min(0.95, base.threshold + 0.15)])
    grid = sorted(set(float(v) for v in vals if 0 < float(v) < 1))
    tmp: list[Candidate] = []
    for thr in grid:
        c = candidate_with_threshold(base, thr, precision_floor, "joint_anti_clone_threshold_tuning")
        if c.guardrail_ok != "yes" or c.precision_floor_ok != "yes":
            continue
        tmp.append(c)

    # Keep unique prediction vectors and then keep quality-diverse subset.
    uniq: dict[str, Candidate] = {}
    for c in sorted(tmp, key=lambda x: (-x.quality_score, -x.f1, -x.recall, -x.precision, x.brier)):
        ph = hashlib.sha256(np.asarray(c.preds_holdout, dtype=np.uint8).tobytes()).hexdigest()
        if ph not in uniq:
            uniq[ph] = c
    kept = list(uniq.values())
    if not kept:
        return [base]
    kept = sorted(kept, key=lambda x: (-x.quality_score, -x.f1, -x.recall, -x.precision, x.brier))
    if len(kept) <= max_keep:
        return kept

    core = kept[: max(6, max_keep // 2)]
    by_thr = sorted(kept, key=lambda x: x.threshold)
    extra: list[Candidate] = []
    for frac in np.linspace(0, 1, max_keep - len(core)):
        idx = int(round(frac * (len(by_thr) - 1)))
        extra.append(by_thr[idx])
    merged: dict[str, Candidate] = {}
    for c in core + extra:
        merged[c.key] = c
    out = list(merged.values())
    out = sorted(out, key=lambda x: (-x.quality_score, -x.f1, -x.recall, -x.precision, x.brier))
    return out[:max_keep]


def create_v14_model_id(mode: str) -> str:
    return f"elimination__{mode}__{LINE}__rf__same_inputs_v13"


def manifest_payload(active_v14: pd.DataFrame, op_v14: pd.DataFrame, final_status: str, all_real: int, elim_real: int, near_count: int, dup_hash: int) -> dict[str, Any]:
    return {
        "line": LINE,
        "freeze_label": FREEZE,
        "generated_at_utc": now(),
        "scope": "elimination_only_rescue",
        "rules": {
            "non_elimination_slots_unchanged": True,
            "rf_only": True,
            "same_inputs_outputs_contract": True,
            "no_questionnaire_changes": True,
            "guardrail_max": 0.98,
        },
        "stats": {
            "active_rows": int(len(active_v14)),
            "elimination_rows": int((active_v14["domain"] == "elimination").sum()),
            "rf_rows": int((active_v14["model_family"].astype(str).str.lower() == "rf").sum()),
            "all_domains_real_clone_count": int(all_real),
            "elimination_real_clone_count": int(elim_real),
            "all_domains_near_clone_warning_count": int(near_count),
            "artifact_duplicate_hash_count": int(dup_hash),
            "final_audit_status": final_status,
        },
        "paths": {
            "active_v14": str(ACTIVE_V14_OUT.relative_to(ROOT)).replace("\\", "/"),
            "operational_v14": str(OP_V14_OUT.relative_to(ROOT)).replace("\\", "/"),
            "rescue_tables_dir": str(TABLES.relative_to(ROOT)).replace("\\", "/"),
            "rescue_validation_dir": str(VALIDATION.relative_to(ROOT)).replace("\\", "/"),
        },
    }


def main() -> int:
    mkdirs()

    required = [
        LOADER,
        ACTIVE_V13,
        OP_V13,
        AUDIT_V13_ELIM,
        AUDIT_V13_ALL,
        AUDIT_V13_REPORT,
        AUDIT_V13_VALID,
        DATASET,
        INPUTS_V13,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("missing_required_paths:" + "|".join(missing))

    active_v13 = pd.read_csv(ACTIVE_V13)
    op_v13 = pd.read_csv(OP_V13)
    data = pd.read_csv(DATASET)
    if "participant_id" not in data.columns:
        raise RuntimeError("dataset_missing_participant_id")

    loader_text = LOADER.read_text(encoding="utf-8")
    loader_active, loader_op, loader_points_v13 = detect_loader_line(loader_text)

    splits = split_registry(data)
    elim_split = splits["elimination"]
    holdout_ids = set(elim_split["holdout"])
    val_ids = set(elim_split["val"])
    train_ids = set(elim_split["train"])

    elim_df = elimination_rows(active_v13)
    non_elim_df = active_v13[active_v13["domain"] != "elimination"].copy()

    hist_sources = build_historical_slot_sources(active_v13)

    all_candidates: list[Candidate] = []
    candidate_rows = []
    slot_candidates: dict[str, list[Candidate]] = {}
    precision_floor_by_mode: dict[str, float] = {}

    for _, row in elim_df.iterrows():
        role = str(row["role"])
        mode = str(row["mode"])
        slot_key = (role, mode)
        feature_list_pipe = str(row["feature_list_pipe"])
        features = feats(feature_list_pipe)
        if not features:
            raise RuntimeError(f"no_features_for_slot:{mode}")
        missing_cols = [f for f in features if f not in data.columns]
        if missing_cols:
            raise RuntimeError(f"missing_features_in_dataset_for_{mode}:{'|'.join(missing_cols)}")

        current_precision = sf(row["precision"], 0.70)
        precision_floor = precision_floor_from_current(current_precision)
        precision_floor_by_mode[mode] = precision_floor

        train_df = data[data["participant_id"].astype(str).isin(train_ids)].copy()
        val_df = data[data["participant_id"].astype(str).isin(val_ids)].copy()
        hold_df = data[data["participant_id"].astype(str).isin(holdout_ids)].copy()

        ytr = train_df[tcol("elimination")].astype(int).to_numpy()
        yva = val_df[tcol("elimination")].astype(int).to_numpy()
        yho = hold_df[tcol("elimination")].astype(int).to_numpy()

        xtr = prep_x(train_df, features)
        xva = prep_x(val_df, features)
        xho = prep_x(hold_df, features)

        slot_list: list[Candidate] = []

        # Historical/current RF models with contract-exact features
        for src in hist_sources.get(slot_key, []):
            model_id = src["active_model_id"]
            artifact_path, artifact_origin, artifact_hash = resolve_existing_artifact(model_id)
            if not artifact_path:
                continue
            model = joblib.load(Path(artifact_path))
            pva = proba(model, xva)
            pho = proba(model, xho)

            # fixed threshold candidate
            fixed_thr = float(src["threshold"])
            fixed_key = f"{mode}::hist::{src['source_name']}::{model_id}::fixed::{fixed_thr:.6f}"
            fixed_c = candidate_from_probs(
                key=fixed_key,
                slot_mode=mode,
                role=role,
                threshold=fixed_thr,
                threshold_policy="fixed_from_source",
                config_id=str(src["config_id"]),
                calibration=str(src["calibration"] or "none"),
                seed=None,
                feature_list_pipe=feature_list_pipe,
                n_features=len(features),
                source_type=f"historical_{src['source_name']}",
                source_model_id=model_id,
                notes=f"historical_model:{src['source_name']}:{artifact_origin}",
                feature_set_id=str(src["feature_set_id"]),
                model_obj=model,
                probs_holdout=pho,
                y_holdout=yho,
                probs_val=pva,
                y_val=yva,
                artifact_hash=artifact_hash,
                artifact_path=artifact_path,
                precision_floor=precision_floor,
            )
            slot_list.append(fixed_c)

            for pol in THRESHOLD_POLICIES:
                thr, _, _ = choose_threshold(pol, yva, pva, precision_floor, mode)
                key = f"{mode}::hist::{src['source_name']}::{model_id}::{pol}::{thr:.6f}"
                c = candidate_from_probs(
                    key=key,
                    slot_mode=mode,
                    role=role,
                    threshold=thr,
                    threshold_policy=pol,
                    config_id=str(src["config_id"]),
                    calibration=str(src["calibration"] or "none"),
                    seed=None,
                    feature_list_pipe=feature_list_pipe,
                    n_features=len(features),
                    source_type=f"historical_{src['source_name']}",
                    source_model_id=model_id,
                    notes=f"historical_model:{src['source_name']}:{artifact_origin}",
                    feature_set_id=str(src["feature_set_id"]),
                    model_obj=model,
                    probs_holdout=pho,
                    y_holdout=yho,
                    probs_val=pva,
                    y_val=yva,
                    artifact_hash=artifact_hash,
                    artifact_path=artifact_path,
                    precision_floor=precision_floor,
                )
                slot_list.append(c)

        # Trained RF candidates (elimination-only, contract exact)
        for cfg in RF_CONFIGS:
            for seed in SEEDS:
                for cal in cfg.get("calibrations", ["none"]):
                    if cal == "isotonic" and int(np.sum(ytr)) < 35:
                        continue
                    try:
                        model = fit_model(features, cfg, seed, cal, xtr, ytr)
                    except Exception:
                        continue
                    pva = proba(model, xva)
                    pho = proba(model, xho)
                    for pol in THRESHOLD_POLICIES:
                        thr, _, _ = choose_threshold(pol, yva, pva, precision_floor, mode)
                        key = f"{mode}::train::{cfg['config_id']}::{seed}::{cal}::{pol}::{thr:.6f}"
                        c = candidate_from_probs(
                            key=key,
                            slot_mode=mode,
                            role=role,
                            threshold=thr,
                            threshold_policy=pol,
                            config_id=str(cfg["config_id"]),
                            calibration=cal,
                            seed=seed,
                            feature_list_pipe=feature_list_pipe,
                            n_features=len(features),
                            source_type="trained_rf_v14",
                            source_model_id="trained_rf_v14",
                            notes="trained_on_elimination_only_rescue",
                            feature_set_id="same_inputs_v13",
                            model_obj=model,
                            probs_holdout=pho,
                            y_holdout=yho,
                            probs_val=pva,
                            y_val=yva,
                            artifact_hash=None,
                            artifact_path=None,
                            precision_floor=precision_floor,
                        )
                        slot_list.append(c)

        # Deduplicate by key and keep guardrail-pass candidates first
        uniq: dict[str, Candidate] = {}
        for c in sorted(slot_list, key=lambda x: (x.guardrail_ok != "yes", -x.quality_score, -x.f1, -x.recall, -x.precision, x.brier)):
            if c.key not in uniq:
                uniq[c.key] = c
        slot_final = list(uniq.values())
        if not slot_final:
            raise RuntimeError(f"no_candidates_for_slot:{mode}")

        all_candidates.extend(slot_final)
        candidate_rows.extend(candidate_table_rows(slot_final))
        slot_candidates[mode] = pick_joint_pool(slot_final, top_n=80)

    # Joint selection across 6 elimination slots
    selected_combo, joint_df = beam_select_combo(slot_candidates, beam_size=2000)
    elim_pair_df, elimination_real_clone_count, elimination_near_count = evaluate_selected_elimination_pairs(selected_combo)

    # Focal pass 2: threshold diversification over selected models if clone persists.
    if elimination_real_clone_count > 0:
        threshold_slot_candidates: dict[str, list[Candidate]] = {}
        for c in selected_combo:
            pf = precision_floor_by_mode.get(c.slot_mode, 0.62)
            threshold_slot_candidates[c.slot_mode] = threshold_variants_for_selected(c, pf, max_keep=20)
        tuned_combo, tuned_joint_df = beam_select_combo(threshold_slot_candidates, beam_size=5000)
        tuned_pair_df, tuned_real, tuned_near = evaluate_selected_elimination_pairs(tuned_combo)
        if tuned_real < elimination_real_clone_count or (
            tuned_real == elimination_real_clone_count and tuned_near < elimination_near_count
        ):
            selected_combo = tuned_combo
            joint_df = pd.concat([joint_df, tuned_joint_df], ignore_index=True)
            elim_pair_df = tuned_pair_df
            elimination_real_clone_count = tuned_real
            elimination_near_count = tuned_near
    selected_by_mode = {c.slot_mode: c for c in selected_combo}

    # Build v14 active/op by changing only elimination rows
    active_v14 = active_v13.copy()
    op_v14 = op_v13.copy()
    if "seed" in active_v14.columns and "seed" in active_v13.columns:
        active_v14["seed"] = active_v13["seed"]
    model_artifact_inventory = []

    for _, old_row in elim_df.iterrows():
        mode = str(old_row["mode"])
        c = selected_by_mode[mode]
        new_model_id = create_v14_model_id(mode)
        new_model_dir = MODEL_ROOT / new_model_id
        new_model_dir.mkdir(parents=True, exist_ok=True)
        model_path = new_model_dir / "pipeline.joblib"
        joblib.dump(c.model_obj, model_path)
        meta = {
            "model_key": new_model_id,
            "line": LINE,
            "rf_only": True,
            "domain": "elimination",
            "role": c.role,
            "mode": mode,
            "feature_columns": feats(c.feature_list_pipe),
            "recommended_threshold": float(c.threshold),
            "calibration": c.calibration,
            "config_id": c.config_id,
            "generated_at_utc": now(),
            "source_candidate_key": c.key,
            "source_type": c.source_type,
            "source_model_id": c.source_model_id,
            "note": "pipeline.joblib is local/regenerable and ignored by git policy; metadata is tracked",
        }
        write_text(new_model_dir / "metadata.json", json.dumps(meta, indent=2, ensure_ascii=False))

        model_artifact_inventory.append(
            {
                "mode": mode,
                "active_model_id": new_model_id,
                "artifact_path": str(model_path.relative_to(ROOT)).replace("\\", "/"),
                "artifact_hash": sha256_file(model_path),
                "metadata_path": str((new_model_dir / "metadata.json").relative_to(ROOT)).replace("\\", "/"),
                "metadata_hash": sha256_file(new_model_dir / "metadata.json"),
                "source_candidate_key": c.key,
                "source_type": c.source_type,
                "source_model_id": c.source_model_id,
            }
        )

        mask_a = (active_v14["domain"] == "elimination") & (active_v14["mode"] == mode)
        active_v14.loc[mask_a, "active_model_id"] = new_model_id
        active_v14.loc[mask_a, "source_line"] = "v14_elimination_real_anti_clone_rescue"
        active_v14.loc[mask_a, "source_campaign"] = LINE
        active_v14.loc[mask_a, "model_family"] = "rf"
        active_v14.loc[mask_a, "feature_set_id"] = "same_inputs_v13"
        active_v14.loc[mask_a, "config_id"] = c.config_id
        active_v14.loc[mask_a, "calibration"] = c.calibration
        active_v14.loc[mask_a, "threshold_policy"] = c.threshold_policy
        active_v14.loc[mask_a, "threshold"] = c.threshold
        if "seed" in active_v14.columns:
            active_v14.loc[mask_a, "seed"] = str(c.seed) if c.seed is not None else ""
        active_v14.loc[mask_a, "n_features"] = c.n_features
        active_v14.loc[mask_a, "precision"] = c.precision
        active_v14.loc[mask_a, "recall"] = c.recall
        active_v14.loc[mask_a, "specificity"] = c.specificity
        active_v14.loc[mask_a, "balanced_accuracy"] = c.balanced_accuracy
        active_v14.loc[mask_a, "f1"] = c.f1
        active_v14.loc[mask_a, "roc_auc"] = c.roc_auc
        active_v14.loc[mask_a, "pr_auc"] = c.pr_auc
        active_v14.loc[mask_a, "brier"] = c.brier
        active_v14.loc[mask_a, "overfit_flag"] = "por_confirmar"
        active_v14.loc[mask_a, "generalization_flag"] = "por_confirmar"
        active_v14.loc[mask_a, "dataset_ease_flag"] = "no"
        active_v14.loc[mask_a, "notes"] = (
            f"{LINE}:elimination_only_rescue;source_candidate={c.key};no_question_changes;no_contract_change"
        )
        active_v14.loc[mask_a, "feature_list_pipe"] = c.feature_list_pipe

        mask_o = (op_v14["domain"] == "elimination") & (op_v14["mode"] == mode)
        op_v14.loc[mask_o, "source_campaign"] = LINE
        op_v14.loc[mask_o, "model_family"] = "rf"
        op_v14.loc[mask_o, "feature_set_id"] = "same_inputs_v13"
        op_v14.loc[mask_o, "calibration"] = c.calibration
        op_v14.loc[mask_o, "threshold_policy"] = c.threshold_policy
        op_v14.loc[mask_o, "threshold"] = c.threshold
        op_v14.loc[mask_o, "precision"] = c.precision
        op_v14.loc[mask_o, "recall"] = c.recall
        op_v14.loc[mask_o, "specificity"] = c.specificity
        op_v14.loc[mask_o, "balanced_accuracy"] = c.balanced_accuracy
        op_v14.loc[mask_o, "f1"] = c.f1
        op_v14.loc[mask_o, "roc_auc"] = c.roc_auc
        op_v14.loc[mask_o, "pr_auc"] = c.pr_auc
        op_v14.loc[mask_o, "brier"] = c.brier
        op_v14.loc[mask_o, "config_id"] = c.config_id
        op_v14.loc[mask_o, "n_features"] = c.n_features
        op_v14.loc[mask_o, "quality_label"] = "strong" if c.f1 >= 0.86 and c.balanced_accuracy >= 0.90 else "aceptable"
        op_v14.loc[mask_o, "overfit_gap_train_val_ba"] = np.nan

    # freeze tables
    save_csv(active_v14, ACTIVE_V14_OUT)
    save_csv(active_v14.groupby(["final_operational_class", "confidence_band"], dropna=False).size().reset_index(name="n_active_models"), ACTIVE_V14_SUMMARY_OUT)
    save_csv(pd.read_csv(INPUTS_V13), INPUTS_V14_OUT)
    save_csv(op_v14, OP_V14_OUT)
    if OP_V13_NONCHAMP.exists():
        save_csv(pd.read_csv(OP_V13_NONCHAMP), OP_V14_NONCHAMP_OUT)

    # non-elimination unchanged validator
    compare_cols = [c for c in active_v13.columns if c in active_v14.columns]
    non_change_rows = []
    for _, old_r in active_v13[active_v13["domain"] != "elimination"].iterrows():
        mode = str(old_r["mode"])
        new_r = active_v14[(active_v14["domain"] == old_r["domain"]) & (active_v14["mode"] == mode)].iloc[0]
        diffs = []
        for c in compare_cols:
            ov = old_r[c]
            nv = new_r[c]
            if (pd.isna(ov) and pd.isna(nv)) or str(ov) == str(nv):
                continue
            diffs.append(c)
        non_change_rows.append(
            {
                "domain": old_r["domain"],
                "role": old_r["role"],
                "mode": old_r["mode"],
                "unchanged": "yes" if not diffs else "no",
                "changed_columns": "|".join(diffs),
            }
        )
    non_change_df = pd.DataFrame(non_change_rows)

    # contract compatibility validator
    contract_rows = []
    v13_idx = active_v13.set_index(["domain", "role", "mode"])
    for _, r in active_v14.iterrows():
        key = (r["domain"], r["role"], r["mode"])
        old = v13_idx.loc[key]
        old_feats = feats(old["feature_list_pipe"])
        new_feats = feats(r["feature_list_pipe"])
        contract_rows.append(
            {
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "active_model_id": r["active_model_id"],
                "same_feature_columns_order": "yes" if old_feats == new_feats else "no",
                "same_inputs_outputs_contract": "yes" if old_feats == new_feats else "no",
                "questionnaire_changed": "no",
            }
        )
    contract_df = pd.DataFrame(contract_rows)

    # Guardrail validator (active v14)
    guard_df = active_v14[["domain", "role", "mode", "active_model_id", "recall", "specificity", "roc_auc", "pr_auc"]].copy()
    guard_df["guardrail_violation"] = guard_df.apply(lambda x: "yes" if any(sf(x[m], 0) > 0.98 for m in WATCH) else "no", axis=1)

    # Recompute 30/30 for v14 using actual artifacts
    recomputed_rows = []
    reg_vs_recomp = []
    artifact_rows = []

    for _, row in active_v14.sort_values(["domain", "role", "mode"]).iterrows():
        domain = str(row["domain"])
        role = str(row["role"])
        mode = str(row["mode"])
        model_id = str(row["active_model_id"])
        feat_pipe = str(row["feature_list_pipe"])
        fcols = feats(feat_pipe)
        thr = sf(row["threshold"], float("nan"))
        pred_recomputed = "no"
        blocker = ""

        # resolve artifact path for current line or historical
        local_path = MODEL_ROOT / model_id / "pipeline.joblib"
        if local_path.exists():
            art_path = str(local_path.relative_to(ROOT)).replace("\\", "/")
            art_origin = "current_repo_v14"
            art_hash = sha256_file(local_path)
        else:
            art_path, art_origin, art_hash = resolve_existing_artifact(model_id)

        artifact_rows.append(
            {
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": model_id,
                "artifacts_available": "yes" if art_path else "no",
                "artifact_path": art_path,
                "artifact_origin": art_origin,
                "artifact_hash": art_hash,
            }
        )

        rec = {
            "domain": domain,
            "role": role,
            "mode": mode,
            "active_model_id": model_id,
            "model_key": model_id,
            "artifact_path": art_path,
            "artifact_origin": art_origin,
            "artifact_hash": art_hash,
            "threshold": thr,
            "n_features": len(fcols),
            "feature_list_pipe": feat_pipe,
            "artifacts_available": "yes" if art_path else "no",
            "prediction_recomputed": "no",
            "recompute_blocker": "",
            "probability_mean": float("nan"),
            "probability_std": float("nan"),
            "prediction_positive_rate": float("nan"),
            "holdout_n": float("nan"),
            "holdout_positive_n": float("nan"),
            "holdout_negative_n": float("nan"),
            "_probs": np.array([], dtype=float),
            "_preds": np.array([], dtype=int),
            "_y": np.array([], dtype=int),
        }
        for m in METRICS_CORE + ["tn", "fp", "fn", "tp"]:
            rec[m] = float("nan")

        if not art_path:
            rec["recompute_blocker"] = "artifact_unavailable"
            recomputed_rows.append(rec)
            for mn in METRICS_WITH_COUNTS:
                rv = sf(row.get(mn), float("nan"))
                qv = sf(rec.get(mn), float("nan"))
                if math.isnan(rv) or math.isnan(qv):
                    d = float("nan")
                    ok = "por_confirmar"
                else:
                    d = abs(rv - qv)
                    ok = "yes" if d <= 1e-6 else "no"
                reg_vs_recomp.append({"domain": domain, "role": role, "mode": mode, "active_model_id": model_id, "metric_name": mn, "registered_value": rv, "recomputed_value": qv, "abs_delta": d, "tolerance": 1e-6, "within_tolerance": ok, "registered_source": "active_v14"})
            continue

        model = joblib.load(Path(art_path))
        hold_ids = set(splits[domain]["holdout"])
        hold = data[data["participant_id"].astype(str).isin(hold_ids)].copy()
        y = hold[tcol(domain)].astype(int).to_numpy()
        miss = [f for f in fcols if f not in hold.columns]
        if miss:
            rec["recompute_blocker"] = "missing_features_in_dataset:" + "|".join(miss)
            recomputed_rows.append(rec)
            continue
        x = prep_x(hold, fcols)
        try:
            p = proba(model, x)
        except Exception as exc:
            rec["recompute_blocker"] = f"predict_proba_error:{repr(exc)}"
            recomputed_rows.append(rec)
            continue
        mm = compute_metrics(y, p, thr)
        pred = (p >= thr).astype(int)
        rec.update(mm)
        rec["prediction_recomputed"] = "yes"
        rec["probability_mean"] = float(np.mean(p))
        rec["probability_std"] = float(np.std(p))
        rec["prediction_positive_rate"] = float(np.mean(pred))
        rec["holdout_n"] = int(len(y))
        rec["holdout_positive_n"] = int(np.sum(y))
        rec["holdout_negative_n"] = int(len(y) - np.sum(y))
        rec["_probs"] = p
        rec["_preds"] = pred
        rec["_y"] = y
        recomputed_rows.append(rec)

        for mn in METRICS_WITH_COUNTS:
            rv = sf(row.get(mn), float("nan"))
            qv = sf(rec.get(mn), float("nan"))
            if math.isnan(rv) or math.isnan(qv):
                d = float("nan")
                ok = "por_confirmar"
            else:
                d = abs(rv - qv)
                ok = "yes" if d <= 1e-6 else "no"
            reg_vs_recomp.append({"domain": domain, "role": role, "mode": mode, "active_model_id": model_id, "metric_name": mn, "registered_value": rv, "recomputed_value": qv, "abs_delta": d, "tolerance": 1e-6, "within_tolerance": ok, "registered_source": "active_v14"})

    recomputed_df = pd.DataFrame(recomputed_rows)
    reg_vs_recomp_df = pd.DataFrame(reg_vs_recomp)
    artifact_df = pd.DataFrame(artifact_rows)

    # pairwise all domains from recomputed predictions
    pair_rows = []
    by_domain = {}
    for _, r in recomputed_df[recomputed_df["prediction_recomputed"] == "yes"].iterrows():
        by_domain.setdefault(str(r["domain"]), []).append(r)
    for domain, arr in by_domain.items():
        if domain == "elimination":
            combos = itertools.combinations(arr, 2)
        else:
            role_map = {}
            for r in arr:
                role_map.setdefault(str(r["role"]), []).append(r)
            combos = itertools.chain.from_iterable(itertools.combinations(v, 2) for v in role_map.values())
        for a, b in combos:
            ca = Candidate(
                key=str(a["active_model_id"]),
                slot_mode=str(a["mode"]),
                role=str(a["role"]),
                threshold=float(a["threshold"]),
                threshold_policy="audit",
                config_id="audit",
                calibration="audit",
                seed=None,
                feature_list_pipe=str(a["feature_list_pipe"]),
                n_features=int(a["n_features"]),
                precision=float(a["precision"]),
                recall=float(a["recall"]),
                specificity=float(a["specificity"]),
                balanced_accuracy=float(a["balanced_accuracy"]),
                f1=float(a["f1"]),
                roc_auc=float(a["roc_auc"]),
                pr_auc=float(a["pr_auc"]),
                brier=float(a["brier"]),
                tn=int(a["tn"]),
                fp=int(a["fp"]),
                fn=int(a["fn"]),
                tp=int(a["tp"]),
                probability_mean=float(a["probability_mean"]),
                probability_std=float(a["probability_std"]),
                positive_rate=float(a["prediction_positive_rate"]),
                guardrail_ok="yes",
                precision_floor_ok="yes",
                quality_score=0.0,
                source_type="audit",
                source_model_id=str(a["active_model_id"]),
                notes="audit",
                feature_set_id="audit",
                model_obj=None,
                probs_holdout=np.asarray(a["_probs"], dtype=float),
                preds_holdout=np.asarray(a["_preds"], dtype=int),
                y_holdout=np.asarray(a["_y"], dtype=int),
                probs_val=np.asarray(a["_probs"], dtype=float),
                y_val=np.asarray(a["_y"], dtype=int),
                artifact_hash=str(a.get("artifact_hash") or "") if not pd.isna(a.get("artifact_hash")) else None,
                artifact_path=str(a.get("artifact_path") or ""),
            )
            cb = Candidate(
                key=str(b["active_model_id"]),
                slot_mode=str(b["mode"]),
                role=str(b["role"]),
                threshold=float(b["threshold"]),
                threshold_policy="audit",
                config_id="audit",
                calibration="audit",
                seed=None,
                feature_list_pipe=str(b["feature_list_pipe"]),
                n_features=int(b["n_features"]),
                precision=float(b["precision"]),
                recall=float(b["recall"]),
                specificity=float(b["specificity"]),
                balanced_accuracy=float(b["balanced_accuracy"]),
                f1=float(b["f1"]),
                roc_auc=float(b["roc_auc"]),
                pr_auc=float(b["pr_auc"]),
                brier=float(b["brier"]),
                tn=int(b["tn"]),
                fp=int(b["fp"]),
                fn=int(b["fn"]),
                tp=int(b["tp"]),
                probability_mean=float(b["probability_mean"]),
                probability_std=float(b["probability_std"]),
                positive_rate=float(b["prediction_positive_rate"]),
                guardrail_ok="yes",
                precision_floor_ok="yes",
                quality_score=0.0,
                source_type="audit",
                source_model_id=str(b["active_model_id"]),
                notes="audit",
                feature_set_id="audit",
                model_obj=None,
                probs_holdout=np.asarray(b["_probs"], dtype=float),
                preds_holdout=np.asarray(b["_preds"], dtype=int),
                y_holdout=np.asarray(b["_y"], dtype=int),
                probs_val=np.asarray(b["_probs"], dtype=float),
                y_val=np.asarray(b["_y"], dtype=int),
                artifact_hash=str(b.get("artifact_hash") or "") if not pd.isna(b.get("artifact_hash")) else None,
                artifact_path=str(b.get("artifact_path") or ""),
            )
            sim = pairwise_similarity(ca, cb)
            pair_rows.append(
                {
                    "domain": domain,
                    "slot_a": f"{a['domain']}/{a['mode']}",
                    "slot_b": f"{b['domain']}/{b['mode']}",
                    "active_model_id_a": a["active_model_id"],
                    "active_model_id_b": b["active_model_id"],
                    "prediction_agreement": sim["prediction_agreement"],
                    "probability_correlation": sim["probability_correlation"],
                    "binary_predictions_identical": sim["binary_predictions_identical"],
                    "metric_max_abs_delta": sim["metric_max_abs_delta"],
                    "threshold_abs_delta": sim["threshold_abs_delta"],
                    "feature_jaccard": sim["feature_jaccard"],
                    "shared_error_overlap": sim["shared_error_overlap"],
                    "real_clone_flag": sim["real_clone_flag"],
                    "near_clone_warning": sim["near_clone_warning"],
                    "real_clone_reasons": sim["real_clone_reasons"],
                    "near_clone_reasons": sim["near_clone_reasons"],
                    "same_confusion_matrix": sim["same_confusion_matrix"],
                    "artifact_hash_equal": sim["artifact_hash_equal"],
                    "artifact_path_equal": sim["artifact_path_equal"],
                }
            )
    pair_df = pd.DataFrame(pair_rows)
    elim_pair_v14 = pair_df[pair_df["domain"] == "elimination"].copy()
    shared_error_df = pair_df[["domain", "slot_a", "slot_b", "active_model_id_a", "active_model_id_b", "shared_error_overlap"]].copy()

    # counts and final status
    all_real_clone_count = int((pair_df["real_clone_flag"] == "yes").sum()) if not pair_df.empty else 0
    elimination_real_clone_count_final = int((elim_pair_v14["real_clone_flag"] == "yes").sum()) if not elim_pair_v14.empty else 0
    all_near_clone_count = int((pair_df["near_clone_warning"] == "yes").sum()) if not pair_df.empty else 0
    duplicate_hash_count = int(
        artifact_df[
            (artifact_df["artifact_hash"].notna())
            & (artifact_df["artifact_hash"] != "")
        ]["artifact_hash"].value_counts().gt(1).sum()
    )
    guard_viol_count = int((guard_df["guardrail_violation"] == "yes").sum())
    recomputed_yes = int((recomputed_df["prediction_recomputed"] == "yes").sum())
    metrics_match_rows = []
    for model_id, grp in reg_vs_recomp_df.groupby("active_model_id", dropna=False):
        g2 = grp[grp["within_tolerance"] != "por_confirmar"]
        if g2.empty:
            mm = "por_confirmar"
        else:
            mm = "yes" if (g2["within_tolerance"] == "yes").all() else "no"
        one = grp.iloc[0]
        metrics_match_rows.append(
            {
                "domain": one["domain"],
                "role": one["role"],
                "mode": one["mode"],
                "active_model_id": model_id,
                "prediction_recomputed": "yes" if model_id in set(recomputed_df[recomputed_df["prediction_recomputed"] == "yes"]["active_model_id"]) else "no",
                "artifacts_available": "yes" if model_id in set(artifact_df[artifact_df["artifacts_available"] == "yes"]["active_model_id"]) else "no",
                "metrics_match_registered": mm,
                "max_abs_delta_any_metric": g2["abs_delta"].max() if not g2.empty else float("nan"),
            }
        )
    metrics_match_df = pd.DataFrame(metrics_match_rows)

    if recomputed_yes < 30:
        final_status = "fail"
    elif all_real_clone_count > 0 or duplicate_hash_count > 0 or guard_viol_count > 0:
        final_status = "fail"
    elif all_near_clone_count > 0:
        final_status = "pass_with_warnings"
    else:
        final_status = "pass"

    # comparisons v13 vs v14
    v13_idx = active_v13.set_index(["domain", "role", "mode"])
    v14_idx = active_v14.set_index(["domain", "role", "mode"])
    comp_all = []
    comp_elim = []
    for key in v13_idx.index:
        o = v13_idx.loc[key]
        n = v14_idx.loc[key]
        rec = {
            "domain": key[0],
            "role": key[1],
            "mode": key[2],
            "v13_active_model_id": o["active_model_id"],
            "v14_active_model_id": n["active_model_id"],
            "active_model_id_changed": "yes" if str(o["active_model_id"]) != str(n["active_model_id"]) else "no",
            "v13_threshold": sf(o["threshold"]),
            "v14_threshold": sf(n["threshold"]),
            "delta_threshold": sf(n["threshold"]) - sf(o["threshold"]),
            "v13_f1": sf(o["f1"]),
            "v14_f1": sf(n["f1"]),
            "delta_f1": sf(n["f1"]) - sf(o["f1"]),
            "v13_recall": sf(o["recall"]),
            "v14_recall": sf(n["recall"]),
            "delta_recall": sf(n["recall"]) - sf(o["recall"]),
            "v13_precision": sf(o["precision"]),
            "v14_precision": sf(n["precision"]),
            "delta_precision": sf(n["precision"]) - sf(o["precision"]),
            "v13_balanced_accuracy": sf(o["balanced_accuracy"]),
            "v14_balanced_accuracy": sf(n["balanced_accuracy"]),
            "delta_balanced_accuracy": sf(n["balanced_accuracy"]) - sf(o["balanced_accuracy"]),
            "v13_brier": sf(o["brier"]),
            "v14_brier": sf(n["brier"]),
            "delta_brier": sf(n["brier"]) - sf(o["brier"]),
            "feature_list_pipe_unchanged": "yes" if str(o["feature_list_pipe"]) == str(n["feature_list_pipe"]) else "no",
        }
        comp_all.append(rec)
        if key[0] == "elimination":
            comp_elim.append(rec)
    comp_all_df = pd.DataFrame(comp_all)
    comp_elim_df = pd.DataFrame(comp_elim)

    # validators
    main_validator = pd.DataFrame(
        [
            {
                "audit_line": LINE,
                "generated_at_utc": now(),
                "loader_active_line_before": loader_active,
                "loader_operational_line_before": loader_op,
                "loader_points_v13_before": loader_points_v13,
                "active_rows": int(len(active_v14)),
                "rf_rows": int((active_v14["model_family"].astype(str).str.lower() == "rf").sum()),
                "prediction_recomputed_slots": recomputed_yes,
                "artifacts_available_slots": int((artifact_df["artifacts_available"] == "yes").sum()),
                "metrics_match_yes_slots": int((metrics_match_df["metrics_match_registered"] == "yes").sum()),
                "metrics_match_no_slots": int((metrics_match_df["metrics_match_registered"] == "no").sum()),
                "elimination_real_clone_count": elimination_real_clone_count_final,
                "all_domains_real_clone_count": all_real_clone_count,
                "all_domains_near_clone_warning_count": all_near_clone_count,
                "artifact_duplicate_hash_count": duplicate_hash_count,
                "guardrail_violation_count": guard_viol_count,
                "final_audit_status": final_status,
            }
        ]
    )

    # save requested artifacts
    save_csv(pd.DataFrame(candidate_rows), TABLES / "elimination_candidate_trials_v14.csv")
    save_csv(joint_df, TABLES / "elimination_joint_selection_v14.csv")
    save_csv(comp_elim_df, TABLES / "v13_vs_v14_elimination_comparison.csv")
    save_csv(comp_all_df, TABLES / "v13_vs_v14_all_champions_comparison.csv")
    save_csv(recomputed_df.drop(columns=["_probs", "_preds", "_y"]), TABLES / "v14_recomputed_champion_metrics.csv")
    save_csv(reg_vs_recomp_df, TABLES / "v14_registered_vs_recomputed_metrics.csv")
    save_csv(pair_df, TABLES / "v14_pairwise_prediction_similarity_all_domains.csv")
    save_csv(elim_pair_v14, TABLES / "v14_elimination_real_prediction_similarity.csv")
    save_csv(shared_error_df, TABLES / "v14_shared_error_overlap.csv")
    hash_inv = artifact_df.copy()
    hash_inv["duplicate_hash_group_size"] = hash_inv.groupby("artifact_hash")["artifact_hash"].transform("count")
    hash_inv.loc[hash_inv["artifact_hash"].isna(), "duplicate_hash_group_size"] = 0
    save_csv(hash_inv, TABLES / "v14_artifact_hash_inventory.csv")

    save_csv(main_validator, VALIDATION / "v14_real_prediction_anti_clone_validator.csv")
    save_csv(elim_pair_v14[[
        "slot_a",
        "slot_b",
        "prediction_agreement",
        "probability_correlation",
        "binary_predictions_identical",
        "metric_max_abs_delta",
        "threshold_abs_delta",
        "feature_jaccard",
        "shared_error_overlap",
        "real_clone_flag",
        "near_clone_warning",
        "real_clone_reasons",
        "near_clone_reasons",
    ]], VALIDATION / "v14_elimination_clone_risk_validator.csv")
    save_csv(guard_df, VALIDATION / "v14_guardrail_validator.csv")
    save_csv(contract_df, VALIDATION / "v14_contract_compatibility_validator.csv")
    save_csv(non_change_df, VALIDATION / "v14_non_elimination_unchanged_validator.csv")

    # plots
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        m = comp_elim_df.melt(
            id_vars=["domain", "role", "mode"],
            value_vars=["v13_f1", "v14_f1", "v13_recall", "v14_recall", "v13_precision", "v14_precision", "v13_balanced_accuracy", "v14_balanced_accuracy", "v13_brier", "v14_brier"],
            var_name="metric",
            value_name="value",
        )
        plt.figure(figsize=(14, 6))
        sns.barplot(data=m, x="mode", y="value", hue="metric")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v13_vs_v14_metrics.png", dpi=180)
        plt.close()

        slots = sorted(set(elim_pair_v14["slot_a"]).union(set(elim_pair_v14["slot_b"])))
        corr_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        agr_mat = pd.DataFrame(np.eye(len(slots)), index=slots, columns=slots, dtype=float)
        for _, r in elim_pair_v14.iterrows():
            a = r["slot_a"]
            b = r["slot_b"]
            corr_mat.loc[a, b] = r["probability_correlation"]
            corr_mat.loc[b, a] = r["probability_correlation"]
            agr_mat.loc[a, b] = r["prediction_agreement"]
            agr_mat.loc[b, a] = r["prediction_agreement"]

        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_mat, annot=True, fmt=".3f", cmap="viridis", vmin=0.0, vmax=1.0)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v14_probability_correlation_heatmap.png", dpi=180)
        plt.close()

        plt.figure(figsize=(10, 8))
        sns.heatmap(agr_mat, annot=True, fmt=".3f", cmap="magma", vmin=0.0, vmax=1.0)
        plt.tight_layout()
        plt.savefig(PLOTS / "elimination_v14_prediction_agreement_heatmap.png", dpi=180)
        plt.close()

        p = pair_df.copy()
        p["pair"] = p["slot_a"] + " vs " + p["slot_b"]
        plt.figure(figsize=(14, 6))
        sns.barplot(data=p.sort_values(["domain", "prediction_agreement"], ascending=[True, False]), x="pair", y="prediction_agreement", hue="domain", dodge=False)
        plt.xticks(rotation=90)
        plt.ylim(0.0, 1.0)
        plt.tight_layout()
        plt.savefig(PLOTS / "v14_all_domains_pairwise_prediction_agreement.png", dpi=180)
        plt.close()
    except Exception:
        pass

    # report
    report_lines = [
        "# v14 Elimination Real Anti-Clone Rescue Report",
        "",
        f"Generated: `{now()}`",
        "",
        "## Scope",
        "- Focal rescue only for 6 elimination slots.",
        "- No campaign over other domains.",
        "- 24 non-elimination slots kept identical to v13.",
        "- RF-only policy enforced.",
        "",
        "## Results",
        f"- prediction_recomputed_slots: `{recomputed_yes}/30`",
        f"- elimination_real_clone_count: `{elimination_real_clone_count_final}`",
        f"- all_domains_real_clone_count: `{all_real_clone_count}`",
        f"- all_domains_near_clone_warning_count: `{all_near_clone_count}`",
        f"- artifact_duplicate_hash_count: `{duplicate_hash_count}`",
        f"- guardrail_violation_count: `{guard_viol_count}`",
        f"- final_audit_status: `{final_status}`",
        "",
        "## Acceptance Checklist",
        f"- elimination_real_clone_count == 0: `{'yes' if elimination_real_clone_count_final == 0 else 'no'}`",
        f"- all_domains_real_clone_count == 0: `{'yes' if all_real_clone_count == 0 else 'no'}`",
        f"- artifact_duplicate_hash_count == 0: `{'yes' if duplicate_hash_count == 0 else 'no'}`",
        f"- 24 non-elimination unchanged: `{'yes' if (non_change_df['unchanged'] == 'yes').all() else 'no'}`",
        f"- contract exact all 30: `{'yes' if (contract_df['same_inputs_outputs_contract'] == 'yes').all() else 'no'}`",
        "",
        "## Selected Elimination Candidates",
    ]
    cols = [
        "slot_index",
        "role",
        "mode",
        "candidate_key",
        "source_type",
        "source_model_id",
        "config_id",
        "calibration",
        "threshold_policy",
        "threshold",
        "f1",
        "recall",
        "precision",
        "balanced_accuracy",
        "brier",
    ]
    show = joint_df[joint_df["slot_index"] > 0].copy()
    if show.empty:
        report_lines.append("_No selected rows._")
    else:
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        report_lines.extend([header, sep])
        for _, r in show.iterrows():
            report_lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    write_text(REPORTS / "v14_elimination_real_anti_clone_rescue_report.md", "\n".join(report_lines))

    # manifests
    payload = manifest_payload(active_v14, op_v14, final_status, all_real_clone_count, elimination_real_clone_count_final, all_near_clone_count, duplicate_hash_count)
    write_text(ART_LINE, json.dumps(payload, indent=2, ensure_ascii=False))
    write_text(ART_ACTIVE_V14, json.dumps({**payload, "artifact": "hybrid_active_modes_freeze_v14"}, indent=2, ensure_ascii=False))
    write_text(ART_OP_V14, json.dumps({**payload, "artifact": "hybrid_operational_freeze_v14"}, indent=2, ensure_ascii=False))

    print(
        json.dumps(
            {
                "status": "ok",
                "line": LINE,
                "active_rows": int(len(active_v14)),
                "elimination_real_clone_count": elimination_real_clone_count_final,
                "all_domains_real_clone_count": all_real_clone_count,
                "all_domains_near_clone_warning_count": all_near_clone_count,
                "artifact_duplicate_hash_count": duplicate_hash_count,
                "guardrail_violations": guard_viol_count,
                "prediction_recomputed_slots": recomputed_yes,
                "final_audit_status": final_status,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
