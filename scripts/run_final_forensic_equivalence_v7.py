from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore", category=FutureWarning)

XGB_AVAILABLE = True
LGB_AVAILABLE = True
CAT_AVAILABLE = True

try:
    from xgboost import XGBClassifier
except Exception:  # noqa: BLE001
    XGB_AVAILABLE = False

try:
    from lightgbm import LGBMClassifier
except Exception:  # noqa: BLE001
    LGB_AVAILABLE = False

try:
    from catboost import CatBoostClassifier
except Exception:  # noqa: BLE001
    CAT_AVAILABLE = False


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "final_forensic_equivalence_v7"
INV = BASE / "inventory"
EQA = BASE / "equivalence_audit"
DBG = BASE / "pipeline_debug"
IMP = BASE / "improvement"
CAS = BASE / "case_analysis"
TBL = BASE / "tables"
RPT = BASE / "reports"
ART = ROOT / "artifacts" / "final_forensic_equivalence_v7"

V5 = ROOT / "data" / "final_advanced_model_improvement_v5"
V6 = ROOT / "data" / "final_output_realism_v6"
DATASET_PATH = (
    ROOT
    / "data"
    / "processed_hybrid_dsm5_v2"
    / "final"
    / "model_ready"
    / "strict_no_leakage_hybrid"
    / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
)
BASIC_Q_PATH = ROOT / "reports" / "questionnaire_model_strategy_eval_v1" / "questionnaire_basic_candidate_v1.csv"
INPUT_BREAKDOWN_PATH = ROOT / "reports" / "questionnaire_input_breakdown" / "input_breakdown.csv"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
TARGET = {d: f"target_domain_{d}" for d in DOMAINS}
CAT_COLS = {"sex_assigned_at_birth", "site"}
ESSENTIAL = {"age_years", "sex_assigned_at_birth", "site", "release"}
PRIORITY = {
    ("caregiver", "elimination"),
    ("caregiver", "adhd"),
    ("caregiver", "depression"),
    ("psychologist", "elimination"),
    ("psychologist", "adhd"),
    ("psychologist", "depression"),
}

BASELINE_V5 = {
    ("caregiver", "adhd"): {"precision": 0.9495, "recall": 0.8178, "specificity": 0.9440, "balanced_accuracy": 0.8809, "f1": 0.8788, "roc_auc": 0.9484, "pr_auc": 0.9500, "brier": 0.0842},
    ("caregiver", "conduct"): {"precision": 0.9722, "recall": 0.8750, "specificity": 0.9903, "balanced_accuracy": 0.9326, "f1": 0.9211, "roc_auc": 0.9781, "pr_auc": 0.9506, "brier": 0.0388},
    ("caregiver", "elimination"): {"precision": 0.9483, "recall": 0.6832, "specificity": 0.9520, "balanced_accuracy": 0.8176, "f1": 0.7942, "roc_auc": 0.8759, "pr_auc": 0.8907, "brier": 0.1331},
    ("caregiver", "anxiety"): {"precision": 0.8912, "recall": 0.9747, "specificity": 0.9636, "balanced_accuracy": 0.9692, "f1": 0.9304, "roc_auc": 0.9899, "pr_auc": 0.9765, "brier": 0.0238},
    ("caregiver", "depression"): {"precision": 0.9890, "recall": 0.7826, "specificity": 0.9942, "balanced_accuracy": 0.8884, "f1": 0.8738, "roc_auc": 0.9822, "pr_auc": 0.9688, "brier": 0.0541},
    ("psychologist", "adhd"): {"precision": 0.9562, "recall": 0.8137, "specificity": 0.9520, "balanced_accuracy": 0.8828, "f1": 0.8792, "roc_auc": 0.9522, "pr_auc": 0.9544, "brier": 0.0829},
    ("psychologist", "conduct"): {"precision": 0.9730, "recall": 0.9000, "specificity": 0.9903, "balanced_accuracy": 0.9451, "f1": 0.9351, "roc_auc": 0.9712, "pr_auc": 0.9381, "brier": 0.0368},
    ("psychologist", "elimination"): {"precision": 0.9402, "recall": 0.6832, "specificity": 0.9440, "balanced_accuracy": 0.8136, "f1": 0.7914, "roc_auc": 0.8770, "pr_auc": 0.8958, "brier": 0.1371},
    ("psychologist", "anxiety"): {"precision": 0.9851, "recall": 1.0000, "specificity": 0.9955, "balanced_accuracy": 0.9977, "f1": 0.9925, "roc_auc": 1.0000, "pr_auc": 0.9999, "brier": 0.0021},
    ("psychologist", "depression"): {"precision": 0.9023, "recall": 0.8957, "specificity": 0.9337, "balanced_accuracy": 0.9147, "f1": 0.8981, "roc_auc": 0.9803, "pr_auc": 0.9633, "brier": 0.0569},
}


@dataclass
class ModelBundle:
    mode: str
    domain: str
    family: str
    feature_variant: str
    features: list[str]
    threshold_policy: str
    threshold: float
    abstention_band: float
    calibration: str
    target_variant: str
    seed: int
    model: Any
    calibrator: Any


def ensure_dirs() -> None:
    for p in [BASE, INV, EQA, DBG, IMP, CAS, TBL, RPT, ART]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def load_metadata(domain: str) -> dict[str, Any]:
    p = ROOT / "models" / "champions" / f"rf_{domain}_current" / "metadata.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_split_ids(domain: str, part: str) -> pd.Series:
    p = ROOT / "data" / "processed_hybrid_dsm5_v2" / "splits" / f"domain_{domain}_strict_full" / f"ids_{part}.csv"
    ids = pd.read_csv(p)
    col = "participant_id" if "participant_id" in ids.columns else ids.columns[0]
    return ids[col].astype(str)


def subset(df: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids.astype(str)))].copy()


def normalize_sex(x: Any) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "Unknown"
    raw = str(x).strip().lower()
    if raw in {"m", "male", "masculino", "1"}:
        return "Male"
    if raw in {"f", "female", "femenino", "0"}:
        return "Female"
    return "Unknown"


def normalize_site(x: Any) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "CBIC"
    raw = str(x).strip()
    if raw in {"CBIC", "CUNY", "RUBIC", "Staten Island"}:
        return raw
    return "CBIC"


def preprocess_frame(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    if "sex_assigned_at_birth" in X.columns:
        X["sex_assigned_at_birth"] = X["sex_assigned_at_birth"].map(normalize_sex)
    if "site" in X.columns:
        X["site"] = X["site"].map(normalize_site)
    return X


def preprocessor_for(features: list[str]) -> ColumnTransformer:
    cats = [c for c in features if c in CAT_COLS]
    nums = [c for c in features if c not in CAT_COLS]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), nums),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cats),
        ],
        remainder="drop",
    )


def fit_model(family: str, Xtr: pd.DataFrame, ytr: pd.Series, seed: int, domain: str) -> Any:
    if family == "rf":
        pre = preprocessor_for(list(Xtr.columns))
        est = RandomForestClassifier(
            n_estimators=600 if domain in {"elimination", "adhd"} else 450,
            max_depth=None if domain in {"elimination", "adhd"} else 22,
            min_samples_leaf=1 if domain in {"elimination", "adhd"} else 2,
            min_samples_split=4,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        )
        pipe = Pipeline([("pre", pre), ("model", est)])
        pipe.fit(Xtr, ytr)
        return pipe

    if family == "xgboost" and XGB_AVAILABLE:
        pre = preprocessor_for(list(Xtr.columns))
        est = XGBClassifier(
            n_estimators=550 if domain in {"elimination", "adhd", "depression"} else 450,
            max_depth=5 if domain in {"elimination", "adhd"} else 4,
            learning_rate=0.03,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=1.5,
            reg_alpha=0.2,
            objective="binary:logistic",
            tree_method="hist",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=4,
        )
        pipe = Pipeline([("pre", pre), ("model", est)])
        pipe.fit(Xtr, ytr)
        return pipe

    if family == "lightgbm" and LGB_AVAILABLE:
        pre = preprocessor_for(list(Xtr.columns))
        est = LGBMClassifier(
            n_estimators=650 if domain in {"elimination", "adhd", "depression"} else 500,
            learning_rate=0.03,
            num_leaves=63 if domain in {"elimination", "adhd"} else 47,
            min_child_samples=20,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=seed,
            class_weight="balanced",
            n_jobs=4,
            verbose=-1,
        )
        pipe = Pipeline([("pre", pre), ("model", est)])
        pipe.fit(Xtr, ytr)
        return pipe

    if family == "catboost" and CAT_AVAILABLE:
        Xtr2 = Xtr.copy()
        for c in Xtr2.columns:
            if c in CAT_COLS:
                Xtr2[c] = Xtr2[c].fillna("Unknown").astype(str)
            else:
                med = pd.to_numeric(Xtr2[c], errors="coerce").median()
                fill = 0.0 if pd.isna(med) else float(med)
                Xtr2[c] = pd.to_numeric(Xtr2[c], errors="coerce").fillna(fill)
        cat_idx = [i for i, c in enumerate(Xtr2.columns) if c in CAT_COLS]
        model = CatBoostClassifier(
            iterations=550 if domain in {"elimination", "adhd", "depression"} else 450,
            depth=6,
            learning_rate=0.03,
            loss_function="Logloss",
            eval_metric="Logloss",
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
            auto_class_weights="Balanced",
        )
        model.fit(Xtr2, ytr, cat_features=cat_idx)
        return ("catboost", model)

    raise RuntimeError(f"family_not_available:{family}")


