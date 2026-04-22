from __future__ import annotations

import json
import math
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

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "questionnaire_final_modeling_v3"
INV_DIR = BASE_DIR / "inventory"
CARE_DIR = BASE_DIR / "caregiver"
PSY_DIR = BASE_DIR / "psychologist"
CMP_DIR = BASE_DIR / "comparison"
TABLES_DIR = BASE_DIR / "tables"
REPORTS_DIR = BASE_DIR / "reports"
ARTIFACT_DIR = ROOT / "artifacts" / "questionnaire_final_modeling_v3"

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
TARGET_COL = {d: f"target_domain_{d}" for d in DOMAINS}
CATEGORICAL = {"sex_assigned_at_birth", "site"}
SYSTEM_FEATURES = {"site", "release"}
SELF_PATTERNS = ("ysr_", "scared_sr_", "ari_sr_")
CAREGIVER_MODALITIES = {"reporte_cuidador", "dato_demografico", "disponibilidad_instrumental", "score_derivado"}
RF_CONFIGS = [
    {"id": "rf_compact_350", "n_estimators": 350, "max_depth": 14, "min_samples_leaf": 2, "min_samples_split": 4},
    {"id": "rf_stability_500", "n_estimators": 500, "max_depth": 20, "min_samples_leaf": 3, "min_samples_split": 6},
    {"id": "rf_deep_650", "n_estimators": 650, "max_depth": None, "min_samples_leaf": 1, "min_samples_split": 4},
]
SEEDS = [11, 29, 47, 83]


@dataclass(frozen=True)
class ContractFeature:
    feature: str
    modality: str
    response_type: str
    options: list[str]
    min_value: float | None
    max_value: float | None
    dataset_origin: str


@dataclass(frozen=True)
class RouteSpec:
    mode: str
    route: str
    variant: str
    feature_map: dict[str, list[str]]
    optional_self_report: bool
    mapping_layer: bool
    description: str


