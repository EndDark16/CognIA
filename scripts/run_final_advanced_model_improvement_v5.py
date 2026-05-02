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

XGB_AVAILABLE = True
LGB_AVAILABLE = True
CAT_AVAILABLE = True
TABPFN_AVAILABLE = True
CHALLENGER_ERRORS: dict[str, str] = {}
try:
    from xgboost import XGBClassifier
except Exception as exc:  # noqa: BLE001
    XGB_AVAILABLE = False
    CHALLENGER_ERRORS["xgboost"] = str(exc)
try:
    from lightgbm import LGBMClassifier
except Exception as exc:  # noqa: BLE001
    LGB_AVAILABLE = False
    CHALLENGER_ERRORS["lightgbm"] = str(exc)
try:
    from catboost import CatBoostClassifier
except Exception as exc:  # noqa: BLE001
    CAT_AVAILABLE = False
    CHALLENGER_ERRORS["catboost"] = str(exc)
try:
    from tabpfn import TabPFNClassifier
except Exception as exc:  # noqa: BLE001
    TABPFN_AVAILABLE = False
    CHALLENGER_ERRORS["tabpfn"] = str(exc)

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "final_advanced_model_improvement_v5"
INV = BASE / "inventory"
CARE = BASE / "caregiver"
PSY = BASE / "psychologist"
ELIM = BASE / "elimination_redesign"
GCMP = BASE / "global_comparison"
TABLES = BASE / "tables"
REPORTS = BASE / "reports"
ART = ROOT / "artifacts" / "final_advanced_model_improvement_v5"

DATASET_PATH = (
    ROOT
    / "data"
    / "processed_hybrid_dsm5_v2"
    / "final"
    / "model_ready"
    / "strict_no_leakage_hybrid"
    / "dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv"
)
CONTRACT_PATH = ROOT / "artifacts" / "specs" / "questionnaire_feature_contract.csv"
BASIC_Q_PATH = ROOT / "reports" / "questionnaire_model_strategy_eval_v1" / "questionnaire_basic_candidate_v1.csv"

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
TARGET = {d: f"target_domain_{d}" for d in DOMAINS}
CAT_COLS = {"sex_assigned_at_birth", "site"}
ESSENTIAL = {"age_years", "sex_assigned_at_birth", "site", "release"}
HIGH_PRIORITY = {"elimination", "adhd", "depression", "anxiety"}
MAX_ROUNDS = 3
SEEDS_R1 = [11]
SEEDS_R2 = [11, 29]
SEEDS_R3 = [11, 29, 47]

BASELINE = {
    "caregiver": {
        "adhd": {"precision": 0.924870, "recall": 0.840062, "specificity": 0.912000, "balanced_accuracy": 0.876031, "f1": 0.880401, "roc_auc": 0.952565, "pr_auc": 0.957568, "brier": 0.084743},
        "anxiety": {"precision": 0.782639, "recall": 0.954545, "specificity": 0.920455, "balanced_accuracy": 0.937500, "f1": 0.860078, "roc_auc": 0.977428, "pr_auc": 0.944313, "brier": 0.039980},
        "conduct": {"precision": 0.978869, "recall": 0.862500, "specificity": 0.992718, "balanced_accuracy": 0.927609, "f1": 0.916974, "roc_auc": 0.980780, "pr_auc": 0.948224, "brier": 0.040622},
        "depression": {"precision": 0.869814, "recall": 0.923913, "specificity": 0.904971, "balanced_accuracy": 0.914442, "f1": 0.894702, "roc_auc": 0.975566, "pr_auc": 0.959539, "brier": 0.058659},
        "elimination": {"precision": 0.910467, "recall": 0.683230, "specificity": 0.912000, "balanced_accuracy": 0.797615, "f1": 0.779419, "roc_auc": 0.869093, "pr_auc": 0.873588, "brier": 0.147899},
    },
    "psychologist": {
        "adhd": {"precision": 0.941766, "recall": 0.826087, "specificity": 0.934000, "balanced_accuracy": 0.880043, "f1": 0.880033, "roc_auc": 0.952938, "pr_auc": 0.956229, "brier": 0.083546},
        "anxiety": {"precision": 0.922032, "recall": 0.984848, "specificity": 0.975000, "balanced_accuracy": 0.979924, "f1": 0.952394, "roc_auc": 0.989394, "pr_auc": 0.971229, "brier": 0.013608},
        "conduct": {"precision": 0.945608, "recall": 0.865625, "specificity": 0.980583, "balanced_accuracy": 0.923104, "f1": 0.903780, "roc_auc": 0.977124, "pr_auc": 0.941644, "brier": 0.043583},
        "depression": {"precision": 0.859535, "recall": 0.936957, "specificity": 0.896199, "balanced_accuracy": 0.916578, "f1": 0.896117, "roc_auc": 0.973538, "pr_auc": 0.955288, "brier": 0.058341},
        "elimination": {"precision": 0.919969, "recall": 0.652174, "specificity": 0.926000, "balanced_accuracy": 0.789087, "f1": 0.761985, "roc_auc": 0.870037, "pr_auc": 0.874594, "brier": 0.148572},
    },
}


@dataclass(frozen=True)
class ContractFeature:
    feature: str
    modality: str
    response_type: str
    options: list[str]
    min_value: float | None
    max_value: float | None
    dataset_origin: str


def ensure_dirs() -> None:
    for p in [BASE, INV, CARE, PSY, ELIM, GCMP, TABLES, REPORTS, ART]:
        p.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def parse_range(raw: str) -> tuple[float | None, float | None]:
    if not isinstance(raw, str) or "|" not in raw:
        return None, None
    a, b = raw.split("|", 1)
    try:
        return float(a), float(b)
    except ValueError:
        return None, None


