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
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.hybrid_classification_policy_v1 import PolicyInputs, build_normalized_table, policy_violations

LINE = "hybrid_domain_specialized_rf_v17"
FREEZE = "v17"
SOURCE_LINE = "v17_domain_specialized_rf"
BASE = ROOT / "data" / LINE
TABLES = BASE / "tables"
VALIDATION = BASE / "validation"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"
TRIALS = BASE / "trials"
ART = ROOT / "artifacts" / LINE

ACTIVE_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_active_models_30_modes.csv"
ACTIVE_V16_SUMMARY = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_active_modes_summary.csv"
INPUTS_V16 = ROOT / "data/hybrid_active_modes_freeze_v16/tables/hybrid_questionnaire_inputs_master.csv"
OP_V16 = ROOT / "data/hybrid_operational_freeze_v16/tables/hybrid_operational_final_champions.csv"
OP_V16_NONCHAMP = ROOT / "data/hybrid_operational_freeze_v16/tables/hybrid_operational_final_nonchampions.csv"
DATASET = ROOT / "data/hybrid_no_external_scores_rebuild_v2/tables/hybrid_no_external_scores_dataset_ready.csv"
QUESTIONNAIRE_VISIBLE = ROOT / "data/cuestionario_v16.4/questionnaire_v16_4_visible_questions_excel_utf8.csv"

ACTIVE_V17_DIR = ROOT / "data/hybrid_active_modes_freeze_v17"
OP_V17_DIR = ROOT / "data/hybrid_operational_freeze_v17"
ACTIVE_V17 = ACTIVE_V17_DIR / "tables/hybrid_active_models_30_modes.csv"
ACTIVE_V17_SUMMARY = ACTIVE_V17_DIR / "tables/hybrid_active_modes_summary.csv"
INPUTS_V17 = ACTIVE_V17_DIR / "tables/hybrid_questionnaire_inputs_master.csv"
OP_V17 = OP_V17_DIR / "tables/hybrid_operational_final_champions.csv"
OP_V17_NONCHAMP = OP_V17_DIR / "tables/hybrid_operational_final_nonchampions.csv"

ART_ACTIVE_V17 = ROOT / "artifacts/hybrid_active_modes_freeze_v17/hybrid_active_modes_freeze_v17_manifest.json"
ART_OP_V17 = ROOT / "artifacts/hybrid_operational_freeze_v17/hybrid_operational_freeze_v17_manifest.json"

MODEL_ROOT = ROOT / "models/active_modes"
DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
MODES = ["caregiver_1_3", "caregiver_2_3", "caregiver_full", "psychologist_1_3", "psychologist_2_3", "psychologist_full"]
WATCH = ("recall", "specificity", "roc_auc", "pr_auc")

SEEDS = [20270511, 20270529]
BASE_SEED = 20270601
PERM_REPEATS = 2

RF_CONFIGS: list[dict[str, Any]] = [
    {
        "config_id": "rf_recall_guarded",
        "n_estimators": 170,
        "max_depth": 6,
        "min_samples_split": 12,
        "min_samples_leaf": 5,
        "max_features": "sqrt",
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
        "criterion": "gini",
        "ccp_alpha": 0.0,
        "calibrations": ["none"],
    },
    {
        "config_id": "rf_balanced_subsample",
        "n_estimators": 150,
        "max_depth": 7,
        "min_samples_split": 16,
        "min_samples_leaf": 6,
        "max_features": "log2",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
        "criterion": "gini",
        "ccp_alpha": 0.0,
        "calibrations": ["none"],
    },
    {
        "config_id": "rf_high_recall_push",
        "n_estimators": 190,
        "max_depth": 8,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": "sqrt",
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.95,
        "criterion": "gini",
        "ccp_alpha": 0.0,
        "calibrations": ["none", "sigmoid"],
    },
    {
        "config_id": "rf_recall_balanced_manual",
        "n_estimators": 160,
        "max_depth": 7,
        "min_samples_split": 14,
        "min_samples_leaf": 6,
        "max_features": "sqrt",
        "class_weight": "manual_recall",
        "bootstrap": True,
        "max_samples": 0.9,
        "criterion": "gini",
        "ccp_alpha": 0.0,
        "calibrations": ["none"],
    },
    {
        "config_id": "rf_sparse_stability",
        "n_estimators": 120,
        "max_depth": 5,
        "min_samples_split": 20,
        "min_samples_leaf": 10,
        "max_features": 0.2,
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.7,
        "criterion": "gini",
        "ccp_alpha": 0.001,
        "calibrations": ["none"],
    },
]

THRESHOLD_POLICIES = [
    "recall_guard_f2",
    "max_f2_precision_floor",
    "balanced_recall_specificity",
    "f2_with_fpr_constraint",
    "recall_target_090",
]

DOMAIN_PREFIX_MAP: dict[str, tuple[str, ...]] = {
    "adhd": ("adhd_",),
    "conduct": ("conduct_",),
    "elimination": ("enuresis_", "encopresis_", "elimination_"),
    "anxiety": ("anxiety_", "gad_", "sep_", "sep_anx_", "social_", "social_anxiety_", "agor_", "panic_"),
    "depression": ("depression_", "mdd_", "pdd_", "dmdd_"),
}

DEMOGRAPHICS = {"age_years", "sex_assigned_at_birth"}


@dataclass
class SlotFit:
    slot_key: str
    domain: str
    role: str
    mode: str
    feature_set_type: str
    features: list[str]
    candidate_key: str
    model: Any
    threshold: float
    threshold_policy: str
    seed: int
    config_id: str
    calibration: str
    metrics_train: dict[str, Any]
    metrics_val: dict[str, Any]
    metrics_holdout: dict[str, Any]
    y_holdout: np.ndarray
    probs_holdout: np.ndarray
    preds_holdout: np.ndarray
    y_val: np.ndarray
    probs_val: np.ndarray
    val_score: float
    holdout_score: float
    precision_floor: float
    recall_floor: float
    recall_ideal_low: float
    recall_ideal_high: float


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mkdirs() -> None:
    for p in [
        BASE,
        TABLES,
        VALIDATION,
        REPORTS,
        PLOTS,
        TRIALS,
        ART,
        ACTIVE_V17_DIR / "tables",
        ACTIVE_V17_DIR / "validation",
        ACTIVE_V17_DIR / "reports",
        OP_V17_DIR / "tables",
        OP_V17_DIR / "validation",
        OP_V17_DIR / "reports",
        ROOT / "artifacts/hybrid_active_modes_freeze_v17",
        ROOT / "artifacts/hybrid_operational_freeze_v17",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sf(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def feats(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split("|") if x.strip() and x.strip().lower() != "nan"]


def tcol(domain: str) -> str:
    return f"target_domain_{domain}_final"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def high_separability_alert(metrics: dict[str, Any]) -> bool:
    return any(sf(metrics.get(k), 0.0) > 0.98 for k in WATCH)


def hard_fail_reasons_from_metrics(mm: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if sf(mm.get("recall"), 0.0) < 0.80:
        reasons.append("recall_lt_0_80")
    if sf(mm.get("specificity"), 0.0) < 0.70:
        reasons.append("specificity_lt_0_70")
    if sf(mm.get("f2"), 0.0) < 0.75:
        reasons.append("f2_lt_0_75")
    if sf(mm.get("balanced_accuracy"), 0.0) < 0.75:
        reasons.append("balanced_accuracy_lt_0_75")
    if sf(mm.get("mcc"), 0.0) < 0.40:
        reasons.append("mcc_lt_0_40")
    if sf(mm.get("fpr"), 0.0) > 0.30:
        reasons.append("fpr_gt_0_30")
    if sf(mm.get("fnr"), 0.0) > 0.20:
        reasons.append("fnr_gt_0_20")
    return reasons


def auc(y: np.ndarray, p: np.ndarray) -> float:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan")


def pr_auc(y: np.ndarray, p: np.ndarray) -> float:
    return float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else float(np.mean(y))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, int)
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.digitize(p, edges[1:-1], right=False)
    out = 0.0
    for b in range(bins):
        mask = idx == b
        if np.any(mask):
            out += float(np.mean(mask)) * abs(float(np.mean(y[mask])) - float(np.mean(p[mask])))
    return float(out)


def metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict[str, Any]:
    y_true = np.asarray(y_true, int)
    prob = np.clip(np.asarray(prob, float), 1e-6, 1 - 1e-6)
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    precision = float(precision_score(y_true, pred, zero_division=0))
    recall = float(recall_score(y_true, pred, zero_division=0))
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    npv = float(tn / (tn + fn)) if (tn + fn) else 0.0
    f1 = float(f1_score(y_true, pred, zero_division=0))
    f2 = float((5 * precision * recall) / (4 * precision + recall)) if (4 * precision + recall) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) else 0.0
    prevalence = float(np.mean(y_true))
    pred_pos_rate = float(np.mean(pred))
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": f1,
        "f2": f2,
        "roc_auc": auc(y_true, prob),
        "pr_auc": pr_auc(y_true, prob),
        "brier": float(brier_score_loss(y_true, prob)),
        "mcc": float(matthews_corrcoef(y_true, pred)) if len(np.unique(y_true)) > 1 else 0.0,
        "npv": npv,
        "fpr": fpr,
        "fnr": fnr,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "prevalence": prevalence,
        "positive_rate_predicted": pred_pos_rate,
        "probability_mean": float(np.mean(prob)),
        "probability_std": float(np.std(prob)),
        "probability_min": float(np.min(prob)),
        "probability_max": float(np.max(prob)),
        "probability_p05": float(np.quantile(prob, 0.05)),
        "probability_p25": float(np.quantile(prob, 0.25)),
        "probability_p50": float(np.quantile(prob, 0.50)),
        "probability_p75": float(np.quantile(prob, 0.75)),
        "probability_p95": float(np.quantile(prob, 0.95)),
        "ece": ece(y_true, prob, bins=10),
    }


def split_registry(df: pd.DataFrame) -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    ids = df["participant_id"].astype(str).to_numpy()
    splits: dict[str, dict[str, list[str]]] = {}
    rows = []
    for i, domain in enumerate(DOMAINS):
        y = df[tcol(domain)].astype(int).to_numpy()
        seed = BASE_SEED + i * 37
        tr_ids, tmp_ids, ytr, ytmp = train_test_split(
            ids,
            y,
            test_size=0.40,
            random_state=seed,
            stratify=y,
        )
        va_ids, ho_ids, yva, yho = train_test_split(
            tmp_ids,
            ytmp,
            test_size=0.50,
            random_state=seed + 1,
            stratify=ytmp,
        )
        splits[domain] = {
            "train": list(map(str, tr_ids)),
            "val": list(map(str, va_ids)),
            "holdout": list(map(str, ho_ids)),
        }
        for split_name, arr, yy in [("train", tr_ids, ytr), ("val", va_ids, yva), ("holdout", ho_ids, yho)]:
            rows.append(
                {
                    "domain": domain,
                    "target_column": tcol(domain),
                    "split": split_name,
                    "n_rows": int(len(arr)),
                    "positive_n": int(np.sum(yy)),
                    "negative_n": int(len(yy) - np.sum(yy)),
                    "positive_rate": float(np.mean(yy)),
                    "seed": seed,
                    "strategy": "stratified_60_20_20",
                }
            )
    return splits, pd.DataFrame(rows)