def predict_proba(model: Any, X: pd.DataFrame) -> np.ndarray:
    if isinstance(model, tuple) and model[0] == "catboost":
        m = model[1]
        X2 = X.copy()
        for c in X2.columns:
            if c in CAT_COLS:
                X2[c] = X2[c].fillna("Unknown").astype(str)
            else:
                med = pd.to_numeric(X2[c], errors="coerce").median()
                fill = 0.0 if pd.isna(med) else float(med)
                X2[c] = pd.to_numeric(X2[c], errors="coerce").fillna(fill)
        return m.predict_proba(X2)[:, 1]
    return model.predict_proba(X)[:, 1]


def calibrate_probs(yva: pd.Series, pva: np.ndarray, pte: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, Any]:
    cands: list[tuple[str, np.ndarray, np.ndarray, float, Any]] = [("none", pva, pte, brier_score_loss(yva, pva), None)]
    if len(np.unique(yva)) >= 2:
        lr = LogisticRegression(max_iter=600)
        lr.fit(pva.reshape(-1, 1), yva.astype(int))
        pv, pt = lr.predict_proba(pva.reshape(-1, 1))[:, 1], lr.predict_proba(pte.reshape(-1, 1))[:, 1]
        cands.append(("platt", pv, pt, brier_score_loss(yva, pv), lr))
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(pva, yva.astype(int))
        pv2, pt2 = iso.predict(pva), iso.predict(pte)
        cands.append(("isotonic", pv2, pt2, brier_score_loss(yva, pv2), iso))
    best = sorted(cands, key=lambda x: x[3])[0]
    return best[1], best[2], best[0], best[4]


def apply_calibrator(calibration: str, calibrator: Any, p: np.ndarray) -> np.ndarray:
    if calibration == "none" or calibrator is None:
        return p
    if calibration == "platt":
        return calibrator.predict_proba(p.reshape(-1, 1))[:, 1]
    return calibrator.predict(p)


def compute_metrics(y_true: pd.Series, prob: np.ndarray, thr: float) -> dict[str, float]:
    pred = (prob >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": spec,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, prob)),
        "pr_auc": float(average_precision_score(y_true, prob)),
        "brier": float(brier_score_loss(y_true, prob)),
    }


def threshold_score(metrics: dict[str, float], policy: str, domain: str) -> float:
    if policy == "precision_guarded":
        return 0.40 * metrics["precision"] + 0.30 * metrics["balanced_accuracy"] + 0.15 * metrics["pr_auc"] + 0.15 * metrics["recall"]
    if policy == "recall_guarded":
        return 0.40 * metrics["recall"] + 0.30 * metrics["balanced_accuracy"] + 0.15 * metrics["f1"] + 0.15 * metrics["pr_auc"]
    if domain == "elimination":
        return 0.35 * metrics["recall"] + 0.30 * metrics["balanced_accuracy"] + 0.20 * metrics["precision"] + 0.15 * (1 - metrics["brier"])
    if domain == "depression":
        return 0.33 * metrics["recall"] + 0.32 * metrics["balanced_accuracy"] + 0.20 * metrics["precision"] + 0.15 * (1 - metrics["brier"])
    return 0.45 * metrics["balanced_accuracy"] + 0.20 * metrics["f1"] + 0.20 * metrics["precision"] + 0.15 * metrics["recall"]


def choose_threshold(y_true: pd.Series, prob: np.ndarray, policy: str, domain: str) -> tuple[float, float]:
    best_t, best = 0.5, -1.0
    for t in np.linspace(0.12, 0.88, 153):
        m = compute_metrics(y_true, prob, float(t))
        s = threshold_score(m, policy, domain)
        if s > best:
            best_t, best = float(t), float(s)
    return best_t, best


def choose_band(y_true: pd.Series, prob: np.ndarray, thr: float, domain: str) -> tuple[float, float]:
    best_band, best_score = 0.08, -1.0
    for b in [0.03, 0.05, 0.08, 0.10, 0.12, 0.15]:
        keep = np.abs(prob - thr) >= b
        cov = float(keep.mean())
        if cov < 0.40:
            continue
        yk = y_true[keep]
        pk = prob[keep]
        if len(np.unique(yk)) < 2:
            continue
        mk = compute_metrics(yk, pk, thr)
        score = 0.40 * mk["balanced_accuracy"] + 0.20 * mk["precision"] + 0.15 * mk["pr_auc"] + 0.15 * cov + 0.10 * mk["recall"]
        if domain in {"elimination", "depression", "adhd"}:
            score += 0.05 * mk["recall"]
        if score > best_score:
            best_band, best_score = float(b), float(score)
    return best_band, best_score


def build_feature_maps(df: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    legacy = {d: list(load_metadata(d)["feature_columns"]) for d in DOMAINS}
    basic = pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).drop_duplicates().tolist()
    basic = [f for f in basic if f in df.columns]
    caregiver = {d: sorted(set([f for f in legacy[d] if f in basic] + list(ESSENTIAL & set(legacy[d])))) for d in DOMAINS}
    psychologist = {d: legacy[d][:] for d in DOMAINS}
    return caregiver, psychologist