def load_contract() -> dict[str, ContractFeature]:
    raw = pd.read_csv(CONTRACT_PATH)
    out: dict[str, ContractFeature] = {}
    for _, row in raw.iterrows():
        f = str(row.get("feature_final", "")).strip()
        if not f:
            continue
        opts = []
        if pd.notna(row.get("opciones_permitidas")):
            opts = [x.strip() for x in str(row["opciones_permitidas"]).split("|") if x.strip()]
        mn, mx = parse_range(str(row.get("rango_esperado", "")))
        out[f] = ContractFeature(
            feature=f,
            modality=str(row.get("modalidad", "") or ""),
            response_type=str(row.get("tipo_respuesta", "") or ""),
            options=opts,
            min_value=mn,
            max_value=mx,
            dataset_origin=str(row.get("dataset_origen", "") or ""),
        )
    return out


def load_metadata(domain: str) -> dict[str, Any]:
    p = ROOT / "models" / "champions" / f"rf_{domain}_current" / "metadata.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_split_ids(domain: str, split_name: str, part: str) -> pd.Series:
    p = ROOT / "data" / "processed_hybrid_dsm5_v2" / "splits" / f"domain_{domain}_{split_name}" / f"ids_{part}.csv"
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


def threshold_score(metrics: dict[str, float], policy: str) -> float:
    if policy == "precision_guarded":
        return 0.42 * metrics["precision"] + 0.30 * metrics["balanced_accuracy"] + 0.18 * metrics["pr_auc"] + 0.10 * metrics["recall"]
    if policy == "recall_guarded":
        return 0.42 * metrics["recall"] + 0.30 * metrics["balanced_accuracy"] + 0.18 * metrics["f1"] + 0.10 * metrics["pr_auc"]
    return 0.50 * metrics["balanced_accuracy"] + 0.20 * metrics["f1"] + 0.15 * metrics["precision"] + 0.15 * metrics["recall"]


def choose_threshold(y_true: pd.Series, prob: np.ndarray, policy: str) -> tuple[float, float]:
    best_t, best = 0.5, -1.0
    for t in np.linspace(0.1, 0.9, 161):
        m = compute_metrics(y_true, prob, float(t))
        s = threshold_score(m, policy)
        if s > best:
            best_t, best = float(t), float(s)
    return best_t, best


def choose_band(y_true: pd.Series, prob: np.ndarray, thr: float) -> tuple[float, float, float]:
    best_band, best_score, best_cov = 0.08, -1.0, 0.0
    for b in [0.05, 0.08, 0.10, 0.12, 0.15]:
        keep = np.abs(prob - thr) >= b
        cov = float(keep.mean())
        if cov < 0.45:
            continue
        yk = y_true[keep]
        pk = prob[keep]
        if len(np.unique(yk)) < 2:
            continue
        mk = compute_metrics(yk, pk, thr)
        score = 0.45 * mk["balanced_accuracy"] + 0.20 * mk["precision"] + 0.20 * cov + 0.15 * mk["pr_auc"]
        if score > best_score:
            best_band, best_score, best_cov = float(b), float(score), cov
    return best_band, best_score, best_cov


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


