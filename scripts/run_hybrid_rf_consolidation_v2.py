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
LINE = "hybrid_rf_consolidation_v2"
BASE = ROOT / "data" / LINE
INV = BASE / "inventory"
REPRO = BASE / "reproduction"
BOOT = BASE / "bootstrap"
STAB = BASE / "stability"
CAL = BASE / "calibration"
ABL = BASE / "ablation"
STRESS = BASE / "stress"
TABLES = BASE / "tables"
REPORTS = BASE / "reports"
ART = ROOT / "artifacts" / LINE

DATASET_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "hybrid_dataset_synthetic_complete_final.csv"
RESP_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "hybrid_model_input_respondability_final.csv"
MODE_MATRIX_PATH = ROOT / "data" / "hybrid_dsm5_rebuild_v1" / "questionnaire_modes_priority_matrix_final.csv"

V1_BASE = ROOT / "data" / "hybrid_rf_ceiling_push_v1"
V1_WINNERS = V1_BASE / "tables" / "hybrid_rf_mode_domain_winners.csv"
V1_FINAL = V1_BASE / "tables" / "hybrid_rf_mode_domain_final_metrics.csv"
V1_FEATURESETS = V1_BASE / "trials" / "hybrid_rf_trial_feature_sets.csv"
V1_SPLITS = V1_BASE / "splits"

RF_CONFIGS: dict[str, dict[str, Any]] = {
    "rf_baseline": {
        "n_estimators": 280,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": None,
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_balanced_subsample": {
        "n_estimators": 360,
        "max_depth": 24,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.9,
    },
    "rf_precision_push": {
        "n_estimators": 320,
        "max_depth": 18,
        "min_samples_split": 8,
        "min_samples_leaf": 3,
        "max_features": 0.55,
        "class_weight": {0: 1.0, 1: 1.35},
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_recall_guard": {
        "n_estimators": 340,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "max_features": "sqrt",
        "class_weight": {0: 1.0, 1: 1.8},
        "bootstrap": True,
        "max_samples": None,
    },
    "rf_regularized": {
        "n_estimators": 300,
        "max_depth": 14,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "max_features": 0.45,
        "class_weight": "balanced",
        "bootstrap": True,
        "max_samples": 0.85,
    },
    "rf_large_subsample": {
        "n_estimators": 420,
        "max_depth": 30,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "bootstrap": True,
        "max_samples": 0.8,
    },
}

CANDIDATE_PLAN = [
    ("adhd", "psychologist_full", "primary"),
    ("adhd", "psychologist_2_3", "fallback"),
    ("anxiety", "caregiver_2_3", "primary"),
    ("anxiety", "caregiver_full", "compare"),
    ("conduct", "psychologist_2_3", "review"),
    ("conduct", "caregiver_2_3", "review"),
    ("conduct", "psychologist_full", "review"),
    ("depression", "caregiver_2_3", "primary"),
    ("depression", "caregiver_full", "compare"),
    ("depression", "psychologist_full", "compare"),
    ("elimination", "caregiver_2_3", "primary"),
    ("elimination", "caregiver_full", "compare"),
    ("elimination", "psychologist_full", "compare"),
]

REPRESENTATIVE_DSM5 = {
    "adhd": "psychologist_full",
    "anxiety": "caregiver_2_3",
    "conduct": "psychologist_2_3",
    "depression": "caregiver_2_3",
    "elimination": "caregiver_2_3",
}

THRESHOLD_POLICIES = ["default_0_5", "precision_oriented", "balanced", "recall_constrained"]
ALT_SPLIT_SEEDS = [20260721, 20260819]
SEED_VARIANTS = [0, 17, 43]

MODE_CHAIN = {
    "caregiver_full": ["caregiver_2_3", "caregiver_1_3"],
    "caregiver_2_3": ["caregiver_1_3"],
    "caregiver_1_3": [],
    "psychologist_full": ["psychologist_2_3", "psychologist_1_3"],
    "psychologist_2_3": ["psychologist_1_3"],
    "psychologist_1_3": [],
}


@dataclass
class Candidate:
    candidate_id: str
    domain: str
    mode: str
    role_tag: str
    winner_feature_set_id: str
    winner_config_id: str
    winner_calibration: str
    winner_threshold_policy: str
    winner_threshold: float
    winner_seed: int
    v1_holdout_precision: float
    v1_holdout_recall: float
    v1_holdout_specificity: float
    v1_holdout_balanced_accuracy: float
    v1_holdout_f1: float
    v1_holdout_roc_auc: float
    v1_holdout_pr_auc: float
    v1_holdout_brier: float


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_progress(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_dirs() -> None:
    for p in [BASE, INV, REPRO, BOOT, STAB, CAL, ABL, STRESS, TABLES, REPORTS, ART]:
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
        mask = idx == b
        if not np.any(mask):
            continue
        conf = float(np.mean(probs[mask]))
        acc = float(np.mean(y_true[mask]))
        ece += (np.sum(mask) / n) * abs(acc - conf)
    return float(ece)


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


def objective_score(metrics: dict[str, float]) -> float:
    return (
        0.40 * metrics["precision"]
        + 0.25 * metrics["balanced_accuracy"]
        + 0.20 * metrics["pr_auc"]
        + 0.10 * metrics["recall"]
        - 0.05 * metrics["brier"]
    )


def choose_threshold(policy: str, y_true: np.ndarray, probs: np.ndarray, recall_floor: float = 0.55) -> tuple[float, float]:
    if policy == "default_0_5":
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective_score(m)
    grid = np.linspace(0.05, 0.95, 181)
    best_t = 0.5
    best_score = -1e9
    for t in grid:
        m = compute_metrics(y_true, probs, float(t))
        if policy == "precision_oriented":
            if m["recall"] < max(0.50, recall_floor):
                continue
            score = 0.62 * m["precision"] + 0.20 * m["balanced_accuracy"] + 0.12 * m["pr_auc"] + 0.06 * m["recall"]
        elif policy == "balanced":
            score = 0.50 * m["balanced_accuracy"] + 0.20 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
        elif policy == "recall_constrained":
            if m["recall"] < max(0.62, recall_floor):
                continue
            score = 0.48 * m["precision"] + 0.22 * m["balanced_accuracy"] + 0.20 * m["recall"] + 0.10 * m["pr_auc"]
        else:
            score = objective_score(m)
        if score > best_score:
            best_score = float(score)
            best_t = float(t)
    if best_score < -1e8:
        m = compute_metrics(y_true, probs, 0.5)
        return 0.5, objective_score(m)
    return best_t, best_score


def make_pipeline(features: list[str], cfg: dict[str, Any], seed: int) -> Pipeline:
    cat = [c for c in features if c == "sex_assigned_at_birth"]
    num = [c for c in features if c not in cat]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                cat,
            ),
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