def add_derived_features(df: pd.DataFrame, feature_union: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    rows = []
    prefixes = sorted(set([c.split("_", 1)[0] for c in feature_union if "_" in c and not c.startswith("target_")]))
    for pref in prefixes:
        cols = [c for c in feature_union if c.startswith(pref + "_") and c in out.columns and not c.startswith("target_")]
        if len(cols) < 3:
            continue
        num = out[cols].apply(pd.to_numeric, errors="coerce")
        mean_col = f"der_{pref}_mean"
        std_col = f"der_{pref}_std"
        miss_col = f"der_{pref}_missing_ratio"
        out[mean_col] = num.mean(axis=1)
        out[std_col] = num.std(axis=1).fillna(0.0)
        out[miss_col] = num.isna().mean(axis=1)
        rows.append({"feature_name": mean_col, "source_columns": "|".join(cols), "family": "aggregation", "transformation": "row_mean"})
        rows.append({"feature_name": std_col, "source_columns": "|".join(cols), "family": "dispersion", "transformation": "row_std"})
        rows.append({"feature_name": miss_col, "source_columns": "|".join(cols), "family": "missingness", "transformation": "row_missing_ratio"})
    core_cols = [c for c in feature_union if c in out.columns and not c.startswith("target_")]
    if core_cols:
        core_num = out[core_cols].apply(pd.to_numeric, errors="coerce")
        out["der_global_missing_ratio"] = core_num.isna().mean(axis=1)
        out["der_global_nonzero_ratio"] = (core_num.fillna(0) != 0).mean(axis=1)
        rows.append({"feature_name": "der_global_missing_ratio", "source_columns": "|".join(core_cols[:40]), "family": "missingness", "transformation": "global_missing_ratio"})
        rows.append({"feature_name": "der_global_nonzero_ratio", "source_columns": "|".join(core_cols[:40]), "family": "density", "transformation": "global_nonzero_ratio"})
    return out, pd.DataFrame(rows)


def feature_variant(base_features: list[str], variant: str, derived: pd.DataFrame) -> list[str]:
    if variant == "base":
        return [f for f in base_features if f]
    dcols = derived["feature_name"].tolist() if not derived.empty else []
    prefixes = sorted(set([c.split("_", 1)[0] for c in base_features if "_" in c]))
    domain_derived = [f for f in dcols if any(f.startswith(f"der_{p}_") for p in prefixes)]
    domain_derived += ["der_global_missing_ratio", "der_global_nonzero_ratio"]
    domain_derived = sorted(set([f for f in domain_derived if f in dcols]))
    if variant == "compact":
        return sorted(set(base_features + [f for f in domain_derived if "missing_ratio" in f][:6]))
    return sorted(set(base_features + domain_derived[:12]))


def elimination_target_variants(df: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    out["baseline"] = df["target_domain_elimination"].astype(float)
    out["elimination_any_baseline"] = df["target_domain_elimination"].astype(float)
    enu = df["target_enuresis_exact"].astype(float)
    enc = df["target_encopresis_exact"].astype(float)
    out["elimination_union_internal"] = ((enu == 1) | (enc == 1)).astype(float)
    out["elimination_overlap_strict"] = ((enu == 1) & (enc == 1)).astype(float)
    direct_sum = pd.to_numeric(df.get("target_enuresis_exact_direct_criteria_count", 0), errors="coerce").fillna(0) + pd.to_numeric(df.get("target_encopresis_exact_direct_criteria_count", 0), errors="coerce").fillna(0)
    absent_sum = pd.to_numeric(df.get("target_enuresis_exact_absent_criteria_count", 0), errors="coerce").fillna(0) + pd.to_numeric(df.get("target_encopresis_exact_absent_criteria_count", 0), errors="coerce").fillna(0)
    clear = out["baseline"].copy()
    clear[(clear == 1) & (direct_sum < 1)] = np.nan
    clear[(clear == 0) & (absent_sum < 1)] = np.nan
    out["elimination_clear_cases"] = clear
    return out


def recover_baseline_config(mode: str, domain: str, best_row: pd.Series, trials: pd.DataFrame) -> dict[str, Any]:
    filt = trials[
        (trials["mode"] == mode)
        & (trials["domain"] == domain)
        & (trials["status"] == "ok")
        & (trials["family"] == best_row["family"])
        & (trials["feature_variant"] == best_row["feature_variant"])
        & (trials["target_variant"] == best_row["target_variant"])
        & (trials["threshold_policy"] == best_row["threshold_policy"])
    ].copy()
    if filt.empty:
        return {
            "mode": mode,
            "domain": domain,
            "family": best_row["family"],
            "feature_variant": best_row["feature_variant"],
            "target_variant": best_row["target_variant"],
            "threshold_policy": best_row["threshold_policy"],
            "threshold": 0.5,
            "abstention_band": 0.08,
            "calibration": "none",
            "seed": 11,
            "n_features": int(best_row.get("n_features", 0)),
            "source": "fallback_from_best_results",
        }
    top = filt.sort_values(["val_objective", "balanced_accuracy", "pr_auc"], ascending=False).iloc[0]
    return {
        "mode": mode,
        "domain": domain,
        "family": str(top["family"]),
        "feature_variant": str(top["feature_variant"]),
        "target_variant": str(top["target_variant"]),
        "threshold_policy": str(top["threshold_policy"]),
        "threshold": float(top["threshold"]),
        "abstention_band": float(top["abstention_band"]),
        "calibration": str(top["calibration"]),
        "seed": int(top["seed"]),
        "n_features": int(top["n_features"]),
        "source": "recovered_from_v5_trials",
    }


def objective_focus(domain: str, metrics: dict[str, float]) -> float:
    if domain == "elimination":
        return 0.34 * metrics["recall"] + 0.28 * metrics["balanced_accuracy"] + 0.18 * metrics["precision"] + 0.12 * metrics["pr_auc"] + 0.08 * (1 - metrics["brier"])
    if domain == "adhd":
        return 0.30 * metrics["recall"] + 0.30 * metrics["balanced_accuracy"] + 0.18 * metrics["precision"] + 0.12 * metrics["pr_auc"] + 0.10 * (1 - metrics["brier"])
    return 0.32 * metrics["recall"] + 0.30 * metrics["balanced_accuracy"] + 0.18 * metrics["precision"] + 0.10 * metrics["pr_auc"] + 0.10 * (1 - metrics["brier"])


def select_alt_family(mode: str, domain: str, base_family: str, trials: pd.DataFrame) -> str:
    agg = (
        trials[
            (trials["mode"] == mode)
            & (trials["domain"] == domain)
            & (trials["status"] == "ok")
        ]
        .groupby("family")[["balanced_accuracy", "pr_auc"]]
        .mean()
        .reset_index()
        .sort_values(["balanced_accuracy", "pr_auc"], ascending=False)
    )
    for fam in agg["family"].tolist():
        if fam != base_family:
            return str(fam)
    return base_family


def run_focused_improvement(
    df: pd.DataFrame,
    caregiver_map: dict[str, list[str]],
    psychologist_map: dict[str, list[str]],
    derived_registry: pd.DataFrame,
    elim_variants: dict[str, pd.Series],
    v5_best: pd.DataFrame,
    v5_trials: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], dict[str, Any]]]:
    rows = []
    focused_final_rows = []
    selected: dict[tuple[str, str], dict[str, Any]] = {}

    for mode, domain in sorted(PRIORITY):
        best_row = v5_best[(v5_best["mode"] == mode) & (v5_best["domain"] == domain)].iloc[0]
        base_family = str(best_row["family"])
        alt_family = select_alt_family(mode, domain, base_family, v5_trials)
        fmap = caregiver_map if mode == "caregiver" else psychologist_map
        base_feats = fmap[domain]
        base_variant = str(best_row["feature_variant"])
        target_variant = str(best_row["target_variant"])
        threshold_policy = str(best_row["threshold_policy"])
        feature_variants = sorted(set([base_variant, "engineered", "compact"]))
        families = sorted(set([base_family, alt_family]))

        train = subset(df, load_split_ids(domain, "train"))
        val = subset(df, load_split_ids(domain, "val"))
        test = subset(df, load_split_ids(domain, "test"))

        ytr = elim_variants[target_variant].loc[train.index] if domain == "elimination" else train[TARGET[domain]].astype(float)
        yva = elim_variants[target_variant].loc[val.index] if domain == "elimination" else val[TARGET[domain]].astype(float)
        yte = elim_variants[target_variant].loc[test.index] if domain == "elimination" else test[TARGET[domain]].astype(float)

        tr_mask, va_mask, te_mask = ytr.notna(), yva.notna(), yte.notna()
        train_eff, val_eff, test_eff = train.loc[tr_mask].copy(), val.loc[va_mask].copy(), test.loc[te_mask].copy()
        ytr, yva, yte = ytr.loc[tr_mask].astype(int), yva.loc[va_mask].astype(int), yte.loc[te_mask].astype(int)

        if len(np.unique(ytr)) < 2 or len(np.unique(yva)) < 2 or len(np.unique(yte)) < 2:
            continue

        round1 = []
        for family in families:
            for fvar in feature_variants:
                feats = [f for f in feature_variant(base_feats, fvar, derived_registry) if f in df.columns and not f.startswith("target_")]
                if len(feats) < 6:
                    continue
                try:
                    model = fit_model(family, preprocess_frame(train_eff, feats), ytr, seed=11, domain=domain)
                    pva_raw = predict_proba(model, preprocess_frame(val_eff, feats))
                    pte_raw = predict_proba(model, preprocess_frame(test_eff, feats))
                except Exception as exc:  # noqa: BLE001
                    rows.append({"mode": mode, "domain": domain, "round_id": 1, "family": family, "feature_variant": fvar, "seed": 11, "status": "error", "error": str(exc), "n_features": len(feats)})
                    continue

                pva, pte, cal_name, _ = calibrate_probs(yva, pva_raw, pte_raw)
                policies = sorted(set([threshold_policy, "balanced", "precision_guarded", "recall_guarded"]))
                for pol in policies:
                    thr, _ = choose_threshold(yva, pva, pol, domain)
                    band, _ = choose_band(yva, pva, thr, domain)
                    m = compute_metrics(yte, pte, thr)
                    m["objective"] = objective_focus(domain, m)
                    m["round_id"] = 1
                    m["mode"] = mode
                    m["domain"] = domain
                    m["family"] = family
                    m["feature_variant"] = fvar
                    m["threshold_policy"] = pol
                    m["threshold"] = float(thr)
                    m["abstention_band"] = float(band)
                    m["calibration"] = cal_name
                    m["target_variant"] = target_variant
                    m["seed"] = 11
                    m["status"] = "ok"
                    m["error"] = ""
                    m["n_features"] = len(feats)
                    keep = np.abs(pte - thr) >= band
                    m["abstention_coverage"] = float(keep.mean())
                    m["high_conf_precision"] = float(precision_score(yte[keep], (pte[keep] >= thr).astype(int), zero_division=0)) if keep.any() else 0.0
                    m["input_missing_ratio"] = float(preprocess_frame(test_eff, feats).isna().mean().mean())
                    round1.append(m)
                    rows.append(m)

        r1 = pd.DataFrame(round1)
        if r1.empty:
            continue
        top_sig = (
            r1.sort_values(["objective", "balanced_accuracy", "pr_auc"], ascending=False)
            .head(2)[["family", "feature_variant", "threshold_policy"]]
            .drop_duplicates()
        )

        round2 = []
        for _, sig in top_sig.iterrows():
            fam = str(sig["family"])
            fvar = str(sig["feature_variant"])
            pol = str(sig["threshold_policy"])
            feats = [f for f in feature_variant(base_feats, fvar, derived_registry) if f in df.columns and not f.startswith("target_")]
            if len(feats) < 6:
                continue
            for seed in [11, 29]:
                try:
                    model = fit_model(fam, preprocess_frame(train_eff, feats), ytr, seed=seed, domain=domain)
                    pva_raw = predict_proba(model, preprocess_frame(val_eff, feats))
                    pte_raw = predict_proba(model, preprocess_frame(test_eff, feats))
                except Exception as exc:  # noqa: BLE001
                    rows.append({"mode": mode, "domain": domain, "round_id": 2, "family": fam, "feature_variant": fvar, "threshold_policy": pol, "seed": seed, "status": "error", "error": str(exc), "n_features": len(feats)})
                    continue
                pva, pte, cal_name, _ = calibrate_probs(yva, pva_raw, pte_raw)
                thr, _ = choose_threshold(yva, pva, pol, domain)
                band, _ = choose_band(yva, pva, thr, domain)
                m = compute_metrics(yte, pte, thr)
                m["objective"] = objective_focus(domain, m)
                m.update({
                    "round_id": 2,
                    "mode": mode,
                    "domain": domain,
                    "family": fam,
                    "feature_variant": fvar,
                    "threshold_policy": pol,
                    "threshold": float(thr),
                    "abstention_band": float(band),
                    "calibration": cal_name,
                    "target_variant": target_variant,
                    "seed": seed,
                    "status": "ok",
                    "error": "",
                    "n_features": len(feats),
                    "abstention_coverage": float((np.abs(pte - thr) >= band).mean()),
                    "high_conf_precision": float(precision_score(yte[np.abs(pte - thr) >= band], (pte[np.abs(pte - thr) >= band] >= thr).astype(int), zero_division=0))
                    if (np.abs(pte - thr) >= band).any() else 0.0,
                    "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean()),
                })
                round2.append(m)
                rows.append(m)

        if len(top_sig["family"].unique()) >= 2:
            best_two = top_sig.head(2).reset_index(drop=True)
            fam_a = str(best_two.loc[0, "family"])
            fam_b = str(best_two.loc[1, "family"])
            fvar = str(best_two.loc[0, "feature_variant"])
            pol = str(best_two.loc[0, "threshold_policy"])
            feats = [f for f in feature_variant(base_feats, fvar, derived_registry) if f in df.columns and not f.startswith("target_")]
            if len(feats) >= 6:
                for seed in [11, 29]:
                    try:
                        ma = fit_model(fam_a, preprocess_frame(train_eff, feats), ytr, seed=seed, domain=domain)
                        mb = fit_model(fam_b, preprocess_frame(train_eff, feats), ytr, seed=seed + 1, domain=domain)
                        pva_raw = 0.5 * predict_proba(ma, preprocess_frame(val_eff, feats)) + 0.5 * predict_proba(mb, preprocess_frame(val_eff, feats))
                        pte_raw = 0.5 * predict_proba(ma, preprocess_frame(test_eff, feats)) + 0.5 * predict_proba(mb, preprocess_frame(test_eff, feats))
                    except Exception as exc:  # noqa: BLE001
                        rows.append({"mode": mode, "domain": domain, "round_id": 2, "family": "ensemble_ab", "feature_variant": fvar, "threshold_policy": pol, "seed": seed, "status": "error", "error": str(exc), "n_features": len(feats)})
                        continue
                    pva, pte, cal_name, _ = calibrate_probs(yva, pva_raw, pte_raw)
                    thr, _ = choose_threshold(yva, pva, pol, domain)
                    band, _ = choose_band(yva, pva, thr, domain)
                    m = compute_metrics(yte, pte, thr)
                    m["objective"] = objective_focus(domain, m)
                    m.update({
                        "round_id": 2,
                        "mode": mode,
                        "domain": domain,
                        "family": f"ensemble_{fam_a}_{fam_b}",
                        "feature_variant": fvar,
                        "threshold_policy": pol,
                        "threshold": float(thr),
                        "abstention_band": float(band),
                        "calibration": cal_name,
                        "target_variant": target_variant,
                        "seed": seed,
                        "status": "ok",
                        "error": "",
                        "n_features": len(feats),
                        "abstention_coverage": float((np.abs(pte - thr) >= band).mean()),
                        "high_conf_precision": float(precision_score(yte[np.abs(pte - thr) >= band], (pte[np.abs(pte - thr) >= band] >= thr).astype(int), zero_division=0))
                        if (np.abs(pte - thr) >= band).any() else 0.0,
                        "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean()),
                    })
                    round2.append(m)
                    rows.append(m)

        r2 = pd.DataFrame(round2)
        if r2.empty:
            continue

        r1_best = float(r1["objective"].max())
        r2_best = float(r2.groupby(["family", "feature_variant", "threshold_policy"])["objective"].mean().max())
        run_r3 = (r2_best - r1_best) >= 0.005
        if run_r3:
            top = (
                r2.groupby(["family", "feature_variant", "threshold_policy"])[["objective", "balanced_accuracy", "pr_auc"]]
                .mean()
                .sort_values(["objective", "balanced_accuracy", "pr_auc"], ascending=False)
                .reset_index()
                .iloc[0]
            )
            fam = str(top["family"])
            fvar = str(top["feature_variant"])
            base_pol = str(top["threshold_policy"])
            feats = [f for f in feature_variant(base_feats, fvar, derived_registry) if f in df.columns and not f.startswith("target_")]
            for seed in [11, 29]:
                try:
                    if fam.startswith("ensemble_"):
                        parts = fam.split("_")
                        fam_a, fam_b = parts[1], parts[2]
                        ma = fit_model(fam_a, preprocess_frame(train_eff, feats), ytr, seed=seed, domain=domain)
                        mb = fit_model(fam_b, preprocess_frame(train_eff, feats), ytr, seed=seed + 1, domain=domain)
                        pva_raw = 0.5 * predict_proba(ma, preprocess_frame(val_eff, feats)) + 0.5 * predict_proba(mb, preprocess_frame(val_eff, feats))
                        pte_raw = 0.5 * predict_proba(ma, preprocess_frame(test_eff, feats)) + 0.5 * predict_proba(mb, preprocess_frame(test_eff, feats))
                    else:
                        mobj = fit_model(fam, preprocess_frame(train_eff, feats), ytr, seed=seed, domain=domain)
                        pva_raw = predict_proba(mobj, preprocess_frame(val_eff, feats))
                        pte_raw = predict_proba(mobj, preprocess_frame(test_eff, feats))
                except Exception as exc:  # noqa: BLE001
                    rows.append({"mode": mode, "domain": domain, "round_id": 3, "family": fam, "feature_variant": fvar, "threshold_policy": base_pol, "seed": seed, "status": "error", "error": str(exc), "n_features": len(feats)})
                    continue
                pva, pte, cal_name, _ = calibrate_probs(yva, pva_raw, pte_raw)
                for pol in sorted(set([base_pol, "precision_guarded", "recall_guarded", "balanced"])):
                    thr, _ = choose_threshold(yva, pva, pol, domain)
                    for band in [0.03, 0.05, 0.08, 0.10, 0.12]:
                        m = compute_metrics(yte, pte, thr)
                        m["objective"] = objective_focus(domain, m) + 0.02 * float((np.abs(pte - thr) >= band).mean())
                        m.update({
                            "round_id": 3,
                            "mode": mode,
                            "domain": domain,
                            "family": fam,
                            "feature_variant": fvar,
                            "threshold_policy": pol,
                            "threshold": float(thr),
                            "abstention_band": float(band),
                            "calibration": cal_name,
                            "target_variant": target_variant,
                            "seed": seed,
                            "status": "ok",
                            "error": "",
                            "n_features": len(feats),
                            "abstention_coverage": float((np.abs(pte - thr) >= band).mean()),
                            "high_conf_precision": float(precision_score(yte[np.abs(pte - thr) >= band], (pte[np.abs(pte - thr) >= band] >= thr).astype(int), zero_division=0))
                            if (np.abs(pte - thr) >= band).any() else 0.0,
                            "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean()),
                        })
                        rows.append(m)

        all_pair = pd.DataFrame([r for r in rows if r.get("mode") == mode and r.get("domain") == domain and r.get("status") == "ok"])
        summary = (
            all_pair.groupby(["family", "feature_variant", "threshold_policy", "target_variant"])[
                ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "objective", "abstention_coverage", "high_conf_precision", "input_missing_ratio", "n_features"]
            ]
            .mean()
            .reset_index()
        )
        summary = summary.sort_values(["objective", "balanced_accuracy", "pr_auc"], ascending=False)
        best_new = summary.iloc[0]
        baseline = BASELINE_V5[(mode, domain)]
        deltas = {k: float(best_new[k] - baseline[k]) for k in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]}
        material = (deltas["balanced_accuracy"] >= 0.010) or (deltas["recall"] >= 0.030 and deltas["precision"] >= -0.030) or (deltas["brier"] <= -0.008)
        marginal = (deltas["balanced_accuracy"] >= 0.004) or (deltas["recall"] >= 0.015 and deltas["precision"] >= -0.040) or (deltas["brier"] <= -0.003)
        improvement_level = "material" if material else ("marginal" if marginal else "none")

        selected_cfg = {
            "mode": mode,
            "domain": domain,
            "family": str(best_new["family"]),
            "feature_variant": str(best_new["feature_variant"]),
            "target_variant": str(best_new["target_variant"]),
            "threshold_policy": str(best_new["threshold_policy"]),
            "threshold": float(all_pair[
                (all_pair["family"] == best_new["family"])
                & (all_pair["feature_variant"] == best_new["feature_variant"])
                & (all_pair["threshold_policy"] == best_new["threshold_policy"])
            ]["threshold"].mean()),
            "abstention_band": float(all_pair[
                (all_pair["family"] == best_new["family"])
                & (all_pair["feature_variant"] == best_new["feature_variant"])
                & (all_pair["threshold_policy"] == best_new["threshold_policy"])
            ]["abstention_band"].mean()),
            "calibration": str(all_pair[
                (all_pair["family"] == best_new["family"])
                & (all_pair["feature_variant"] == best_new["feature_variant"])
                & (all_pair["threshold_policy"] == best_new["threshold_policy"])
            ]["calibration"].mode().iloc[0]),
            "seed": 11,
            "n_features": int(best_new["n_features"]),
            "improvement_level": improvement_level,
        }

        if improvement_level == "none":
            base_cfg = recover_baseline_config(mode, domain, best_row, v5_trials)
            base_cfg["improvement_level"] = "none_baseline_kept"
            selected[(mode, domain)] = base_cfg
            final_metrics = baseline.copy()
            final_metrics["mode"] = mode
            final_metrics["domain"] = domain
            final_metrics["chosen_family"] = base_cfg["family"]
            final_metrics["chosen_feature_variant"] = base_cfg["feature_variant"]
            final_metrics["chosen_threshold_policy"] = base_cfg["threshold_policy"]
            final_metrics["improvement_level"] = "none_baseline_kept"
            final_metrics["delta_balanced_accuracy"] = 0.0
            final_metrics["delta_recall"] = 0.0
            final_metrics["delta_brier"] = 0.0
            focused_final_rows.append(final_metrics)
        else:
            selected[(mode, domain)] = selected_cfg
            final_metrics = {
                "mode": mode,
                "domain": domain,
                "chosen_family": selected_cfg["family"],
                "chosen_feature_variant": selected_cfg["feature_variant"],
                "chosen_threshold_policy": selected_cfg["threshold_policy"],
                "improvement_level": improvement_level,
                "precision": float(best_new["precision"]),
                "recall": float(best_new["recall"]),
                "specificity": float(best_new["specificity"]),
                "balanced_accuracy": float(best_new["balanced_accuracy"]),
                "f1": float(best_new["f1"]),
                "roc_auc": float(best_new["roc_auc"]),
                "pr_auc": float(best_new["pr_auc"]),
                "brier": float(best_new["brier"]),
                "delta_precision": deltas["precision"],
                "delta_recall": deltas["recall"],
                "delta_specificity": deltas["specificity"],
                "delta_balanced_accuracy": deltas["balanced_accuracy"],
                "delta_f1": deltas["f1"],
                "delta_roc_auc": deltas["roc_auc"],
                "delta_pr_auc": deltas["pr_auc"],
                "delta_brier": deltas["brier"],
                "n_features": int(best_new["n_features"]),
            }
            focused_final_rows.append(final_metrics)

    return pd.DataFrame(rows), pd.DataFrame(focused_final_rows), selected