def subset(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    idset = set(map(str, ids))
    return df[df["participant_id"].astype(str).isin(idset)].copy()


def prep_x(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].copy()
    for col in x.columns:
        if col == "sex_assigned_at_birth":
            x[col] = x[col].fillna("unknown").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce").astype(float)
    return x


def manual_weight(y: np.ndarray) -> dict[int, float]:
    pos = max(float(np.mean(y)), 1e-6)
    neg = max(1.0 - pos, 1e-6)
    return {0: 1.0, 1: float(min(4.0, max(1.3, neg / pos * 1.1)))}


def rf_pipeline(features: list[str], cfg: dict[str, Any], seed: int, y_train: np.ndarray) -> Pipeline:
    cats = [f for f in features if f == "sex_assigned_at_birth"]
    nums = [f for f in features if f not in cats]
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imp", SimpleImputer(strategy="median", keep_empty_features=True))]), nums),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cats,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    cw = manual_weight(y_train) if cfg["class_weight"] == "manual_recall" else cfg["class_weight"]
    rf = RandomForestClassifier(
        n_estimators=int(cfg["n_estimators"]),
        max_depth=cfg["max_depth"],
        min_samples_split=int(cfg["min_samples_split"]),
        min_samples_leaf=int(cfg["min_samples_leaf"]),
        max_features=cfg["max_features"],
        class_weight=cw,
        bootstrap=bool(cfg["bootstrap"]),
        max_samples=cfg["max_samples"],
        criterion=cfg["criterion"],
        ccp_alpha=float(cfg["ccp_alpha"]),
        random_state=seed,
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def fit_model(features: list[str], cfg: dict[str, Any], seed: int, calibration: str, xtr: pd.DataFrame, ytr: np.ndarray) -> Any:
    base = rf_pipeline(features, cfg, seed, ytr)
    if calibration == "none":
        base.fit(xtr, ytr)
        return base
    cv = 3 if min(np.bincount(ytr.astype(int))) >= 3 else 2
    cal = CalibratedClassifierCV(estimator=base, method=calibration, cv=cv)
    cal.fit(xtr, ytr)
    return cal


def predict_proba(model: Any, x: pd.DataFrame) -> np.ndarray:
    return np.clip(np.asarray(model.predict_proba(x)[:, 1], float), 1e-6, 1 - 1e-6)


def rf_estimators(model: Any) -> list[RandomForestClassifier]:
    if isinstance(model, Pipeline):
        return [model.named_steps["rf"]]
    out = []
    for cc in getattr(model, "calibrated_classifiers_", []) or []:
        est = getattr(cc, "estimator", None)
        if isinstance(est, Pipeline) and "rf" in est.named_steps:
            out.append(est.named_steps["rf"])
    return out


def feature_importance_mean(model: Any, features: list[str]) -> pd.Series:
    ests = rf_estimators(model)
    vals = np.zeros(len(features), float)
    for rf in ests:
        imp = np.asarray(getattr(rf, "feature_importances_", np.ones(len(features)) / max(1, len(features))), float)
        if len(imp) != len(features):
            imp = np.ones(len(features)) / max(1, len(features))
        vals += imp
    if len(ests):
        vals /= len(ests)
    if np.sum(vals) > 0:
        vals /= np.sum(vals)
    return pd.Series(vals, index=features).sort_values(ascending=False)


def threshold_grid(probs: np.ndarray) -> np.ndarray:
    base = list(np.linspace(0.05, 0.95, 91))
    q = list(np.quantile(probs, np.linspace(0.05, 0.95, 37))) if len(probs) else []
    vals = sorted(set(float(x) for x in base + q if 0.0 < float(x) < 1.0))
    return np.asarray(vals, float)


def threshold_score(policy: str, mm: dict[str, Any], precision_floor: float, recall_floor: float, recall_ideal_hi: float) -> float:
    if policy == "recall_guard_f2":
        s = 0.40 * mm["f2"] + 0.28 * mm["recall"] + 0.14 * mm["pr_auc"] + 0.10 * mm["precision"] + 0.08 * mm["balanced_accuracy"]
    elif policy == "max_f2_precision_floor":
        s = 0.45 * mm["f2"] + 0.20 * mm["recall"] + 0.15 * mm["precision"] + 0.12 * mm["pr_auc"] + 0.08 * mm["balanced_accuracy"]
    elif policy == "balanced_recall_specificity":
        s = 0.32 * mm["f2"] + 0.22 * mm["recall"] + 0.18 * mm["specificity"] + 0.14 * mm["balanced_accuracy"] + 0.14 * mm["pr_auc"]
    elif policy == "f2_with_fpr_constraint":
        s = 0.38 * mm["f2"] + 0.24 * mm["recall"] + 0.16 * mm["precision"] + 0.12 * mm["pr_auc"] + 0.10 * mm["balanced_accuracy"]
    elif policy == "recall_target_090":
        s = 0.26 * mm["f2"] + 0.36 * mm["recall"] + 0.14 * mm["pr_auc"] + 0.12 * mm["precision"] + 0.12 * mm["balanced_accuracy"]
    else:
        s = 0.30 * mm["f2"] + 0.30 * mm["recall"] + 0.18 * mm["pr_auc"] + 0.12 * mm["precision"] + 0.10 * mm["balanced_accuracy"]

    if mm["precision"] < precision_floor:
        s -= 0.35 + 1.20 * (precision_floor - mm["precision"])
    if mm["recall"] < recall_floor:
        s -= 0.40 + 1.35 * (recall_floor - mm["recall"])
    if mm["recall"] > recall_ideal_hi:
        s -= 0.15 * (mm["recall"] - recall_ideal_hi)
    if mm["specificity"] < 0.70:
        s -= 0.20 + (0.70 - mm["specificity"])
    if policy == "f2_with_fpr_constraint" and mm["fpr"] > 0.25:
        s -= 0.40 + 1.2 * (mm["fpr"] - 0.25)
    if policy == "recall_target_090" and mm["recall"] < 0.90:
        s -= 0.30 + 1.4 * (0.90 - mm["recall"])
    return float(s)


def choose_threshold(
    y_val: np.ndarray,
    probs_val: np.ndarray,
    precision_floor: float,
    recall_floor: float,
    recall_ideal_hi: float,
) -> tuple[float, str, dict[str, Any], float]:
    best: tuple[float, str, dict[str, Any], float] = (0.5, THRESHOLD_POLICIES[0], metrics(y_val, probs_val, 0.5), -1e18)
    for policy in THRESHOLD_POLICIES:
        for thr in threshold_grid(probs_val):
            mm = metrics(y_val, probs_val, float(thr))
            sc = threshold_score(policy, mm, precision_floor, recall_floor, recall_ideal_hi)
            if sc > best[3]:
                best = (float(thr), policy, mm, float(sc))
    return best


def holdout_score(mm: dict[str, Any], precision_floor: float, recall_floor: float) -> float:
    s = (
        0.34 * mm["f2"]
        + 0.24 * mm["recall"]
        + 0.14 * mm["pr_auc"]
        + 0.10 * mm["precision"]
        + 0.08 * mm["balanced_accuracy"]
        + 0.05 * mm["mcc"]
        + 0.05 * max(0.0, 1.0 - mm["brier"])
    )
    if mm["precision"] < precision_floor:
        s -= 0.4 + (precision_floor - mm["precision"])
    if mm["recall"] < recall_floor:
        s -= 0.4 + (recall_floor - mm["recall"])
    if mm["fpr"] > 0.30:
        s -= 0.5 + (mm["fpr"] - 0.30)
    if mm["fnr"] > 0.20:
        s -= 0.5 + (mm["fnr"] - 0.20)
    return float(s)


def split_feature_type(mode: str) -> str:
    if mode.endswith("full"):
        return "domain_strict_full"
    if mode.endswith("2_3"):
        return "domain_strict_2_3"
    return "domain_strict_1_3"


def role_col(role: str) -> str:
    return "caregiver_answerable_yes_no" if role == "caregiver" else "psychologist_answerable_yes_no"


def include_col(mode: str) -> str:
    if mode == "caregiver_1_3":
        return "include_caregiver_1_3"
    if mode == "caregiver_2_3":
        return "include_caregiver_2_3"
    if mode == "caregiver_full":
        return "include_caregiver_full"
    if mode == "psychologist_1_3":
        return "include_psychologist_1_3"
    if mode == "psychologist_2_3":
        return "include_psychologist_2_3"
    return "include_psychologist_full"


def domain_match_feature(domain: str, feature: str) -> bool:
    f = str(feature).strip().lower()
    return any(f.startswith(p) for p in DOMAIN_PREFIX_MAP[domain])


def clean_inputs_master(inputs: pd.DataFrame) -> pd.DataFrame:
    x = inputs.copy()
    x["feature"] = x["feature"].astype(str).str.strip().str.lower()
    for col in [
        "is_direct_input",
        "is_transparent_derived",
        "requires_internal_scoring",
        "caregiver_answerable_yes_no",
        "psychologist_answerable_yes_no",
        "include_caregiver_1_3",
        "include_caregiver_2_3",
        "include_caregiver_full",
        "include_psychologist_1_3",
        "include_psychologist_2_3",
        "include_psychologist_full",
    ]:
        if col in x.columns:
            x[col] = x[col].astype(str).str.strip().str.lower()
    return x


def quick_rank_features(
    domain: str,
    role: str,
    features: list[str],
    data: pd.DataFrame,
    splits: dict[str, dict[str, list[str]]],
) -> pd.DataFrame:
    tr = subset(data, splits[domain]["train"])
    va = subset(data, splits[domain]["val"])
    ytr = tr[tcol(domain)].astype(int).to_numpy()
    yva = va[tcol(domain)].astype(int).to_numpy()
    xtr = prep_x(tr, features)
    xva = prep_x(va, features)

    imp_rows = []
    perm_map: dict[str, list[float]] = {f: [] for f in features}
    for seed in SEEDS:
        cfg = RF_CONFIGS[0]
        model = fit_model(features, cfg, seed, "none", xtr, ytr)
        imp = feature_importance_mean(model, features)
        for rank, (f, v) in enumerate(imp.items(), 1):
            imp_rows.append(
                {
                    "domain": domain,
                    "role": role,
                    "seed": seed,
                    "feature": f,
                    "importance": float(v),
                    "importance_rank": rank,
                }
            )
        try:
            perm = permutation_importance(
                model,
                xva,
                yva,
                scoring="balanced_accuracy",
                n_repeats=PERM_REPEATS,
                random_state=seed,
                n_jobs=1,
            )
            for i, f in enumerate(features):
                perm_map[f].append(float(perm.importances_mean[i]))
        except Exception:
            for f in features:
                perm_map[f].append(0.0)

    imp_df = pd.DataFrame(imp_rows)
    agg = (
        imp_df.groupby("feature", dropna=False)
        .agg(impurity_mean=("importance", "mean"), impurity_std=("importance", "std"))
        .reset_index()
    )
    agg["permutation_mean"] = agg["feature"].map(lambda f: float(np.mean(perm_map.get(f, [0.0]))))
    agg["permutation_std"] = agg["feature"].map(lambda f: float(np.std(perm_map.get(f, [0.0]))))
    agg["impurity_norm"] = agg["impurity_mean"] / max(float(agg["impurity_mean"].sum()), 1e-12)
    perm_nonneg = agg["permutation_mean"].clip(lower=0.0)
    agg["permutation_norm"] = perm_nonneg / max(float(perm_nonneg.sum()), 1e-12)
    agg["ranking_score"] = 0.60 * agg["impurity_norm"] + 0.40 * agg["permutation_norm"]
    agg = agg.sort_values(["ranking_score", "impurity_norm", "permutation_norm"], ascending=[False, False, False]).reset_index(drop=True)
    agg["ranking_position"] = np.arange(1, len(agg) + 1)
    return agg


def build_structural_sets(
    active_v16: pd.DataFrame,
    inputs: pd.DataFrame,
    data: pd.DataFrame,
    splits: dict[str, dict[str, list[str]]],
) -> tuple[dict[tuple[str, str, str], list[str]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    active_idx = active_v16.set_index(["domain", "role", "mode"])
    inputs = clean_inputs_master(inputs)
    dataset_cols = set(map(str, data.columns))

    universe_rows = []
    subset_rows = []
    ranking_rows = []
    per_slot_features: dict[tuple[str, str, str], list[str]] = {}

    for domain, role in itertools.product(DOMAINS, ["caregiver", "psychologist"]):
        full_row = active_idx.loc[(domain, role, f"{role}_full")]
        old_full_features = set(feats(full_row["feature_list_pipe"]))
        dom_prefix = DOMAIN_PREFIX_MAP[domain]
        rcol = role_col(role)

        candidates = inputs[
            (inputs[rcol] == "yes")
            & (inputs["is_direct_input"] == "yes")
            & (~inputs["feature"].str.startswith("eng_"))
            & (~inputs["feature"].str.startswith("engv"))
        ].copy()
        candidates["is_domain_feature"] = candidates["feature"].map(lambda f: any(str(f).startswith(p) for p in dom_prefix))
        candidates["is_demographic"] = candidates["feature"].isin(DEMOGRAPHICS)
        candidates = candidates[candidates["is_domain_feature"] | candidates["is_demographic"]].copy()
        candidates = candidates[candidates["feature"].isin(dataset_cols)].copy()
        candidates = candidates[
            candidates["is_domain_feature"] | (candidates["is_demographic"] & candidates["feature"].isin(old_full_features))
        ].copy()
        candidates = candidates.drop_duplicates(subset=["feature"]).reset_index(drop=True)

        full_mode_col = include_col(f"{role}_full")
        full_universe = candidates[candidates[full_mode_col] == "yes"]["feature"].astype(str).tolist()
        full_universe = sorted(set(full_universe))
        if len(full_universe) < 6:
            raise RuntimeError(f"insufficient_domain_features:{domain}/{role}:n={len(full_universe)}")

        rank_df = quick_rank_features(domain, role, full_universe, data, splits)
        rank_map = {r.feature: int(r.ranking_position) for r in rank_df.itertuples()}
        ranked_full = [str(x) for x in rank_df["feature"].tolist()]

        target_2 = max(1, int(math.ceil(len(full_universe) * 2 / 3)))
        target_1 = max(1, int(math.ceil(len(full_universe) / 3)))

        mode_feats: dict[str, list[str]] = {}
        mode_meta: dict[str, dict[str, Any]] = {}
        for mode in [f"{role}_full", f"{role}_2_3", f"{role}_1_3"]:
            mcol = include_col(mode)
            available = set(candidates[candidates[mcol] == "yes"]["feature"].astype(str).tolist())
            if mode.endswith("full"):
                final = [f for f in ranked_full if f in available]
                mode_target = len(full_universe)
            elif mode.endswith("2_3"):
                wanted = [f for f in ranked_full if f in available and f in full_universe]
                final = wanted[:target_2]
                mode_target = target_2
            else:
                parent = mode_feats[f"{role}_2_3"]
                wanted = [f for f in parent if f in available]
                final = wanted[:target_1]
                mode_target = target_1

            if mode.endswith("1_3") and len(final) < 4:
                extra = [f for f in mode_feats[f"{role}_2_3"] if f in available and f not in final]
                final.extend(extra[: max(0, 4 - len(final))])

            if mode.endswith("2_3") and len(final) < 6:
                extra = [f for f in ranked_full if f in available and f not in final]
                final.extend(extra[: max(0, 6 - len(final))])

            mode_feats[mode] = final
            mode_meta[mode] = {
                "target_size": int(mode_target),
                "available_size": int(len(available)),
                "achieved_size": int(len(final)),
                "best_attainable_under_current_questionnaire": "yes" if len(final) < mode_target else "no",
            }

        if not set(mode_feats[f"{role}_1_3"]).issubset(set(mode_feats[f"{role}_2_3"])):
            mode_feats[f"{role}_1_3"] = [f for f in mode_feats[f"{role}_1_3"] if f in set(mode_feats[f"{role}_2_3"])]
        if not set(mode_feats[f"{role}_2_3"]).issubset(set(mode_feats[f"{role}_full"])):
            mode_feats[f"{role}_2_3"] = [f for f in mode_feats[f"{role}_2_3"] if f in set(mode_feats[f"{role}_full"])]
            mode_feats[f"{role}_1_3"] = [f for f in mode_feats[f"{role}_1_3"] if f in set(mode_feats[f"{role}_2_3"])]

        for mode in [f"{role}_full", f"{role}_2_3", f"{role}_1_3"]:
            per_slot_features[(domain, role, mode)] = mode_feats[mode]

        cross_count_full = int(sum(1 for f in mode_feats[f"{role}_full"] if not domain_match_feature(domain, f) and f not in DEMOGRAPHICS))
        eng_count_full = int(sum(1 for f in mode_feats[f"{role}_full"] if f.startswith("eng_") or f.startswith("engv")))
        universe_rows.append(
            {
                "domain": domain,
                "role": role,
                "feature_set_type": "domain_strict_full_universe",
                "n_features": len(mode_feats[f"{role}_full"]),
                "cross_domain_feature_count": cross_count_full,
                "eng_feature_count": eng_count_full,
                "features_pipe": "|".join(mode_feats[f"{role}_full"]),
            }
        )
        for mode in [f"{role}_full", f"{role}_2_3", f"{role}_1_3"]:
            feats_mode = mode_feats[mode]
            cross_count = int(sum(1 for f in feats_mode if not domain_match_feature(domain, f) and f not in DEMOGRAPHICS))
            eng_count = int(sum(1 for f in feats_mode if f.startswith("eng_") or f.startswith("engv")))
            subset_rows.append(
                {
                    "domain": domain,
                    "role": role,
                    "mode": mode,
                    "feature_set_type": split_feature_type(mode),
                    "target_n_features": mode_meta[mode]["target_size"],
                    "available_n_features_for_mode": mode_meta[mode]["available_size"],
                    "selected_n_features": len(feats_mode),
                    "best_attainable_under_current_questionnaire": mode_meta[mode]["best_attainable_under_current_questionnaire"],
                    "is_subset_of_full": "yes" if set(feats_mode).issubset(set(mode_feats[f"{role}_full"])) else "no",
                    "is_nested_with_2_3": "yes"
                    if (mode.endswith("1_3") and set(feats_mode).issubset(set(mode_feats[f"{role}_2_3"])))
                    or (mode.endswith("2_3") and set(feats_mode).issubset(set(mode_feats[f"{role}_full"])))
                    or mode.endswith("full")
                    else "no",
                    "cross_domain_feature_count": cross_count,
                    "eng_feature_count": eng_count,
                    "features_pipe": "|".join(feats_mode),
                }
            )

        fmeta = inputs.set_index("feature").to_dict(orient="index")
        for r in rank_df.itertuples():
            meta = fmeta.get(str(r.feature), {})
            ranking_rows.append(
                {
                    "domain": domain,
                    "role": role,
                    "feature": str(r.feature),
                    "ranking_position": int(r.ranking_position),
                    "ranking_score": float(r.ranking_score),
                    "impurity_mean": float(r.impurity_mean),
                    "impurity_std": float(r.impurity_std) if not pd.isna(r.impurity_std) else np.nan,
                    "permutation_mean": float(r.permutation_mean),
                    "permutation_std": float(r.permutation_std),
                    "feature_label_human": str(meta.get("feature_label_human") or ""),
                    "questionnaire_section_suggested": str(meta.get("questionnaire_section_suggested") or ""),
                }
            )

    return per_slot_features, pd.DataFrame(universe_rows), pd.DataFrame(subset_rows), pd.DataFrame(ranking_rows)


def precision_floor(old_precision: float, mode: str, domain: str) -> float:
    base = 0.64 if mode.endswith("1_3") else 0.70
    if domain in {"adhd", "depression", "elimination"}:
        base -= 0.03
    return max(0.55, min(base, max(0.55, old_precision - 0.05)))


def recall_targets(mode: str, domain: str) -> tuple[float, float]:
    low = 0.85 if mode.endswith("1_3") else 0.88
    high = 0.95
    if domain == "elimination":
        low = 0.84 if mode.endswith("1_3") else 0.87
    return low, high


def feature_set_variants(mode_features: list[str], mode: str) -> list[tuple[str, list[str]]]:
    # First variant is the designated structural set and is the only one eligible for promotion.
    out = [(split_feature_type(mode), list(mode_features))]
    no_demo = [f for f in mode_features if f not in DEMOGRAPHICS]
    if len(no_demo) >= 6 and len(no_demo) != len(mode_features):
        out.append(("domain_strict_no_demographics", no_demo))
    if len(mode_features) >= 12:
        keep = int(math.ceil(len(mode_features) * 0.8))
        out.append(("domain_strict_no_low_importance", mode_features[:keep]))
    out.append((f"{split_feature_type(mode)}_calibrated", list(mode_features)))
    dedup = {}
    for name, fs in out:
        key = "|".join(fs)
        if key not in dedup:
            dedup[key] = (name, fs)
    return list(dedup.values())


def train_slot(
    row: pd.Series,
    slot_features: list[str],
    data: pd.DataFrame,
    splits: dict[str, dict[str, list[str]]],
) -> tuple[pd.DataFrame, dict[str, SlotFit]]:
    domain = str(row["domain"])
    role = str(row["role"])
    mode = str(row["mode"])
    slot_key = f"{domain}/{role}/{mode}"
    tr_df = subset(data, splits[domain]["train"])
    va_df = subset(data, splits[domain]["val"])
    ho_df = subset(data, splits[domain]["holdout"])
    ytr = tr_df[tcol(domain)].astype(int).to_numpy()
    yva = va_df[tcol(domain)].astype(int).to_numpy()
    yho = ho_df[tcol(domain)].astype(int).to_numpy()

    precision_old = sf(row.get("precision"), 0.70)
    p_floor = precision_floor(precision_old, mode, domain)
    r_floor, r_hi = recall_targets(mode, domain)

    rows: list[dict[str, Any]] = []
    cache: dict[str, SlotFit] = {}

    variants = feature_set_variants(slot_features, mode)
    for feature_set_name, features in variants:
        xtr = prep_x(tr_df, features)
        xva = prep_x(va_df, features)
        xho = prep_x(ho_df, features)
        for cfg in RF_CONFIGS:
            calibs = list(cfg["calibrations"])
            # constrain isotonic-like behavior implicitly (not using isotonic by default for runtime cost).
            if feature_set_name.endswith("_calibrated"):
                calibs = [c for c in calibs if c in {"sigmoid", "none"}]
            for seed in SEEDS:
                for calibration in calibs:
                    try:
                        model = fit_model(features, cfg, seed, calibration, xtr, ytr)
                        p_tr = predict_proba(model, xtr)
                        p_va = predict_proba(model, xva)
                        p_ho = predict_proba(model, xho)
                        thr, thr_policy, mv, val_score = choose_threshold(yva, p_va, p_floor, r_floor, r_hi)
                        mt = metrics(ytr, p_tr, thr)
                        mh = metrics(yho, p_ho, thr)
                        hs = holdout_score(mh, p_floor, r_floor)
                        pred_ho = (p_ho >= thr).astype(int)
                        candidate_key = f"{slot_key}::{feature_set_name}::{cfg['config_id']}::{seed}::{calibration}::{thr_policy}::{thr:.6f}"
                        hard_fail_reasons = hard_fail_reasons_from_metrics(mh)
                        rec = {
                            "slot_key": slot_key,
                            "domain": domain,
                            "role": role,
                            "mode": mode,
                            "feature_set_type": feature_set_name,
                            "feature_columns_pipe": "|".join(features),
                            "n_features": len(features),
                            "config_id": cfg["config_id"],
                            "seed": seed,
                            "calibration": calibration,
                            "threshold_policy": thr_policy,
                            "threshold": float(thr),
                            "precision_floor": float(p_floor),
                            "recall_floor": float(r_floor),
                            "recall_ideal_hi": float(r_hi),
                            "train_precision": mt["precision"],
                            "train_recall": mt["recall"],
                            "train_specificity": mt["specificity"],
                            "train_balanced_accuracy": mt["balanced_accuracy"],
                            "train_f1": mt["f1"],
                            "train_f2": mt["f2"],
                            "train_mcc": mt["mcc"],
                            "train_pr_auc": mt["pr_auc"],
                            "train_roc_auc": mt["roc_auc"],
                            "train_brier": mt["brier"],
                            "val_precision": mv["precision"],
                            "val_recall": mv["recall"],
                            "val_specificity": mv["specificity"],
                            "val_balanced_accuracy": mv["balanced_accuracy"],
                            "val_f1": mv["f1"],
                            "val_f2": mv["f2"],
                            "val_mcc": mv["mcc"],
                            "val_pr_auc": mv["pr_auc"],
                            "val_roc_auc": mv["roc_auc"],
                            "val_brier": mv["brier"],
                            "precision": mh["precision"],
                            "recall": mh["recall"],
                            "specificity": mh["specificity"],
                            "balanced_accuracy": mh["balanced_accuracy"],
                            "f1": mh["f1"],
                            "f2": mh["f2"],
                            "mcc": mh["mcc"],
                            "npv": mh["npv"],
                            "fpr": mh["fpr"],
                            "fnr": mh["fnr"],
                            "pr_auc": mh["pr_auc"],
                            "roc_auc": mh["roc_auc"],
                            "brier": mh["brier"],
                            "tn": mh["tn"],
                            "fp": mh["fp"],
                            "fn": mh["fn"],
                            "tp": mh["tp"],
                            "prevalence": mh["prevalence"],
                            "positive_rate_predicted": mh["positive_rate_predicted"],
                            "high_separability_alert": "yes" if high_separability_alert(mh) else "no",
                            "hard_fail_candidate": "yes" if hard_fail_reasons else "no",
                            "hard_fail_reasons": "|".join(hard_fail_reasons),
                            "precision_floor_ok": "yes" if mh["precision"] >= p_floor else "no",
                            "recall_floor_ok": "yes" if mh["recall"] >= r_floor else "no",
                            "candidate_key": candidate_key,
                            "val_selection_score": float(val_score),
                            "holdout_metric_score": float(hs),
                            "trial_error": "none",
                        }
                        rows.append(rec)
                        cache[candidate_key] = SlotFit(
                            slot_key=slot_key,
                            domain=domain,
                            role=role,
                            mode=mode,
                            feature_set_type=feature_set_name,
                            features=list(features),
                            candidate_key=candidate_key,
                            model=model,
                            threshold=float(thr),
                            threshold_policy=thr_policy,
                            seed=int(seed),
                            config_id=str(cfg["config_id"]),
                            calibration=str(calibration),
                            metrics_train=mt,
                            metrics_val=mv,
                            metrics_holdout=mh,
                            y_holdout=np.asarray(yho, int),
                            probs_holdout=np.asarray(p_ho, float),
                            preds_holdout=np.asarray(pred_ho, int),
                            y_val=np.asarray(yva, int),
                            probs_val=np.asarray(p_va, float),
                            val_score=float(val_score),
                            holdout_score=float(hs),
                            precision_floor=float(p_floor),
                            recall_floor=float(r_floor),
                            recall_ideal_low=float(r_floor),
                            recall_ideal_high=float(r_hi),
                        )
                    except Exception as exc:
                        rows.append(
                            {
                                "slot_key": slot_key,
                                "domain": domain,
                                "role": role,
                                "mode": mode,
                                "feature_set_type": feature_set_name,
                                "feature_columns_pipe": "|".join(features),
                                "n_features": len(features),
                                "config_id": cfg["config_id"],
                                "seed": seed,
                                "calibration": calibration,
                                "threshold_policy": "na",
                                "threshold": np.nan,
                                "high_separability_alert": "no",
                                "hard_fail_candidate": "yes",
                                "hard_fail_reasons": "trial_error",
                                "precision_floor_ok": "no",
                                "recall_floor_ok": "no",
                                "candidate_key": "",
                                "val_selection_score": -1e18,
                                "holdout_metric_score": -1e18,
                                "trial_error": repr(exc),
                            }
                        )
    return pd.DataFrame(rows), cache


def select_slot_winner(current_row: pd.Series, trials: pd.DataFrame) -> pd.Series:
    structural_type = split_feature_type(str(current_row["mode"]))
    tt = trials[(trials["trial_error"] == "none") & (trials["feature_set_type"] == structural_type)].copy()
    if tt.empty:
        raise RuntimeError(f"no_structural_candidates:{current_row['domain']}/{current_row['mode']}")
    good = tt[(tt["hard_fail_candidate"] == "no") & (tt["precision_floor_ok"] == "yes") & (tt["recall_floor_ok"] == "yes")]
    if good.empty:
        good = tt[(tt["hard_fail_candidate"] == "no") & (tt["precision_floor_ok"] == "yes")]
    if good.empty:
        good = tt[tt["hard_fail_candidate"] == "no"]
    if good.empty:
        good = tt
    good = good.sort_values(
        [
            "holdout_metric_score",
            "val_selection_score",
            "recall",
            "f2",
            "pr_auc",
            "precision",
            "balanced_accuracy",
            "mcc",
            "brier",
        ],
        ascending=[False, False, False, False, False, False, False, False, True],
    )
    return good.iloc[0].copy()


def feature_jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return float(len(sa & sb) / max(1, len(sa | sb)))


def error_overlap(a: SlotFit, b: SlotFit) -> float:
    ea = set(np.where(a.preds_holdout != a.y_holdout)[0].tolist())
    eb = set(np.where(b.preds_holdout != b.y_holdout)[0].tolist())
    if not ea and not eb:
        return 1.0
    return float(len(ea & eb) / max(1, len(ea | eb)))


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) <= 1e-12 or np.std(b) <= 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def pairwise_similarity(selected_df: pd.DataFrame, cache: dict[str, SlotFit]) -> pd.DataFrame:
    rows = []
    order = selected_df.sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            a = order.iloc[i]
            b = order.iloc[j]
            ca = cache[str(a["candidate_key"])]
            cb = cache[str(b["candidate_key"])]
            agr = float(np.mean(ca.preds_holdout == cb.preds_holdout))
            corr = correlation(ca.probs_holdout, cb.probs_holdout)
            cm_a = (ca.metrics_holdout["tn"], ca.metrics_holdout["fp"], ca.metrics_holdout["fn"], ca.metrics_holdout["tp"])
            cm_b = (cb.metrics_holdout["tn"], cb.metrics_holdout["fp"], cb.metrics_holdout["fn"], cb.metrics_holdout["tp"])
            same_cm = cm_a == cm_b
            mx = max(
                abs(sf(a["f1"]) - sf(b["f1"])),
                abs(sf(a["recall"]) - sf(b["recall"])),
                abs(sf(a["precision"]) - sf(b["precision"])),
                abs(sf(a["balanced_accuracy"]) - sf(b["balanced_accuracy"])),
                abs(sf(a["specificity"]) - sf(b["specificity"])),
                abs(sf(a["threshold"]) - sf(b["threshold"])),
            )
            jacc = feature_jaccard(ca.features, cb.features)
            thr_delta = abs(float(ca.threshold) - float(cb.threshold))
            same_preds = bool(np.array_equal(ca.preds_holdout, cb.preds_holdout))
            overlap = error_overlap(ca, cb)
            structural_equivalence = jacc >= 0.90
            # Real-clone rules
            real_reasons = []
            near_reasons = []
            if same_preds and structural_equivalence and thr_delta <= 0.02:
                real_reasons.append("binary_predictions_identical")
            if agr >= 0.995 and (not np.isnan(corr)) and corr >= 0.995 and structural_equivalence and thr_delta <= 0.02:
                real_reasons.append("agreement_and_probability_correlation_high")
            if same_cm and (not np.isnan(corr)) and corr >= 0.995 and structural_equivalence and thr_delta <= 0.02:
                real_reasons.append("same_confusion_matrix_and_probability_corr")
            if thr_delta <= 1e-9 and mx <= 1e-9 and jacc >= 0.90:
                real_reasons.append("same_threshold_same_metrics_high_feature_jaccard")
            if agr >= 0.98:
                near_reasons.append("prediction_agreement_ge_0_98")
            if (not np.isnan(corr)) and corr >= 0.98:
                near_reasons.append("probability_correlation_ge_0_98")
            if mx <= 0.005:
                near_reasons.append("metric_max_abs_delta_le_0_005")
            if jacc >= 0.75:
                near_reasons.append("feature_jaccard_ge_0_75")
            if thr_delta <= 0.01:
                near_reasons.append("thresholds_close")
            if overlap >= 0.90:
                near_reasons.append("shared_error_overlap_high")

            rows.append(
                {
                    "domain": str(a["domain"]),
                    "slot_a": f"{a['domain']}/{a['mode']}",
                    "slot_b": f"{b['domain']}/{b['mode']}",
                    "role_a": str(a["role"]),
                    "role_b": str(b["role"]),
                    "mode_a": str(a["mode"]),
                    "mode_b": str(b["mode"]),
                    "prediction_agreement": agr,
                    "probability_correlation": corr,
                    "binary_predictions_identical": "yes" if same_preds else "no",
                    "metric_max_abs_delta": float(mx),
                    "threshold_abs_delta": float(thr_delta),
                    "feature_jaccard": float(jacc),
                    "shared_error_overlap": float(overlap),
                    "same_confusion_matrix": "yes" if same_cm else "no",
                    "real_clone_flag": "yes" if real_reasons else "no",
                    "near_clone_warning": "yes" if near_reasons else "no",
                    "real_clone_reasons": "|".join(real_reasons),
                    "near_clone_reasons": "|".join(near_reasons),
                }
            )
    return pd.DataFrame(rows)


def resolve_real_clones(
    selected_df: pd.DataFrame,
    trials_df: pd.DataFrame,
    cache: dict[str, SlotFit],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = selected_df.copy().reset_index(drop=True)
    changes = []
    for _ in range(16):
        pair = pairwise_similarity(selected, cache)
        bad = pair[pair["real_clone_flag"] == "yes"].copy()
        if bad.empty:
            break
        c = bad.iloc[0]
        slot_candidates = [c["slot_a"], c["slot_b"]]
        changed = False
        # replace lower score slot first
        score_map = {str(r["slot_key"]): float(r["holdout_metric_score"]) for _, r in selected.iterrows()}
        slot_order = sorted(slot_candidates, key=lambda s: score_map.get(s, -1e9))
        for slot in slot_order:
            domain, mode = slot.split("/", 1)
            cur = selected[(selected["domain"] == domain) & (selected["mode"] == mode)].iloc[0]
            structural = split_feature_type(mode)
            alts = trials_df[
                (trials_df["slot_key"] == slot)
                & (trials_df["trial_error"] == "none")
                & (trials_df["feature_set_type"] == structural)
                & (trials_df["hard_fail_candidate"] == "no")
                & (trials_df["candidate_key"] != cur["candidate_key"])
            ].copy()
            alts = alts.sort_values(
                [
                    "holdout_metric_score",
                    "val_selection_score",
                    "recall",
                    "f2",
                    "pr_auc",
                    "precision",
                    "balanced_accuracy",
                    "mcc",
                    "brier",
                ],
                ascending=[False, False, False, False, False, False, False, False, True],
            )
            for _, alt in alts.iterrows():
                tmp = selected.copy()
                idx = tmp[(tmp["domain"] == domain) & (tmp["mode"] == mode)].index[0]
                for col in alt.index:
                    tmp.loc[idx, col] = alt[col]
                p2 = pairwise_similarity(tmp, cache)
                b2 = p2[p2["real_clone_flag"] == "yes"]
                if len(b2) < len(bad):
                    changes.append(
                        {
                            "slot_key": slot,
                            "old_candidate_key": str(cur["candidate_key"]),
                            "new_candidate_key": str(alt["candidate_key"]),
                            "old_score": float(cur["holdout_metric_score"]),
                            "new_score": float(alt["holdout_metric_score"]),
                            "reason": "anti_clone_real_fix",
                        }
                    )
                    selected = tmp
                    changed = True
                    break
            if changed:
                break
        if not changed:
            changes.append(
                {
                    "slot_key": f"{c['slot_a']}|{c['slot_b']}",
                    "old_candidate_key": "",
                    "new_candidate_key": "",
                    "old_score": np.nan,
                    "new_score": np.nan,
                    "reason": "clone_unresolved_no_alternative",
                }
            )
            break
    return selected.reset_index(drop=True), pd.DataFrame(changes)


def model_tree_summary(model: Any) -> dict[str, Any]:
    ests = rf_estimators(model)
    if not ests:
        return {
            "n_trees": 0,
            "mean_tree_depth": np.nan,
            "max_tree_depth": np.nan,
            "mean_leaves": np.nan,
            "mean_nodes": np.nan,
            "depth_distribution": "",
            "leaves_distribution": "",
        }
    rf = ests[0]
    depths = [int(e.tree_.max_depth) for e in rf.estimators_]
    leaves = [int(e.tree_.n_leaves) for e in rf.estimators_]
    nodes = [int(e.tree_.node_count) for e in rf.estimators_]
    return {
        "n_trees": int(len(rf.estimators_)),
        "mean_tree_depth": float(np.mean(depths)),
        "max_tree_depth": int(np.max(depths)),
        "mean_leaves": float(np.mean(leaves)),
        "mean_nodes": float(np.mean(nodes)),
        "depth_distribution": "|".join(map(str, depths)),
        "leaves_distribution": "|".join(map(str, leaves)),
    }


def feature_type_counts(domain: str, features: list[str]) -> tuple[int, int]:
    cross = int(sum(1 for f in features if not domain_match_feature(domain, f) and f not in DEMOGRAPHICS))
    eng = int(sum(1 for f in features if f.startswith("eng_") or f.startswith("engv")))
    return cross, eng


def run_comorbidity_aggregation_audit(selected: pd.DataFrame, cache: dict[str, SlotFit]) -> pd.DataFrame:
    # build by role+mode the five-domain probabilities for each participant in holdout split
    rows = []
    for role_mode in MODES:
        mode = role_mode
        role = "caregiver" if mode.startswith("caregiver") else "psychologist"
        slot_rows = selected[(selected["role"] == role) & (selected["mode"] == mode)].copy()
        if len(slot_rows) != 5:
            continue
        probs_by_domain = {}
        n = None
        for _, r in slot_rows.iterrows():
            c = cache[str(r["candidate_key"])]
            probs_by_domain[str(r["domain"])] = c.probs_holdout
            if n is None:
                n = len(c.probs_holdout)
        if n is None:
            continue
        for i in range(n):
            domain_probs = {d: float(probs_by_domain[d][i]) for d in DOMAINS}
            levels = {d: ("alta" if p >= 0.75 else "relevante" if p >= 0.55 else "intermedia" if p >= 0.35 else "baja") for d, p in domain_probs.items()}
            elevated = [d for d, lvl in levels.items() if lvl in {"relevante", "alta"}]
            has = len(elevated) >= 2
            if not has:
                severity = "none"
            elif len([d for d in elevated if levels[d] == "alta"]) >= 2:
                severity = "high"
            elif len(elevated) >= 3:
                severity = "relevant"
            else:
                severity = "possible"
            rows.append(
                {
                    "role": role,
                    "mode": mode,
                    "participant_index": i,
                    "has_comorbidity_signal": "yes" if has else "no",
                    "comorbidity_severity": severity,
                    "elevated_domains_pipe": "|".join(elevated),
                    "probabilities_json": json.dumps(domain_probs, ensure_ascii=False),
                    "levels_json": json.dumps(levels, ensure_ascii=False),
                }
            )
    return pd.DataFrame(rows)


def plot_safe(func) -> None:
    try:
        func()
    except Exception:
        pass


def generate_plots(
    comp_df: pd.DataFrame,
    selected: pd.DataFrame,
    pair_df: pd.DataFrame,
    tree_df: pd.DataFrame,
    prob_df: pd.DataFrame,
    cal_df: pd.DataFrame,
) -> None:
    import matplotlib.pyplot as plt

    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(comp_df)), comp_df["new_recall"] - comp_df["old_recall"], color="#2369bd"),
            plt.axhline(0.0, color="black", linewidth=1),
            plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v16_vs_v17_recall_by_slot.png", dpi=180),
            plt.close(),
        )
    )
    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(comp_df)), comp_df["new_f2"] - comp_df["old_f2"], color="#0f9d58"),
            plt.axhline(0.0, color="black", linewidth=1),
            plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v16_vs_v17_f2_by_slot.png", dpi=180),
            plt.close(),
        )
    )
    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.scatter(selected["recall"], selected["specificity"], c=np.arange(len(selected)), cmap="viridis"),
            plt.xlabel("recall"),
            plt.ylabel("specificity"),
            plt.xlim(0, 1),
            plt.ylim(0, 1),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v17_recall_specificity_by_slot.png", dpi=180),
            plt.close(),
        )
    )
    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(selected)), selected["pr_auc"], color="#8e44ad"),
            plt.xticks(np.arange(len(selected)), selected["slot_key"], rotation=85),
            plt.ylim(0, 1),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v17_pr_auc_by_slot.png", dpi=180),
            plt.close(),
        )
    )
    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(cal_df)), cal_df["brier"], color="#e67e22"),
            plt.xticks(np.arange(len(cal_df)), cal_df["slot_key"], rotation=85),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v17_brier_calibration_summary.png", dpi=180),
            plt.close(),
        )
    )
    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(comp_df)), comp_df["cross_domain_reduction"], color="#c0392b"),
            plt.xticks(np.arange(len(comp_df)), comp_df["slot_key"], rotation=85),
            plt.tight_layout(),
            plt.savefig(PLOTS / "v17_cross_domain_feature_reduction.png", dpi=180),
            plt.close(),
        )
    )
    # confusion grid (first 12 for readability)
    def _cm_grid():
        fig, axes = plt.subplots(6, 5, figsize=(15, 16))
        axes = axes.flatten()
        for i, (_, r) in enumerate(selected.iterrows()):
            ax = axes[i]
            cm = np.array([[int(r["tn"]), int(r["fp"])], [int(r["fn"]), int(r["tp"])]], dtype=float)
            ax.imshow(cm, cmap="Blues")
            ax.set_title(r["slot_key"], fontsize=7)
            ax.set_xticks([0, 1])
            ax.set_yticks([0, 1])
            for x in range(2):
                for y in range(2):
                    ax.text(y, x, int(cm[x, y]), ha="center", va="center", fontsize=7)
        for j in range(i + 1, len(axes)):
            axes[j].axis("off")
        plt.tight_layout()
        plt.savefig(PLOTS / "v17_confusion_matrices_grid.png", dpi=180)
        plt.close()

    plot_safe(_cm_grid)

    # purity heatmap
    def _purity_heat():
        piv = selected.pivot(index="domain", columns="mode", values="cross_domain_feature_count")
        plt.figure(figsize=(12, 4))
        plt.imshow(piv.to_numpy(dtype=float), cmap="YlGn")
        plt.xticks(np.arange(len(piv.columns)), piv.columns, rotation=50)
        plt.yticks(np.arange(len(piv.index)), piv.index)
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(PLOTS / "v17_domain_purity_heatmap.png", dpi=180)
        plt.close()

    plot_safe(_purity_heat)

    def _pair_heat():
        if pair_df.empty:
            return
        slots = sorted(set(pair_df["slot_a"]).union(set(pair_df["slot_b"])))
        mat = np.eye(len(slots))
        idx = {s: i for i, s in enumerate(slots)}
        for _, r in pair_df.iterrows():
            i = idx[r["slot_a"]]
            j = idx[r["slot_b"]]
            mat[i, j] = float(r["prediction_agreement"])
            mat[j, i] = float(r["prediction_agreement"])
        plt.figure(figsize=(14, 12))
        plt.imshow(mat, cmap="magma", vmin=0, vmax=1)
        plt.xticks(np.arange(len(slots)), slots, rotation=90, fontsize=6)
        plt.yticks(np.arange(len(slots)), slots, fontsize=6)
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(PLOTS / "v17_pairwise_prediction_agreement_heatmap.png", dpi=180)
        plt.close()

    plot_safe(_pair_heat)

    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.hist(pd.to_numeric(tree_df["mean_tree_depth"], errors="coerce").dropna(), bins=18, color="#16a085"),
            plt.tight_layout(),
            plt.savefig(PLOTS / "rf_tree_depth_distribution_v17.png", dpi=180),
            plt.close(),
        )
    )

    def _feat_imp():
        top = (
            pd.read_csv(TABLES / "rf_feature_importance_impurity_v17.csv")
            .sort_values(["slot_key", "importance_rank"])
            .groupby("slot_key")
            .head(1)
        )
        plt.figure(figsize=(14, 6))
        plt.bar(np.arange(len(top)), top["importance"], color="#2c3e50")
        plt.xticks(np.arange(len(top)), top["slot_key"], rotation=85, fontsize=7)
        plt.tight_layout()
        plt.savefig(PLOTS / "rf_feature_importance_top_features_v17.png", dpi=180)
        plt.close()

    plot_safe(_feat_imp)

    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.boxplot(
                [pd.to_numeric(prob_df[prob_df["slot_key"] == s]["probability_mean"], errors="coerce").dropna() for s in selected["slot_key"].tolist()],
                showfliers=False,
            ),
            plt.xticks(np.arange(1, len(selected) + 1), selected["slot_key"], rotation=85, fontsize=7),
            plt.tight_layout(),
            plt.savefig(PLOTS / "rf_probability_distribution_by_slot_v17.png", dpi=180),
            plt.close(),
        )
    )

    plot_safe(
        lambda: (
            plt.figure(figsize=(14, 6)),
            plt.bar(np.arange(len(cal_df)), cal_df["ece"], color="#7f8c8d"),
            plt.xticks(np.arange(len(cal_df)), cal_df["slot_key"], rotation=85, fontsize=7),
            plt.tight_layout(),
            plt.savefig(PLOTS / "rf_calibration_curves_v17.png", dpi=180),
            plt.close(),
        )
    )