def prepare_X(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for c in X.columns:
        if c == "sex_assigned_at_birth":
            X[c] = X[c].fillna("Unknown").astype(str)
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    return X


def choose_target_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    work = df.copy()
    if all(c in work.columns for c in ["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]):
        work["target_domain_depression_final"] = (
            work[["mdd_threshold_met", "dmdd_threshold_met", "pdd_threshold_met_child"]]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .max(axis=1)
            .astype(int)
        )
    target_map = {
        "adhd": "adhd_final_dsm5_threshold_met",
        "conduct": "conduct_final_dsm5_threshold_met",
        "elimination": "elimination_any_threshold_met",
        "anxiety": "anxiety_any_module_threshold_met",
        "depression": "target_domain_depression_final",
    }
    for d, c in target_map.items():
        out = f"target_domain_{d}_final"
        work[out] = pd.to_numeric(work[c], errors="coerce").fillna(0).astype(int)
        work[out] = (work[out] > 0).astype(int)
        target_map[d] = out
    return work, target_map


def load_ids(path: Path) -> list[str]:
    df = pd.read_csv(path)
    col = "participant_id" if "participant_id" in df.columns else df.columns[0]
    return df[col].astype(str).tolist()


def build_alt_splits(df: pd.DataFrame, target_col: str, seeds: list[int]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    ids = df["participant_id"].astype(str).to_numpy()
    y = df[target_col].astype(int).to_numpy()
    for i, seed in enumerate(seeds, start=1):
        strat = y if len(np.unique(y)) > 1 else None
        tr_ids, tmp_ids, tr_y, tmp_y = train_test_split(
            ids,
            y,
            test_size=0.40,
            random_state=seed,
            stratify=strat,
        )
        strat_tmp = tmp_y if len(np.unique(tmp_y)) > 1 else None
        va_ids, ho_ids = train_test_split(
            tmp_ids,
            test_size=0.50,
            random_state=seed + 1,
            stratify=strat_tmp,
        )
        out[f"alt_split_{i}"] = {
            "train": [str(x) for x in tr_ids.tolist()],
            "val": [str(x) for x in va_ids.tolist()],
            "holdout": [str(x) for x in ho_ids.tolist()],
        }
    return out


def subset_by_ids(df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids))].copy()


def calibrate_probabilities(
    y_val: np.ndarray,
    train_raw: np.ndarray,
    val_raw: np.ndarray,
    hold_raw: np.ndarray,
) -> tuple[
    dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    dict[str, dict[str, float]],
    dict[str, Callable[[np.ndarray], np.ndarray]],
]:
    probs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    diag: dict[str, dict[str, float]] = {}
    transforms: dict[str, Callable[[np.ndarray], np.ndarray]] = {}

    def _clip(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 1e-6, 1 - 1e-6)

    def _none(x: np.ndarray) -> np.ndarray:
        return _clip(x)

    probs["none"] = (_none(train_raw), _none(val_raw), _none(hold_raw))
    diag["none"] = {
        "val_brier": float(brier_score_loss(y_val, probs["none"][1])),
        "val_ece": float(expected_calibration_error(y_val, probs["none"][1])),
    }
    transforms["none"] = _none

    if len(np.unique(y_val)) >= 2:
        lr = LogisticRegression(max_iter=1200)
        lr.fit(val_raw.reshape(-1, 1), y_val.astype(int))

        def sig(x: np.ndarray) -> np.ndarray:
            return _clip(lr.predict_proba(x.reshape(-1, 1))[:, 1])

        probs["sigmoid"] = (sig(train_raw), sig(val_raw), sig(hold_raw))
        diag["sigmoid"] = {
            "val_brier": float(brier_score_loss(y_val, probs["sigmoid"][1])),
            "val_ece": float(expected_calibration_error(y_val, probs["sigmoid"][1])),
        }
        transforms["sigmoid"] = sig

        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(val_raw, y_val.astype(int))

        def iso_f(x: np.ndarray) -> np.ndarray:
            return _clip(iso.predict(x))

        probs["isotonic"] = (iso_f(train_raw), iso_f(val_raw), iso_f(hold_raw))
        diag["isotonic"] = {
            "val_brier": float(brier_score_loss(y_val, probs["isotonic"][1])),
            "val_ece": float(expected_calibration_error(y_val, probs["isotonic"][1])),
        }
        transforms["isotonic"] = iso_f

    return probs, diag, transforms


def aggregate_importance(pipe: Pipeline, feature_names: list[str]) -> pd.Series:
    pre = pipe.named_steps["pre"]
    rf = pipe.named_steps["rf"]
    transformed = pre.get_feature_names_out()
    importance = rf.feature_importances_
    agg = {f: 0.0 for f in feature_names}
    for name, val in zip(transformed, importance):
        clean = str(name)
        orig = clean
        if clean.startswith("num__"):
            orig = clean.split("num__", 1)[1]
        elif clean.startswith("cat__"):
            tail = clean.split("cat__", 1)[1]
            orig = "sex_assigned_at_birth" if tail.startswith("sex_assigned_at_birth") else tail.split("_", 1)[0]
        if orig in agg:
            agg[orig] += float(val)
    return pd.Series(agg).sort_values(ascending=False)


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


def bootstrap_intervals(y_true: np.ndarray, probs: np.ndarray, threshold: float, n_boot: int, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx_all = np.arange(len(y_true))
    names = ["precision", "recall", "balanced_accuracy", "pr_auc", "brier"]
    values = {k: [] for k in names}
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        m = compute_metrics(y_true[idx], probs[idx], threshold)
        for k in names:
            values[k].append(float(m[k]))
    out: dict[str, float] = {}
    for k in names:
        arr = np.array(values[k], dtype=float)
        out[f"{k}_mean"] = float(np.mean(arr))
        out[f"{k}_ci_low"] = float(np.quantile(arr, 0.025))
        out[f"{k}_ci_high"] = float(np.quantile(arr, 0.975))
        out[f"{k}_ci_width"] = float(np.quantile(arr, 0.975) - np.quantile(arr, 0.025))
    return out


def mode_complexity(mode: str) -> int:
    if mode.endswith("1_3"):
        return 1
    if mode.endswith("2_3"):
        return 2
    return 3


def decision_rank(label: str) -> int:
    order = {
        "PROMOTE_NOW": 4,
        "PROMOTE_WITH_CAVEAT": 3,
        "HOLD_FOR_TARGETED_FIX": 2,
        "REJECT_AS_PRIMARY": 1,
    }
    return order.get(label, 0)


def mode_role(mode: str) -> str:
    return "caregiver" if mode.startswith("caregiver") else "psychologist"


def read_feature_list(fs_df: pd.DataFrame, mode: str, domain: str, fs_id: str) -> list[str]:
    row = fs_df[(fs_df["mode"] == mode) & (fs_df["domain"] == domain) & (fs_df["feature_set_id"] == fs_id)]
    if row.empty:
        raise RuntimeError(f"Missing feature set for {mode}/{domain}/{fs_id}")
    return [x for x in str(row.iloc[0]["feature_list_pipe"]).split("|") if x]


def calibrate_select(
    calibration_method: str,
    probs_all: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    transforms: dict[str, Callable[[np.ndarray], np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Callable[[np.ndarray], np.ndarray], str]:
    if calibration_method in probs_all:
        tr, va, ho = probs_all[calibration_method]
        return tr, va, ho, transforms.get(calibration_method, transforms["none"]), calibration_method
    tr, va, ho = probs_all["none"]
    return tr, va, ho, transforms["none"], "none"


def normalize_flag(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip().lower()


def parse_feature_pipe(x: Any) -> list[str]:
    return [f for f in str(x).split("|") if f]


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_dsm5_feature(feature: str) -> bool:
    f = str(feature).lower()
    if f in {"age_years", "sex_assigned_at_birth"}:
        return False
    if f.startswith(("swan_", "sdq_", "icut_", "ari_", "scared_", "mfq_")):
        return False
    dsm_prefix = (
        "adhd_",
        "conduct_",
        "enuresis_",
        "encopresis_",
        "elimination_",
        "sep_anx_",
        "social_anx_",
        "gad_",
        "agor_",
        "anxiety_",
        "mdd_",
        "dmdd_",
        "pdd_",
    )
    if f.startswith(dsm_prefix):
        return True
    key_tokens = ["symptom", "threshold", "impairment", "onset", "duration", "context", "criterion", "specifier"]
    return any(tok in f for tok in key_tokens)


def material_gain(delta_precision: float, delta_recall: float, delta_ba: float, delta_pr_auc: float) -> bool:
    return bool((delta_ba >= 0.01) or (delta_pr_auc >= 0.01) or ((delta_precision >= 0.01) and (delta_recall > -0.03)))


def load_domain_splits() -> tuple[dict[str, dict[str, list[str]]], pd.DataFrame]:
    split_map: dict[str, dict[str, list[str]]] = {}
    rows: list[dict[str, Any]] = []
    for domain in ["adhd", "conduct", "elimination", "anxiety", "depression"]:
        ddir = V1_SPLITS / f"domain_{domain}"
        tr = load_ids(ddir / "ids_train.csv")
        va = load_ids(ddir / "ids_val.csv")
        ho = load_ids(ddir / "ids_holdout.csv")
        split_map[domain] = {"train": tr, "val": va, "holdout": ho}
        rows.append(
            {
                "domain": domain,
                "source": "hybrid_rf_ceiling_push_v1",
                "train_n": len(tr),
                "val_n": len(va),
                "holdout_n": len(ho),
                "train_ids_path": str((ddir / "ids_train.csv").relative_to(ROOT)).replace("\\", "/"),
                "val_ids_path": str((ddir / "ids_val.csv").relative_to(ROOT)).replace("\\", "/"),
                "holdout_ids_path": str((ddir / "ids_holdout.csv").relative_to(ROOT)).replace("\\", "/"),
            }
        )
    return split_map, pd.DataFrame(rows)


def build_mode_feature_coverage(
    df: pd.DataFrame,
    respondability: pd.DataFrame,
    mode_matrix: pd.DataFrame,
    fs_df: pd.DataFrame,
) -> tuple[dict[str, set[str]], pd.DataFrame]:
    direct_keep = set(
        respondability[
            respondability["is_direct_input"].map(normalize_flag).eq("yes")
            & respondability["keep_for_model_v1"].map(normalize_flag).eq("yes")
        ]["feature"].astype(str)
    )
    derived_keep = set(
        respondability[
            respondability["is_transparent_derived"].map(normalize_flag).eq("yes")
            & respondability["keep_for_model_v1"].map(normalize_flag).eq("yes")
        ]["feature"].astype(str)
    )

    union_by_mode: dict[str, set[str]] = {m: set() for m in MODE_CHAIN}
    for _, row in fs_df.iterrows():
        mode = str(row["mode"])
        feats = parse_feature_pipe(row["feature_list_pipe"])
        if mode not in union_by_mode:
            union_by_mode[mode] = set()
        union_by_mode[mode].update(feats)

    eligible_map: dict[str, set[str]] = {}
    rows: list[dict[str, Any]] = []

    for mode in MODE_CHAIN:
        include_col = f"include_{mode}"
        direct_matrix = set(
            mode_matrix[mode_matrix[include_col].map(normalize_flag).eq("si")]["feature"].astype(str)
        )
        direct_usable = sorted(f for f in direct_matrix if f in direct_keep and f in df.columns)
        derived_usable = sorted(f for f in union_by_mode.get(mode, set()) if f in derived_keep and f in df.columns)
        eligible = sorted(set(direct_usable) | set(derived_usable))
        eligible_map[mode] = set(eligible)
        rows.append(
            {
                "mode": mode,
                "role": mode_role(mode),
                "direct_features_from_priority_matrix": int(len(direct_matrix)),
                "direct_features_usable_in_dataset": int(len(direct_usable)),
                "transparent_derived_eligible": int(len(derived_usable)),
                "total_eligible_features": int(len(eligible)),
            }
        )

    return eligible_map, pd.DataFrame(rows).sort_values(["role", "mode"]).reset_index(drop=True)


def fit_and_evaluate(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    hold_df: pd.DataFrame,
    features: list[str],
    target_col: str,
    config: dict[str, Any],
    seed: int,
    calibration_method: str,
    threshold_policy: str,
    fixed_threshold: float | None,
    recall_floor: float = 0.55,
) -> dict[str, Any]:
    y_train = train_df[target_col].astype(int).to_numpy()
    y_val = val_df[target_col].astype(int).to_numpy()
    y_hold = hold_df[target_col].astype(int).to_numpy()

    X_train = prepare_X(train_df, features)
    X_val = prepare_X(val_df, features)
    X_hold = prepare_X(hold_df, features)

    pipe = make_pipeline(features, config, seed)
    pipe.fit(X_train, y_train)

    train_raw = np.clip(pipe.predict_proba(X_train)[:, 1], 1e-6, 1 - 1e-6)
    val_raw = np.clip(pipe.predict_proba(X_val)[:, 1], 1e-6, 1 - 1e-6)
    hold_raw = np.clip(pipe.predict_proba(X_hold)[:, 1], 1e-6, 1 - 1e-6)

    probs_all, cal_diag, transforms = calibrate_probabilities(y_val, train_raw, val_raw, hold_raw)
    train_prob, val_prob, hold_prob, transform, used_calibration = calibrate_select(
        calibration_method,
        probs_all,
        transforms,
    )

    threshold_opt, threshold_score = choose_threshold(threshold_policy, y_val, val_prob, recall_floor=recall_floor)
    if fixed_threshold is None or (isinstance(fixed_threshold, float) and math.isnan(fixed_threshold)):
        threshold = float(threshold_opt)
    else:
        threshold = float(fixed_threshold)

    m_train = compute_metrics(y_train, train_prob, threshold)
    m_val = compute_metrics(y_val, val_prob, threshold)
    m_hold = compute_metrics(y_hold, hold_prob, threshold)

    importance = aggregate_importance(pipe, features)

    return {
        "model": pipe,
        "features": features,
        "target_col": target_col,
        "seed": seed,
        "X_train": X_train,
        "X_val": X_val,
        "X_hold": X_hold,
        "y_train": y_train,
        "y_val": y_val,
        "y_hold": y_hold,
        "train_raw": train_raw,
        "val_raw": val_raw,
        "hold_raw": hold_raw,
        "probs_all": probs_all,
        "cal_diag": cal_diag,
        "transform": transform,
        "used_calibration": used_calibration,
        "train_prob": train_prob,
        "val_prob": val_prob,
        "hold_prob": hold_prob,
        "threshold_opt": float(threshold_opt),
        "threshold_opt_score": float(threshold_score),
        "threshold_used": float(threshold),
        "metrics_train": m_train,
        "metrics_val": m_val,
        "metrics_hold": m_hold,
        "importance": importance,
    }


def summarize_candidate_stability(
    candidate_id: str,
    reproduction_row: pd.Series,
    bootstrap_row: pd.Series,
    stability_df: pd.DataFrame,
    stress_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
) -> dict[str, Any]:
    seed_rows = stability_df[(stability_df["candidate_id"] == candidate_id) & (stability_df["stability_axis"] == "seed")]
    split_rows = stability_df[(stability_df["candidate_id"] == candidate_id) & (stability_df["stability_axis"] == "split")]
    stress_rows = stress_df[stress_df["candidate_id"] == candidate_id]
    abl_rows = ablation_df[ablation_df["candidate_id"] == candidate_id]

    seed_std_ba = float(seed_rows["holdout_balanced_accuracy"].std()) if len(seed_rows) > 1 else 0.0
    seed_std_precision = float(seed_rows["holdout_precision"].std()) if len(seed_rows) > 1 else 0.0
    seed_std_recall = float(seed_rows["holdout_recall"].std()) if len(seed_rows) > 1 else 0.0

    split_std_ba = float(split_rows["holdout_balanced_accuracy"].std()) if len(split_rows) > 1 else 0.0
    split_std_precision = float(split_rows["holdout_precision"].std()) if len(split_rows) > 1 else 0.0
    split_std_recall = float(split_rows["holdout_recall"].std()) if len(split_rows) > 1 else 0.0

    worst_stress_ba = float(stress_rows["delta_balanced_accuracy_vs_baseline"].min()) if not stress_rows.empty else 0.0
    worst_stress_precision = float(stress_rows["delta_precision_vs_baseline"].min()) if not stress_rows.empty else 0.0
    worst_stress_recall = float(stress_rows["delta_recall_vs_baseline"].min()) if not stress_rows.empty else 0.0

    top3_drop = abl_rows[abl_rows["ablation_case"] == "drop_top3"]
    top3_drop_ba = float(top3_drop["delta_balanced_accuracy_vs_baseline"].min()) if not top3_drop.empty else 0.0

    boot_ba_width = float(bootstrap_row.get("balanced_accuracy_ci_width", np.nan))
    boot_prec_width = float(bootstrap_row.get("precision_ci_width", np.nan))

    if (
        seed_std_ba <= 0.010
        and split_std_ba <= 0.015
        and boot_ba_width <= 0.040
        and worst_stress_ba >= -0.050
        and top3_drop_ba >= -0.050
    ):
        stability_grade = "strong"
    elif (
        seed_std_ba <= 0.020
        and split_std_ba <= 0.025
        and boot_ba_width <= 0.070
        and worst_stress_ba >= -0.090
        and top3_drop_ba >= -0.090
    ):
        stability_grade = "acceptable"
    else:
        stability_grade = "fragile"

    return {
        "candidate_id": candidate_id,
        "domain": reproduction_row["domain"],
        "mode": reproduction_row["mode"],
        "holdout_precision": float(reproduction_row["holdout_precision"]),
        "holdout_recall": float(reproduction_row["holdout_recall"]),
        "holdout_balanced_accuracy": float(reproduction_row["holdout_balanced_accuracy"]),
        "holdout_pr_auc": float(reproduction_row["holdout_pr_auc"]),
        "holdout_brier": float(reproduction_row["holdout_brier"]),
        "seed_std_balanced_accuracy": seed_std_ba,
        "seed_std_precision": seed_std_precision,
        "seed_std_recall": seed_std_recall,
        "split_std_balanced_accuracy": split_std_ba,
        "split_std_precision": split_std_precision,
        "split_std_recall": split_std_recall,
        "bootstrap_balanced_accuracy_ci_low": float(bootstrap_row.get("balanced_accuracy_ci_low", np.nan)),
        "bootstrap_balanced_accuracy_ci_high": float(bootstrap_row.get("balanced_accuracy_ci_high", np.nan)),
        "bootstrap_balanced_accuracy_ci_width": boot_ba_width,
        "bootstrap_precision_ci_width": boot_prec_width,
        "worst_stress_delta_balanced_accuracy": worst_stress_ba,
        "worst_stress_delta_precision": worst_stress_precision,
        "worst_stress_delta_recall": worst_stress_recall,
        "drop_top3_delta_balanced_accuracy": top3_drop_ba,
        "stability_grade": stability_grade,
    }


def classify_candidate(
    row: pd.Series,
    stability_row: pd.Series,
    calibration_df: pd.DataFrame,
) -> tuple[str, str, int]:
    risks: list[str] = []

    if str(row["reproduced_material"]).lower() != "yes":
        risks.append("reproduction_drift")
    if float(row["overfit_gap_train_val_ba"]) > 0.06:
        risks.append("train_val_gap")
    if float(row["generalization_gap_val_holdout_ba"]) > 0.05:
        risks.append("val_holdout_gap")
    if float(stability_row["seed_std_balanced_accuracy"]) > 0.02:
        risks.append("seed_instability")
    if float(stability_row["split_std_balanced_accuracy"]) > 0.025:
        risks.append("split_instability")
    if float(stability_row["bootstrap_balanced_accuracy_ci_width"]) > 0.07:
        risks.append("wide_bootstrap_ci")
    if float(stability_row["worst_stress_delta_balanced_accuracy"]) < -0.09:
        risks.append("stress_fragility")
    if float(stability_row["drop_top3_delta_balanced_accuracy"]) < -0.09:
        risks.append("top_feature_dependency")

    hold_precision = float(row["holdout_precision"])
    hold_recall = float(row["holdout_recall"])
    hold_ba = float(row["holdout_balanced_accuracy"])
    hold_pr = float(row["holdout_pr_auc"])
    hold_brier = float(row["holdout_brier"])

    csub = calibration_df[calibration_df["candidate_id"] == row["candidate_id"]]
    cal_gain = 0.0
    if not csub.empty:
        baseline = csub[csub["calibration_method"] == "none"]
        best = csub.sort_values(["val_brier", "val_ece", "holdout_brier"], ascending=[True, True, True]).head(1)
        if not baseline.empty and not best.empty:
            cal_gain = float(baseline.iloc[0]["holdout_brier"] - best.iloc[0]["holdout_brier"])

    hard_weak = (hold_precision < 0.70) or (hold_ba < 0.75)
    moderate_weak = (hold_precision < 0.78) or (hold_ba < 0.80) or (hold_recall < 0.50)

    if hard_weak and len(risks) >= 2:
        decision = "REJECT_AS_PRIMARY"
    elif len(risks) == 0 and hold_precision >= 0.85 and hold_ba >= 0.86 and hold_pr >= 0.85 and hold_brier <= 0.06:
        decision = "PROMOTE_NOW"
    elif len(risks) <= 2 and hold_precision >= 0.80 and hold_ba >= 0.82 and hold_recall >= 0.55:
        decision = "PROMOTE_WITH_CAVEAT"
    elif moderate_weak or len(risks) >= 3:
        decision = "HOLD_FOR_TARGETED_FIX"
    else:
        decision = "PROMOTE_WITH_CAVEAT"

    if str(row["domain"]) == "depression" and decision == "PROMOTE_NOW":
        decision = "PROMOTE_WITH_CAVEAT"
        risks.append("depression_fragility_caveat")
    if str(row["domain"]) == "elimination" and hold_recall < 0.88 and decision == "PROMOTE_NOW":
        decision = "PROMOTE_WITH_CAVEAT"
        risks.append("elimination_recall_caveat")

    if float(row["generalization_gap_val_holdout_ba"]) > 0.08:
        if decision in {"PROMOTE_NOW", "PROMOTE_WITH_CAVEAT"}:
            decision = "HOLD_FOR_TARGETED_FIX"
            risks.append("severe_generalization_gap")

    if decision == "PROMOTE_WITH_CAVEAT" and cal_gain <= 0.0 and hold_brier > 0.08:
        risks.append("calibration_not_helping")

    return decision, "|".join(sorted(set(risks))), len(set(risks))


def build_candidate_objects(
    winners_v1: pd.DataFrame,
    final_v1: pd.DataFrame,
) -> tuple[list[Candidate], pd.DataFrame]:
    candidates: list[Candidate] = []
    caveats: list[dict[str, Any]] = []

    for domain, mode, role_tag in CANDIDATE_PLAN:
        w = winners_v1[(winners_v1["domain"] == domain) & (winners_v1["mode"] == mode)]
        f = final_v1[(final_v1["domain"] == domain) & (final_v1["mode"] == mode)]
        if w.empty or f.empty:
            caveats.append(
                {
                    "domain": domain,
                    "mode": mode,
                    "role_tag": role_tag,
                    "status": "missing_in_v1",
                    "note": "candidate not found in v1 winners/final metrics",
                }
            )
            continue

        wr = w.iloc[0]
        fr = f.iloc[0]
        candidates.append(
            Candidate(
                candidate_id=f"{domain}__{mode}",
                domain=domain,
                mode=mode,
                role_tag=role_tag,
                winner_feature_set_id=str(wr["winner_feature_set_id"]),
                winner_config_id=str(wr["winner_config_id"]),
                winner_calibration=str(wr["winner_calibration"]),
                winner_threshold_policy=str(wr["winner_threshold_policy"]),
                winner_threshold=float(wr["winner_threshold"]),
                winner_seed=int(wr["winner_seed"]),
                v1_holdout_precision=float(fr["holdout_precision"]),
                v1_holdout_recall=float(fr["holdout_recall"]),
                v1_holdout_specificity=float(fr["holdout_specificity"]),
                v1_holdout_balanced_accuracy=float(fr["holdout_balanced_accuracy"]),
                v1_holdout_f1=float(fr["holdout_f1"]),
                v1_holdout_roc_auc=float(fr["holdout_roc_auc"]),
                v1_holdout_pr_auc=float(fr["holdout_pr_auc"]),
                v1_holdout_brier=float(fr["holdout_brier"]),
            )
        )
    return candidates, pd.DataFrame(caveats)


def run_campaign() -> None:
    ensure_dirs()
    print_progress("Loading source tables")

    df_raw = pd.read_csv(DATASET_PATH)
    respondability = pd.read_csv(RESP_PATH)
    mode_matrix = pd.read_csv(MODE_MATRIX_PATH)
    winners_v1 = pd.read_csv(V1_WINNERS)
    final_v1 = pd.read_csv(V1_FINAL)
    fs_v1 = pd.read_csv(V1_FEATURESETS)

    df, target_map = choose_target_columns(df_raw)
    split_map, split_registry_df = load_domain_splits()
    eligible_map, coverage_df = build_mode_feature_coverage(df, respondability, mode_matrix, fs_v1)

    candidates, candidate_caveats = build_candidate_objects(winners_v1, final_v1)
    if not candidates:
        raise RuntimeError("No candidates available for consolidation v2.")

    inventory_rows = [
        {"item": "campaign_line", "value": LINE},
        {"item": "dataset_path", "value": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/")},
        {"item": "dataset_n_rows", "value": int(df.shape[0])},
        {"item": "dataset_n_columns", "value": int(df.shape[1])},
        {"item": "candidates_requested", "value": int(len(CANDIDATE_PLAN))},
        {"item": "candidates_loaded", "value": int(len(candidates))},
        {"item": "audit_scope", "value": "targeted_candidates_only"},
        {"item": "seed_variants", "value": "|".join(str(x) for x in SEED_VARIANTS)},
        {"item": "alt_split_seeds", "value": "|".join(str(x) for x in ALT_SPLIT_SEEDS)},
        {"item": "threshold_policies", "value": "|".join(THRESHOLD_POLICIES)},
        {"item": "created_at_utc", "value": now_iso()},
    ]
    inventory_df = pd.DataFrame(inventory_rows)
    save_csv(inventory_df, INV / "hybrid_rf_consolidation_inventory.csv")

    inventory_md = [
        "# Hybrid RF Consolidation v2 - Inventory",
        "",
        "## Inventory",
        md_table(inventory_df),
        "",
        "## Candidate Scope",
        md_table(pd.DataFrame([c.__dict__ for c in candidates])[
            [
                "candidate_id",
                "domain",
                "mode",
                "role_tag",
                "winner_feature_set_id",
                "winner_config_id",
                "winner_calibration",
                "winner_threshold_policy",
                "winner_threshold",
                "winner_seed",
            ]
        ]),
        "",
        "## Split Registry (reused from v1)",
        md_table(split_registry_df),
        "",
        "## Mode Coverage",
        md_table(coverage_df),
    ]
    if not candidate_caveats.empty:
        inventory_md.extend(["", "## Candidate Caveats", md_table(candidate_caveats)])
    write_md(INV / "hybrid_rf_consolidation_inventory.md", "\n".join(inventory_md))

    save_csv(coverage_df, TABLES / "hybrid_rf_mode_feature_coverage_recheck.csv")
    save_csv(split_registry_df, TABLES / "hybrid_rf_split_registry_reused.csv")

    print_progress("Reproducing candidate winners on v1 holdout splits")

    candidate_states: dict[str, dict[str, Any]] = {}
    reproduction_rows: list[dict[str, Any]] = []

    for cand in candidates:
        cfg = RF_CONFIGS.get(cand.winner_config_id)
        if cfg is None:
            raise RuntimeError(f"Unknown RF config id: {cand.winner_config_id}")

        feats = read_feature_list(fs_v1, cand.mode, cand.domain, cand.winner_feature_set_id)
        feats = [f for f in feats if f in df.columns]

        split_ids = split_map[cand.domain]
        train_df = subset_by_ids(df, split_ids["train"])
        val_df = subset_by_ids(df, split_ids["val"])
        hold_df = subset_by_ids(df, split_ids["holdout"])

        target_col = target_map[cand.domain]
        unsupported = [f for f in feats if f not in eligible_map.get(cand.mode, set())]

        eval_res = fit_and_evaluate(
            train_df=train_df,
            val_df=val_df,
            hold_df=hold_df,
            features=feats,
            target_col=target_col,
            config=cfg,
            seed=cand.winner_seed,
            calibration_method=cand.winner_calibration,
            threshold_policy=cand.winner_threshold_policy,
            fixed_threshold=cand.winner_threshold,
            recall_floor=0.55,
        )

        m_tr = eval_res["metrics_train"]
        m_va = eval_res["metrics_val"]
        m_ho = eval_res["metrics_hold"]

        d_precision = float(m_ho["precision"] - cand.v1_holdout_precision)
        d_recall = float(m_ho["recall"] - cand.v1_holdout_recall)
        d_ba = float(m_ho["balanced_accuracy"] - cand.v1_holdout_balanced_accuracy)
        d_pr = float(m_ho["pr_auc"] - cand.v1_holdout_pr_auc)
        d_brier = float(m_ho["brier"] - cand.v1_holdout_brier)

        reproduced_material = "yes" if (
            abs(d_ba) <= 0.01 and abs(d_pr) <= 0.015 and abs(d_precision) <= 0.02 and abs(d_recall) <= 0.03
        ) else "no"

        reproduction_rows.append(
            {
                "candidate_id": cand.candidate_id,
                "domain": cand.domain,
                "mode": cand.mode,
                "role": mode_role(cand.mode),
                "role_tag": cand.role_tag,
                "winner_feature_set_id": cand.winner_feature_set_id,
                "winner_config_id": cand.winner_config_id,
                "winner_calibration": cand.winner_calibration,
                "winner_threshold_policy": cand.winner_threshold_policy,
                "winner_threshold_v1": cand.winner_threshold,
                "winner_seed": cand.winner_seed,
                "n_features": len(feats),
                "unsupported_feature_count": int(len(unsupported)),
                "unsupported_features_pipe": "|".join(unsupported),
                "reproduced_calibration_used": eval_res["used_calibration"],
                "reproduced_threshold_used": eval_res["threshold_used"],
                "reproduced_threshold_opt_val": eval_res["threshold_opt"],
                "train_precision": m_tr["precision"],
                "train_recall": m_tr["recall"],
                "train_specificity": m_tr["specificity"],
                "train_balanced_accuracy": m_tr["balanced_accuracy"],
                "train_f1": m_tr["f1"],
                "train_roc_auc": m_tr["roc_auc"],
                "train_pr_auc": m_tr["pr_auc"],
                "train_brier": m_tr["brier"],
                "val_precision": m_va["precision"],
                "val_recall": m_va["recall"],
                "val_specificity": m_va["specificity"],
                "val_balanced_accuracy": m_va["balanced_accuracy"],
                "val_f1": m_va["f1"],
                "val_roc_auc": m_va["roc_auc"],
                "val_pr_auc": m_va["pr_auc"],
                "val_brier": m_va["brier"],
                "holdout_precision": m_ho["precision"],
                "holdout_recall": m_ho["recall"],
                "holdout_specificity": m_ho["specificity"],
                "holdout_balanced_accuracy": m_ho["balanced_accuracy"],
                "holdout_f1": m_ho["f1"],
                "holdout_roc_auc": m_ho["roc_auc"],
                "holdout_pr_auc": m_ho["pr_auc"],
                "holdout_brier": m_ho["brier"],
                "v1_holdout_precision": cand.v1_holdout_precision,
                "v1_holdout_recall": cand.v1_holdout_recall,
                "v1_holdout_specificity": cand.v1_holdout_specificity,
                "v1_holdout_balanced_accuracy": cand.v1_holdout_balanced_accuracy,
                "v1_holdout_f1": cand.v1_holdout_f1,
                "v1_holdout_roc_auc": cand.v1_holdout_roc_auc,
                "v1_holdout_pr_auc": cand.v1_holdout_pr_auc,
                "v1_holdout_brier": cand.v1_holdout_brier,
                "delta_holdout_precision_vs_v1": d_precision,
                "delta_holdout_recall_vs_v1": d_recall,
                "delta_holdout_balanced_accuracy_vs_v1": d_ba,
                "delta_holdout_pr_auc_vs_v1": d_pr,
                "delta_holdout_brier_vs_v1": d_brier,
                "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                "generalization_gap_val_holdout_ba": float(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]),
                "reproduced_material": reproduced_material,
            }
        )

        candidate_states[cand.candidate_id] = {
            "candidate": cand,
            "features": feats,
            "unsupported": unsupported,
            "target_col": target_col,
            "split_ids": split_ids,
            "base_eval": eval_res,
            "cfg": cfg,
        }

    reproduction_df = pd.DataFrame(reproduction_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(reproduction_df, REPRO / "hybrid_rf_reproduced_candidates.csv")

    print_progress("Running bootstrap confidence intervals")
    boot_rows: list[dict[str, Any]] = []
    for cid, st in candidate_states.items():
        cand = st["candidate"]
        base = st["base_eval"]
        b = bootstrap_intervals(
            y_true=base["y_hold"],
            probs=base["hold_prob"],
            threshold=base["threshold_used"],
            n_boot=350,
            seed=int(cand.winner_seed + 97),
        )
        row = {
            "candidate_id": cid,
            "domain": cand.domain,
            "mode": cand.mode,
            "threshold_used": base["threshold_used"],
            **b,
        }
        boot_rows.append(row)
    boot_df = pd.DataFrame(boot_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(boot_df, BOOT / "hybrid_rf_bootstrap_intervals.csv")

    print_progress("Running seed and split stability checks")
    alt_splits_by_domain = {d: build_alt_splits(df, target_map[d], ALT_SPLIT_SEEDS) for d in target_map}
    stability_rows: list[dict[str, Any]] = []

    for cid, st in candidate_states.items():
        cand = st["candidate"]
        cfg = st["cfg"]
        feats = st["features"]
        target_col = st["target_col"]

        base_split = st["split_ids"]
        base_train = subset_by_ids(df, base_split["train"])
        base_val = subset_by_ids(df, base_split["val"])
        base_hold = subset_by_ids(df, base_split["holdout"])

        seed_values = sorted(set([cand.winner_seed] + [cand.winner_seed + s for s in SEED_VARIANTS]))
        for s in seed_values:
            ev = fit_and_evaluate(
                train_df=base_train,
                val_df=base_val,
                hold_df=base_hold,
                features=feats,
                target_col=target_col,
                config=cfg,
                seed=int(s),
                calibration_method=cand.winner_calibration,
                threshold_policy=cand.winner_threshold_policy,
                fixed_threshold=None,
                recall_floor=0.55,
            )
            m_tr = ev["metrics_train"]
            m_va = ev["metrics_val"]
            m_ho = ev["metrics_hold"]
            stability_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stability_axis": "seed",
                    "variant_id": f"seed_{s}",
                    "seed": int(s),
                    "calibration_method": ev["used_calibration"],
                    "threshold": ev["threshold_used"],
                    "holdout_precision": m_ho["precision"],
                    "holdout_recall": m_ho["recall"],
                    "holdout_specificity": m_ho["specificity"],
                    "holdout_balanced_accuracy": m_ho["balanced_accuracy"],
                    "holdout_f1": m_ho["f1"],
                    "holdout_roc_auc": m_ho["roc_auc"],
                    "holdout_pr_auc": m_ho["pr_auc"],
                    "holdout_brier": m_ho["brier"],
                    "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                    "generalization_gap_val_holdout_ba": float(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]),
                }
            )

        for split_name, split_ids in alt_splits_by_domain[cand.domain].items():
            tr = subset_by_ids(df, split_ids["train"])
            va = subset_by_ids(df, split_ids["val"])
            ho = subset_by_ids(df, split_ids["holdout"])
            ev = fit_and_evaluate(
                train_df=tr,
                val_df=va,
                hold_df=ho,
                features=feats,
                target_col=target_col,
                config=cfg,
                seed=cand.winner_seed,
                calibration_method=cand.winner_calibration,
                threshold_policy=cand.winner_threshold_policy,
                fixed_threshold=None,
                recall_floor=0.55,
            )
            m_tr = ev["metrics_train"]
            m_va = ev["metrics_val"]
            m_ho = ev["metrics_hold"]
            stability_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stability_axis": "split",
                    "variant_id": split_name,
                    "seed": cand.winner_seed,
                    "calibration_method": ev["used_calibration"],
                    "threshold": ev["threshold_used"],
                    "holdout_precision": m_ho["precision"],
                    "holdout_recall": m_ho["recall"],
                    "holdout_specificity": m_ho["specificity"],
                    "holdout_balanced_accuracy": m_ho["balanced_accuracy"],
                    "holdout_f1": m_ho["f1"],
                    "holdout_roc_auc": m_ho["roc_auc"],
                    "holdout_pr_auc": m_ho["pr_auc"],
                    "holdout_brier": m_ho["brier"],
                    "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                    "generalization_gap_val_holdout_ba": float(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]),
                }
            )

    stability_df = pd.DataFrame(stability_rows).sort_values(["domain", "mode", "stability_axis", "variant_id"]).reset_index(drop=True)
    save_csv(stability_df, STAB / "hybrid_rf_seed_stability.csv")

    print_progress("Running calibration and operating-point audits")
    calibration_rows: list[dict[str, Any]] = []
    op_rows: list[dict[str, Any]] = []

    for cid, st in candidate_states.items():
        cand = st["candidate"]
        base = st["base_eval"]

        y_train = base["y_train"]
        y_val = base["y_val"]
        y_hold = base["y_hold"]

        method_rows: list[dict[str, Any]] = []
        for method, ppack in base["probs_all"].items():
            trp, vap, hop = ppack
            if method not in base["cal_diag"]:
                continue
            thr, val_score = choose_threshold(cand.winner_threshold_policy, y_val, vap, recall_floor=0.55)
            m_tr = compute_metrics(y_train, trp, thr)
            m_va = compute_metrics(y_val, vap, thr)
            m_ho = compute_metrics(y_hold, hop, thr)
            row = {
                "candidate_id": cid,
                "domain": cand.domain,
                "mode": cand.mode,
                "calibration_method": method,
                "threshold_policy": cand.winner_threshold_policy,
                "threshold": thr,
                "val_selection_score": val_score,
                "val_brier": float(base["cal_diag"][method]["val_brier"]),
                "val_ece": float(base["cal_diag"][method]["val_ece"]),
                "holdout_precision": m_ho["precision"],
                "holdout_recall": m_ho["recall"],
                "holdout_specificity": m_ho["specificity"],
                "holdout_balanced_accuracy": m_ho["balanced_accuracy"],
                "holdout_f1": m_ho["f1"],
                "holdout_roc_auc": m_ho["roc_auc"],
                "holdout_pr_auc": m_ho["pr_auc"],
                "holdout_brier": m_ho["brier"],
                "overfit_gap_train_val_ba": float(m_tr["balanced_accuracy"] - m_va["balanced_accuracy"]),
                "generalization_gap_val_holdout_ba": float(m_va["balanced_accuracy"] - m_ho["balanced_accuracy"]),
            }
            method_rows.append(row)

        if not method_rows:
            continue

        cdf = pd.DataFrame(method_rows)
        baseline = cdf[cdf["calibration_method"] == "none"]
        if baseline.empty:
            baseline = cdf.head(1)
        b_row = baseline.iloc[0]
        cdf["delta_holdout_brier_vs_none"] = cdf["holdout_brier"] - float(b_row["holdout_brier"])
        cdf["delta_holdout_balanced_accuracy_vs_none"] = cdf["holdout_balanced_accuracy"] - float(b_row["holdout_balanced_accuracy"])
        cdf["delta_holdout_pr_auc_vs_none"] = cdf["holdout_pr_auc"] - float(b_row["holdout_pr_auc"])
        cdf["calibration_recommended"] = "no"
        rec_idx = cdf.sort_values(["val_brier", "val_ece", "holdout_brier"], ascending=[True, True, True]).index[0]
        cdf.loc[rec_idx, "calibration_recommended"] = "yes"
        calibration_rows.extend(cdf.to_dict(orient="records"))

        _, va_sel, ho_sel, _, _ = calibrate_select(
            cand.winner_calibration,
            base["probs_all"],
            {"none": base["transform"], cand.winner_calibration: base["transform"]},
        )

        op_pack: list[dict[str, Any]] = []
        for pol in THRESHOLD_POLICIES:
            thr, score = choose_threshold(pol, y_val, va_sel, recall_floor=0.55)
            m_ho = compute_metrics(y_hold, ho_sel, thr)
            op_pack.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "calibration_method": cand.winner_calibration,
                    "threshold_policy": pol,
                    "threshold": thr,
                    "selection_score": score,
                    "holdout_precision": m_ho["precision"],
                    "holdout_recall": m_ho["recall"],
                    "holdout_specificity": m_ho["specificity"],
                    "holdout_balanced_accuracy": m_ho["balanced_accuracy"],
                    "holdout_f1": m_ho["f1"],
                    "holdout_roc_auc": m_ho["roc_auc"],
                    "holdout_pr_auc": m_ho["pr_auc"],
                    "holdout_brier": m_ho["brier"],
                    "is_winner_fixed_threshold": "no",
                }
            )

        m_fixed = compute_metrics(y_hold, ho_sel, base["threshold_used"])
        op_pack.append(
            {
                "candidate_id": cid,
                "domain": cand.domain,
                "mode": cand.mode,
                "calibration_method": cand.winner_calibration,
                "threshold_policy": "winner_fixed",
                "threshold": base["threshold_used"],
                "selection_score": objective_score(m_fixed),
                "holdout_precision": m_fixed["precision"],
                "holdout_recall": m_fixed["recall"],
                "holdout_specificity": m_fixed["specificity"],
                "holdout_balanced_accuracy": m_fixed["balanced_accuracy"],
                "holdout_f1": m_fixed["f1"],
                "holdout_roc_auc": m_fixed["roc_auc"],
                "holdout_pr_auc": m_fixed["pr_auc"],
                "holdout_brier": m_fixed["brier"],
                "is_winner_fixed_threshold": "yes",
            }
        )

        opdf = pd.DataFrame(op_pack)
        reci = opdf[opdf["threshold_policy"].isin(THRESHOLD_POLICIES)].sort_values("selection_score", ascending=False).index[0]
        opdf["operating_point_recommended"] = "no"
        opdf.loc[reci, "operating_point_recommended"] = "yes"
        op_rows.extend(opdf.to_dict(orient="records"))

    calibration_df = pd.DataFrame(calibration_rows).sort_values(["domain", "mode", "calibration_method"]).reset_index(drop=True)
    save_csv(calibration_df, CAL / "hybrid_rf_candidate_calibration.csv")

    op_df = pd.DataFrame(op_rows).sort_values(["domain", "mode", "threshold_policy"]).reset_index(drop=True)
    save_csv(op_df, TABLES / "hybrid_rf_candidate_operating_points.csv")

    print_progress("Running ablation and stress audits")
    ablation_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []

    for cid, st in candidate_states.items():
        cand = st["candidate"]
        base = st["base_eval"]
        model = base["model"]
        transform = base["transform"]
        threshold = base["threshold_used"]
        y_hold = base["y_hold"]
        X_hold = base["X_hold"]
        features = st["features"]
        imp = base["importance"].index.tolist()

        m_base = base["metrics_hold"]
        top1 = imp[:1]
        top3 = imp[:3]
        top5 = imp[:5]
        top10 = imp[:10]

        dsm5_feats = [f for f in features if is_dsm5_feature(f)]
        clean_feats = [f for f in features if not is_dsm5_feature(f)]

        ablation_cases: list[tuple[str, list[str]]] = []
        if top1:
            ablation_cases.append(("drop_top1", top1))
        if top3:
            ablation_cases.append(("drop_top3", top3))
        if top5:
            ablation_cases.append(("drop_top5", top5))
        if top10 and len(features) > len(top10):
            ablation_cases.append(("keep_top10_only", [f for f in features if f not in top10]))
        if dsm5_feats:
            ablation_cases.append(("drop_dsm5_features", dsm5_feats))
        if clean_feats:
            ablation_cases.append(("drop_cleanbase_features", clean_feats))

        for case_name, impacted in ablation_cases:
            X_case = X_hold.copy()
            X_case.loc[:, [f for f in impacted if f in X_case.columns]] = np.nan
            prob = transform(np.clip(model.predict_proba(X_case)[:, 1], 1e-6, 1 - 1e-6))
            m = compute_metrics(y_hold, prob, threshold)
            ablation_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "ablation_case": case_name,
                    "impacted_features": "|".join(impacted),
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                    "delta_precision_vs_baseline": m["precision"] - m_base["precision"],
                    "delta_recall_vs_baseline": m["recall"] - m_base["recall"],
                    "delta_balanced_accuracy_vs_baseline": m["balanced_accuracy"] - m_base["balanced_accuracy"],
                    "delta_pr_auc_vs_baseline": m["pr_auc"] - m_base["pr_auc"],
                    "delta_brier_vs_baseline": m["brier"] - m_base["brier"],
                }
            )

        for j, feat in enumerate(top5):
            X_perm = X_hold.copy()
            rng = np.random.default_rng(cand.winner_seed + 300 + j)
            X_perm[feat] = rng.permutation(X_perm[feat].to_numpy())
            prob = transform(np.clip(model.predict_proba(X_perm)[:, 1], 1e-6, 1 - 1e-6))
            m = compute_metrics(y_hold, prob, threshold)
            ablation_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "ablation_case": f"permute_{feat}",
                    "impacted_features": feat,
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                    "delta_precision_vs_baseline": m["precision"] - m_base["precision"],
                    "delta_recall_vs_baseline": m["recall"] - m_base["recall"],
                    "delta_balanced_accuracy_vs_baseline": m["balanced_accuracy"] - m_base["balanced_accuracy"],
                    "delta_pr_auc_vs_baseline": m["pr_auc"] - m_base["pr_auc"],
                    "delta_brier_vs_baseline": m["brier"] - m_base["brier"],
                }
            )

        for ratio in [0.05, 0.10, 0.20]:
            X_miss = inject_missing(X_hold, features, ratio=ratio, seed=cand.winner_seed + int(ratio * 1000))
            prob = transform(np.clip(model.predict_proba(X_miss)[:, 1], 1e-6, 1 - 1e-6))
            m = compute_metrics(y_hold, prob, threshold)
            stress_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stress_type": "missingness",
                    "scenario": f"missing_ratio_{ratio:.2f}",
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                    "delta_precision_vs_baseline": m["precision"] - m_base["precision"],
                    "delta_recall_vs_baseline": m["recall"] - m_base["recall"],
                    "delta_balanced_accuracy_vs_baseline": m["balanced_accuracy"] - m_base["balanced_accuracy"],
                    "delta_pr_auc_vs_baseline": m["pr_auc"] - m_base["pr_auc"],
                    "delta_brier_vs_baseline": m["brier"] - m_base["brier"],
                }
            )

        for short_mode in MODE_CHAIN.get(cand.mode, []):
            try:
                short_allowed = set(read_feature_list(fs_v1, short_mode, cand.domain, "full_eligible"))
            except Exception:
                short_allowed = eligible_map.get(short_mode, set())
            to_nan = [f for f in features if f not in short_allowed]
            if not to_nan:
                continue
            X_cut = X_hold.copy()
            X_cut.loc[:, to_nan] = np.nan
            prob = transform(np.clip(model.predict_proba(X_cut)[:, 1], 1e-6, 1 - 1e-6))
            m = compute_metrics(y_hold, prob, threshold)
            stress_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stress_type": "mode_shortening",
                    "scenario": f"truncate_to_{short_mode}",
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                    "delta_precision_vs_baseline": m["precision"] - m_base["precision"],
                    "delta_recall_vs_baseline": m["recall"] - m_base["recall"],
                    "delta_balanced_accuracy_vs_baseline": m["balanced_accuracy"] - m_base["balanced_accuracy"],
                    "delta_pr_auc_vs_baseline": m["pr_auc"] - m_base["pr_auc"],
                    "delta_brier_vs_baseline": m["brier"] - m_base["brier"],
                }
            )

        for dthr in [-0.10, -0.05, 0.05, 0.10]:
            thr = float(np.clip(threshold + dthr, 0.01, 0.99))
            m = compute_metrics(y_hold, base["hold_prob"], thr)
            stress_rows.append(
                {
                    "candidate_id": cid,
                    "domain": cand.domain,
                    "mode": cand.mode,
                    "stress_type": "threshold_sensitivity",
                    "scenario": f"threshold_shift_{dthr:+.2f}",
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                    "delta_precision_vs_baseline": m["precision"] - m_base["precision"],
                    "delta_recall_vs_baseline": m["recall"] - m_base["recall"],
                    "delta_balanced_accuracy_vs_baseline": m["balanced_accuracy"] - m_base["balanced_accuracy"],
                    "delta_pr_auc_vs_baseline": m["pr_auc"] - m_base["pr_auc"],
                    "delta_brier_vs_baseline": m["brier"] - m_base["brier"],
                }
            )

    ablation_df = pd.DataFrame(ablation_rows).sort_values(["domain", "mode", "ablation_case"]).reset_index(drop=True)
    save_csv(ablation_df, ABL / "hybrid_rf_candidate_ablation.csv")

    stress_df = pd.DataFrame(stress_rows).sort_values(["domain", "mode", "stress_type", "scenario"]).reset_index(drop=True)
    save_csv(stress_df, STRESS / "hybrid_rf_candidate_stress.csv")

    print_progress("Estimating DSM-5 contribution")
    dsm_rows: list[dict[str, Any]] = []

    for domain in ["adhd", "conduct", "elimination", "anxiety", "depression"]:
        preferred_mode = REPRESENTATIVE_DSM5.get(domain)
        cands_domain = [s for s in candidate_states.values() if s["candidate"].domain == domain]
        chosen_state: dict[str, Any] | None = None
        if preferred_mode is not None:
            for s in cands_domain:
                if s["candidate"].mode == preferred_mode:
                    chosen_state = s
                    break
        if chosen_state is None and cands_domain:
            chosen_state = cands_domain[0]
        if chosen_state is None:
            continue

        cand = chosen_state["candidate"]
        cfg = chosen_state["cfg"]
        feats_full = chosen_state["features"]
        target_col = chosen_state["target_col"]
        split_ids = chosen_state["split_ids"]

        train_df = subset_by_ids(df, split_ids["train"])
        val_df = subset_by_ids(df, split_ids["val"])
        hold_df = subset_by_ids(df, split_ids["holdout"])

        dsm5_feats = [f for f in feats_full if is_dsm5_feature(f)]
        clean_feats = [f for f in feats_full if not is_dsm5_feature(f)]

        variants = [
            ("clean_base_only", clean_feats),
            ("dsm5_only", dsm5_feats),
            ("hybrid_full", feats_full),
        ]
        domain_rows: list[dict[str, Any]] = []

        for variant_name, feats in variants:
            if len(feats) < 4:
                domain_rows.append(
                    {
                        "domain": domain,
                        "representative_mode": cand.mode,
                        "candidate_id": cand.candidate_id,
                        "variant": variant_name,
                        "n_features": int(len(feats)),
                        "status": "insufficient_features",
                        "holdout_precision": np.nan,
                        "holdout_recall": np.nan,
                        "holdout_specificity": np.nan,
                        "holdout_balanced_accuracy": np.nan,
                        "holdout_f1": np.nan,
                        "holdout_roc_auc": np.nan,
                        "holdout_pr_auc": np.nan,
                        "holdout_brier": np.nan,
                    }
                )
                continue

            ev = fit_and_evaluate(
                train_df=train_df,
                val_df=val_df,
                hold_df=hold_df,
                features=feats,
                target_col=target_col,
                config=cfg,
                seed=cand.winner_seed,
                calibration_method=cand.winner_calibration,
                threshold_policy=cand.winner_threshold_policy,
                fixed_threshold=None,
                recall_floor=0.55,
            )
            m = ev["metrics_hold"]
            domain_rows.append(
                {
                    "domain": domain,
                    "representative_mode": cand.mode,
                    "candidate_id": cand.candidate_id,
                    "variant": variant_name,
                    "n_features": int(len(feats)),
                    "status": "ok",
                    "holdout_precision": m["precision"],
                    "holdout_recall": m["recall"],
                    "holdout_specificity": m["specificity"],
                    "holdout_balanced_accuracy": m["balanced_accuracy"],
                    "holdout_f1": m["f1"],
                    "holdout_roc_auc": m["roc_auc"],
                    "holdout_pr_auc": m["pr_auc"],
                    "holdout_brier": m["brier"],
                }
            )

        ddf = pd.DataFrame(domain_rows)
        clean_ok = ddf[(ddf["variant"] == "clean_base_only") & (ddf["status"] == "ok")]
        full_ok = ddf[(ddf["variant"] == "hybrid_full") & (ddf["status"] == "ok")]
        clean_ref = clean_ok.iloc[0] if not clean_ok.empty else None
        full_ref = full_ok.iloc[0] if not full_ok.empty else None

        for col in [
            "delta_precision_vs_clean",
            "delta_recall_vs_clean",
            "delta_balanced_accuracy_vs_clean",
            "delta_pr_auc_vs_clean",
            "delta_brier_vs_clean",
            "delta_precision_vs_hybrid_full",
            "delta_recall_vs_hybrid_full",
            "delta_balanced_accuracy_vs_hybrid_full",
            "delta_pr_auc_vs_hybrid_full",
            "delta_brier_vs_hybrid_full",
        ]:
            ddf[col] = np.nan

        if clean_ref is not None:
            ddf.loc[:, "delta_precision_vs_clean"] = ddf["holdout_precision"] - float(clean_ref["holdout_precision"])
            ddf.loc[:, "delta_recall_vs_clean"] = ddf["holdout_recall"] - float(clean_ref["holdout_recall"])
            ddf.loc[:, "delta_balanced_accuracy_vs_clean"] = ddf["holdout_balanced_accuracy"] - float(clean_ref["holdout_balanced_accuracy"])
            ddf.loc[:, "delta_pr_auc_vs_clean"] = ddf["holdout_pr_auc"] - float(clean_ref["holdout_pr_auc"])
            ddf.loc[:, "delta_brier_vs_clean"] = ddf["holdout_brier"] - float(clean_ref["holdout_brier"])

        if full_ref is not None:
            ddf.loc[:, "delta_precision_vs_hybrid_full"] = ddf["holdout_precision"] - float(full_ref["holdout_precision"])
            ddf.loc[:, "delta_recall_vs_hybrid_full"] = ddf["holdout_recall"] - float(full_ref["holdout_recall"])
            ddf.loc[:, "delta_balanced_accuracy_vs_hybrid_full"] = ddf["holdout_balanced_accuracy"] - float(full_ref["holdout_balanced_accuracy"])
            ddf.loc[:, "delta_pr_auc_vs_hybrid_full"] = ddf["holdout_pr_auc"] - float(full_ref["holdout_pr_auc"])
            ddf.loc[:, "delta_brier_vs_hybrid_full"] = ddf["holdout_brier"] - float(full_ref["holdout_brier"])

        dsm_rows.extend(ddf.to_dict(orient="records"))

    dsm_df = pd.DataFrame(dsm_rows).sort_values(["domain", "variant"]).reset_index(drop=True)
    save_csv(dsm_df, TABLES / "hybrid_rf_dsm5_contribution_analysis.csv")

    print_progress("Building stability summary and final promotion decisions")
    summary_rows: list[dict[str, Any]] = []
    for _, r in reproduction_df.iterrows():
        cid = str(r["candidate_id"])
        bdf = boot_df[boot_df["candidate_id"] == cid]
        if bdf.empty:
            continue
        b = bdf.iloc[0]
        summary_rows.append(summarize_candidate_stability(cid, r, b, stability_df, stress_df, ablation_df))

    stability_summary_df = pd.DataFrame(summary_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(stability_summary_df, TABLES / "hybrid_rf_candidate_stability_summary.csv")

    decision_rows: list[dict[str, Any]] = []
    for _, r in reproduction_df.iterrows():
        cid = str(r["candidate_id"])
        ss = stability_summary_df[stability_summary_df["candidate_id"] == cid]
        if ss.empty:
            continue
        srow = ss.iloc[0]
        dec, risk_pipe, risk_n = classify_candidate(r, srow, calibration_df)
        decision_rows.append(
            {
                "candidate_id": cid,
                "domain": r["domain"],
                "mode": r["mode"],
                "role": r["role"],
                "role_tag": r["role_tag"],
                "winner_feature_set_id": r["winner_feature_set_id"],
                "winner_config_id": r["winner_config_id"],
                "winner_calibration": r["winner_calibration"],
                "winner_threshold_policy": r["winner_threshold_policy"],
                "n_features": int(r["n_features"]),
                "holdout_precision": float(r["holdout_precision"]),
                "holdout_recall": float(r["holdout_recall"]),
                "holdout_specificity": float(r["holdout_specificity"]),
                "holdout_balanced_accuracy": float(r["holdout_balanced_accuracy"]),
                "holdout_f1": float(r["holdout_f1"]),
                "holdout_roc_auc": float(r["holdout_roc_auc"]),
                "holdout_pr_auc": float(r["holdout_pr_auc"]),
                "holdout_brier": float(r["holdout_brier"]),
                "delta_holdout_precision_vs_v1": float(r["delta_holdout_precision_vs_v1"]),
                "delta_holdout_recall_vs_v1": float(r["delta_holdout_recall_vs_v1"]),
                "delta_holdout_balanced_accuracy_vs_v1": float(r["delta_holdout_balanced_accuracy_vs_v1"]),
                "delta_holdout_pr_auc_vs_v1": float(r["delta_holdout_pr_auc_vs_v1"]),
                "delta_holdout_brier_vs_v1": float(r["delta_holdout_brier_vs_v1"]),
                "overfit_gap_train_val_ba": float(r["overfit_gap_train_val_ba"]),
                "generalization_gap_val_holdout_ba": float(r["generalization_gap_val_holdout_ba"]),
                "seed_std_balanced_accuracy": float(srow["seed_std_balanced_accuracy"]),
                "split_std_balanced_accuracy": float(srow["split_std_balanced_accuracy"]),
                "bootstrap_balanced_accuracy_ci_width": float(srow["bootstrap_balanced_accuracy_ci_width"]),
                "worst_stress_delta_balanced_accuracy": float(srow["worst_stress_delta_balanced_accuracy"]),
                "drop_top3_delta_balanced_accuracy": float(srow["drop_top3_delta_balanced_accuracy"]),
                "stability_grade": srow["stability_grade"],
                "reproduced_material": r["reproduced_material"],
                "promotion_decision": dec,
                "risk_flags": risk_pipe,
                "risk_count": risk_n,
            }
        )

    decisions_df = pd.DataFrame(decision_rows).sort_values(["domain", "mode"]).reset_index(drop=True)
    save_csv(decisions_df, TABLES / "hybrid_rf_final_promotion_decisions.csv")

    compare_rows: list[dict[str, Any]] = []
    for domain in sorted(decisions_df["domain"].unique()):
        sub = decisions_df[decisions_df["domain"] == domain]
        for role in ["caregiver", "psychologist"]:
            m23 = sub[(sub["role"] == role) & (sub["mode"].str.endswith("2_3"))]
            mf = sub[(sub["role"] == role) & (sub["mode"].str.endswith("full"))]
            if m23.empty or mf.empty:
                continue
            r23 = m23.iloc[0]
            rf = mf.iloc[0]
            d_prec = float(rf["holdout_precision"] - r23["holdout_precision"])
            d_rec = float(rf["holdout_recall"] - r23["holdout_recall"])
            d_ba = float(rf["holdout_balanced_accuracy"] - r23["holdout_balanced_accuracy"])
            d_pr = float(rf["holdout_pr_auc"] - r23["holdout_pr_auc"])
            practical_23 = (abs(d_ba) < 0.01) and (abs(d_pr) < 0.01) and (abs(d_prec) < 0.015)
            compare_rows.append(
                {
                    "domain": domain,
                    "role": role,
                    "mode_2_3": r23["mode"],
                    "mode_full": rf["mode"],
                    "decision_2_3": r23["promotion_decision"],
                    "decision_full": rf["promotion_decision"],
                    "delta_precision_full_minus_2_3": d_prec,
                    "delta_recall_full_minus_2_3": d_rec,
                    "delta_balanced_accuracy_full_minus_2_3": d_ba,
                    "delta_pr_auc_full_minus_2_3": d_pr,
                    "full_material_gain": "yes" if material_gain(d_prec, d_rec, d_ba, d_pr) else "no",
                    "prefer_2_3_practical": "yes" if practical_23 else "no",
                }
            )
    compare_df = pd.DataFrame(compare_rows).sort_values(["domain", "role"]).reset_index(drop=True)
    save_csv(compare_df, TABLES / "hybrid_rf_2_3_vs_full_comparison.csv")

    champion_rows: list[dict[str, Any]] = []
    for domain in sorted(decisions_df["domain"].unique()):
        sub = decisions_df[decisions_df["domain"] == domain].copy()
        sub["decision_rank"] = sub["promotion_decision"].map(decision_rank)
        sub["mode_complexity"] = sub["mode"].map(mode_complexity)
        sub = sub.sort_values(
            ["decision_rank", "holdout_balanced_accuracy", "holdout_precision", "holdout_pr_auc", "mode_complexity"],
            ascending=[False, False, False, False, True],
        )

        chosen = sub.iloc[0].copy()
        note = "best_decision_rank_and_metrics"

        if chosen["mode"].endswith("full"):
            role = chosen["role"]
            m23 = sub[(sub["role"] == role) & (sub["mode"].str.endswith("2_3"))]
            if not m23.empty:
                c23 = m23.iloc[0]
                d_prec = float(chosen["holdout_precision"] - c23["holdout_precision"])
                d_rec = float(chosen["holdout_recall"] - c23["holdout_recall"])
                d_ba = float(chosen["holdout_balanced_accuracy"] - c23["holdout_balanced_accuracy"])
                d_pr = float(chosen["holdout_pr_auc"] - c23["holdout_pr_auc"])
                full_material = material_gain(d_prec, d_rec, d_ba, d_pr)
                if (not full_material) and (decision_rank(str(c23["promotion_decision"])) >= decision_rank(str(chosen["promotion_decision"])) - 1):
                    chosen = c23.copy()
                    note = "prefer_2_3_due_to_practical_equivalence"

        champion_rows.append(
            {
                "domain": domain,
                "champion_candidate_id": chosen["candidate_id"],
                "champion_mode": chosen["mode"],
                "champion_role": chosen["role"],
                "champion_decision": chosen["promotion_decision"],
                "champion_precision": chosen["holdout_precision"],
                "champion_recall": chosen["holdout_recall"],
                "champion_specificity": chosen["holdout_specificity"],
                "champion_balanced_accuracy": chosen["holdout_balanced_accuracy"],
                "champion_f1": chosen["holdout_f1"],
                "champion_roc_auc": chosen["holdout_roc_auc"],
                "champion_pr_auc": chosen["holdout_pr_auc"],
                "champion_brier": chosen["holdout_brier"],
                "selection_note": note,
            }
        )

    champions_df = pd.DataFrame(champion_rows).sort_values("domain").reset_index(drop=True)
    save_csv(champions_df, TABLES / "hybrid_rf_final_champions.csv")

    print_progress("Writing reports")
    overfit_df = decisions_df.copy()
    overfit_df["overfit_warning"] = (
        (overfit_df["overfit_gap_train_val_ba"] > 0.06)
        | (overfit_df["generalization_gap_val_holdout_ba"] > 0.05)
    )

    generalization_df = decisions_df.copy()
    generalization_df["generalization_ok"] = (
        (generalization_df["holdout_balanced_accuracy"] >= 0.80)
        & (generalization_df["holdout_precision"] >= 0.80)
        & (generalization_df["holdout_recall"] >= 0.55)
        & (generalization_df["stability_grade"].isin(["strong", "acceptable"]))
    )

    dsm_gain_rows = []
    if not dsm_df.empty:
        for domain in sorted(dsm_df["domain"].unique()):
            dd = dsm_df[(dsm_df["domain"] == domain) & (dsm_df["status"] == "ok")]
            if dd.empty:
                continue
            h = dd[dd["variant"] == "hybrid_full"]
            c = dd[dd["variant"] == "clean_base_only"]
            d = dd[dd["variant"] == "dsm5_only"]
            if h.empty or c.empty:
                continue
            hh = h.iloc[0]
            cc = c.iloc[0]
            ddm = d.iloc[0] if not d.empty else None
            dsm_gain_rows.append(
                {
                    "domain": domain,
                    "hybrid_minus_clean_precision": float(hh["holdout_precision"] - cc["holdout_precision"]),
                    "hybrid_minus_clean_recall": float(hh["holdout_recall"] - cc["holdout_recall"]),
                    "hybrid_minus_clean_balanced_accuracy": float(hh["holdout_balanced_accuracy"] - cc["holdout_balanced_accuracy"]),
                    "hybrid_minus_clean_pr_auc": float(hh["holdout_pr_auc"] - cc["holdout_pr_auc"]),
                    "hybrid_minus_clean_brier": float(hh["holdout_brier"] - cc["holdout_brier"]),
                    "dsm5_only_balanced_accuracy": float(ddm["holdout_balanced_accuracy"]) if ddm is not None else np.nan,
                    "dsm5_material_value": "yes"
                    if material_gain(
                        float(hh["holdout_precision"] - cc["holdout_precision"]),
                        float(hh["holdout_recall"] - cc["holdout_recall"]),
                        float(hh["holdout_balanced_accuracy"] - cc["holdout_balanced_accuracy"]),
                        float(hh["holdout_pr_auc"] - cc["holdout_pr_auc"]),
                    )
                    else "no",
                }
            )
    dsm_gain_df = pd.DataFrame(dsm_gain_rows).sort_values("domain").reset_index(drop=True)
    save_csv(dsm_gain_df, TABLES / "hybrid_rf_dsm5_domain_gain_summary.csv")

    report_analysis = [
        "# Hybrid RF Consolidation v2 - Analysis",
        "",
        "## Reproduced Candidates",
        md_table(
            reproduction_df[
                [
                    "candidate_id",
                    "domain",
                    "mode",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "reproduced_material",
                ]
            ]
        ),
        "",
        "## Stability Summary",
        md_table(
            stability_summary_df[
                [
                    "candidate_id",
                    "stability_grade",
                    "seed_std_balanced_accuracy",
                    "split_std_balanced_accuracy",
                    "bootstrap_balanced_accuracy_ci_width",
                    "worst_stress_delta_balanced_accuracy",
                ]
            ]
        ),
        "",
        "## Promotion Decisions",
        md_table(
            decisions_df[
                [
                    "candidate_id",
                    "promotion_decision",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "holdout_brier",
                    "risk_flags",
                ]
            ]
        ),
        "",
        "## 2/3 vs Full",
        md_table(compare_df),
    ]
    write_md(REPORTS / "hybrid_rf_consolidation_analysis.md", "\n".join(report_analysis))

    report_overfit = [
        "# Hybrid RF Overfitting Resolution",
        "",
        f"- candidates_with_overfit_warning: {int(overfit_df['overfit_warning'].sum())}/{len(overfit_df)}",
        "",
        md_table(
            overfit_df[
                [
                    "candidate_id",
                    "domain",
                    "mode",
                    "overfit_gap_train_val_ba",
                    "generalization_gap_val_holdout_ba",
                    "overfit_warning",
                    "promotion_decision",
                ]
            ]
        ),
        "",
        "- Rule: train-val BA gap > 0.06 or val-holdout BA gap > 0.05.",
    ]
    write_md(REPORTS / "hybrid_rf_overfitting_resolution.md", "\n".join(report_overfit))

    report_gen = [
        "# Hybrid RF Generalization Confirmation",
        "",
        f"- candidates_generalization_ok: {int(generalization_df['generalization_ok'].sum())}/{len(generalization_df)}",
        "",
        md_table(
            generalization_df[
                [
                    "candidate_id",
                    "domain",
                    "mode",
                    "holdout_precision",
                    "holdout_recall",
                    "holdout_balanced_accuracy",
                    "holdout_pr_auc",
                    "stability_grade",
                    "generalization_ok",
                ]
            ]
        ),
    ]
    write_md(REPORTS / "hybrid_rf_generalization_confirmation.md", "\n".join(report_gen))

    report_dsm = [
        "# Hybrid RF DSM-5 Value Report",
        "",
        "## Per-domain hybrid vs clean-base contribution",
        md_table(dsm_gain_df),
        "",
        "## Detailed experiment table",
        md_table(dsm_df),
    ]
    write_md(REPORTS / "hybrid_rf_dsm5_value_report.md", "\n".join(report_dsm))

    promoted_now = decisions_df[decisions_df["promotion_decision"] == "PROMOTE_NOW"]
    promoted_caveat = decisions_df[decisions_df["promotion_decision"] == "PROMOTE_WITH_CAVEAT"]
    hold_rows = decisions_df[decisions_df["promotion_decision"] == "HOLD_FOR_TARGETED_FIX"]
    reject_rows = decisions_df[decisions_df["promotion_decision"] == "REJECT_AS_PRIMARY"]

    closure_ready = bool(len(hold_rows) <= 1 and len(reject_rows) == 0)

    report_final = [
        "# Hybrid RF Final Promotion Report",
        "",
        f"- PROMOTE_NOW: {len(promoted_now)}",
        f"- PROMOTE_WITH_CAVEAT: {len(promoted_caveat)}",
        f"- HOLD_FOR_TARGETED_FIX: {len(hold_rows)}",
        f"- REJECT_AS_PRIMARY: {len(reject_rows)}",
        f"- close_main_modeling_stage: {'yes' if closure_ready else 'no'}",
        "",
        "## Decisions",
        md_table(decisions_df),
        "",
        "## Champions",
        md_table(champions_df),
    ]
    write_md(REPORTS / "hybrid_rf_final_promotion_report.md", "\n".join(report_final))

    report_exec = [
        "# Hybrid RF Executive Summary v2",
        "",
        f"- candidate_count: {len(decisions_df)}",
        f"- promoted_now: {len(promoted_now)}",
        f"- promoted_with_caveat: {len(promoted_caveat)}",
        f"- hold_for_fix: {len(hold_rows)}",
        f"- rejected: {len(reject_rows)}",
        f"- overfitting_evidence: {'yes' if bool(overfit_df['overfit_warning'].any()) else 'no'}",
        f"- generalization_evidence: {'yes' if bool(generalization_df['generalization_ok'].mean() >= 0.70) else 'no'}",
        f"- close_main_modeling_stage: {'yes' if closure_ready else 'no'}",
        "",
        "## Final Champions",
        md_table(champions_df),
    ]
    write_md(REPORTS / "hybrid_rf_executive_summary_v2.md", "\n".join(report_exec))

    print_progress("Writing artifact manifest")
    generated: list[Path] = []
    for parent in [INV, REPRO, BOOT, STAB, CAL, ABL, STRESS, TABLES, REPORTS]:
        generated.extend(sorted([p for p in parent.rglob("*") if p.is_file()]))

    entries: list[dict[str, Any]] = []
    for p in generated:
        entries.append(
            {
                "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": p.stat().st_size,
                "sha256": hash_file(p),
            }
        )

    manifest = {
        "campaign_line": LINE,
        "created_at_utc": now_iso(),
        "source_dataset": str(DATASET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_v1_line": "hybrid_rf_ceiling_push_v1",
        "candidate_count": int(len(decisions_df)),
        "promotion_counts": {
            "PROMOTE_NOW": int(len(promoted_now)),
            "PROMOTE_WITH_CAVEAT": int(len(promoted_caveat)),
            "HOLD_FOR_TARGETED_FIX": int(len(hold_rows)),
            "REJECT_AS_PRIMARY": int(len(reject_rows)),
        },
        "close_main_modeling_stage": "yes" if closure_ready else "no",
        "generated_files": entries,
    }
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "hybrid_rf_consolidation_v2_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print_progress("Campaign completed")


if __name__ == "__main__":
    run_campaign()