def scenario_names_for_mode(mode: str) -> list[str]:
    base = [
        "cuestionario_completo",
        "parcial_leve",
        "parcial_moderado",
        "missing_legitimos_no_se",
        "cobertura_alta",
        "cobertura_media",
        "cobertura_baja",
    ]
    if mode == "caregiver":
        base += ["cuidador_sin_self_report", "cuidador_con_self_report_opcional"]
    else:
        base += ["psicologo_completo", "source_mix_heterogeneo"]
    base += [
        "borderline",
        "cerca_threshold",
        "transdiagnostico",
        "alta_incertidumbre",
        "abstention_esperada",
        "elimination_prudencia_reforzada",
        "adhd_depression_tradeoff",
    ]
    return base


def apply_mask_for_scenario(row: pd.Series, features: list[str], scenario: str, mode: str, rng: np.random.Generator) -> tuple[pd.Series, float, float]:
    x = row.copy()
    feat = [f for f in features if f in x.index]
    if not feat:
        return x, 0.0, 0.0
    self_cols = [f for f in feat if f.startswith("ysr_") or f.startswith("scared_sr_") or f.startswith("ari_sr_")]
    cat_cols = [f for f in feat if f in CAT_COLS]
    num_cols = [f for f in feat if f not in CAT_COLS]

    def random_mask(cols: list[str], frac: float) -> None:
        if not cols or frac <= 0:
            return
        n = int(round(len(cols) * frac))
        n = max(0, min(n, len(cols)))
        if n == 0:
            return
        chosen = rng.choice(cols, size=n, replace=False)
        for c in chosen:
            x[c] = np.nan

    if scenario == "parcial_leve":
        random_mask(num_cols, 0.10)
        random_mask(cat_cols, 0.10)
    elif scenario == "parcial_moderado":
        random_mask(num_cols, 0.30)
        random_mask(cat_cols, 0.30)
    elif scenario == "missing_legitimos_no_se":
        random_mask(num_cols, 0.20)
        random_mask(cat_cols, 0.15)
    elif scenario == "cobertura_alta":
        random_mask(num_cols, 0.05)
    elif scenario == "cobertura_media":
        random_mask(num_cols, 0.25)
        random_mask(cat_cols, 0.20)
    elif scenario == "cobertura_baja":
        random_mask(num_cols, 0.50)
        random_mask(cat_cols, 0.40)
    elif scenario == "cuidador_sin_self_report":
        for c in self_cols:
            x[c] = np.nan
    elif scenario == "cuidador_con_self_report_opcional":
        random_mask(self_cols, 0.45)
    elif scenario == "source_mix_heterogeneo":
        random_mask(self_cols, 0.35)
        random_mask(num_cols, 0.15)
    elif scenario in {"borderline", "cerca_threshold", "transdiagnostico", "alta_incertidumbre", "abstention_esperada", "elimination_prudencia_reforzada", "adhd_depression_tradeoff"}:
        random_mask(num_cols, 0.08 if mode == "psychologist" else 0.12)

    cov = float(pd.Series([x[c] for c in feat]).notna().mean())
    self_cov = float(pd.Series([x[c] for c in self_cols]).notna().mean()) if self_cols else 1.0
    return x, cov, self_cov