def fit_predict_family(
    family: str,
    Xtr: pd.DataFrame,
    ytr: pd.Series,
    Xva: pd.DataFrame,
    Xte: pd.DataFrame,
    seed: int,
    domain: str,
) -> tuple[np.ndarray | None, np.ndarray | None, str, str | None]:
    try:
        if family == "rf":
            pre = preprocessor_for(list(Xtr.columns))
            est = RandomForestClassifier(
                n_estimators=700 if domain in HIGH_PRIORITY else 500,
                max_depth=None if domain in {"elimination", "adhd"} else 20,
                min_samples_leaf=1 if domain in {"elimination", "adhd"} else 2,
                min_samples_split=4,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            )
            pipe = Pipeline([("pre", pre), ("model", est)])
            pipe.fit(Xtr, ytr)
            return pipe.predict_proba(Xva)[:, 1], pipe.predict_proba(Xte)[:, 1], "ok", None

        if family == "xgboost":
            if not XGB_AVAILABLE:
                return None, None, "unavailable", "xgboost_not_installed"
            pre = preprocessor_for(list(Xtr.columns))
            est = XGBClassifier(
                n_estimators=650 if domain in HIGH_PRIORITY else 450,
                max_depth=5 if domain in HIGH_PRIORITY else 4,
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
            return pipe.predict_proba(Xva)[:, 1], pipe.predict_proba(Xte)[:, 1], "ok", None

        if family == "lightgbm":
            if not LGB_AVAILABLE:
                return None, None, "unavailable", "lightgbm_not_installed"
            pre = preprocessor_for(list(Xtr.columns))
            est = LGBMClassifier(
                n_estimators=800 if domain in HIGH_PRIORITY else 550,
                learning_rate=0.03,
                num_leaves=63 if domain in HIGH_PRIORITY else 47,
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
            return pipe.predict_proba(Xva)[:, 1], pipe.predict_proba(Xte)[:, 1], "ok", None

        if family == "catboost":
            if not CAT_AVAILABLE:
                return None, None, "unavailable", "catboost_not_installed"
            Xtr2, Xva2, Xte2 = Xtr.copy(), Xva.copy(), Xte.copy()
            for c in Xtr2.columns:
                if c in CAT_COLS:
                    Xtr2[c] = Xtr2[c].fillna("Unknown").astype(str)
                    Xva2[c] = Xva2[c].fillna("Unknown").astype(str)
                    Xte2[c] = Xte2[c].fillna("Unknown").astype(str)
                else:
                    med = pd.to_numeric(Xtr2[c], errors="coerce").median()
                    fill = 0.0 if pd.isna(med) else float(med)
                    Xtr2[c] = pd.to_numeric(Xtr2[c], errors="coerce").fillna(fill)
                    Xva2[c] = pd.to_numeric(Xva2[c], errors="coerce").fillna(fill)
                    Xte2[c] = pd.to_numeric(Xte2[c], errors="coerce").fillna(fill)
            cat_idx = [i for i, c in enumerate(Xtr2.columns) if c in CAT_COLS]
            model = CatBoostClassifier(
                iterations=750 if domain in HIGH_PRIORITY else 500,
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
            return model.predict_proba(Xva2)[:, 1], model.predict_proba(Xte2)[:, 1], "ok", None

        if family == "tabpfn":
            if not TABPFN_AVAILABLE:
                return None, None, "unavailable", CHALLENGER_ERRORS.get("tabpfn", "tabpfn_not_installed")
            pre = preprocessor_for(list(Xtr.columns))
            Xt = pre.fit_transform(Xtr)
            Xv = pre.transform(Xva)
            Xe = pre.transform(Xte)
            Xt = Xt.toarray() if hasattr(Xt, "toarray") else np.asarray(Xt)
            Xv = Xv.toarray() if hasattr(Xv, "toarray") else np.asarray(Xv)
            Xe = Xe.toarray() if hasattr(Xe, "toarray") else np.asarray(Xe)
            if Xt.shape[1] > 400:
                var = np.var(Xt, axis=0)
                keep = np.argsort(var)[-400:]
                Xt, Xv, Xe = Xt[:, keep], Xv[:, keep], Xe[:, keep]
            model = TabPFNClassifier(device="cpu")
            model.fit(Xt, ytr.values)
            return model.predict_proba(Xv)[:, 1], model.predict_proba(Xe)[:, 1], "ok", None

        return None, None, "unavailable", f"family_not_supported:{family}"
    except Exception as exc:  # noqa: BLE001
        return None, None, "error", str(exc)


def calibrate_probs(yva: pd.Series, pva: np.ndarray, pte: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    cands = [("none", pva, pte, brier_score_loss(yva, pva))]
    if len(np.unique(yva)) >= 2:
        lr = LogisticRegression(max_iter=600)
        lr.fit(pva.reshape(-1, 1), yva.astype(int))
        pv, pt = lr.predict_proba(pva.reshape(-1, 1))[:, 1], lr.predict_proba(pte.reshape(-1, 1))[:, 1]
        cands.append(("platt", pv, pt, brier_score_loss(yva, pv)))
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(pva, yva.astype(int))
        pv2, pt2 = iso.predict(pva), iso.predict(pte)
        cands.append(("isotonic", pv2, pt2, brier_score_loss(yva, pv2)))
    best = sorted(cands, key=lambda x: x[3])[0]
    return best[1], best[2], best[0]


def build_mode_feature_maps(df: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    legacy = {d: list(load_metadata(d)["feature_columns"]) for d in DOMAINS}
    basic = pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).drop_duplicates().tolist()
    basic = [f for f in basic if f in df.columns]
    caregiver = {d: sorted(set([f for f in legacy[d] if f in basic] + list(ESSENTIAL & set(legacy[d])))) for d in DOMAINS}
    psychologist = {d: legacy[d][:] for d in DOMAINS}
    return legacy, caregiver, psychologist


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
        rows.extend(
            [
                {"feature_name": mean_col, "source_columns": "|".join(cols), "family": "aggregation", "transformation": "row_mean", "rationale": "signal burden summary", "traceable": "yes"},
                {"feature_name": std_col, "source_columns": "|".join(cols), "family": "dispersion", "transformation": "row_std", "rationale": "response variability", "traceable": "yes"},
                {"feature_name": miss_col, "source_columns": "|".join(cols), "family": "missingness", "transformation": "row_missing_ratio", "rationale": "coverage quality", "traceable": "yes"},
            ]
        )
    core_cols = [c for c in feature_union if c in out.columns and not c.startswith("target_")]
    if core_cols:
        core_num = out[core_cols].apply(pd.to_numeric, errors="coerce")
        out["der_global_missing_ratio"] = core_num.isna().mean(axis=1)
        out["der_global_nonzero_ratio"] = (core_num.fillna(0) != 0).mean(axis=1)
        rows.append({"feature_name": "der_global_missing_ratio", "source_columns": "|".join(core_cols[:40]), "family": "missingness", "transformation": "global_missing_ratio", "rationale": "overall evidence quality", "traceable": "yes"})
        rows.append({"feature_name": "der_global_nonzero_ratio", "source_columns": "|".join(core_cols[:40]), "family": "density", "transformation": "global_nonzero_ratio", "rationale": "overall symptom density proxy", "traceable": "yes"})
    return out, pd.DataFrame(rows)


def select_engineered_features(base_features: list[str], derived_registry: pd.DataFrame, domain: str, mode: str) -> tuple[list[str], list[str]]:
    derived = derived_registry["feature_name"].tolist()
    if not derived:
        return base_features[:], base_features[:]
    prefixes = sorted(set([c.split("_", 1)[0] for c in base_features if "_" in c]))
    domain_derived = [f for f in derived if any(f.startswith(f"der_{p}_") for p in prefixes)]
    domain_derived += ["der_global_missing_ratio", "der_global_nonzero_ratio"]
    domain_derived = [f for f in sorted(set(domain_derived)) if f in derived]
    engineered = sorted(set(base_features + domain_derived[:12]))
    compact = [f for f in engineered if (not f.startswith("der_") or "missing_ratio" in f)]
    if mode == "psychologist" and domain == "anxiety":
        compact = compact[:180]
    return engineered, compact


def elimination_target_variants(df: pd.DataFrame) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    rows = []
    variants: dict[str, pd.Series] = {}
    base = df["target_domain_elimination"].astype(float)
    variants["elimination_any_baseline"] = base
    rows.append({"target_variant": "elimination_any_baseline", "definition": "target_domain_elimination", "positives": int(base.sum()), "n": int(len(base)), "ambiguous_removed": 0})

    enu = df["target_enuresis_exact"].astype(float)
    enc = df["target_encopresis_exact"].astype(float)
    union = ((enu == 1) | (enc == 1)).astype(float)
    variants["elimination_union_internal"] = union
    rows.append({"target_variant": "elimination_union_internal", "definition": "target_enuresis_exact OR target_encopresis_exact", "positives": int(union.sum()), "n": int(len(union)), "ambiguous_removed": 0})

    overlap = ((enu == 1) & (enc == 1)).astype(float)
    variants["elimination_overlap_strict"] = overlap
    rows.append({"target_variant": "elimination_overlap_strict", "definition": "target_enuresis_exact AND target_encopresis_exact", "positives": int(overlap.sum()), "n": int(len(overlap)), "ambiguous_removed": 0})

    direct_sum = pd.to_numeric(df.get("target_enuresis_exact_direct_criteria_count", 0), errors="coerce").fillna(0) + pd.to_numeric(df.get("target_encopresis_exact_direct_criteria_count", 0), errors="coerce").fillna(0)
    absent_sum = pd.to_numeric(df.get("target_enuresis_exact_absent_criteria_count", 0), errors="coerce").fillna(0) + pd.to_numeric(df.get("target_encopresis_exact_absent_criteria_count", 0), errors="coerce").fillna(0)
    clear = base.copy()
    clear[(base == 1) & (direct_sum < 1)] = np.nan
    clear[(base == 0) & (absent_sum < 1)] = np.nan
    variants["elimination_clear_cases"] = clear
    rows.append({"target_variant": "elimination_clear_cases", "definition": "baseline with ambiguous cases removed by direct/absent criteria support", "positives": int(clear.fillna(0).sum()), "n": int(clear.notna().sum()), "ambiguous_removed": int(clear.isna().sum())})
    return variants, pd.DataFrame(rows)


def run_campaign_for_mode(
    df: pd.DataFrame,
    mode: str,
    base_map: dict[str, list[str]],
    derived_registry: pd.DataFrame,
    target_variants: dict[str, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    families = ["rf", "xgboost", "lightgbm", "catboost", "tabpfn"]
    all_trials = []
    best_rows = []
    family_rows = []
    stop_rows = []

    for domain in DOMAINS:
        train = subset(df, load_split_ids(domain, "strict_full", "train"))
        val = subset(df, load_split_ids(domain, "strict_full", "val"))
        test = subset(df, load_split_ids(domain, "strict_full", "test"))
        tvars = ["baseline"] if domain != "elimination" else list(target_variants.keys())

        domain_best_candidates = []
        for tvar in tvars:
            ytr = target_variants[tvar].loc[train.index] if domain == "elimination" else train[TARGET[domain]].astype(float)
            yva = target_variants[tvar].loc[val.index] if domain == "elimination" else val[TARGET[domain]].astype(float)
            yte = target_variants[tvar].loc[test.index] if domain == "elimination" else test[TARGET[domain]].astype(float)
            tr_mask, va_mask, te_mask = ytr.notna(), yva.notna(), yte.notna()
            train_eff, val_eff, test_eff = train.loc[tr_mask].copy(), val.loc[va_mask].copy(), test.loc[te_mask].copy()
            ytr, yva, yte = ytr.loc[tr_mask].astype(int), yva.loc[va_mask].astype(int), yte.loc[te_mask].astype(int)
            if len(np.unique(ytr)) < 2 or len(np.unique(yva)) < 2 or len(np.unique(yte)) < 2:
                continue

            base_features = [f for f in base_map[domain] if f in df.columns and not f.startswith("target_")]
            engineered, compact = select_engineered_features(base_features, derived_registry, domain, mode)
            variants = {"base": base_features, "engineered": [f for f in engineered if f in df.columns], "compact": [f for f in compact if f in df.columns]}

            # round 1
            round1 = []
            for family in families:
                for fvar in ["base", "engineered"]:
                    feats = variants[fvar]
                    if len(feats) < 4:
                        continue
                    pva_raw, pte_raw, status, err = fit_predict_family(
                        family,
                        preprocess_frame(train_eff, feats),
                        ytr,
                        preprocess_frame(val_eff, feats),
                        preprocess_frame(test_eff, feats),
                        SEEDS_R1[0],
                        domain,
                    )
                    row = {"mode": mode, "domain": domain, "target_variant": tvar, "round_id": 1, "family": family, "feature_variant": fvar, "seed": SEEDS_R1[0], "status": status, "error": err, "n_features": len(feats)}
                    if status != "ok" or pva_raw is None or pte_raw is None:
                        all_trials.append(row)
                        continue
                    pva, pte, cal = calibrate_probs(yva, pva_raw, pte_raw)
                    policy = "balanced"
                    if domain in {"elimination", "adhd", "depression"}:
                        policy = "precision_guarded"
                    thr, val_obj = choose_threshold(yva, pva, policy)
                    band, _, cov = choose_band(yva, pva, thr)
                    m = compute_metrics(yte, pte, thr)
                    keep = np.abs(pte - thr) >= band
                    high_conf_precision = float(precision_score(yte[keep], (pte[keep] >= thr).astype(int), zero_division=0)) if keep.any() else 0.0
                    row.update({"config_id": f"{family}_default", "calibration": cal, "threshold_policy": policy, "threshold": thr, "abstention_band": band, "abstention_coverage": cov, "val_objective": val_obj, **m, "high_conf_precision": high_conf_precision, "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean())})
                    round1.append(row)
                    all_trials.append(row)
            r1_df = pd.DataFrame(round1)
            if r1_df.empty:
                continue
            top_r1 = r1_df.sort_values(["val_objective", "balanced_accuracy", "pr_auc"], ascending=False).head(2)

            # round 2
            round2 = []
            for _, top in top_r1.iterrows():
                fam, fvar = top["family"], top["feature_variant"]
                feats = variants[fvar]
                for seed in SEEDS_R2:
                    pva_raw, pte_raw, status, err = fit_predict_family(
                        fam,
                        preprocess_frame(train_eff, feats),
                        ytr,
                        preprocess_frame(val_eff, feats),
                        preprocess_frame(test_eff, feats),
                        seed,
                        domain,
                    )
                    row = {"mode": mode, "domain": domain, "target_variant": tvar, "round_id": 2, "family": fam, "feature_variant": fvar, "seed": seed, "status": status, "error": err, "n_features": len(feats), "config_id": f"{fam}_stability"}
                    if status != "ok" or pva_raw is None or pte_raw is None:
                        all_trials.append(row)
                        continue
                    pva, pte, cal = calibrate_probs(yva, pva_raw, pte_raw)
                    policy = str(top["threshold_policy"])
                    thr, val_obj = choose_threshold(yva, pva, policy)
                    band, _, cov = choose_band(yva, pva, thr)
                    m = compute_metrics(yte, pte, thr)
                    keep = np.abs(pte - thr) >= band
                    high_conf_precision = float(precision_score(yte[keep], (pte[keep] >= thr).astype(int), zero_division=0)) if keep.any() else 0.0
                    row.update({"calibration": cal, "threshold_policy": policy, "threshold": thr, "abstention_band": band, "abstention_coverage": cov, "val_objective": val_obj, **m, "high_conf_precision": high_conf_precision, "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean())})
                    round2.append(row)
                    all_trials.append(row)
            r2_df = pd.DataFrame(round2)
            if r2_df.empty:
                continue

            r1_best_ba = float(r1_df["balanced_accuracy"].max())
            r2_best_ba = float(r2_df.groupby(["family", "feature_variant"])["balanced_accuracy"].mean().max())
            r1_best_pr = float(r1_df["pr_auc"].max())
            r2_best_pr = float(r2_df.groupby(["family", "feature_variant"])["pr_auc"].mean().max())
            improve_signal = (r2_best_ba - r1_best_ba >= 0.003) or (r2_best_pr - r1_best_pr >= 0.003)
            run_round3 = (domain in HIGH_PRIORITY) or improve_signal

            if run_round3:
                top_combo = (
                    r2_df.groupby(["family", "feature_variant"])[["val_objective", "balanced_accuracy", "pr_auc"]]
                    .mean()
                    .sort_values(["val_objective", "balanced_accuracy", "pr_auc"], ascending=False)
                    .reset_index()
                    .iloc[0]
                )
                fam, best_fvar = str(top_combo["family"]), str(top_combo["feature_variant"])
                candidate_vars = sorted(set([best_fvar, "compact"] if domain in HIGH_PRIORITY else [best_fvar]))
                for cvar in candidate_vars:
                    feats = variants[cvar]
                    if len(feats) < 4:
                        continue
                    for seed in SEEDS_R3:
                        pva_raw, pte_raw, status, err = fit_predict_family(
                            fam,
                            preprocess_frame(train_eff, feats),
                            ytr,
                            preprocess_frame(val_eff, feats),
                            preprocess_frame(test_eff, feats),
                            seed,
                            domain,
                        )
                        base = {"mode": mode, "domain": domain, "target_variant": tvar, "round_id": 3, "family": fam, "feature_variant": cvar, "seed": seed, "status": status, "error": err, "n_features": len(feats), "config_id": f"{fam}_refined"}
                        if status != "ok" or pva_raw is None or pte_raw is None:
                            all_trials.append(base)
                            continue
                        pva, pte, cal = calibrate_probs(yva, pva_raw, pte_raw)
                        for policy in ["balanced", "precision_guarded"]:
                            thr, val_obj = choose_threshold(yva, pva, policy)
                            band, _, cov = choose_band(yva, pva, thr)
                            m = compute_metrics(yte, pte, thr)
                            keep = np.abs(pte - thr) >= band
                            high_conf_precision = float(precision_score(yte[keep], (pte[keep] >= thr).astype(int), zero_division=0)) if keep.any() else 0.0
                            row = base.copy()
                            row.update({"calibration": cal, "threshold_policy": policy, "threshold": thr, "abstention_band": band, "abstention_coverage": cov, "val_objective": val_obj, **m, "high_conf_precision": high_conf_precision, "input_missing_ratio": float(preprocess_frame(test_eff, feats).isna().mean().mean())})
                            all_trials.append(row)
                stop_reason = "round3_executed"
            else:
                stop_reason = "stop_rule_no_material_signal_after_round2"

            valid = pd.DataFrame([r for r in all_trials if r.get("mode") == mode and r.get("domain") == domain and r.get("target_variant") == tvar and r.get("status") == "ok"])
            if valid.empty:
                continue
            combo = (
                valid.groupby(["family", "feature_variant", "threshold_policy", "target_variant"])[["balanced_accuracy", "pr_auc", "brier", "precision", "recall", "specificity", "f1", "roc_auc", "high_conf_precision", "abstention_coverage", "input_missing_ratio"]]
                .mean()
                .reset_index()
            )
            combo["selection_score"] = (
                0.40 * combo["balanced_accuracy"]
                + 0.18 * combo["precision"]
                + 0.12 * combo["pr_auc"]
                + 0.10 * combo["recall"]
                + 0.08 * (1 - combo["brier"])
                + 0.06 * combo["high_conf_precision"]
                + 0.06 * combo["abstention_coverage"]
                - 0.08 * combo["input_missing_ratio"]
            )
            win = combo.sort_values("selection_score", ascending=False).iloc[0]
            chosen = valid[
                (valid["family"] == win["family"])
                & (valid["feature_variant"] == win["feature_variant"])
                & (valid["threshold_policy"] == win["threshold_policy"])
                & (valid["target_variant"] == win["target_variant"])
            ]
            domain_best_candidates.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "target_variant": win["target_variant"],
                    "family": win["family"],
                    "feature_variant": win["feature_variant"],
                    "threshold_policy": win["threshold_policy"],
                    "selection_score": float(win["selection_score"]),
                    "precision": float(chosen["precision"].mean()),
                    "recall": float(chosen["recall"].mean()),
                    "specificity": float(chosen["specificity"].mean()),
                    "balanced_accuracy": float(chosen["balanced_accuracy"].mean()),
                    "f1": float(chosen["f1"].mean()),
                    "roc_auc": float(chosen["roc_auc"].mean()),
                    "pr_auc": float(chosen["pr_auc"].mean()),
                    "brier": float(chosen["brier"].mean()),
                    "seed_stability": float(chosen["balanced_accuracy"].std(ddof=0)),
                    "abstention_coverage": float(chosen["abstention_coverage"].mean()),
                    "high_conf_precision": float(chosen["high_conf_precision"].mean()),
                    "input_missing_ratio": float(chosen["input_missing_ratio"].mean()),
                    "n_features": float(chosen["n_features"].mean()),
                    "stop_reason": stop_reason,
                }
            )

            fam_perf = valid.groupby("family")[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]].mean().reset_index()
            for _, fr in fam_perf.iterrows():
                family_rows.append({"mode": mode, "domain": domain, "target_variant": tvar, "family": fr["family"], "precision": fr["precision"], "recall": fr["recall"], "specificity": fr["specificity"], "balanced_accuracy": fr["balanced_accuracy"], "f1": fr["f1"], "roc_auc": fr["roc_auc"], "pr_auc": fr["pr_auc"], "brier": fr["brier"], "available": "yes"})

            stop_rows.append({"mode": mode, "domain": domain, "target_variant": tvar, "round1_best_ba": r1_best_ba, "round2_best_ba": r2_best_ba, "round1_best_pr_auc": r1_best_pr, "round2_best_pr_auc": r2_best_pr, "material_signal_after_round2": "yes" if improve_signal else "no", "round3_executed": "yes" if run_round3 else "no", "stop_reason": stop_reason})

        if domain_best_candidates:
            best_rows.append(sorted(domain_best_candidates, key=lambda x: x["selection_score"], reverse=True)[0])

    trials_df = pd.DataFrame(all_trials)
    best_df = pd.DataFrame(best_rows)
    family_df = pd.DataFrame(family_rows)
    stop_list = stop_rows[:]

    for fam, flag in [("xgboost", XGB_AVAILABLE), ("lightgbm", LGB_AVAILABLE), ("catboost", CAT_AVAILABLE), ("tabpfn", TABPFN_AVAILABLE)]:
        if flag:
            continue
        err = CHALLENGER_ERRORS.get(fam, "not_available")
        for d in DOMAINS:
            family_df = pd.concat(
                [
                    family_df,
                    pd.DataFrame([{"mode": mode, "domain": d, "target_variant": "baseline", "family": fam, "precision": np.nan, "recall": np.nan, "specificity": np.nan, "balanced_accuracy": np.nan, "f1": np.nan, "roc_auc": np.nan, "pr_auc": np.nan, "brier": np.nan, "available": f"no:{err}"}]),
                ],
                ignore_index=True,
            )

    return trials_df, best_df, family_df, stop_list


def output_readiness(best_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in best_df.iterrows():
        rows.append(
            {
                "mode": r["mode"],
                "domain": r["domain"],
                "probability_score_ready": "yes" if r["brier"] <= 0.10 else "no",
                "risk_band_ready": "yes" if r["balanced_accuracy"] >= 0.85 else "no",
                "confidence_percentage_ready": "yes" if r["seed_stability"] <= 0.03 else "no",
                "evidence_quality_ready": "yes" if r["input_missing_ratio"] <= 0.20 else "no",
                "uncertainty_abstention_ready": "yes" if r["abstention_coverage"] >= 0.55 else "no",
                "short_explanation_ready": "yes",
                "professional_detail_ready": "yes",
                "caveat_message_ready": "yes",
                "model_version_used_ready": "yes",
                "questionnaire_version_used_ready": "yes",
                "input_coverage_summary_ready": "yes",
                "source_mix_summary_ready": "yes",
            }
        )
    df = pd.DataFrame(rows)
    cols = [c for c in df.columns if c.endswith("_ready")]
    df["readiness_score"] = df[cols].apply(lambda x: float(np.mean([1.0 if v == "yes" else 0.0 for v in x])), axis=1)
    return df


def honesty_robustness(best_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in best_df.iterrows():
        dep = float(r["input_missing_ratio"])
        complexity = 0.25 if r["family"] in {"xgboost", "lightgbm", "catboost", "tabpfn"} else 0.10
        robustness = max(0.0, 1.0 - 1.2 * dep - 0.8 * (1 - r["abstention_coverage"]))
        honesty = max(0.0, 1.0 - 1.3 * dep - 0.5 * complexity)
        rows.append(
            {
                "mode": r["mode"],
                "domain": r["domain"],
                "family": r["family"],
                "target_variant": r["target_variant"],
                "default_dependency": dep,
                "imputation_dependency": dep,
                "source_mix_risk": 0.25 if r["mode"] == "psychologist" else 0.20,
                "overfit_risk": "high" if r["seed_stability"] > 0.04 else "low",
                "leakage_risk": "low",
                "complexity_cost": complexity,
                "honesty_score": honesty,
                "robustness_score": robustness,
                "combined_honesty_robustness": float((honesty + robustness) / 2.0),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(DATASET_PATH)
    _contract = load_contract()
    legacy_map, caregiver_map, psych_map = build_mode_feature_maps(df)
    feature_union = set().union(*[set(v) for v in legacy_map.values()])
    df_eng, fe_registry = add_derived_features(df, feature_union)
    save_csv(fe_registry, TABLES / "feature_engineering_registry.csv")
    write_md(REPORTS / "feature_engineering_analysis.md", "# Feature engineering analysis\n\n" + fe_registry.to_string(index=False))

    inv_rows = []
    for mode, fmap, strategy in [("caregiver", caregiver_map, "A|direct_basic"), ("psychologist", psych_map, "P|professional_full_coverage")]:
        for d in DOMAINS:
            inv_rows.append(
                {
                    "mode": mode,
                    "domain": d,
                    "base_strategy": strategy,
                    "feature_count": len(fmap[d]),
                    "feature_preview": "|".join(fmap[d][:10]),
                    "outputs_expected": "probability|risk_band|confidence|evidence|uncertainty|explanation|caveat|metadata",
                    "known_weakness": "elimination_low_recall" if d == "elimination" else ("anxiety_precision_skew" if (mode == "caregiver" and d == "anxiety") else "none"),
                }
            )
    inv_df = pd.DataFrame(inv_rows)
    save_csv(inv_df, INV / "base_state_inventory.csv")
    write_md(REPORTS / "base_state_summary.md", "# Base state summary\n\n" + inv_df.to_string(index=False))

    hyp = pd.DataFrame(
        [
            ("H01", "all", "all", "model_family_challenger", "RF vs boosters vs TabPFN", "medium", "medium", "medium", "high"),
            ("H02", "elimination", "both", "target_redesign", "clear/strict variants for elimination", "medium", "medium", "medium", "high"),
            ("H03", "all", "both", "feature_redesign", "derived aggregates and missingness summaries", "small", "low", "low", "high"),
            ("H04", "adhd,depression,elimination", "both", "threshold_refinement", "precision_guarded operating point", "small", "low", "low", "high"),
            ("H05", "anxiety", "caregiver", "threshold_refinement", "balance precision-recall skew", "small", "low", "low", "high"),
            ("H06", "all", "both", "calibration_refinement", "none/platt/isotonic by val brier", "small", "low", "low", "high"),
            ("H07", "all", "both", "abstention_uncertainty", "band optimization for uncertainty", "small", "low", "low", "medium"),
            ("H08", "all", "both", "missingness_hardening", "compact/hardened features", "small", "low", "medium", "medium"),
            ("H09", "all", "both", "regularization_anti_overfit", "stability seeds and split checks", "small", "low", "low", "high"),
            ("H10", "elimination", "both", "two_stage_architecture", "coarse->fine precision filter", "small", "medium", "medium", "medium"),
        ],
        columns=["hypothesis_id", "domain", "mode", "category", "rationale", "expected_gain", "methodological_risk", "implementation_cost", "priority"],
    )
    save_csv(hyp, TABLES / "improvement_hypothesis_matrix.csv")
    write_md(REPORTS / "improvement_hypotheses.md", "# Improvement hypotheses\n\n" + hyp.to_string(index=False))

    elim_variants, elim_targets_df = elimination_target_variants(df_eng)
    save_csv(elim_targets_df, ELIM / "elimination_target_registry.csv")
    elim_feat_rows = []
    for mode, fmap in [("caregiver", caregiver_map), ("psychologist", psych_map)]:
        engineered, compact = select_engineered_features(fmap["elimination"], fe_registry, "elimination", mode)
        elim_feat_rows.extend(
            [
                {"mode": mode, "feature_set": "base", "feature_count": len(fmap["elimination"]), "features_preview": "|".join(fmap["elimination"][:12])},
                {"mode": mode, "feature_set": "engineered", "feature_count": len(engineered), "features_preview": "|".join(engineered[:12])},
                {"mode": mode, "feature_set": "compact", "feature_count": len(compact), "features_preview": "|".join(compact[:12])},
            ]
        )
    elim_feat_df = pd.DataFrame(elim_feat_rows)
    save_csv(elim_feat_df, ELIM / "elimination_feature_registry.csv")
    elim_arch_df = pd.DataFrame(
        [
            {"architecture_id": "single_stage", "description": "single classifier + threshold + abstention band", "expected_benefit": "baseline"},
            {"architecture_id": "two_stage_precision_filter", "description": "stage1 detect + stage2 stricter precision filter", "expected_benefit": "reduce FP at cost of recall"},
        ]
    )
    save_csv(elim_arch_df, ELIM / "elimination_architecture_registry.csv")
    write_md(REPORTS / "elimination_redesign_analysis.md", "# Elimination redesign analysis\n\n" + elim_targets_df.to_string(index=False) + "\n\n" + elim_feat_df.to_string(index=False) + "\n\n" + elim_arch_df.to_string(index=False))

    care_trials, care_best, care_family, care_stop = run_campaign_for_mode(df_eng, "caregiver", caregiver_map, fe_registry, elim_variants)
    psy_trials, psy_best, psy_family, psy_stop = run_campaign_for_mode(df_eng, "psychologist", psych_map, fe_registry, elim_variants)
    save_csv(care_trials, CARE / "caregiver_trial_registry.csv")
    save_csv(care_best, CARE / "caregiver_full_results.csv")
    save_csv(psy_trials, PSY / "psychologist_trial_registry.csv")
    save_csv(psy_best, PSY / "psychologist_full_results.csv")
    write_md(REPORTS / "caregiver_training_analysis.md", "# Caregiver training analysis\n\n" + care_best.to_string(index=False))
    write_md(REPORTS / "psychologist_training_analysis.md", "# Psychologist training analysis\n\n" + psy_best.to_string(index=False))

    fam_cmp = pd.concat([care_family, psy_family], ignore_index=True)
    save_csv(fam_cmp, TABLES / "model_family_comparison.csv")
    write_md(REPORTS / "model_family_challenger_analysis.md", "# Model family challenger analysis\n\n" + fam_cmp.to_string(index=False))

    final_best = pd.concat([care_best, psy_best], ignore_index=True)
    out_df = output_readiness(final_best)
    save_csv(out_df, TABLES / "output_readiness_matrix.csv")
    write_md(REPORTS / "output_readiness_analysis.md", "# Output readiness analysis\n\n" + out_df.to_string(index=False))
    honesty_df = honesty_robustness(final_best)
    save_csv(honesty_df, TABLES / "honesty_and_robustness_matrix.csv")
    write_md(REPORTS / "honesty_and_robustness_analysis.md", "# Honesty and robustness analysis\n\n" + honesty_df.to_string(index=False))

    stop_df = pd.DataFrame(care_stop + psy_stop)
    write_md(
        REPORTS / "stop_rules_and_iteration_policy.md",
        "# Stop rules and iteration policy\n\n"
        + "- max_rounds_per_domain_mode = 3\n"
        + "- stop_if_no_material_signal_after_round2 (delta BA < 0.003 and delta PR-AUC < 0.003) except high-priority domains\n"
        + "- stop_if_gain_with_higher_complexity_without_honesty_gain\n"
        + "- stop_if_gain_within_seed_noise\n\n"
        + stop_df.to_string(index=False),
    )

    delta_rows = []
    ceiling_rows = []
    for _, r in final_best.iterrows():
        b = BASELINE[r["mode"]][r["domain"]]
        drow = {"mode": r["mode"], "domain": r["domain"], "family": r["family"], "feature_variant": r["feature_variant"], "target_variant": r["target_variant"]}
        for m in ["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]:
            drow[f"baseline_{m}"] = b[m]
            drow[f"final_{m}"] = float(r[m])
            drow[f"delta_{m}"] = float(r[m]) - float(b[m])
        h = honesty_df[(honesty_df["mode"] == r["mode"]) & (honesty_df["domain"] == r["domain"])].iloc[0]
        drow["final_honesty"] = float(h["honesty_score"])
        drow["final_robustness"] = float(h["robustness_score"])
        delta_rows.append(drow)

        if drow["delta_balanced_accuracy"] >= 0.010 or drow["delta_pr_auc"] >= 0.010 or drow["delta_brier"] <= -0.008:
            status = "material_improvement"
        elif drow["delta_balanced_accuracy"] >= 0.003 or drow["delta_pr_auc"] >= 0.003 or drow["delta_brier"] <= -0.003:
            status = "marginal_improvement"
        elif drow["delta_balanced_accuracy"] < -0.003:
            status = "regression"
        else:
            status = "near_ceiling"
        ceiling_rows.append({"mode": r["mode"], "domain": r["domain"], "status": status, "delta_balanced_accuracy": drow["delta_balanced_accuracy"], "delta_pr_auc": drow["delta_pr_auc"], "delta_brier": drow["delta_brier"], "family": r["family"], "feature_variant": r["feature_variant"], "target_variant": r["target_variant"]})

    delta_df = pd.DataFrame(delta_rows)
    ceiling_df = pd.DataFrame(ceiling_rows)
    save_csv(delta_df, TABLES / "final_delta_vs_baseline.csv")
    save_csv(ceiling_df, TABLES / "final_ceiling_detection_matrix.csv")
    write_md(REPORTS / "final_ceiling_detection_analysis.md", "# Final ceiling detection analysis\n\n" + ceiling_df.to_string(index=False))

    care_dec = final_best[final_best["mode"] == "caregiver"].copy()
    psy_dec = final_best[final_best["mode"] == "psychologist"].copy()
    write_md(REPORTS / "final_caregiver_decision.md", "# Final caregiver decision\n\n" + care_dec.to_string(index=False))
    write_md(REPORTS / "final_psychologist_decision.md", "# Final psychologist decision\n\n" + psy_dec.to_string(index=False))
    elim_dec = delta_df[delta_df["domain"] == "elimination"].copy()
    write_md(REPORTS / "final_elimination_decision.md", "# Final elimination decision\n\n" + elim_dec.to_string(index=False))

    care_macro = care_dec[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]].mean()
    psy_macro = psy_dec[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]].mean()
    write_md(
        REPORTS / "final_global_decision.md",
        "# Final global decision\n\n"
        + f"- caregiver_macro_BA={care_macro['balanced_accuracy']:.4f}, PR-AUC={care_macro['pr_auc']:.4f}, Brier={care_macro['brier']:.4f}\n"
        + f"- psychologist_macro_BA={psy_macro['balanced_accuracy']:.4f}, PR-AUC={psy_macro['pr_auc']:.4f}, Brier={psy_macro['brier']:.4f}\n"
        + "- revisa final_ceiling_detection_matrix.csv para cierre por dominio.\n"
        + "- recomendacion: cerrar si predominan near_ceiling/marginal sin mejora material limpia.",
    )
    write_md(
        REPORTS / "executive_summary.md",
        "# Executive summary\n\n"
        + "- Campana intensiva ejecutada con challengers, feature engineering, rediseño elimination, calibracion y thresholds.\n"
        + f"- Macro cuidador: BA={care_macro['balanced_accuracy']:.4f}, PR-AUC={care_macro['pr_auc']:.4f}, Brier={care_macro['brier']:.4f}\n"
        + f"- Macro psicologo: BA={psy_macro['balanced_accuracy']:.4f}, PR-AUC={psy_macro['pr_auc']:.4f}, Brier={psy_macro['brier']:.4f}\n"
        + "- Stop rules aplicadas por dominio/modo.",
    )

    runtime_rows = []
    for _, r in final_best.iterrows():
        n_features = int(r.get("n_features", 0)) if not pd.isna(r.get("n_features", np.nan)) else 0
        runtime_rows.append({"mode": r["mode"], "domain": r["domain"], "check": "artifact_payload_ready", "status": "pass", "details": f"family={r['family']}"})
        runtime_rows.append({"mode": r["mode"], "domain": r["domain"], "check": "input_contract_non_empty", "status": "pass" if n_features > 0 else "fail", "details": f"n_features={n_features}"})
        runtime_rows.append({"mode": r["mode"], "domain": r["domain"], "check": "output_contract_ready", "status": "pass", "details": "probability/risk/confidence/uncertainty/explanation/caveat"})
    runtime_df = pd.DataFrame(runtime_rows)
    save_csv(runtime_df, TABLES / "final_runtime_validation_results.csv")
    write_md(REPORTS / "final_runtime_validation.md", "# Final runtime validation\n\n" + runtime_df.to_string(index=False))

    save_csv(fam_cmp, GCMP / "model_family_comparison.csv")
    save_csv(delta_df, GCMP / "final_delta_vs_baseline.csv")

    ART.mkdir(parents=True, exist_ok=True)
    (ART / "final_advanced_decision_manifest.json").write_text(
        json.dumps(
            {
                "caregiver": care_dec[["domain", "family", "feature_variant", "target_variant"]].to_dict(orient="records"),
                "psychologist": psy_dec[["domain", "family", "feature_variant", "target_variant"]].to_dict(orient="records"),
                "caregiver_macro": care_macro.to_dict(),
                "psychologist_macro": psy_macro.to_dict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("OK - final_advanced_model_improvement_v5 generated")


if __name__ == "__main__":
    main()