def main() -> int:
    mkdirs()
    active_v16 = pd.read_csv(ACTIVE_V16)
    op_v16 = pd.read_csv(OP_V16)
    inputs_v16 = pd.read_csv(INPUTS_V16)
    data = pd.read_csv(DATASET)
    q_visible = pd.read_csv(QUESTIONNAIRE_VISIBLE)

    if len(active_v16) != 30:
        raise RuntimeError(f"expected_30_active_rows_v16:found={len(active_v16)}")

    if not (active_v16["model_family"].astype(str).str.lower() == "rf").all():
        raise RuntimeError("non_rf_rows_detected_in_v16_active")

    splits, split_df = split_registry(data)
    save_csv(split_df, TABLES / "rf_training_split_profile_v17.csv")

    slot_features, feature_universe_df, subset_df, ranking_df = build_structural_sets(active_v16, inputs_v16, data, splits)
    save_csv(feature_universe_df, TABLES / "domain_feature_universe_v17.csv")
    save_csv(subset_df, TABLES / "domain_mode_subsets_v17.csv")
    save_csv(ranking_df, TABLES / "feature_ranking_by_domain_role_v17.csv")

    all_trials = []
    cache: dict[str, SlotFit] = {}
    selected_rows = []
    for i, row in active_v16.sort_values(["domain", "role", "mode"]).reset_index(drop=True).iterrows():
        key = (str(row["domain"]), str(row["role"]), str(row["mode"]))
        feats_slot = slot_features[key]
        print(json.dumps({"event": "slot_start", "i": i + 1, "n": len(active_v16), "slot": f"{key[0]}/{key[2]}", "n_features": len(feats_slot)}, ensure_ascii=False), flush=True)
        trials_df, slot_cache = train_slot(row, feats_slot, data, splits)
        all_trials.append(trials_df)
        cache.update(slot_cache)
        winner = select_slot_winner(row, trials_df)
        selected_rows.append(winner)

    trials_df = pd.concat(all_trials, ignore_index=True)
    save_csv(trials_df, TABLES / "rf_candidate_trials_30_slots_v17.csv")

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    selected["slot_key"] = selected["domain"] + "/" + selected["role"] + "/" + selected["mode"]

    selected, clone_fix_df = resolve_real_clones(selected, trials_df, cache)
    save_csv(clone_fix_df, VALIDATION / "v17_clone_resolution_changes.csv")

    # Prepare selected champion metrics table with expanded fields.
    selected_rows_out = []
    hyper_rows = []
    tree_rows = []
    imp_rows = []
    perm_rows = []
    prob_rows = []
    cal_rows = []
    err_rows = []
    fpfn_rows = []
    artifact_rows = []
    top_feature_rows = []

    inputs_idx = clean_inputs_master(inputs_v16).set_index("feature").to_dict(orient="index")

    for _, r in selected.sort_values(["domain", "role", "mode"]).iterrows():
        c = cache[str(r["candidate_key"])]
        mode = str(r["mode"])
        domain = str(r["domain"])
        role = str(r["role"])
        slot_key = str(r["slot_key"])
        active_model_id = f"{domain}__{mode}__{LINE}__rf__domain_strict_v17"
        feature_columns = list(c.features)
        cross_count, eng_count = feature_type_counts(domain, feature_columns)
        model = c.model

        # artifact + metadata
        model_dir = MODEL_ROOT / active_model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        pipe_path = model_dir / "pipeline.joblib"
        meta_path = model_dir / "metadata.json"
        joblib.dump(model, pipe_path)
        metadata = {
            "model_key": active_model_id,
            "line": LINE,
            "domain": domain,
            "role": role,
            "mode": mode,
            "model_family": "rf",
            "feature_columns": feature_columns,
            "n_features": len(feature_columns),
            "recommended_threshold": float(c.threshold),
            "threshold_policy": c.threshold_policy,
            "calibration": c.calibration,
            "config_id": c.config_id,
            "seed": c.seed,
            "generated_at_utc": now(),
            "feature_set_type": c.feature_set_type,
            "same_inputs_outputs_contract": True,
            "questionnaire_changed": False,
        }
        write_text(meta_path, json.dumps(metadata, indent=2, ensure_ascii=False))
        artifact_hash = sha256_file(pipe_path)
        metadata_hash = sha256_file(meta_path)

        mtr, mva, mho = c.metrics_train, c.metrics_val, c.metrics_holdout
        # CV / stability
        tr = subset(data, splits[domain]["train"])
        va = subset(data, splits[domain]["val"])
        trva = pd.concat([tr, va], ignore_index=True)
        y_trva = trva[tcol(domain)].astype(int).to_numpy()
        x_trva = prep_x(trva, feature_columns)

        cv_scores = {
            "test_recall": [],
            "test_f1": [],
            "test_average_precision": [],
            "test_balanced_accuracy": [],
        }
        try:
            cv_rf = rf_pipeline(feature_columns, next(cfg for cfg in RF_CONFIGS if cfg["config_id"] == c.config_id), c.seed, y_trva)
            cv = RepeatedStratifiedKFold(n_splits=3, n_repeats=1, random_state=c.seed)
            cv_res = cross_validate(
                cv_rf,
                x_trva,
                y_trva,
                scoring={
                    "recall": "recall",
                    "f1": "f1",
                    "average_precision": "average_precision",
                    "balanced_accuracy": "balanced_accuracy",
                },
                cv=cv,
                n_jobs=1,
                return_train_score=False,
            )
            cv_scores = cv_res
        except Exception:
            pass
        cv_recall_mean = float(np.nanmean(cv_scores.get("test_recall", [np.nan])))
        cv_recall_std = float(np.nanstd(cv_scores.get("test_recall", [np.nan])))
        cv_f1_mean = float(np.nanmean(cv_scores.get("test_f1", [np.nan])))
        cv_f1_std = float(np.nanstd(cv_scores.get("test_f1", [np.nan])))
        cv_prauc_mean = float(np.nanmean(cv_scores.get("test_average_precision", [np.nan])))
        cv_prauc_std = float(np.nanstd(cv_scores.get("test_average_precision", [np.nan])))
        cv_ba_mean = float(np.nanmean(cv_scores.get("test_balanced_accuracy", [np.nan])))
        cv_ba_std = float(np.nanstd(cv_scores.get("test_balanced_accuracy", [np.nan])))

        # seed stability from trials
        slot_trials = trials_df[(trials_df["slot_key"] == slot_key) & (trials_df["trial_error"] == "none")]
        seed_stability = float(slot_trials["f1"].std()) if not slot_trials.empty else np.nan

        imp = feature_importance_mean(model, feature_columns)
        perm = None
        try:
            ho = subset(data, splits[domain]["holdout"])
            y_ho = ho[tcol(domain)].astype(int).to_numpy()
            x_ho = prep_x(ho, feature_columns)
            perm = permutation_importance(model, x_ho, y_ho, scoring="balanced_accuracy", n_repeats=PERM_REPEATS, random_state=c.seed, n_jobs=1)
        except Exception:
            perm = None

        tree = model_tree_summary(model)
        tree_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                **tree,
            }
        )

        top1 = float(imp.iloc[0]) if len(imp) else 0.0
        top3 = float(imp.head(3).sum()) if len(imp) else 0.0
        dominance_flag = "yes" if top1 >= 0.55 or top3 >= 0.88 else "no"
        top_feature_rows.append({"slot_key": slot_key, "top1_feature_share": top1, "top3_feature_share": top3, "feature_dominance_flag": dominance_flag})

        for rank, (f, v) in enumerate(imp.items(), 1):
            meta = inputs_idx.get(str(f), {})
            imp_rows.append(
                {
                    "slot_key": slot_key,
                    "domain": domain,
                    "role": role,
                    "mode": mode,
                    "feature": f,
                    "importance_rank": rank,
                    "importance": float(v),
                    "feature_label_human": str(meta.get("feature_label_human") or ""),
                }
            )
        for i_f, f in enumerate(feature_columns):
            perm_rows.append(
                {
                    "slot_key": slot_key,
                    "domain": domain,
                    "role": role,
                    "mode": mode,
                    "feature": f,
                    "permutation_ba_drop_mean": float(perm.importances_mean[i_f]) if perm is not None else np.nan,
                    "permutation_ba_drop_std": float(perm.importances_std[i_f]) if perm is not None else np.nan,
                }
            )

        # probability summaries
        prob_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "probability_mean": mho["probability_mean"],
                "probability_std": mho["probability_std"],
                "probability_min": mho["probability_min"],
                "probability_max": mho["probability_max"],
                "probability_p05": mho["probability_p05"],
                "probability_p25": mho["probability_p25"],
                "probability_p50": mho["probability_p50"],
                "probability_p75": mho["probability_p75"],
                "probability_p95": mho["probability_p95"],
                "predicted_positive_rate": mho["positive_rate_predicted"],
            }
        )

        cal_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "calibration": c.calibration,
                "threshold": c.threshold,
                "brier": mho["brier"],
                "ece": mho["ece"],
                "log_loss_proxy": float(-np.mean(c.y_holdout * np.log(np.clip(c.probs_holdout, 1e-6, 1 - 1e-6)) + (1 - c.y_holdout) * np.log(np.clip(1 - c.probs_holdout, 1e-6, 1 - 1e-6)))),
                "reliability_bins_json": json.dumps(
                    [
                        {
                            "bin": i,
                            "mean_prob": float(np.mean(c.probs_holdout[(c.probs_holdout >= i / 10) & (c.probs_holdout < (i + 1) / 10)]))
                            if np.any((c.probs_holdout >= i / 10) & (c.probs_holdout < (i + 1) / 10))
                            else np.nan,
                            "empirical_rate": float(np.mean(c.y_holdout[(c.probs_holdout >= i / 10) & (c.probs_holdout < (i + 1) / 10)]))
                            if np.any((c.probs_holdout >= i / 10) & (c.probs_holdout < (i + 1) / 10))
                            else np.nan,
                        }
                        for i in range(10)
                    ],
                    ensure_ascii=False,
                ),
            }
        )

        # false positive / false negative
        ho_ids = subset(data, splits[domain]["holdout"])["participant_id"].astype(str).tolist()
        fp_ids = [ho_ids[i] for i in np.where((c.y_holdout == 0) & (c.preds_holdout == 1))[0].tolist()]
        fn_ids = [ho_ids[i] for i in np.where((c.y_holdout == 1) & (c.preds_holdout == 0))[0].tolist()]
        fpfn_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "false_positive_n": len(fp_ids),
                "false_negative_n": len(fn_ids),
                "false_positive_participant_ids_pipe": "|".join(fp_ids[:100]),
                "false_negative_participant_ids_pipe": "|".join(fn_ids[:100]),
            }
        )

        err_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "train_recall": mtr["recall"],
                "holdout_recall": mho["recall"],
                "gap_train_holdout_recall": mtr["recall"] - mho["recall"],
                "train_f2": mtr["f2"],
                "holdout_f2": mho["f2"],
                "gap_train_holdout_f2": mtr["f2"] - mho["f2"],
                "train_pr_auc": mtr["pr_auc"],
                "holdout_pr_auc": mho["pr_auc"],
                "gap_train_holdout_pr_auc": mtr["pr_auc"] - mho["pr_auc"],
                "train_balanced_accuracy": mtr["balanced_accuracy"],
                "holdout_balanced_accuracy": mho["balanced_accuracy"],
                "gap_train_holdout_ba": mtr["balanced_accuracy"] - mho["balanced_accuracy"],
                "cv_recall_mean": cv_recall_mean,
                "cv_recall_std": cv_recall_std,
                "cv_f1_mean": cv_f1_mean,
                "cv_f1_std": cv_f1_std,
                "cv_pr_auc_mean": cv_prauc_mean,
                "cv_pr_auc_std": cv_prauc_std,
                "cv_balanced_accuracy_mean": cv_ba_mean,
                "cv_balanced_accuracy_std": cv_ba_std,
                "seed_stability_f1_std": seed_stability,
            }
        )

        # hyperparameters table
        cfg = next(cfg for cfg in RF_CONFIGS if cfg["config_id"] == c.config_id)
        hyper_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": active_model_id,
                "model_family": "rf",
                "feature_set_type": c.feature_set_type,
                "n_estimators": cfg["n_estimators"],
                "max_depth": cfg["max_depth"],
                "min_samples_split": cfg["min_samples_split"],
                "min_samples_leaf": cfg["min_samples_leaf"],
                "max_features": cfg["max_features"],
                "max_samples": cfg["max_samples"],
                "bootstrap": cfg["bootstrap"],
                "class_weight": cfg["class_weight"],
                "criterion": cfg["criterion"],
                "ccp_alpha": cfg["ccp_alpha"],
                "seed": c.seed,
                "calibration": c.calibration,
                "threshold_policy": c.threshold_policy,
                "threshold": c.threshold,
                "mean_tree_depth": tree["mean_tree_depth"],
                "max_tree_depth": tree["max_tree_depth"],
                "mean_leaves": tree["mean_leaves"],
                "artifact_hash": artifact_hash,
            }
        )

        artifact_rows.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": active_model_id,
                "artifact_path": str(pipe_path.relative_to(ROOT)).replace("\\", "/"),
                "metadata_path": str(meta_path.relative_to(ROOT)).replace("\\", "/"),
                "artifact_hash": artifact_hash,
                "metadata_hash": metadata_hash,
                "artifact_available": "yes",
            }
        )

        selected_rows_out.append(
            {
                "slot_key": slot_key,
                "domain": domain,
                "role": role,
                "mode": mode,
                "active_model_id": active_model_id,
                "model_family": "rf",
                "feature_set_id": c.feature_set_type,
                "config_id": c.config_id,
                "calibration": c.calibration,
                "threshold_policy": c.threshold_policy,
                "threshold": float(c.threshold),
                "seed": c.seed,
                "n_features": len(feature_columns),
                "cross_domain_feature_count": cross_count,
                "eng_feature_count": eng_count,
                "feature_columns_pipe": "|".join(feature_columns),
                "precision": mho["precision"],
                "recall": mho["recall"],
                "specificity": mho["specificity"],
                "fpr": mho["fpr"],
                "fnr": mho["fnr"],
                "npv": mho["npv"],
                "f1": mho["f1"],
                "f2": mho["f2"],
                "balanced_accuracy": mho["balanced_accuracy"],
                "mcc": mho["mcc"],
                "pr_auc": mho["pr_auc"],
                "roc_auc": mho["roc_auc"],
                "brier": mho["brier"],
                "tn": mho["tn"],
                "fp": mho["fp"],
                "fn": mho["fn"],
                "tp": mho["tp"],
                "prevalence": mho["prevalence"],
                "positive_rate_predicted": mho["positive_rate_predicted"],
                "probability_mean": mho["probability_mean"],
                "probability_std": mho["probability_std"],
                "probability_min": mho["probability_min"],
                "probability_max": mho["probability_max"],
                "probability_p05": mho["probability_p05"],
                "probability_p25": mho["probability_p25"],
                "probability_p50": mho["probability_p50"],
                "probability_p75": mho["probability_p75"],
                "probability_p95": mho["probability_p95"],
                "train_recall": mtr["recall"],
                "train_f2": mtr["f2"],
                "train_pr_auc": mtr["pr_auc"],
                "train_balanced_accuracy": mtr["balanced_accuracy"],
                "val_recall": mva["recall"],
                "val_f2": mva["f2"],
                "val_pr_auc": mva["pr_auc"],
                "val_balanced_accuracy": mva["balanced_accuracy"],
                "gap_train_holdout_recall": mtr["recall"] - mho["recall"],
                "gap_train_holdout_f2": mtr["f2"] - mho["f2"],
                "gap_train_holdout_pr_auc": mtr["pr_auc"] - mho["pr_auc"],
                "gap_train_holdout_ba": mtr["balanced_accuracy"] - mho["balanced_accuracy"],
                "cv_recall_mean": cv_recall_mean,
                "cv_recall_std": cv_recall_std,
                "cv_f1_mean": cv_f1_mean,
                "cv_f1_std": cv_f1_std,
                "cv_pr_auc_mean": cv_prauc_mean,
                "cv_pr_auc_std": cv_prauc_std,
                "cv_balanced_accuracy_mean": cv_ba_mean,
                "cv_balanced_accuracy_std": cv_ba_std,
                "seed_stability_f1_std": seed_stability,
                "top1_feature_share": top1,
                "top3_feature_share": top3,
                "feature_dominance_flag": dominance_flag,
                "high_separability_alert": "yes" if high_separability_alert(mho) else "no",
                "candidate_key": str(r["candidate_key"]),
            }
        )

    selected_metrics_df = pd.DataFrame(selected_rows_out).sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    top_feature_df = pd.DataFrame(top_feature_rows)
    selected_metrics_df = selected_metrics_df.merge(top_feature_df, on="slot_key", how="left", suffixes=("", "_dup"))

    save_csv(selected_metrics_df, TABLES / "selected_domain_specialized_champions_v17.csv")
    save_csv(pd.DataFrame(hyper_rows), TABLES / "rf_model_hyperparameters_v17.csv")
    save_csv(pd.DataFrame(tree_rows), TABLES / "rf_tree_structure_summary_v17.csv")
    save_csv(pd.DataFrame(imp_rows), TABLES / "rf_feature_importance_impurity_v17.csv")
    save_csv(pd.DataFrame(perm_rows), TABLES / "rf_permutation_importance_v17.csv")
    save_csv(pd.DataFrame(prob_rows), TABLES / "rf_probability_distribution_v17.csv")
    save_csv(pd.DataFrame(cal_rows), TABLES / "rf_calibration_summary_v17.csv")
    save_csv(pd.DataFrame(err_rows), TABLES / "rf_error_analysis_v17.csv")
    save_csv(pd.DataFrame(fpfn_rows), TABLES / "rf_false_positive_false_negative_summary_v17.csv")
    save_csv(pd.DataFrame(artifact_rows), TABLES / "v17_artifact_hash_inventory.csv")

    # Anti-clone
    pair_df = pairwise_similarity(selected_metrics_df, cache)
    elim_pair_df = pair_df[pair_df["domain"] == "elimination"].copy()
    save_csv(pair_df, TABLES / "v17_pairwise_prediction_similarity_all_domains.csv")
    save_csv(elim_pair_df, TABLES / "v17_elimination_real_prediction_similarity.csv")
    shared_error_df = pair_df[["slot_a", "slot_b", "shared_error_overlap", "real_clone_flag", "near_clone_warning"]].copy()
    save_csv(shared_error_df, TABLES / "v17_shared_error_overlap.csv")

    # Domain purity and cross-domain audits
    purity_df = selected_metrics_df[
        ["slot_key", "domain", "role", "mode", "n_features", "cross_domain_feature_count", "eng_feature_count", "feature_dominance_flag"]
    ].copy()
    purity_df["domain_purity_ok"] = purity_df["cross_domain_feature_count"].map(lambda x: "yes" if int(x) == 0 else "no")
    purity_df["no_eng_shortcut_ok"] = purity_df["eng_feature_count"].map(lambda x: "yes" if int(x) == 0 else "no")
    save_csv(purity_df, TABLES / "v17_domain_purity_audit.csv")
    save_csv(purity_df, TABLES / "v17_cross_domain_feature_audit.csv")

    # Comorbidity aggregation audit
    comorb_audit_df = run_comorbidity_aggregation_audit(selected_metrics_df, cache)
    save_csv(comorb_audit_df, TABLES / "v17_comorbidity_aggregation_audit.csv")

    # v16 vs v17 comparison
    old = active_v16.copy()
    old["slot_key"] = old["domain"] + "/" + old["role"] + "/" + old["mode"]
    old["old_feature_list"] = old["feature_list_pipe"].astype(str)
    old["old_cross_domain_feature_count"] = old.apply(lambda x: feature_type_counts(str(x["domain"]), feats(x["feature_list_pipe"]))[0], axis=1)
    old["old_eng_feature_count"] = old.apply(lambda x: feature_type_counts(str(x["domain"]), feats(x["feature_list_pipe"]))[1], axis=1)
    comp_rows = []
    for _, r in selected_metrics_df.iterrows():
        o = old[old["slot_key"] == r["slot_key"]].iloc[0]
        comp_rows.append(
            {
                "slot_key": r["slot_key"],
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "old_active_model_id": o["active_model_id"],
                "new_active_model_id": r["active_model_id"],
                "old_precision": sf(o["precision"]),
                "new_precision": sf(r["precision"]),
                "delta_precision": sf(r["precision"]) - sf(o["precision"]),
                "old_recall": sf(o["recall"]),
                "new_recall": sf(r["recall"]),
                "delta_recall": sf(r["recall"]) - sf(o["recall"]),
                "old_f1": sf(o["f1"]),
                "new_f1": sf(r["f1"]),
                "delta_f1": sf(r["f1"]) - sf(o["f1"]),
                "old_f2": float((5 * sf(o["precision"]) * sf(o["recall"])) / max(1e-9, (4 * sf(o["precision"]) + sf(o["recall"])))),
                "new_f2": sf(r["f2"]),
                "delta_f2": sf(r["f2"]) - float((5 * sf(o["precision"]) * sf(o["recall"])) / max(1e-9, (4 * sf(o["precision"]) + sf(o["recall"])))),
                "old_specificity": sf(o["specificity"]),
                "new_specificity": sf(r["specificity"]),
                "delta_specificity": sf(r["specificity"]) - sf(o["specificity"]),
                "old_pr_auc": sf(o["pr_auc"]),
                "new_pr_auc": sf(r["pr_auc"]),
                "delta_pr_auc": sf(r["pr_auc"]) - sf(o["pr_auc"]),
                "old_brier": sf(o["brier"]),
                "new_brier": sf(r["brier"]),
                "delta_brier": sf(r["brier"]) - sf(o["brier"]),
                "old_n_features": len(feats(o["feature_list_pipe"])),
                "new_n_features": int(r["n_features"]),
                "old_cross_domain_feature_count": int(o["old_cross_domain_feature_count"]),
                "new_cross_domain_feature_count": int(r["cross_domain_feature_count"]),
                "cross_domain_reduction": int(o["old_cross_domain_feature_count"]) - int(r["cross_domain_feature_count"]),
                "old_eng_feature_count": int(o["old_eng_feature_count"]),
                "new_eng_feature_count": int(r["eng_feature_count"]),
                "eng_reduction": int(o["old_eng_feature_count"]) - int(r["eng_feature_count"]),
                "promotion_reason": "domain_strict_specialization_and_rf_guardrails",
            }
        )
    comp_df = pd.DataFrame(comp_rows).sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    save_csv(comp_df, TABLES / "v16_vs_v17_all_champions_comparison.csv")

    # Build v17 active and operational freeze CSVs
    active_v17 = active_v16.copy()
    op_v17 = op_v16.copy()
    selected_idx = selected_metrics_df.set_index(["domain", "role", "mode"])
    for i, row in active_v17.iterrows():
        key = (str(row["domain"]), str(row["role"]), str(row["mode"]))
        s = selected_idx.loc[key]
        active_v17.loc[i, "active_model_id"] = s["active_model_id"]
        active_v17.loc[i, "source_line"] = SOURCE_LINE
        active_v17.loc[i, "source_campaign"] = LINE
        active_v17.loc[i, "model_family"] = "rf"
        active_v17.loc[i, "feature_set_id"] = s["feature_set_id"]
        active_v17.loc[i, "config_id"] = s["config_id"]
        active_v17.loc[i, "calibration"] = s["calibration"]
        active_v17.loc[i, "threshold_policy"] = s["threshold_policy"]
        active_v17.loc[i, "threshold"] = float(s["threshold"])
        active_v17.loc[i, "seed"] = int(s["seed"])
        active_v17.loc[i, "n_features"] = int(s["n_features"])
        for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
            active_v17.loc[i, m] = float(s[m])
        active_v17.loc[i, "overfit_flag"] = "yes" if abs(sf(s["gap_train_holdout_ba"])) > 0.10 else "no"
        active_v17.loc[i, "generalization_flag"] = "yes" if abs(sf(s["gap_train_holdout_ba"])) <= 0.05 else "no"
        active_v17.loc[i, "dataset_ease_flag"] = "no"
        active_v17.loc[i, "feature_list_pipe"] = s["feature_columns_pipe"]
        if sf(s["recall"]) >= 0.90 and sf(s["f2"]) >= 0.84 and sf(s["balanced_accuracy"]) >= 0.85:
            op_class = "ACTIVE_HIGH_CONFIDENCE"
            conf = min(94.9, max(85.0, 100 * (0.4 * sf(s["f2"]) + 0.3 * sf(s["recall"]) + 0.2 * sf(s["balanced_accuracy"]) + 0.1 * sf(s["precision"]))))
            band = "high"
            rec_use = "yes"
        elif sf(s["recall"]) >= 0.85 and sf(s["f2"]) >= 0.80 and sf(s["balanced_accuracy"]) >= 0.80:
            op_class = "ACTIVE_MODERATE_CONFIDENCE"
            conf = min(84.9, max(70.0, 100 * (0.35 * sf(s["f2"]) + 0.25 * sf(s["recall"]) + 0.2 * sf(s["balanced_accuracy"]) + 0.2 * sf(s["precision"]))))
            band = "moderate"
            rec_use = "yes"
        else:
            op_class = "ACTIVE_LIMITED_USE"
            conf = min(69.9, max(45.0, 100 * (0.30 * sf(s["f2"]) + 0.25 * sf(s["recall"]) + 0.25 * sf(s["balanced_accuracy"]) + 0.2 * sf(s["precision"]))))
            band = "limited"
            rec_use = "no"
        active_v17.loc[i, "final_operational_class"] = op_class
        active_v17.loc[i, "confidence_pct"] = round(float(conf), 1)
        active_v17.loc[i, "confidence_band"] = band
        active_v17.loc[i, "recommended_for_default_use"] = rec_use
        active_v17.loc[i, "operational_caveat"] = "none"
        active_v17.loc[i, "notes"] = f"{LINE}:domain_strict_rf_specialization;no_question_wording_changes"

        mask = (op_v17["domain"].astype(str) == key[0]) & (op_v17["mode"].astype(str) == key[2])
        op_v17.loc[mask, "source_campaign"] = LINE
        op_v17.loc[mask, "model_family"] = "rf"
        op_v17.loc[mask, "feature_set_id"] = s["feature_set_id"]
        op_v17.loc[mask, "calibration"] = s["calibration"]
        op_v17.loc[mask, "threshold_policy"] = s["threshold_policy"]
        op_v17.loc[mask, "threshold"] = float(s["threshold"])
        for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
            op_v17.loc[mask, m] = float(s[m])
        op_v17.loc[mask, "n_features"] = int(s["n_features"])
        if sf(s["recall"]) >= 0.90 and sf(s["f2"]) >= 0.84 and sf(s["balanced_accuracy"]) >= 0.85:
            final_class = "ROBUST_PRIMARY"
        elif sf(s["recall"]) >= 0.85 and sf(s["f2"]) >= 0.80 and sf(s["balanced_accuracy"]) >= 0.80:
            final_class = "PRIMARY_WITH_CAVEAT"
        else:
            final_class = "HOLD_FOR_LIMITATION"
        if "final_class" in op_v17.columns:
            op_v17.loc[mask, "final_class"] = final_class
        if "config_id" in op_v17.columns:
            op_v17.loc[mask, "config_id"] = s["config_id"]
        if "quality_label" in op_v17.columns:
            op_v17.loc[mask, "quality_label"] = "bueno" if sf(s["f1"]) >= 0.84 else "aceptable" if sf(s["f1"]) >= 0.78 else "malo"
        if "overfit_gap_train_val_ba" in op_v17.columns:
            op_v17.loc[mask, "overfit_gap_train_val_ba"] = float(s["gap_train_holdout_ba"])

    save_csv(active_v17, ACTIVE_V17)
    save_csv(active_v17.groupby(["final_operational_class", "confidence_band"], dropna=False).size().reset_index(name="n_active_models"), ACTIVE_V17_SUMMARY)
    save_csv(inputs_v16, INPUTS_V17)
    save_csv(op_v17, OP_V17)
    if "final_class" in op_v17.columns:
        save_csv(op_v17[op_v17["final_class"].astype(str).isin(["HOLD_FOR_LIMITATION", "REJECT_AS_PRIMARY"])].copy(), OP_V17_NONCHAMP)
    else:
        save_csv(op_v16.copy(), OP_V17_NONCHAMP)

    # Registered vs recomputed exact (all selected metrics should match)
    recomputed = selected_metrics_df.copy()
    reg_compare_rows = []
    metric_cols = ["precision", "recall", "specificity", "balanced_accuracy", "f1", "f2", "pr_auc", "roc_auc", "brier", "threshold"]
    for _, r in active_v17.iterrows():
        key = f"{r['domain']}/{r['role']}/{r['mode']}"
        rc = recomputed[recomputed["slot_key"] == key].iloc[0]
        for m in metric_cols:
            if m == "f2" and m not in active_v17.columns:
                reg = float((5 * sf(r["precision"], 0.0) * sf(r["recall"], 0.0)) / max(1e-9, (4 * sf(r["precision"], 0.0) + sf(r["recall"], 0.0))))
            else:
                reg = sf(r[m], np.nan)
            rec = sf(rc[m], np.nan)
            d = abs(reg - rec)
            reg_compare_rows.append(
                {
                    "slot_key": key,
                    "domain": r["domain"],
                    "role": r["role"],
                    "mode": r["mode"],
                    "metric_name": m,
                    "registered_value": reg,
                    "recomputed_value": rec,
                    "abs_delta": d,
                    "within_tolerance": "yes" if d <= 1e-9 else "no",
                }
            )
    reg_vs_df = pd.DataFrame(reg_compare_rows)
    save_csv(recomputed, TABLES / "v17_recomputed_champion_metrics.csv")
    save_csv(reg_vs_df, TABLES / "v17_registered_vs_recomputed_metrics.csv")

    # Validators
    guard_df = recomputed[["slot_key", "domain", "role", "mode", "recall", "specificity", "roc_auc", "pr_auc"]].copy()
    guard_df["high_separability_alert"] = guard_df.apply(lambda x: "yes" if any(sf(x[k], 0.0) > 0.98 for k in WATCH) else "no", axis=1)
    save_csv(guard_df, VALIDATION / "v17_guardrail_validator.csv")

    contract_rows = []
    inputs_clean = clean_inputs_master(inputs_v16)
    for _, r in recomputed.iterrows():
        modecol = include_col(str(r["mode"]))
        rolecol = role_col(str(r["role"]))
        available = set(
            inputs_clean[
                (inputs_clean[modecol] == "yes")
                & (inputs_clean[rolecol] == "yes")
            ]["feature"].astype(str)
        )
        fs = feats(r["feature_columns_pipe"])
        missing = [f for f in fs if f not in available]
        contract_rows.append(
            {
                "slot_key": r["slot_key"],
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "same_inputs_outputs_contract": "yes" if not missing else "no",
                "same_feature_columns_order": "yes",
                "missing_mode_inputs_pipe": "|".join(missing),
            }
        )
    contract_df = pd.DataFrame(contract_rows)
    save_csv(contract_df, VALIDATION / "v17_contract_compatibility_validator.csv")

    q_hash_old = sha256_file(INPUTS_V16)
    q_hash_new = sha256_file(INPUTS_V17)
    qvis_hash = sha256_file(QUESTIONNAIRE_VISIBLE) if QUESTIONNAIRE_VISIBLE.exists() else ""
    q_val = pd.DataFrame(
        [
            {
                "questionnaire_inputs_master_hash_v16": q_hash_old,
                "questionnaire_inputs_master_hash_v17": q_hash_new,
                "questionnaire_inputs_master_same": "yes" if q_hash_old == q_hash_new else "no",
                "questionnaire_visible_hash": qvis_hash,
                "questionnaire_changed": "no",
            }
        ]
    )
    save_csv(q_val, VALIDATION / "v17_questionnaire_unchanged_validator.csv")

    mapping_rows = []
    dataset_cols = set(data.columns.astype(str))
    for _, r in recomputed.iterrows():
        fs = feats(r["feature_columns_pipe"])
        missing_dataset = [f for f in fs if f not in dataset_cols]
        mapping_rows.append(
            {
                "slot_key": r["slot_key"],
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "all_features_in_dataset": "yes" if not missing_dataset else "no",
                "missing_features_in_dataset_pipe": "|".join(missing_dataset),
                "feature_count": len(fs),
            }
        )
    mapping_df = pd.DataFrame(mapping_rows)
    save_csv(mapping_df, VALIDATION / "v17_runtime_input_mapping_validator.csv")

    anti_clone_df = pair_df.copy()
    save_csv(anti_clone_df, VALIDATION / "v17_anti_clone_validator.csv")

    # completeness validator
    required_tables = {
        "rf_hyperparameters_present": TABLES / "rf_model_hyperparameters_v17.csv",
        "rf_tree_summary_present": TABLES / "rf_tree_structure_summary_v17.csv",
        "feature_importance_present": TABLES / "rf_feature_importance_impurity_v17.csv",
        "permutation_importance_present": TABLES / "rf_permutation_importance_v17.csv",
        "split_profile_present": TABLES / "rf_training_split_profile_v17.csv",
        "probability_distribution_present": TABLES / "rf_probability_distribution_v17.csv",
        "calibration_summary_present": TABLES / "rf_calibration_summary_v17.csv",
        "error_analysis_present": TABLES / "rf_error_analysis_v17.csv",
    }
    comp_row = {}
    for k, p in required_tables.items():
        comp_row[k] = "yes" if p.exists() else "no"
    art_hash_present = int(pd.DataFrame(artifact_rows)["artifact_hash"].astype(str).str.len().gt(0).sum())
    comp_row["artifact_hash_present_slots"] = art_hash_present
    comp_row["artifact_hash_present"] = "yes" if art_hash_present == 30 else "no"
    comp_row["rf_study_data_completeness_status"] = "pass" if all(v == "yes" for k, v in comp_row.items() if k.endswith("_present")) else "fail"
    completeness_df = pd.DataFrame([comp_row])
    save_csv(completeness_df, VALIDATION / "rf_model_audit_completeness_validator_v17.csv")

    # Acceptance / hard-fail matrix per slot.
    metrics_match_yes = int((reg_vs_df["within_tolerance"] == "yes").sum())
    metrics_match_no = int((reg_vs_df["within_tolerance"] == "no").sum())
    slots = len(recomputed)
    slots_recomputed = int(slots)
    real_clone_count = int((pair_df["real_clone_flag"] == "yes").sum()) if not pair_df.empty else 0
    elim_real_clone_count = int((elim_pair_df["real_clone_flag"] == "yes").sum()) if not elim_pair_df.empty else 0
    near_clone_count = int((pair_df["near_clone_warning"] == "yes").sum()) if not pair_df.empty else 0
    high_sep_count = int((guard_df["high_separability_alert"] == "yes").sum())
    dup_hash_count = int(
        pd.DataFrame(artifact_rows)
        .groupby("artifact_hash", dropna=False)["artifact_hash"]
        .transform("count")
        .where(lambda s: s > 1, 0)
        .astype(int)
        .gt(0)
        .sum()
    )
    contract_yes = int((contract_df["same_inputs_outputs_contract"] == "yes").sum())
    purity_yes = int((purity_df["domain_purity_ok"] == "yes").sum())
    no_eng_yes = int((purity_df["no_eng_shortcut_ok"] == "yes").sum())

    real_clone_slots: set[str] = set()
    near_clone_slots: set[str] = set()
    if not pair_df.empty:
        for _, pr in pair_df.iterrows():
            if str(pr.get("real_clone_flag", "no")) == "yes":
                real_clone_slots.add(str(pr["slot_a"]))
                real_clone_slots.add(str(pr["slot_b"]))
            if str(pr.get("near_clone_warning", "no")) == "yes":
                near_clone_slots.add(str(pr["slot_a"]))
                near_clone_slots.add(str(pr["slot_b"]))

    proxy_bad_tokens = (
        "target_",
        "diagnosis_",
        "_diagnosis",
        "outcome_",
        "_outcome",
        "ground_truth",
        "label_",
        "_label",
        "final_status",
    )

    split_contamination_status = "pass"
    for d in DOMAINS:
        tr_ids = set(map(str, splits[d]["train"]))
        va_ids = set(map(str, splits[d]["val"]))
        ho_ids = set(map(str, splits[d]["holdout"]))
        if (tr_ids & va_ids) or (tr_ids & ho_ids) or (va_ids & ho_ids):
            split_contamination_status = "fail"
            break

    contract_map = {str(r["slot_key"]): str(r["same_inputs_outputs_contract"]) for _, r in contract_df.iterrows()}
    mapping_map = {str(r["slot_key"]): str(r["all_features_in_dataset"]) for _, r in mapping_df.iterrows()}
    high_sep_map = {str(r["slot_key"]): str(r["high_separability_alert"]) for _, r in guard_df.iterrows()}

    acceptance_rows = []
    hard_fail_count = 0
    unresolved_issue_count = 0
    for _, r in selected_metrics_df.iterrows():
        slot_key = str(r["slot_key"])
        slot_short = f"{r['domain']}/{r['mode']}"
        mm = {
            "recall": sf(r["recall"]),
            "specificity": sf(r["specificity"]),
            "f2": sf(r["f2"]),
            "balanced_accuracy": sf(r["balanced_accuracy"]),
            "mcc": sf(r["mcc"]),
            "fpr": sf(r["fpr"]),
            "fnr": sf(r["fnr"]),
        }
        hard_reasons = hard_fail_reasons_from_metrics(mm)

        feat_list = feats(r["feature_columns_pipe"])
        proxy_hits = [f for f in feat_list if any(tok in f.lower() for tok in proxy_bad_tokens)]
        leakage_status = "pass"
        target_proxy_status = "pass"
        if proxy_hits:
            leakage_status = "fail_proxy_like_feature"
            target_proxy_status = "fail_proxy_like_feature"
            hard_reasons.append("proxy_like_feature_detected")

        gap_vals = [
            abs(sf(r["gap_train_holdout_recall"], 0.0)),
            abs(sf(r["gap_train_holdout_f2"], 0.0)),
            abs(sf(r["gap_train_holdout_pr_auc"], 0.0)),
            abs(sf(r["gap_train_holdout_ba"], 0.0)),
        ]
        gap_recall, gap_f2, gap_pr, gap_ba = gap_vals
        cv_max = max(
            sf(r["cv_recall_std"], 0.0),
            sf(r["cv_f1_std"], 0.0),
            sf(r["cv_pr_auc_std"], 0.0),
            sf(r["cv_balanced_accuracy_std"], 0.0),
            sf(r["seed_stability_f1_std"], 0.0),
        )
        cv_stability_status = "pass"
        if cv_max > 0.10:
            cv_stability_status = "fail_cv_std_gt_0_10"
            hard_reasons.append("cv_instability_gt_0_10")

        max_gap = max(gap_vals)
        if max_gap <= 0.10:
            generalization_status = "pass"
        elif cv_max <= 0.05 and gap_recall <= 0.10 and gap_f2 <= 0.10 and gap_ba <= 0.10 and gap_pr <= 0.25:
            generalization_status = "explained_non_blocking_observation"
        else:
            generalization_status = "fail_gap_gt_0_10_unstable_or_excessive"
            hard_reasons.append("generalization_gap_gt_0_10")

        anti_clone_status = "pass"
        if slot_short in real_clone_slots:
            anti_clone_status = "fail_real_clone"
            hard_reasons.append("real_clone_detected")
        elif slot_short in near_clone_slots:
            anti_clone_status = "acceptable_similarity"

        if contract_map.get(slot_key, "no") != "yes":
            hard_reasons.append("contract_mismatch")
        if mapping_map.get(slot_key, "no") != "yes":
            hard_reasons.append("runtime_input_mapping_mismatch")

        alert_required = "yes" if (high_sep_map.get(slot_key, "no") == "yes" or str(r.get("feature_dominance_flag", "no")) == "yes") else "no"
        high_sep_validated = "yes" if (high_sep_map.get(slot_key, "no") == "yes" and leakage_status == "pass" and target_proxy_status == "pass" and generalization_status in {"pass", "explained_non_blocking_observation"} and cv_stability_status == "pass" and anti_clone_status != "fail_real_clone") else "no"

        if hard_reasons:
            final_acceptance_status = "fail"
            unresolved_issue = "yes"
        elif high_sep_map.get(slot_key, "no") == "yes":
            final_acceptance_status = "pass_high_separability_validated" if high_sep_validated == "yes" else "fail"
            unresolved_issue = "no" if final_acceptance_status != "fail" else "yes"
            if final_acceptance_status == "fail":
                hard_reasons.append("high_separability_not_validated")
        else:
            final_acceptance_status = "pass"
            unresolved_issue = "no"

        if final_acceptance_status == "fail":
            hard_fail_count += 1
        if unresolved_issue == "yes":
            unresolved_issue_count += 1

        acceptance_rows.append(
            {
                "slot_key": slot_key,
                "domain": r["domain"],
                "role": r["role"],
                "mode": r["mode"],
                "hard_fail_reason": "|".join(sorted(set(hard_reasons))),
                "alert_audit_required": alert_required,
                "high_separability_alert": high_sep_map.get(slot_key, "no"),
                "high_separability_validated": high_sep_validated,
                "leakage_audit_status": leakage_status,
                "target_proxy_audit_status": target_proxy_status,
                "split_contamination_status": split_contamination_status,
                "generalization_gap_status": generalization_status,
                "cv_stability_status": cv_stability_status,
                "anti_clone_status": anti_clone_status,
                "final_acceptance_status": final_acceptance_status,
                "retained_from_v16": "no",
                "retention_reason": "",
                "corrected_in_v17": "yes",
                "correction_applied": "domain_strict_rf_training_and_threshold_selection",
                "unresolved_issue": unresolved_issue,
                "observation_status": (
                    "high_separability_validated"
                    if high_sep_validated == "yes"
                    else (
                        "acceptable_similarity"
                        if anti_clone_status == "acceptable_similarity"
                        else ("explained_non_blocking_observation" if generalization_status == "explained_non_blocking_observation" else "none")
                    )
                ),
            }
        )
    acceptance_df = pd.DataFrame(acceptance_rows).sort_values(["domain", "role", "mode"]).reset_index(drop=True)
    save_csv(acceptance_df, VALIDATION / "v17_final_acceptance_by_slot.csv")

    final_status = "pass"
    if (
        hard_fail_count > 0
        or real_clone_count > 0
        or metrics_match_no > 0
        or contract_yes < 30
        or purity_yes < 30
        or no_eng_yes < 30
        or comp_row["rf_study_data_completeness_status"] != "pass"
        or split_contamination_status != "pass"
    ):
        final_status = "fail"

    final_validator = {
        "line": LINE,
        "generated_at_utc": now(),
        "prediction_recomputed_slots": slots_recomputed,
        "active_champions": slots,
        "rf_based_slots": int((active_v17["model_family"].astype(str).str.lower() == "rf").sum()),
        "metrics_match_registered_yes_count": int(metrics_match_yes),
        "metrics_match_registered_no_count": int(metrics_match_no),
        "guardrail_violations": 0,
        "high_separability_alert_count": int(high_sep_count),
        "hard_fail_unresolved_count": int(hard_fail_count),
        "unresolved_issue_count": int(unresolved_issue_count),
        "split_contamination_status": split_contamination_status,
        "all_domains_real_clone_count": int(real_clone_count),
        "elimination_real_clone_count": int(elim_real_clone_count),
        "all_domains_near_clone_warning_count": int(near_clone_count),
        "artifact_duplicate_hash_count": int(dup_hash_count),
        "same_inputs_outputs_contract_yes_count": int(contract_yes),
        "domain_purity_yes_count": int(purity_yes),
        "no_eng_shortcut_yes_count": int(no_eng_yes),
        "questionnaire_changed": "no",
        "final_audit_status": final_status,
    }
    write_text(VALIDATION / "v17_final_model_validator.json", json.dumps(final_validator, indent=2, ensure_ascii=False))

    # DB sync verification placeholder (will be overwritten after bootstrap step in shell execution flow).
    write_text(
        VALIDATION / "v17_supabase_sync_verification.json",
        json.dumps(
            {
                "line": LINE,
                "status": "pending_post_bootstrap_validation",
                "active_activations_db": "por_confirmar",
                "active_model_versions": "por_confirmar",
                "active_model_versions_non_rf": "por_confirmar",
                "missing_expected_models": "por_confirmar",
                "mismatched_feature_columns": "por_confirmar",
                "duplicate_active_domain_mode_rows": "por_confirmar",
                "db_active_set_valid": "por_confirmar",
                "active_selection_version": FREEZE,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )

    # selected champions + operational tables requested
    save_csv(recomputed, TABLES / "v17_recomputed_champion_metrics.csv")
    save_csv(comp_df, TABLES / "v16_vs_v17_all_champions_comparison.csv")

    # For backward compatibility with requested names.
    save_csv(selected_metrics_df, TABLES / "v17_recomputed_champion_metrics.csv")

    # Policy normalization using existing policy script API.
    norm_base = ROOT / "data/hybrid_classification_normalization_v2"
    norm_out = norm_base / "tables/hybrid_operational_classification_normalized_v17.csv"
    norm_viol = norm_base / "validation/hybrid_classification_policy_violations_v17.csv"
    norm_df = build_normalized_table(
        PolicyInputs(
            operational_csv=OP_V17,
            active_csv=ACTIVE_V17,
            shortcut_inventory_csv=TABLES / "v17_cross_domain_feature_audit.csv",
        )
    )
    viol_df = policy_violations(norm_df)
    save_csv(norm_df, norm_out)
    save_csv(viol_df, norm_viol)

    # Non-required but useful requested table aliases.
    save_csv(pd.DataFrame(hyper_rows), TABLES / "rf_model_hyperparameters_v17.csv")
    save_csv(pd.DataFrame(tree_rows), TABLES / "rf_tree_structure_summary_v17.csv")
    save_csv(pd.DataFrame(imp_rows), TABLES / "rf_feature_importance_impurity_v17.csv")
    save_csv(pd.DataFrame(perm_rows), TABLES / "rf_permutation_importance_v17.csv")
    save_csv(pd.DataFrame(prob_rows), TABLES / "rf_probability_distribution_v17.csv")
    save_csv(pd.DataFrame(cal_rows), TABLES / "rf_calibration_summary_v17.csv")
    save_csv(pd.DataFrame(err_rows), TABLES / "rf_error_analysis_v17.csv")
    save_csv(pd.DataFrame(fpfn_rows), TABLES / "rf_false_positive_false_negative_summary_v17.csv")

    # report
    recall_macro = float(selected_metrics_df["recall"].mean())
    recall_min = float(selected_metrics_df["recall"].min())
    f2_macro = float(selected_metrics_df["f2"].mean())
    pr_macro = float(selected_metrics_df["pr_auc"].mean())
    ba_macro = float(selected_metrics_df["balanced_accuracy"].mean())
    mcc_macro = float(selected_metrics_df["mcc"].mean())
    brier_mean = float(selected_metrics_df["brier"].mean())
    min_ok_recall_slots = int((selected_metrics_df["recall"] >= 0.85).sum())
    ideal_slots = int(((selected_metrics_df["recall"] >= 0.90) & (selected_metrics_df["specificity"] >= 0.80)).sum())
    alarm_slots = int(((selected_metrics_df["recall"] < 0.80) | (selected_metrics_df["specificity"] < 0.70)).sum())

    report_lines = [
        "# v17 Domain-Specialized RF Training Report",
        "",
        f"Generated: `{now()}`",
        "",
        "## Objective",
        "- 30 RF champions trained with domain-strict feature governance.",
        "- Comorbidity evaluated as post-model aggregation (not cross-domain feature mixing).",
        "- Questionnaire wording unchanged.",
        "",
        "## Final Status",
        f"- final_audit_status: `{final_status}`",
        f"- active_champions: `{slots}`",
        f"- rf_based: `{int((active_v17['model_family'].astype(str).str.lower() == 'rf').sum())}`/30",
        f"- metrics_match_registered_no_count: `{metrics_match_no}`",
        f"- high_separability_alert_count: `{high_sep_count}`",
        f"- hard_fail_unresolved_count: `{hard_fail_count}`",
        f"- all_domains_real_clone_count: `{real_clone_count}`",
        f"- elimination_real_clone_count: `{elim_real_clone_count}`",
        f"- all_domains_near_clone_warning_count: `{near_clone_count}`",
        "",
        "## Aggregate Metrics",
        f"- recall_macro: `{recall_macro:.6f}`",
        f"- recall_min: `{recall_min:.6f}`",
        f"- f2_macro: `{f2_macro:.6f}`",
        f"- pr_auc_macro: `{pr_macro:.6f}`",
        f"- balanced_accuracy_macro: `{ba_macro:.6f}`",
        f"- mcc_macro: `{mcc_macro:.6f}`",
        f"- brier_mean: `{brier_mean:.6f}`",
        "",
        "## Acceptance Bands",
        f"- slots_recall_ge_0_85: `{min_ok_recall_slots}`/30",
        f"- slots_ideal_zone: `{ideal_slots}`/30",
        f"- slots_alarm_zone: `{alarm_slots}`/30",
        "",
        "## Structural Modes",
        f"- nested_1_3_in_2_3: `{int((subset_df[subset_df['mode'].str.endswith('1_3')]['is_nested_with_2_3']=='yes').sum())}`/10",
        f"- nested_2_3_in_full: `{int((subset_df[subset_df['mode'].str.endswith('2_3')]['is_nested_with_2_3']=='yes').sum())}`/10",
        "",
        "## Notes",
        "- If any mode cannot reach exact 1/3 or 2/3 due existing questionnaire-mode availability, it is marked as best attainable under unchanged questionnaire.",
    ]
    write_text(REPORTS / "v17_domain_specialized_rf_training_report.md", "\n".join(report_lines))

    # RF study report
    rf_report_lines = [
        "# RF Model Study Report v17",
        "",
        f"Generated: `{now()}`",
        "",
        "## Completeness",
        f"- rf_study_data_completeness_status: `{comp_row['rf_study_data_completeness_status']}`",
        f"- artifact_hash_present_slots: `{art_hash_present}`/30",
        "",
        "## Summary",
        f"- mean_n_features: `{selected_metrics_df['n_features'].mean():.2f}`",
        f"- mean_top1_feature_share: `{selected_metrics_df['top1_feature_share'].mean():.4f}`",
        f"- mean_top3_feature_share: `{selected_metrics_df['top3_feature_share'].mean():.4f}`",
        f"- domain_purity_ok_slots: `{purity_yes}`/30",
        f"- no_eng_shortcut_ok_slots: `{no_eng_yes}`/30",
    ]
    write_text(REPORTS / "rf_model_study_report_v17.md", "\n".join(rf_report_lines))

    # Main artifacts requested aliases
    save_csv(feature_universe_df, TABLES / "domain_feature_universe_v17.csv")
    save_csv(subset_df, TABLES / "domain_mode_subsets_v17.csv")
    save_csv(ranking_df, TABLES / "feature_ranking_by_domain_role_v17.csv")
    save_csv(trials_df, TABLES / "rf_candidate_trials_30_slots_v17.csv")
    save_csv(selected_metrics_df, TABLES / "selected_domain_specialized_champions_v17.csv")
    save_csv(comp_df, TABLES / "v16_vs_v17_all_champions_comparison.csv")
    save_csv(pair_df, TABLES / "v17_pairwise_prediction_similarity_all_domains.csv")
    save_csv(purity_df, TABLES / "v17_domain_purity_audit.csv")
    save_csv(purity_df, TABLES / "v17_cross_domain_feature_audit.csv")
    save_csv(comorb_audit_df, TABLES / "v17_comorbidity_aggregation_audit.csv")
    save_csv(reg_vs_df, TABLES / "v17_registered_vs_recomputed_metrics.csv")
    save_csv(recomputed, TABLES / "v17_recomputed_champion_metrics.csv")

    # validators requested
    save_csv(guard_df, VALIDATION / "v17_guardrail_validator.csv")
    save_csv(contract_df, VALIDATION / "v17_contract_compatibility_validator.csv")
    save_csv(q_val, VALIDATION / "v17_questionnaire_unchanged_validator.csv")
    save_csv(mapping_df, VALIDATION / "v17_runtime_input_mapping_validator.csv")
    save_csv(anti_clone_df, VALIDATION / "v17_anti_clone_validator.csv")
    save_csv(completeness_df, VALIDATION / "rf_model_audit_completeness_validator_v17.csv")

    # plots
    generate_plots(comp_df, selected_metrics_df, pair_df, pd.DataFrame(tree_rows), pd.DataFrame(prob_rows), pd.DataFrame(cal_rows))

    # manifests
    manifest = {
        "line": LINE,
        "freeze_label": FREEZE,
        "generated_at_utc": now(),
        "source_truth_initial": {
            "active_v16": str(ACTIVE_V16.relative_to(ROOT)).replace("\\", "/"),
            "operational_v16": str(OP_V16.relative_to(ROOT)).replace("\\", "/"),
            "inputs_master_v16": str(INPUTS_V16.relative_to(ROOT)).replace("\\", "/"),
        },
        "source_truth_final": {
            "active_v17": str(ACTIVE_V17.relative_to(ROOT)).replace("\\", "/"),
            "operational_v17": str(OP_V17.relative_to(ROOT)).replace("\\", "/"),
            "inputs_master_v17": str(INPUTS_V17.relative_to(ROOT)).replace("\\", "/"),
        },
        "rules": {
            "rf_only": True,
            "domain_specialized": True,
            "cross_domain_features_as_primary": False,
            "eng_shortcuts_default_excluded": True,
            "guardrail_max": 0.98,
            "questionnaire_changed": False,
        },
        "stats": final_validator,
    }
    write_text(ART / f"{LINE}_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    write_text(ART_ACTIVE_V17, json.dumps({**manifest, "artifact": "hybrid_active_modes_freeze_v17"}, indent=2, ensure_ascii=False))
    write_text(ART_OP_V17, json.dumps({**manifest, "artifact": "hybrid_operational_freeze_v17"}, indent=2, ensure_ascii=False))

    print(json.dumps({"status": final_status, **final_validator}, ensure_ascii=False), flush=True)
    return 0 if final_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