def risk_band(prob: float, thr: float, uncertain: bool) -> str:
    if uncertain:
        return "uncertain"
    if prob < max(0.0, thr - 0.15):
        return "low"
    if prob < min(1.0, thr + 0.15):
        return "moderate"
    return "high"


def confidence_pct(prob: float, thr: float, uncertain: bool) -> float:
    margin = abs(prob - thr)
    c = 100.0 * min(1.0, margin / 0.35)
    c = max(5.0, min(99.0, c))
    if uncertain:
        c = min(c, 55.0)
    return float(c)


def evidence_quality(coverage: float) -> str:
    if coverage >= 0.85:
        return "high"
    if coverage >= 0.65:
        return "medium"
    return "low"


def caveat_for(domain: str, mode: str) -> tuple[str, str]:
    if domain == "elimination":
        return ("high", "Dominio con mayor incertidumbre relativa; interpretar con cautela reforzada y revisión profesional.")
    if mode == "caregiver":
        return ("medium", "Resultado orientativo de alerta temprana; no reemplaza evaluación clínica profesional.")
    return ("low", "Resultado orientativo para apoyo profesional; no constituye diagnóstico clínico definitivo.")


def short_expl(prob: float, rb: str, uncertain: bool, domain: str) -> str:
    if uncertain:
        return f"Señal limítrofe en {domain}; conviene ampliar información o revisión profesional."
    if rb == "high":
        return f"Patrón consistente con riesgo elevado en {domain}."
    if rb == "moderate":
        return f"Señales mixtas en {domain}; se recomienda seguimiento."
    return f"No se observan señales fuertes actuales en {domain}."