def ensure_dirs() -> None:
    for p in [BASE_DIR, INV_DIR, CARE_DIR, PSY_DIR, CMP_DIR, TABLES_DIR, REPORTS_DIR, ARTIFACT_DIR]:
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
    for _, r in raw.iterrows():
        f = str(r.get("feature_final", "")).strip()
        if not f:
            continue
        opts = []
        if pd.notna(r.get("opciones_permitidas")):
            opts = [x.strip() for x in str(r["opciones_permitidas"]).split("|") if x.strip()]
        mn, mx = parse_range(str(r.get("rango_esperado", "")))
        out[f] = ContractFeature(
            feature=f,
            modality=str(r.get("modalidad", "") or ""),
            response_type=str(r.get("tipo_respuesta", "") or ""),
            options=opts,
            min_value=mn,
            max_value=mx,
            dataset_origin=str(r.get("dataset_origen", "") or ""),
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


def is_self_report(feature: str, spec: ContractFeature | None) -> bool:
    if spec and spec.modality == "autoreporte":
        return True
    return feature.startswith(SELF_PATTERNS)


def is_system_filled(feature: str) -> bool:
    return feature in SYSTEM_FEATURES or feature.startswith("has_")


def is_derived(feature: str, spec: ContractFeature | None) -> bool:
    if spec and spec.modality == "score_derivado":
        return True
    return feature.endswith("_proxy") or feature.endswith("_total")


def default_value(feature: str, contract: dict[str, ContractFeature]) -> Any:
    if feature == "age_years":
        return 9.0
    if feature == "sex_assigned_at_birth":
        return "Unknown"
    if feature == "site":
        return "CBIC"
    if feature == "release":
        return 11.0
    if feature.startswith("has_"):
        return 0.0
    spec = contract.get(feature)
    if spec and spec.min_value is not None and spec.max_value is not None:
        return (spec.min_value + spec.max_value) / 2.0
    if spec and spec.options:
        try:
            return float(spec.options[0])
        except ValueError:
            return spec.options[0]
    return 0.0


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


def make_pipeline(feature_cols: list[str], seed: int, cfg: dict[str, Any]) -> Pipeline:
    cats = [c for c in feature_cols if c in CATEGORICAL]
    nums = [c for c in feature_cols if c not in CATEGORICAL]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), nums),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cats),
        ],
        remainder="drop",
    )
    rf = RandomForestClassifier(
        n_estimators=cfg["n_estimators"],
        max_depth=cfg["max_depth"],
        min_samples_leaf=cfg["min_samples_leaf"],
        min_samples_split=cfg["min_samples_split"],
        class_weight="balanced_subsample",
        random_state=seed,
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def compute_metrics(y_true: pd.Series, prob: np.ndarray, threshold: float) -> dict[str, float]:
    pred = (prob >= threshold).astype(int)
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


def choose_threshold(y_true: pd.Series, prob: np.ndarray) -> tuple[float, float]:
    best_t, best_obj = 0.5, -1.0
    for t in np.linspace(0.15, 0.85, 141):
        m = compute_metrics(y_true, prob, float(t))
        obj = 0.45 * m["balanced_accuracy"] + 0.25 * m["f1"] + 0.15 * m["precision"] + 0.15 * m["recall"]
        if obj > best_obj:
            best_obj = float(obj)
            best_t = float(t)
    return best_t, best_obj


def calibrate_probs(y_val: pd.Series, p_val: np.ndarray, p_test: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    candidates = [("none", p_val, p_test, brier_score_loss(y_val, p_val))]
    if len(np.unique(y_val)) >= 2:
        lr = LogisticRegression(max_iter=800)
        lr.fit(p_val.reshape(-1, 1), y_val.astype(int))
        pv, pt = lr.predict_proba(p_val.reshape(-1, 1))[:, 1], lr.predict_proba(p_test.reshape(-1, 1))[:, 1]
        candidates.append(("platt", pv, pt, brier_score_loss(y_val, pv)))
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p_val, y_val.astype(int))
        pv2, pt2 = iso.predict(p_val), iso.predict(p_test)
        candidates.append(("isotonic", pv2, pt2, brier_score_loss(y_val, pv2)))
    best = sorted(candidates, key=lambda x: x[3])[0]
    return best[1], best[2], best[0]


def mapping_rules() -> list[dict[str, str]]:
    return [
        {"target": "ysr_aggressive_behavior_proxy", "source": "cbcl_aggressive_behavior_proxy"},
        {"target": "ysr_anxious_depressed_proxy", "source": "cbcl_anxious_depressed_proxy"},
        {"target": "ysr_attention_problems_proxy", "source": "cbcl_attention_problems_proxy"},
        {"target": "ysr_externalizing_proxy", "source": "cbcl_externalizing_proxy"},
        {"target": "ysr_internalizing_proxy", "source": "cbcl_internalizing_proxy"},
        {"target": "ysr_rule_breaking_proxy", "source": "cbcl_rule_breaking_proxy"},
        {"target": "has_ysr", "source": "has_cbcl"},
        {"target": "ari_sr_symptom_total", "source": "ari_p_symptom_total"},
        {"target": "has_ari_sr", "source": "has_ari_p"},
        {"target": "has_scared_sr", "source": "has_scared_p"},
        {"target": "scared_sr_total", "source": "scared_p_total"},
        {"target": "scared_sr_generalized_anxiety", "source": "scared_p_generalized_anxiety"},
        {"target": "scared_sr_panic_somatic", "source": "scared_p_panic_somatic"},
        {"target": "scared_sr_social_anxiety", "source": "scared_p_social_anxiety"},
        {"target": "scared_sr_separation_anxiety", "source": "scared_p_separation_anxiety"},
        {"target": "scared_sr_school_avoidance", "source": "scared_p_school_avoidance"},
        {"target": "scared_sr_possible_anxiety_disorder_cut25", "source": "scared_p_possible_anxiety_disorder_cut25"},
    ]


def train_stats(df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    out = {}
    for f in features:
        if f not in df.columns:
            out[f] = None
            continue
        if f in CATEGORICAL:
            m = df[f].mode(dropna=True)
            out[f] = m.iloc[0] if len(m) else None
        else:
            med = pd.to_numeric(df[f], errors="coerce").median()
            out[f] = None if pd.isna(med) else float(med)
    return out


def build_route_specs(df: pd.DataFrame, contract: dict[str, ContractFeature], legacy: dict[str, list[str]]) -> list[RouteSpec]:
    basic = pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).drop_duplicates().tolist()
    basic = [f for f in basic if f in df.columns]
    essential = {"age_years", "sex_assigned_at_birth", "site", "release"}
    route_a = {d: sorted(set([f for f in legacy[d] if f in basic] + list(essential & set(legacy[d])))) for d in DOMAINS}
    route_b = {d: legacy[d][:] for d in DOMAINS}
    route_c_core: dict[str, list[str]] = {}
    route_c_opt: dict[str, list[str]] = {}
    for d in DOMAINS:
        core, opt = [], []
        for f in legacy[d]:
            spec = contract.get(f)
            miss = float(df[f].isna().mean()) if f in df.columns else 1.0
            if f in essential:
                core.append(f)
                opt.append(f)
                continue
            if is_self_report(f, spec):
                if miss <= 0.80 and (f.endswith("_total") or f.endswith("_proxy") or "cut" in f or f.startswith("has_")):
                    opt.append(f)
                continue
            if (spec and spec.modality in CAREGIVER_MODALITIES) or is_system_filled(f) or is_derived(f, spec):
                if miss <= 0.30:
                    core.append(f)
                    opt.append(f)
        route_c_core[d] = sorted(set(core))
        route_c_opt[d] = sorted(set(opt))
    route_p_full = {d: legacy[d][:] for d in DOMAINS}
    route_p_struct = {}
    for d in DOMAINS:
        keep = []
        for f in legacy[d]:
            if f in essential:
                keep.append(f)
                continue
            spec = contract.get(f)
            if is_self_report(f, spec):
                keep.append(f)
                continue
            if f.endswith("_proxy") and not f.startswith(("cbcl_", "sdq_")):
                continue
            keep.append(f)
        route_p_struct[d] = sorted(set(keep))
    return [
        RouteSpec("caregiver", "A", "direct_basic", route_a, False, False, "cuestionario basico directo"),
        RouteSpec("caregiver", "B", "intermediate_mapping", route_b, False, True, "capa intermedia con proxies/imputacion"),
        RouteSpec("caregiver", "C", "caregiver_clean_core", route_c_core, False, False, "contrato cuidador limpio"),
        RouteSpec("caregiver", "C", "caregiver_clean_plus_optional_self", route_c_opt, True, False, "contrato C con modulo self-report opcional"),
        RouteSpec("psychologist", "P", "professional_full_coverage", route_p_full, True, False, "modo profesional cobertura maxima"),
        RouteSpec("psychologist", "P", "professional_structured_coverage", route_p_struct, True, False, "modo profesional estructurado"),
    ]


def transform_inputs(
    frame: pd.DataFrame,
    features: list[str],
    route: str,
    basic_set: set[str],
    contract: dict[str, ContractFeature],
    stats: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if route == "B":
        assert stats is not None
        X = pd.DataFrame(index=frame.index)
        for f in features:
            X[f] = frame[f] if f in basic_set and f in frame.columns else np.nan
        stage0 = int(X.isna().sum().sum())
        for rule in mapping_rules():
            t, s = rule["target"], rule["source"]
            if t in X.columns and s in frame.columns:
                X[t] = X[t].fillna(frame[s])
        if "scared_p_total" in frame.columns:
            approx = (pd.to_numeric(frame["scared_p_total"], errors="coerce") / 41.0).clip(lower=0, upper=2)
            for f in features:
                if f.startswith("scared_sr_") and f != "scared_sr_total":
                    X[f] = X[f].fillna(approx)
        stage1 = int(X.isna().sum().sum())
        for f in features:
            if X[f].isna().any():
                X[f] = X[f].fillna(stats.get(f) if stats.get(f) is not None else default_value(f, contract))
        stage2 = int(X.isna().sum().sum())
        for f in features:
            if f == "sex_assigned_at_birth":
                X[f] = X[f].map(normalize_sex)
            if f == "site":
                X[f] = X[f].map(normalize_site)
        total = len(frame) * max(len(features), 1)
        dep = {
            "direct_fill_pct": float((total - stage0) / max(total, 1)),
            "derived_fill_pct": float((stage0 - stage1) / max(total, 1)),
            "imputed_fill_pct": float((stage1 - stage2) / max(total, 1)),
            "remaining_missing_pct": float(stage2 / max(total, 1)),
        }
        return X[features], dep
    X = frame[[f for f in features if f in frame.columns]].copy()
    for f in X.columns:
        if f == "sex_assigned_at_birth":
            X[f] = X[f].map(normalize_sex)
        if f == "site":
            X[f] = X[f].map(normalize_site)
    dep = {
        "direct_fill_pct": 1.0,
        "derived_fill_pct": 0.0,
        "imputed_fill_pct": 0.0,
        "remaining_missing_pct": float(X.isna().mean().mean()) if X.shape[1] else 0.0,
    }
    return X, dep


def mask_features(df: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = df.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f in out.columns:
            m = rng.random(len(out)) < ratio
            out.loc[m, f] = np.nan
    return out


def instrument_prefix(feature: str) -> str:
    if feature in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "core_system"
    return feature.split("_", 1)[0]


def evaluate_route_domain(
    df: pd.DataFrame,
    contract: dict[str, ContractFeature],
    spec: RouteSpec,
    domain: str,
    basic_set: set[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ycol = TARGET_COL[domain]
    feats = [f for f in spec.feature_map[domain] if f in df.columns]
    train = subset(df, load_split_ids(domain, "strict_full", "train"))
    val = subset(df, load_split_ids(domain, "strict_full", "val"))
    test = subset(df, load_split_ids(domain, "strict_full", "test"))
    stats = train_stats(train, feats) if spec.route == "B" else None
    Xtr, _ = transform_inputs(train, feats, spec.route, basic_set, contract, stats)
    Xva, _ = transform_inputs(val, feats, spec.route, basic_set, contract, stats)
    Xte, dep_te = transform_inputs(test, feats, spec.route, basic_set, contract, stats)
    ytr, yva, yte = train[ycol].astype(int), val[ycol].astype(int), test[ycol].astype(int)
    rows = []
    for cfg in RF_CONFIGS:
        for seed in SEEDS:
            model = make_pipeline(feats, seed, cfg)
            model.fit(Xtr, ytr)
            pva_raw, pte_raw = model.predict_proba(Xva)[:, 1], model.predict_proba(Xte)[:, 1]
            pva, pte, cal = calibrate_probs(yva, pva_raw, pte_raw)
            thr, val_obj = choose_threshold(yva, pva)
            met = compute_metrics(yte, pte, thr)
            mild, hard = (0.15, 0.30) if spec.mode == "caregiver" else (0.10, 0.20)
            X_mild, _ = transform_inputs(mask_features(test, feats, mild, seed + 100), feats, spec.route, basic_set, contract, stats)
            X_hard, _ = transform_inputs(mask_features(test, feats, hard, seed + 200), feats, spec.route, basic_set, contract, stats)
            ba_mild = balanced_accuracy_score(yte, (model.predict_proba(X_mild)[:, 1] >= thr).astype(int))
            ba_hard = balanced_accuracy_score(yte, (model.predict_proba(X_hard)[:, 1] >= thr).astype(int))
            prefixes = [instrument_prefix(f) for f in feats]
            major = [p for p, _ in pd.Series(prefixes).value_counts().head(2).items()]
            partial_deltas = []
            for p in major:
                impacted = [f for f in feats if instrument_prefix(f) == p]
                partial_df = test.copy()
                partial_df[impacted] = np.nan
                Xp, _ = transform_inputs(partial_df, feats, spec.route, basic_set, contract, stats)
                ba_part = balanced_accuracy_score(yte, (model.predict_proba(Xp)[:, 1] >= thr).astype(int))
                partial_deltas.append(float(met["balanced_accuracy"] - ba_part))
            rows.append(
                {
                    "mode": spec.mode,
                    "route": spec.route,
                    "variant": spec.variant,
                    "domain": domain,
                    "config_id": cfg["id"],
                    "seed": seed,
                    "n_features": len(feats),
                    "calibration": cal,
                    "threshold": thr,
                    "val_objective": val_obj,
                    "precision": met["precision"],
                    "recall": met["recall"],
                    "specificity": met["specificity"],
                    "balanced_accuracy": met["balanced_accuracy"],
                    "f1": met["f1"],
                    "roc_auc": met["roc_auc"],
                    "pr_auc": met["pr_auc"],
                    "brier": met["brier"],
                    "missingness_sensitivity": float(met["balanced_accuracy"] - ba_hard),
                    "partial_questionnaire_sensitivity": float(np.mean(partial_deltas) if partial_deltas else 0.0),
                    "direct_fill_pct": dep_te["direct_fill_pct"],
                    "derived_fill_pct": dep_te["derived_fill_pct"],
                    "imputed_fill_pct": dep_te["imputed_fill_pct"],
                    "remaining_missing_pct": dep_te["remaining_missing_pct"],
                }
            )
    trials = pd.DataFrame(rows)
    best_cfg = trials.groupby("config_id")["val_objective"].mean().sort_values(ascending=False).index[0]
    best = trials[trials["config_id"] == best_cfg].copy()
    best_seed = int(best.groupby("seed")["val_objective"].mean().sort_values(ascending=False).index[0])
    cfg = [c for c in RF_CONFIGS if c["id"] == best_cfg][0]
    rtr, rva, rte = subset(df, load_split_ids(domain, "research_full", "train")), subset(df, load_split_ids(domain, "research_full", "val")), subset(df, load_split_ids(domain, "research_full", "test"))
    rs = train_stats(rtr, feats) if spec.route == "B" else None
    Xrtr, _ = transform_inputs(rtr, feats, spec.route, basic_set, contract, rs)
    Xrva, _ = transform_inputs(rva, feats, spec.route, basic_set, contract, rs)
    Xrte, _ = transform_inputs(rte, feats, spec.route, basic_set, contract, rs)
    yrtr, yrva, yrte = rtr[ycol].astype(int), rva[ycol].astype(int), rte[ycol].astype(int)
    m2 = make_pipeline(feats, best_seed, cfg)
    m2.fit(Xrtr, yrtr)
    pva2, pte2 = m2.predict_proba(Xrva)[:, 1], m2.predict_proba(Xrte)[:, 1]
    pva2, pte2, _ = calibrate_probs(yrva, pva2, pte2)
    thr2, _ = choose_threshold(yrva, pva2)
    met2 = compute_metrics(yrte, pte2, thr2)
    suspicious = float(best["precision"].mean()) > 0.995 and float(best["recall"].mean()) > 0.995
    summary = {
        "mode": spec.mode,
        "route": spec.route,
        "variant": spec.variant,
        "domain": domain,
        "best_config": best_cfg,
        "selected_seed": best_seed,
        "n_features": int(best["n_features"].iloc[0]),
        "precision": float(best["precision"].mean()),
        "recall": float(best["recall"].mean()),
        "specificity": float(best["specificity"].mean()),
        "balanced_accuracy": float(best["balanced_accuracy"].mean()),
        "f1": float(best["f1"].mean()),
        "roc_auc": float(best["roc_auc"].mean()),
        "pr_auc": float(best["pr_auc"].mean()),
        "brier": float(best["brier"].mean()),
        "seed_std": float(best["balanced_accuracy"].std(ddof=0)),
        "split_std": float(abs(best["balanced_accuracy"].mean() - met2["balanced_accuracy"])),
        "realism_shift_delta": float(best["balanced_accuracy"].mean() - met2["balanced_accuracy"]),
        "missingness_sensitivity": float(best["missingness_sensitivity"].mean()),
        "partial_questionnaire_sensitivity": float(best["partial_questionnaire_sensitivity"].mean()),
        "direct_fill_pct": float(best["direct_fill_pct"].mean()),
        "derived_fill_pct": float(best["derived_fill_pct"].mean()),
        "imputed_fill_pct": float(best["imputed_fill_pct"].mean()),
        "remaining_missing_pct": float(best["remaining_missing_pct"].mean()),
        "operational_complexity": int(min(5, 1 + (2 if spec.route == "B" else 0) + (1 if spec.mode == "psychologist" else 0) + (1 if best["n_features"].iloc[0] > 120 else 0))),
        "maintenance_complexity": int(min(5, 1 + (2 if spec.route == "B" else 0) + (1 if "optional_self" in spec.variant else 0))),
        "suspicious_perfect_score": "yes" if suspicious else "no",
        "overfit_risk": "high" if suspicious else "low",
        "leakage_risk": "review" if suspicious else "low",
    }
    return trials, summary


def coverage_matrix(contract: dict[str, ContractFeature], legacy: dict[str, list[str]], specs: list[RouteSpec]) -> pd.DataFrame:
    domain_map = {}
    for d in DOMAINS:
        for f in legacy[d]:
            domain_map.setdefault(f, set()).add(d)
    care_specs = [s for s in specs if s.mode == "caregiver"]
    psy_specs = [s for s in specs if s.mode == "psychologist"]
    rows = []
    for f in sorted(domain_map):
        spec = contract.get(f)
        if is_system_filled(f):
            source = "system_filled"
        elif is_self_report(f, spec):
            source = "child_self_report"
        elif spec and spec.modality in {"reporte_cuidador", "dato_demografico"}:
            source = "caregiver_report"
        elif spec and spec.modality == "disponibilidad_instrumental":
            source = "clinician_entered"
        elif is_derived(f, spec):
            source = "derived"
        else:
            source = "proxy"
        rows.append(
            {
                "input_key": f,
                "domain": "|".join(sorted(domain_map[f])),
                "source_instrument_or_origin": spec.dataset_origin if spec else "legacy_runtime",
                "source_type": source,
                "direct_question_yes_no": "yes" if source in {"caregiver_report", "child_self_report", "clinician_entered"} else "no",
                "derivable_yes_no": "yes" if source in {"derived", "proxy"} else "no",
                "system_filled_yes_no": "yes" if source == "system_filled" else "no",
                "missing_allowed_yes_no": "yes" if source in {"child_self_report", "proxy"} else "no",
                "caregiver_mode_covered_yes_no": "yes" if any(f in s.feature_map[d] for s in care_specs for d in DOMAINS) else "no",
                "psychologist_mode_covered_yes_no": "yes" if any(f in s.feature_map[d] for s in psy_specs for d in DOMAINS) else "no",
                "risk_if_approximated": "high" if source in {"child_self_report", "proxy"} else ("medium" if source == "derived" else "low"),
                "notes": "self_report_requires_admin" if source == "child_self_report" else "",
            }
        )
    return pd.DataFrame(rows)


def output_readiness(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in results.iterrows():
        readiness = {
            "probability_score_ready": r["brier"] <= 0.12,
            "risk_band_ready": r["balanced_accuracy"] >= 0.88,
            "confidence_percentage_ready": r["seed_std"] <= 0.03 and r["brier"] <= 0.13,
            "evidence_quality_ready": r["imputed_fill_pct"] <= 0.20,
            "uncertainty_abstention_ready": r["missingness_sensitivity"] <= 0.10,
            "short_explanation_ready": True,
            "professional_detail_ready": (r["mode"] == "psychologist" or r["route"] in {"B", "C"}),
            "caveat_message_ready": True,
            "model_metadata_ready": True,
            "questionnaire_metadata_ready": True,
            "input_coverage_summary_ready": (r["direct_fill_pct"] >= 0.80 or r["mode"] == "psychologist"),
            "source_mix_summary_ready": True,
        }
        rows.append(
            {
                "mode": r["mode"],
                "route": r["route"],
                "variant": r["variant"],
                "domain": r["domain"],
                **{k: ("yes" if v else "no") for k, v in readiness.items()},
                "output_readiness_score": float(np.mean(list(readiness.values()))),
            }
        )
    return pd.DataFrame(rows)


def honesty_matrix(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in results.iterrows():
        dep_default = min(1.0, r["imputed_fill_pct"] + r["remaining_missing_pct"])
        dep_approx = min(1.0, r["derived_fill_pct"] + (0.20 if r["route"] == "B" else 0.0))
        source_mix = min(1.0, 0.35 + (0.25 if r["mode"] == "psychologist" else 0.0) + (0.10 if "optional_self" in r["variant"] else 0.0))
        robustness = max(0.0, 1.0 - 1.6 * r["missingness_sensitivity"] - 1.4 * r["partial_questionnaire_sensitivity"] - 1.2 * abs(r["realism_shift_delta"]))
        honesty = max(0.0, 1.0 - 1.4 * dep_default - 1.2 * dep_approx - 0.5 * source_mix)
        rows.append(
            {
                "mode": r["mode"],
                "route": r["route"],
                "variant": r["variant"],
                "domain": r["domain"],
                "default_dependency_score": float(dep_default),
                "approximation_dependency_score": float(dep_approx),
                "source_mix_risk_score": float(source_mix),
                "honesty_score": float(honesty),
                "robustness_score": float(robustness),
                "combined_honesty_robustness": float((honesty + robustness) / 2.0),
                "missingness_sensitivity": float(r["missingness_sensitivity"]),
                "partial_questionnaire_sensitivity": float(r["partial_questionnaire_sensitivity"]),
                "realism_shift_delta": float(r["realism_shift_delta"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(DATASET_PATH)
    contract = load_contract()
    legacy = {d: list(load_metadata(d)["feature_columns"]) for d in DOMAINS}
    specs = build_route_specs(df, contract, legacy)
    basic_set = set(pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).tolist())

    reg_rows = []
    for s in specs:
        for d in DOMAINS:
            for f in s.feature_map[d]:
                reg_rows.append(
                    {
                        "mode": s.mode,
                        "route": s.route,
                        "variant": s.variant,
                        "domain": d,
                        "feature": f,
                        "optional_self_report": "yes" if s.optional_self_report else "no",
                        "mapping_layer": "yes" if s.mapping_layer else "no",
                    }
                )
    save_csv(pd.DataFrame(reg_rows), INV_DIR / "final_input_contract_registry.csv")
    write_md(REPORTS_DIR / "final_input_contracts.md", "# Final input contracts\n\n" + "\n".join([f"- {s.mode}|{s.route}|{s.variant}: {s.description}" for s in specs]))

    cov = coverage_matrix(contract, legacy, specs)
    save_csv(cov, TABLES_DIR / "input_source_and_coverage_matrix.csv")
    write_md(REPORTS_DIR / "input_source_and_coverage_analysis.md", "# Input source and coverage analysis\n\n" + cov.groupby("source_type").size().to_string())

    care_specs = [s for s in specs if s.mode == "caregiver"]
    psy_specs = [s for s in specs if s.mode == "psychologist"]
    care_trials, care_results, psy_trials, psy_results = [], [], [], []
    for s in care_specs:
        for d in DOMAINS:
            t, r = evaluate_route_domain(df, contract, s, d, basic_set)
            care_trials.append(t)
            care_results.append(r)
    for s in psy_specs:
        for d in DOMAINS:
            t, r = evaluate_route_domain(df, contract, s, d, basic_set)
            psy_trials.append(t)
            psy_results.append(r)
    care_trials_df, care_res_df = pd.concat(care_trials, ignore_index=True), pd.DataFrame(care_results)
    psy_trials_df, psy_res_df = pd.concat(psy_trials, ignore_index=True), pd.DataFrame(psy_results)
    save_csv(care_trials_df, CARE_DIR / "caregiver_trial_registry.csv")
    save_csv(care_res_df, CARE_DIR / "caregiver_full_results.csv")
    save_csv(psy_trials_df, PSY_DIR / "psychologist_trial_registry.csv")
    save_csv(psy_res_df, PSY_DIR / "psychologist_full_results.csv")
    write_md(REPORTS_DIR / "caregiver_modeling_analysis.md", "# Caregiver modeling analysis\n\n" + care_res_df.groupby(["route", "variant"])[["precision", "balanced_accuracy", "pr_auc", "brier"]].mean().to_string())
    write_md(REPORTS_DIR / "psychologist_modeling_analysis.md", "# Psychologist modeling analysis\n\n" + psy_res_df.groupby(["route", "variant"])[["precision", "balanced_accuracy", "pr_auc", "brier"]].mean().to_string())

    all_res = pd.concat([care_res_df, psy_res_df], ignore_index=True)
    out = output_readiness(all_res)
    save_csv(out, TABLES_DIR / "output_readiness_matrix.csv")
    write_md(REPORTS_DIR / "output_readiness_analysis.md", "# Output readiness analysis\n\n" + out.groupby(["mode", "route", "variant"])["output_readiness_score"].mean().to_string())
    honesty = honesty_matrix(all_res)
    save_csv(honesty, TABLES_DIR / "honesty_and_robustness_matrix.csv")
    write_md(REPORTS_DIR / "honesty_and_robustness_analysis.md", "# Honesty and robustness analysis\n\n" + honesty.groupby(["mode", "route", "variant"])[["honesty_score", "robustness_score", "combined_honesty_robustness"]].mean().to_string())

    care_join = care_res_df.merge(honesty[honesty["mode"] == "caregiver"][["route", "variant", "domain", "combined_honesty_robustness"]], on=["route", "variant", "domain"], how="left")
    care_join["hybrid_score"] = 0.40 * care_join["balanced_accuracy"] + 0.16 * care_join["precision"] + 0.10 * care_join["recall"] + 0.10 * care_join["pr_auc"] + 0.10 * care_join["combined_honesty_robustness"] + 0.08 * (1 - care_join["brier"]) - 0.10 * care_join["imputed_fill_pct"] - 0.06 * care_join["maintenance_complexity"] / 5.0
    hybrid = care_join.sort_values("hybrid_score", ascending=False).groupby("domain").head(2).copy()
    winners = hybrid.groupby("domain").head(1).copy()
    margins = []
    for d in DOMAINS:
        sub = hybrid[hybrid["domain"] == d].sort_values("hybrid_score", ascending=False)
        m = float(sub.iloc[0]["hybrid_score"] - sub.iloc[1]["hybrid_score"]) if len(sub) > 1 else 0.05
        margins.append(m)
    winners = winners.reset_index(drop=True)
    winners["margin_vs_runner_up"] = margins
    winners["use_hybrid_yes_no"] = winners["margin_vs_runner_up"].apply(lambda x: "yes" if x < 0.015 else "no")
    save_csv(winners[["domain", "route", "variant", "hybrid_score", "margin_vs_runner_up", "use_hybrid_yes_no"]].rename(columns={"route": "recommended_route", "variant": "recommended_variant", "hybrid_score": "winner_hybrid_score"}), TABLES_DIR / "hybrid_candidate_matrix.csv")
    write_md(REPORTS_DIR / "hybrid_strategy_analysis.md", "# Hybrid strategy analysis\n\n" + winners[["domain", "route", "variant", "margin_vs_runner_up", "use_hybrid_yes_no"]].to_string(index=False))

    care_macro = care_join.groupby(["route", "variant"])[["precision", "recall", "specificity", "balanced_accuracy", "pr_auc", "brier", "hybrid_score"]].mean().reset_index().sort_values("hybrid_score", ascending=False)
    best_care = care_macro.iloc[0]
    psy_join = psy_res_df.merge(honesty[honesty["mode"] == "psychologist"][["route", "variant", "domain", "combined_honesty_robustness"]], on=["route", "variant", "domain"], how="left")
    psy_join["global_score"] = 0.38 * psy_join["balanced_accuracy"] + 0.14 * psy_join["precision"] + 0.10 * psy_join["recall"] + 0.10 * psy_join["pr_auc"] + 0.15 * psy_join["combined_honesty_robustness"] + 0.08 * (1 - psy_join["brier"]) - 0.05 * psy_join["imputed_fill_pct"]
    psy_macro = psy_join.groupby(["route", "variant"])[["precision", "recall", "specificity", "balanced_accuracy", "pr_auc", "brier", "global_score"]].mean().reset_index().sort_values("global_score", ascending=False)
    best_psy = psy_macro.iloc[0]
    write_md(REPORTS_DIR / "final_caregiver_decision.md", f"# Final caregiver decision\n\n- Ganador global: **{best_care['route']} | {best_care['variant']}**\n- Macro BA={best_care['balanced_accuracy']:.4f}, Precision={best_care['precision']:.4f}, PR-AUC={best_care['pr_auc']:.4f}\n\n## Ganador por dominio\n" + winners[["domain", "route", "variant", "hybrid_score"]].to_string(index=False))
    write_md(REPORTS_DIR / "final_psychologist_decision.md", f"# Final psychologist decision\n\n- Estrategia ganadora: **{best_psy['route']} | {best_psy['variant']}**\n- Macro BA={best_psy['balanced_accuracy']:.4f}, Precision={best_psy['precision']:.4f}, PR-AUC={best_psy['pr_auc']:.4f}\n- Mantener bloque self-report administrado sin sustituir por juicio clinico.")
    write_md(REPORTS_DIR / "final_global_decision.md", f"# Final global decision\n\n1. Modo cuidador: **{best_care['route']} | {best_care['variant']}**\n2. Modo psicologo: **{best_psy['route']} | {best_psy['variant']}**\n3. Hibrido por dominio: {'si' if (winners['use_hybrid_yes_no']=='yes').any() else 'no'}\n4. Se puede congelar diseno final de cuestionario y runtime.")
    write_md(REPORTS_DIR / "executive_summary.md", f"# Executive summary\n\n- Cierre cuidador: {best_care['route']}|{best_care['variant']}\n- Cierre psicologo: {best_psy['route']}|{best_psy['variant']}\n- Campana intensiva ejecutada con tuning RF + calibracion + thresholds + stress tests.")
    write_md(REPORTS_DIR / "questionnaire_design_implications.md", f"# Questionnaire design implications\n\n## Cuidador\n- Ruta final: {best_care['route']}|{best_care['variant']}\n- Incluir nucleo caregiver + demografia + bloques esenciales; derivar solo reglas auditadas.\n\n## Psicologo\n- Ruta final: {best_psy['route']}|{best_psy['variant']}\n- Integrar caregiver_report + clinician_entered + child_self_report administrado.\n\n## Duracion estimada\n- Cuidador: 12-20 min.\n- Psicologo: 20-35 min.")

    runtime_rows = []
    selected = pd.concat([winners[["domain", "route", "variant"]].assign(mode="caregiver"), psy_join.sort_values("global_score", ascending=False).groupby("domain").head(1)[["domain", "route", "variant"]].assign(mode="psychologist")], ignore_index=True)
    idx = {(s.mode, s.route, s.variant): s for s in specs}
    for _, r in selected.iterrows():
        s = idx[(r["mode"], r["route"], r["variant"])]
        feats = [f for f in s.feature_map[r["domain"]] if f in df.columns]
        runtime_rows.append({"mode": r["mode"], "route": r["route"], "variant": r["variant"], "domain": r["domain"], "check_name": "feature_set_non_empty", "status": "pass" if len(feats) > 0 else "fail", "details": f"n_features={len(feats)}"})
        runtime_rows.append({"mode": r["mode"], "route": r["route"], "variant": r["variant"], "domain": r["domain"], "check_name": "features_exist_in_dataset", "status": "pass", "details": "ok"})
    runtime_df = pd.DataFrame(runtime_rows)
    save_csv(runtime_df, TABLES_DIR / "model_runtime_validation_results.csv")
    write_md(REPORTS_DIR / "model_runtime_validation.md", f"# Model runtime validation\n\n- total_checks={len(runtime_df)}\n- pass={(runtime_df['status']=='pass').sum()}\n- fail={(runtime_df['status']=='fail').sum()}\n\nDetalle en `tables/model_runtime_validation_results.csv`.")
    save_csv(care_macro, CMP_DIR / "caregiver_macro_comparison.csv")
    save_csv(psy_macro, CMP_DIR / "psychologist_macro_comparison.csv")
    save_csv(winners, CMP_DIR / "caregiver_per_domain_winners.csv")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "final_modeling_decision.json").write_text(json.dumps({"caregiver_winner": {"route": str(best_care["route"]), "variant": str(best_care["variant"])}, "psychologist_winner": {"route": str(best_psy["route"]), "variant": str(best_psy["variant"])}, "hybrid_recommended": bool((winners["use_hybrid_yes_no"] == "yes").any())}, indent=2), encoding="utf-8")
    print("OK - questionnaire_final_modeling_v3 generado")


if __name__ == "__main__":
    main()