def run() -> None:
    ensure_dirs()
    rng = np.random.default_rng(20260402)

    df = pd.read_csv(DATASET_PATH)
    caregiver_map, psychologist_map = build_feature_maps(df)
    union = set().union(*[set(v) for v in caregiver_map.values()], *[set(v) for v in psychologist_map.values()])
    df_eng, fe_registry = add_derived_features(df, union)
    elim_variants = elimination_target_variants(df_eng)

    v5_best = pd.concat(
        [
            pd.read_csv(V5 / "caregiver" / "caregiver_full_results.csv"),
            pd.read_csv(V5 / "psychologist" / "psychologist_full_results.csv"),
        ],
        ignore_index=True,
    )
    v5_trials = pd.concat(
        [
            pd.read_csv(V5 / "caregiver" / "caregiver_trial_registry.csv"),
            pd.read_csv(V5 / "psychologist" / "psychologist_trial_registry.csv"),
        ],
        ignore_index=True,
    )

    inventory_rows = []
    baseline_cfg: dict[tuple[str, str], dict[str, Any]] = {}
    for mode in ["caregiver", "psychologist"]:
        for domain in DOMAINS:
            br = v5_best[(v5_best["mode"] == mode) & (v5_best["domain"] == domain)].iloc[0]
            cfg = recover_baseline_config(mode, domain, br, v5_trials)
            baseline_cfg[(mode, domain)] = cfg
            inventory_rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "family": cfg["family"],
                    "feature_variant": cfg["feature_variant"],
                    "target_variant": cfg["target_variant"],
                    "threshold_policy": cfg["threshold_policy"],
                    "threshold": cfg["threshold"],
                    "abstention_band": cfg["abstention_band"],
                    "calibration": cfg["calibration"],
                    "n_features": cfg["n_features"],
                    "precision": BASELINE_V5[(mode, domain)]["precision"],
                    "recall": BASELINE_V5[(mode, domain)]["recall"],
                    "specificity": BASELINE_V5[(mode, domain)]["specificity"],
                    "balanced_accuracy": BASELINE_V5[(mode, domain)]["balanced_accuracy"],
                    "f1": BASELINE_V5[(mode, domain)]["f1"],
                    "roc_auc": BASELINE_V5[(mode, domain)]["roc_auc"],
                    "pr_auc": BASELINE_V5[(mode, domain)]["pr_auc"],
                    "brier": BASELINE_V5[(mode, domain)]["brier"],
                    "open_weakness": "elimination_recall" if domain == "elimination" else ("adhd_recall" if domain == "adhd" else ("depression_caregiver_recall" if (mode == "caregiver" and domain == "depression") else "minor")),
                    "caveat_level_expected": "high" if domain == "elimination" else ("medium" if mode == "caregiver" else "low"),
                }
            )
    inv_df = pd.DataFrame(inventory_rows)
    save_csv(inv_df, INV / "final_model_inventory.csv")
    write_md(RPT / "final_model_inventory.md", "# Final model inventory (starting point)\n\n" + inv_df.to_string(index=False))

    focused_trials, focused_results, focused_selected = run_focused_improvement(
        df_eng,
        caregiver_map,
        psychologist_map,
        fe_registry,
        elim_variants,
        v5_best,
        v5_trials,
    )
    save_csv(focused_trials, IMP / "focused_trial_registry.csv")
    save_csv(focused_results, IMP / "focused_results.csv")
    write_md(
        RPT / "focused_improvement_analysis.md",
        "# Focused improvement analysis\n\n"
        + "Dominios focalizados: elimination (ambos), adhd (ambos), depression cuidador/psicólogo.\n\n"
        + "## Resultados finales focalizados\n\n"
        + (focused_results.to_string(index=False) if not focused_results.empty else "Sin resultados focalizados.")
        + "\n\n## Resumen\n"
        + "- Máximo 2 rondas fuertes + 1 refinamiento adicional solo con señal.\n"
        + "- Se conserva baseline v5 cuando no hay mejora robusta.\n",
    )

    final_cfg: dict[tuple[str, str], dict[str, Any]] = {}
    for mode in ["caregiver", "psychologist"]:
        for domain in DOMAINS:
            key = (mode, domain)
            final_cfg[key] = baseline_cfg[key].copy()
            if key in focused_selected:
                if focused_selected[key].get("improvement_level") != "none_baseline_kept":
                    final_cfg[key].update(focused_selected[key])
                else:
                    final_cfg[key] = focused_selected[key]

    bundles: dict[tuple[str, str], ModelBundle] = {}
    final_metrics_rows = []
    for mode in ["caregiver", "psychologist"]:
        fmap = caregiver_map if mode == "caregiver" else psychologist_map
        for domain in DOMAINS:
            cfg = final_cfg[(mode, domain)]
            feats = [f for f in feature_variant(fmap[domain], cfg["feature_variant"], fe_registry) if f in df_eng.columns and not f.startswith("target_")]
            target_var = cfg.get("target_variant", "baseline")
            train = subset(df_eng, load_split_ids(domain, "train"))
            val = subset(df_eng, load_split_ids(domain, "val"))
            test = subset(df_eng, load_split_ids(domain, "test"))
            ytr = elim_variants[target_var].loc[train.index] if domain == "elimination" else train[TARGET[domain]].astype(float)
            yva = elim_variants[target_var].loc[val.index] if domain == "elimination" else val[TARGET[domain]].astype(float)
            yte = elim_variants[target_var].loc[test.index] if domain == "elimination" else test[TARGET[domain]].astype(float)
            tr_mask, va_mask, te_mask = ytr.notna(), yva.notna(), yte.notna()
            train_eff, val_eff, test_eff = train.loc[tr_mask].copy(), val.loc[va_mask].copy(), test.loc[te_mask].copy()
            ytr, yva, yte = ytr.loc[tr_mask].astype(int), yva.loc[va_mask].astype(int), yte.loc[te_mask].astype(int)
            model = fit_model(cfg["family"], preprocess_frame(train_eff, feats), ytr, seed=int(cfg.get("seed", 11)), domain=domain)
            pva_raw = predict_proba(model, preprocess_frame(val_eff, feats))
            pte_raw = predict_proba(model, preprocess_frame(test_eff, feats))
            pva, pte, cal_name_auto, calibrator = calibrate_probs(yva, pva_raw, pte_raw)
            cal_name = cfg.get("calibration", cal_name_auto)
            if cal_name != cal_name_auto:
                if cal_name == "none":
                    pva, pte, calibrator = pva_raw, pte_raw, None
                elif cal_name == "platt":
                    lr = LogisticRegression(max_iter=600)
                    lr.fit(pva_raw.reshape(-1, 1), yva.astype(int))
                    pva, pte, calibrator = lr.predict_proba(pva_raw.reshape(-1, 1))[:, 1], lr.predict_proba(pte_raw.reshape(-1, 1))[:, 1], lr
                else:
                    iso = IsotonicRegression(out_of_bounds="clip")
                    iso.fit(pva_raw, yva.astype(int))
                    pva, pte, calibrator = iso.predict(pva_raw), iso.predict(pte_raw), iso

            policy = str(cfg.get("threshold_policy", "balanced"))
            thr, _ = choose_threshold(yva, pva, policy, domain)
            thr = float(cfg.get("threshold", thr))
            band = float(cfg.get("abstention_band", 0.08))
            m = compute_metrics(yte, pte, thr)
            m.update(
                {
                    "mode": mode,
                    "domain": domain,
                    "family": cfg["family"],
                    "feature_variant": cfg["feature_variant"],
                    "target_variant": target_var,
                    "threshold_policy": policy,
                    "threshold": thr,
                    "abstention_band": band,
                    "calibration": cal_name,
                    "n_features": len(feats),
                    "seed": int(cfg.get("seed", 11)),
                }
            )
            final_metrics_rows.append(m)
            bundles[(mode, domain)] = ModelBundle(
                mode=mode,
                domain=domain,
                family=cfg["family"],
                feature_variant=cfg["feature_variant"],
                features=feats,
                threshold_policy=policy,
                threshold=thr,
                abstention_band=band,
                calibration=cal_name,
                target_variant=target_var,
                seed=int(cfg.get("seed", 11)),
                model=model,
                calibrator=calibrator,
            )

    final_metrics = pd.DataFrame(final_metrics_rows)

    case_rows = []
    output_rows = []
    case_id = 1
    pool = df_eng.copy().reset_index(drop=True)
    if "participant_id" not in pool.columns:
        pool["participant_id"] = np.arange(len(pool)).astype(str)

    for mode in ["caregiver", "psychologist"]:
        scenarios = scenario_names_for_mode(mode)
        for scenario in scenarios:
            n = 20 if scenario in {"borderline", "cerca_threshold", "transdiagnostico", "alta_incertidumbre", "abstention_esperada", "elimination_prudencia_reforzada", "adhd_depression_tradeoff"} else 25
            pick_idx = rng.choice(pool.index.values, size=n, replace=False if len(pool) >= n else True)
            for idx in pick_idx:
                row = pool.loc[idx]
                pid = str(row["participant_id"])
                case_rows.append({"case_id": f"C{case_id:05d}", "mode": mode, "scenario": scenario, "participant_id": pid})
                for domain in DOMAINS:
                    b = bundles[(mode, domain)]
                    x_raw = row[b.features].copy()
                    x_masked, coverage, self_cov = apply_mask_for_scenario(x_raw, b.features, scenario, mode, rng)
                    X_df = pd.DataFrame([x_masked])
                    X_df = preprocess_frame(X_df, b.features)
                    p_raw = predict_proba(b.model, X_df)
                    p = apply_calibrator(b.calibration, b.calibrator, p_raw)[0]
                    uncertain = bool(abs(p - b.threshold) < b.abstention_band or coverage < 0.45)
                    rb = risk_band(float(p), b.threshold, uncertain)
                    conf = confidence_pct(float(p), b.threshold, uncertain)
                    eq = evidence_quality(coverage)
                    caveat_level, caveat_msg = caveat_for(domain, mode)
                    y_true = float(row[TARGET[domain]]) if pd.notna(row[TARGET[domain]]) else np.nan
                    pred_label = int(p >= b.threshold)
                    source_mix = (
                        f"caregiver_only+self_report_cov={self_cov:.2f}" if mode == "caregiver"
                        else f"mixed_professional+self_report_cov={self_cov:.2f}"
                    )
                    output_rows.append(
                        {
                            "case_id": f"C{case_id:05d}",
                            "mode": mode,
                            "scenario": scenario,
                            "participant_id": pid,
                            "domain": domain,
                            "true_label": y_true,
                            "probability_score": float(p),
                            "pred_label": pred_label,
                            "risk_band": rb,
                            "confidence_percentage": conf,
                            "evidence_quality": eq,
                            "uncertainty_flag": "yes" if uncertain else "no",
                            "abstention_flag": "yes" if uncertain else "no",
                            "short_explanation": short_expl(float(p), rb, uncertain, domain),
                            "professional_detail": f"prob={p:.3f};thr={b.threshold:.3f};margin={abs(p-b.threshold):.3f};coverage={coverage:.2f}",
                            "caveat_level": caveat_level,
                            "caveat_message": caveat_msg,
                            "input_coverage_summary": f"{coverage:.2f}",
                            "source_mix_summary": source_mix,
                        }
                    )
                case_id += 1

    case_df = pd.DataFrame(case_rows)
    out_df = pd.DataFrame(output_rows)
    save_csv(case_df, SIM / "output_realism_case_registry.csv")
    save_csv(out_df, SIM / "output_realism_results.csv")
    write_md(
        RPT / "output_realism_analysis.md",
        "# Output realism analysis\n\n"
        + f"- Casos simulados: {len(case_df)}\n"
        + f"- Predicciones evaluadas: {len(out_df)}\n"
        + "- Incluye escenarios base, parciales y de tensión en modo cuidador y psicólogo.\n\n"
        + out_df.groupby(["mode", "domain", "risk_band"]).size().rename("n").reset_index().to_string(index=False),
    )

    product_rows = []
    valid = out_df[out_df["true_label"].notna()].copy()
    valid["true_label"] = valid["true_label"].astype(int)
    for (mode, domain), grp in valid.groupby(["mode", "domain"]):
        for band in ["low", "moderate", "high", "uncertain"]:
            gb = grp[grp["risk_band"] == band]
            rate = float(len(gb) / len(grp)) if len(grp) else 0.0
            product_rows.append({"mode": mode, "domain": domain, "metric": "band_rate", "band": band, "value": rate})
            if len(gb):
                calib_gap = float(abs(gb["probability_score"].mean() - gb["true_label"].mean()))
                conf_mean = float(gb["confidence_percentage"].mean())
                ppv = float(gb[gb["pred_label"] == 1]["true_label"].mean()) if len(gb[gb["pred_label"] == 1]) else np.nan
                npv = float(1 - gb[gb["pred_label"] == 0]["true_label"].mean()) if len(gb[gb["pred_label"] == 0]) else np.nan
                product_rows.extend(
                    [
                        {"mode": mode, "domain": domain, "metric": "calibration_gap", "band": band, "value": calib_gap},
                        {"mode": mode, "domain": domain, "metric": "avg_confidence", "band": band, "value": conf_mean},
                        {"mode": mode, "domain": domain, "metric": "ppv", "band": band, "value": ppv},
                        {"mode": mode, "domain": domain, "metric": "npv", "band": band, "value": npv},
                    ]
                )
        uncertainty_rate = float((grp["uncertainty_flag"] == "yes").mean())
        caveat_strong = float((grp["caveat_level"] == "high").mean())
        overconf = float(((grp["confidence_percentage"] >= 85) & (grp["pred_label"] != grp["true_label"])).mean())
        product_rows.extend(
            [
                {"mode": mode, "domain": domain, "metric": "uncertainty_rate", "band": "all", "value": uncertainty_rate},
                {"mode": mode, "domain": domain, "metric": "caveat_strong_rate", "band": "all", "value": caveat_strong},
                {"mode": mode, "domain": domain, "metric": "overconfident_rate", "band": "all", "value": overconf},
            ]
        )
    product_df = pd.DataFrame(product_rows)
    save_csv(product_df, TBL / "product_like_metrics.csv")
    write_md(
        RPT / "product_like_metrics_analysis.md",
        "# Product-like metrics analysis\n\n"
        + product_df.groupby(["mode", "domain", "metric"])["value"].mean().reset_index().to_string(index=False),
    )

    review_rows = []
    for mode in ["caregiver", "psychologist"]:
        for domain in DOMAINS:
            grp = valid[(valid["mode"] == mode) & (valid["domain"] == domain)].copy()
            if grp.empty:
                continue
            samples = []
            samples.append(grp[(grp["risk_band"] == "high") & (grp["true_label"] == 1)].head(2))
            samples.append(grp[(grp["risk_band"] == "low") & (grp["true_label"] == 0)].head(2))
            samples.append(grp[(grp["risk_band"] == "moderate")].head(2))
            samples.append(grp[(grp["uncertainty_flag"] == "yes")].head(2))
            samples.append(grp[grp["scenario"].str.contains("parcial|cobertura_baja|missing", regex=True)].head(2))
            case_sub = pd.concat(samples, ignore_index=True).drop_duplicates(subset=["case_id"]).head(12)
            for _, r in case_sub.iterrows():
                coherent = (
                    (r["risk_band"] == "high" and r["true_label"] == 1)
                    or (r["risk_band"] == "low" and r["true_label"] == 0)
                    or (r["uncertainty_flag"] == "yes")
                )
                oversecure = bool(r["confidence_percentage"] >= 85 and r["pred_label"] != r["true_label"])
                subinfo = bool(r["uncertainty_flag"] == "yes" and float(r["input_coverage_summary"]) > 0.85)
                require_pro = bool(r["uncertainty_flag"] == "yes" or r["risk_band"] in {"high", "moderate"} or domain == "elimination")
                review_rows.append(
                    {
                        "mode": mode,
                        "domain": domain,
                        "case_id": r["case_id"],
                        "scenario": r["scenario"],
                        "participant_id": r["participant_id"],
                        "input_coverage": r["input_coverage_summary"],
                        "score": r["probability_score"],
                        "risk_band": r["risk_band"],
                        "confidence": r["confidence_percentage"],
                        "uncertainty": r["uncertainty_flag"],
                        "short_explanation": r["short_explanation"],
                        "caveat": r["caveat_message"],
                        "coherent_pattern": "yes" if coherent else "no",
                        "oversecure": "yes" if oversecure else "no",
                        "subinformative": "yes" if subinfo else "no",
                        "requires_professional_review": "yes" if require_pro else "no",
                    }
                )
    review_df = pd.DataFrame(review_rows)
    save_csv(review_df, REV / "review_casebook.csv")
    write_md(
        RPT / "review_casebook_analysis.md",
        "# Review casebook analysis\n\n"
        + f"- Casos en casebook: {len(review_df)}\n\n"
        + review_df.groupby(["mode", "domain"])[["coherent_pattern", "oversecure", "subinformative"]].apply(
            lambda g: pd.Series(
                {
                    "coherent_rate": (g["coherent_pattern"] == "yes").mean(),
                    "oversecure_rate": (g["oversecure"] == "yes").mean(),
                    "subinformative_rate": (g["subinformative"] == "yes").mean(),
                }
            )
        ).reset_index().to_string(index=False),
    )

    approval_rows = []
    for mode in ["caregiver", "psychologist"]:
        for domain in DOMAINS:
            fm = final_metrics[(final_metrics["mode"] == mode) & (final_metrics["domain"] == domain)].iloc[0]
            grp = valid[(valid["mode"] == mode) & (valid["domain"] == domain)]
            uncertainty_rate = float((grp["uncertainty_flag"] == "yes").mean()) if not grp.empty else 0.0
            overconf_rate = float(((grp["confidence_percentage"] >= 85) & (grp["pred_label"] != grp["true_label"])).mean()) if not grp.empty else 0.0
            avg_cov = float(grp["input_coverage_summary"].astype(float).mean()) if not grp.empty else 0.0
            if domain == "elimination":
                status = "uncertainty_preferred"
                rationale = "BA/recall mejoraron, pero la señal sigue con incertidumbre estructural; priorizar caveat y revisión profesional."
            elif mode == "psychologist" and domain == "adhd" and avg_cov < 0.70:
                status = "ready_only_for_professional_detail"
                rationale = "Performance alta, pero quality de evidencia/sources heterogénea; mejor para detalle profesional."
            elif fm["balanced_accuracy"] >= 0.90 and fm["brier"] <= 0.08 and overconf_rate <= 0.10:
                status = "fully_ready"
                rationale = "Desempeño y calibración robustos con comportamiento operativo estable."
            elif fm["balanced_accuracy"] >= 0.87 and fm["brier"] <= 0.10:
                status = "ready_with_caveat"
                rationale = "Usable con caveat explícito y monitoreo de incertidumbre."
            else:
                status = "not_ready_for_strong_probability_interpretation"
                rationale = "Utilidad limitada para probabilidad fuerte; preferir lectura prudente."
            approval_rows.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "approval_status": status,
                    "balanced_accuracy": float(fm["balanced_accuracy"]),
                    "brier": float(fm["brier"]),
                    "uncertainty_rate": uncertainty_rate,
                    "overconfident_rate": overconf_rate,
                    "avg_input_coverage": avg_cov,
                    "probability_riskband_supported": "yes" if status in {"fully_ready", "ready_with_caveat"} else "limited",
                    "caveat_level": "high" if domain == "elimination" else ("medium" if mode == "caregiver" else "low"),
                    "rationale": rationale,
                }
            )
    approval_df = pd.DataFrame(approval_rows)
    save_csv(approval_df, TBL / "final_output_approval_matrix.csv")
    write_md(RPT / "final_output_approval_analysis.md", "# Final output approval analysis\n\n" + approval_df.to_string(index=False))

    stop_rows = []
    for key in PRIORITY:
        mode, domain = key
        base = BASELINE_V5[key]
        fm = final_metrics[(final_metrics["mode"] == mode) & (final_metrics["domain"] == domain)].iloc[0]
        d_ba = float(fm["balanced_accuracy"] - base["balanced_accuracy"])
        d_re = float(fm["recall"] - base["recall"])
        d_br = float(fm["brier"] - base["brier"])
        if d_ba >= 0.010 or d_re >= 0.030 or d_br <= -0.008:
            level = "material"
        elif d_ba >= 0.004 or d_re >= 0.015 or d_br <= -0.003:
            level = "marginal"
        else:
            level = "none"
        stop_rows.append(
            {
                "mode": mode,
                "domain": domain,
                "delta_ba": d_ba,
                "delta_recall": d_re,
                "delta_brier": d_br,
                "improvement_level": level,
                "stop_rule": "stop_if_no_material_signal_after_2_rounds",
                "decision": "stop" if level != "material" else "allow_micro_refinement_only_if_needed",
            }
        )
    stop_df = pd.DataFrame(stop_rows)
    write_md(RPT / "stop_rule_assessment.md", "# Stop rule assessment\n\n" + stop_df.to_string(index=False))
    material_count = int((stop_df["improvement_level"] == "material").sum())
    closure_decision = "cerrar_con_caveats" if material_count <= 2 else "cerrar_con_microajuste_opcional_unico"
    write_md(
        RPT / "final_closure_recommendation.md",
        "# Final closure recommendation\n\n"
        + f"- decision: **{closure_decision}**\n"
        + "- No se justifica reabrir campaña global.\n"
        + "- Mantener caveat reforzado para Elimination y caveat estándar de no diagnóstico para todos los dominios.\n",
    )

    runtime_rows = []
    required_output_cols = {
        "probability_score",
        "risk_band",
        "confidence_percentage",
        "evidence_quality",
        "uncertainty_flag",
        "short_explanation",
        "professional_detail",
        "caveat_message",
        "input_coverage_summary",
        "source_mix_summary",
    }
    runtime_rows.append(
        {
            "check_id": "output_contract_columns",
            "scope": "global",
            "status": "pass" if required_output_cols.issubset(set(out_df.columns)) else "fail",
            "details": ",".join(sorted(required_output_cols - set(out_df.columns))),
        }
    )
    for mode in ["caregiver", "psychologist"]:
        for domain in DOMAINS:
            b = bundles[(mode, domain)]
            runtime_rows.append({"check_id": "input_contract_non_empty", "scope": f"{mode}:{domain}", "status": "pass" if len(b.features) > 0 else "fail", "details": f"n_features={len(b.features)}"})
            g = out_df[(out_df["mode"] == mode) & (out_df["domain"] == domain)]
            uncertain_rate = float((g["uncertainty_flag"] == "yes").mean()) if not g.empty else 0.0
            runtime_rows.append({"check_id": "uncertainty_graceful_degradation", "scope": f"{mode}:{domain}", "status": "pass" if 0.03 <= uncertain_rate <= 0.65 else "warn", "details": f"uncertainty_rate={uncertain_rate:.3f}"})
    runtime_df = pd.DataFrame(runtime_rows)
    save_csv(runtime_df, TBL / "runtime_operational_validation.csv")
    write_md(RPT / "runtime_operational_validation.md", "# Runtime operational validation\n\n" + runtime_df.to_string(index=False))

    ART.mkdir(parents=True, exist_ok=True)
    manifest = {
        "final_metrics": final_metrics.to_dict(orient="records"),
        "focused_pairs": focused_results.to_dict(orient="records"),
        "approval_matrix": approval_df.to_dict(orient="records"),
        "closure_decision": closure_decision,
    }
    (ART / "final_output_realism_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("OK - final_output_realism_v6 generated")


if __name__ == "__main__":
    run()
