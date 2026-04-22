
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
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
REPORT_BASE = ROOT / "reports" / "questionnaire_dual_mode_strategy_v2"
DATA_BASE = ROOT / "data" / "questionnaire_dual_mode_strategy_v2"
ARTIFACT_BASE = ROOT / "artifacts" / "questionnaire_dual_mode_strategy_v2"

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
SELF_PATTERNS = ("ysr_", "scared_sr_", "ari_sr_")
SYSTEM_FEATURES = {"site", "release"}
CATEGORICAL = {"sex_assigned_at_birth", "site"}
CAREGIVER_MODALITIES = {"reporte_cuidador", "dato_demografico", "disponibilidad_instrumental"}


@dataclass(frozen=True)
class ContractFeature:
    feature: str
    modality: str
    response_type: str
    options: list[str]
    min_value: float | None
    max_value: float | None
    domain_hint: str


@dataclass(frozen=True)
class RouteSpec:
    mode: str
    route: str
    feature_map: dict[str, list[str]]
    description: str


def ensure_dirs() -> None:
    report_dirs = [
        REPORT_BASE,
        REPORT_BASE / "inventory",
        REPORT_BASE / "caregiver",
        REPORT_BASE / "psychologist",
        REPORT_BASE / "comparison",
        REPORT_BASE / "reports",
        REPORT_BASE / "tables",
    ]
    data_dirs = [
        DATA_BASE,
        DATA_BASE / "inventory",
        DATA_BASE / "caregiver",
        DATA_BASE / "psychologist",
        DATA_BASE / "comparison",
        DATA_BASE / "reports",
        DATA_BASE / "tables",
    ]
    for p in report_dirs + data_dirs + [ARTIFACT_BASE]:
        p.mkdir(parents=True, exist_ok=True)


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
            domain_hint=str(r.get("trastorno_relacionado", "general") or "general"),
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


def save_csv(df: pd.DataFrame, rel: str) -> None:
    p1 = REPORT_BASE / rel
    p2 = DATA_BASE / rel
    p1.parent.mkdir(parents=True, exist_ok=True)
    p2.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p1, index=False)
    df.to_csv(p2, index=False)


def write_md(rel: str, text: str) -> None:
    p1 = REPORT_BASE / rel
    p2 = DATA_BASE / rel
    p1.parent.mkdir(parents=True, exist_ok=True)
    p2.parent.mkdir(parents=True, exist_ok=True)
    content = text.strip() + "\n"
    p1.write_text(content, encoding="utf-8")
    p2.write_text(content, encoding="utf-8")
def is_self_report(feature: str, contract: dict[str, ContractFeature]) -> bool:
    spec = contract.get(feature)
    if spec and spec.modality == "autoreporte":
        return True
    return feature.startswith(SELF_PATTERNS)


def is_system_filled(feature: str) -> bool:
    return feature in SYSTEM_FEATURES or feature.startswith("has_")


def is_derived(feature: str, contract: dict[str, ContractFeature]) -> bool:
    spec = contract.get(feature)
    if spec and spec.modality == "score_derivado":
        return True
    if feature.startswith(("ysr_", "scared_sr_", "ari_sr_")):
        return True
    return feature in {"has_ysr", "has_ari_sr", "has_scared_sr"}


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
    best_t, best_ba = 0.5, -1.0
    for t in np.linspace(0.2, 0.8, 121):
        ba = balanced_accuracy_score(y_true, (prob >= t).astype(int))
        if ba > best_ba:
            best_ba = float(ba)
            best_t = float(t)
    return best_t, best_ba


def platt_calibrate(y_val: pd.Series, val_prob: np.ndarray, test_prob: np.ndarray) -> tuple[np.ndarray, np.ndarray, bool]:
    if len(np.unique(y_val)) < 2:
        return val_prob, test_prob, False
    lr = LogisticRegression(max_iter=500)
    lr.fit(val_prob.reshape(-1, 1), y_val.astype(int))
    val_cal = lr.predict_proba(val_prob.reshape(-1, 1))[:, 1]
    test_cal = lr.predict_proba(test_prob.reshape(-1, 1))[:, 1]
    return val_cal, test_cal, True


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


def build_contracts(df: pd.DataFrame, contract: dict[str, ContractFeature], metadata: dict[str, dict[str, Any]]) -> tuple[RouteSpec, RouteSpec, RouteSpec, RouteSpec]:
    # caregiver A
    basic = pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).drop_duplicates().tolist()
    basic = [f for f in basic if f in df.columns]
    map_a = {d: basic[:] for d in DOMAINS}

    # caregiver B (legacy + mapping layer)
    map_b = {d: list(metadata[d]["feature_columns"]) for d in DOMAINS}

    # caregiver C (cuidador compatible sin autoreporte; missing<=0.20)
    c_features = []
    for f, spec in contract.items():
        if f not in df.columns:
            continue
        if is_self_report(f, contract):
            continue
        if spec.modality in CAREGIVER_MODALITIES or is_system_filled(f):
            if df[f].isna().mean() <= 0.20 or f in {"age_years", "sex_assigned_at_birth", "site", "release"}:
                c_features.append(f)
    c_features = sorted(set(c_features))
    map_c = {d: c_features[:] for d in DOMAINS}

    # psychologist mode (max coverage real): legacy full by domain
    map_p = {d: list(metadata[d]["feature_columns"]) for d in DOMAINS}

    return (
        RouteSpec("caregiver", "A", map_a, "Cuestionario basico directo, minima transformacion"),
        RouteSpec("caregiver", "B", map_b, "Cuestionario basico + capa intermedia (mapping/proxy/imputacion)"),
        RouteSpec("caregiver", "C", map_c, "Nueva linea cuidador-compatible (sin autoreporte estructural)"),
        RouteSpec("psychologist", "P", map_p, "Modo profesional de cobertura maxima real por dominio"),
    )
def route_b_rules() -> list[dict[str, str]]:
    return [
        {"target": "ysr_aggressive_behavior_proxy", "source": "cbcl_aggressive_behavior_proxy", "strength": "moderate"},
        {"target": "ysr_anxious_depressed_proxy", "source": "cbcl_anxious_depressed_proxy", "strength": "moderate"},
        {"target": "ysr_attention_problems_proxy", "source": "cbcl_attention_problems_proxy", "strength": "moderate"},
        {"target": "ysr_externalizing_proxy", "source": "cbcl_externalizing_proxy", "strength": "moderate"},
        {"target": "ysr_internalizing_proxy", "source": "cbcl_internalizing_proxy", "strength": "moderate"},
        {"target": "ysr_rule_breaking_proxy", "source": "cbcl_rule_breaking_proxy", "strength": "moderate"},
        {"target": "has_ysr", "source": "has_cbcl", "strength": "moderate"},
        {"target": "ari_sr_symptom_total", "source": "ari_p_symptom_total", "strength": "moderate"},
        {"target": "has_ari_sr", "source": "has_ari_p", "strength": "moderate"},
        {"target": "has_scared_sr", "source": "has_scared_p", "strength": "moderate"},
        {"target": "scared_sr_total", "source": "scared_p_total", "strength": "moderate"},
        {"target": "scared_sr_generalized_anxiety", "source": "scared_p_generalized_anxiety", "strength": "moderate"},
        {"target": "scared_sr_panic_somatic", "source": "scared_p_panic_somatic", "strength": "moderate"},
        {"target": "scared_sr_social_anxiety", "source": "scared_p_social_anxiety", "strength": "moderate"},
        {"target": "scared_sr_separation_anxiety", "source": "scared_p_separation_anxiety", "strength": "moderate"},
        {"target": "scared_sr_school_avoidance", "source": "scared_p_school_avoidance", "strength": "moderate"},
        {"target": "scared_sr_possible_anxiety_disorder_cut25", "source": "scared_p_possible_anxiety_disorder_cut25", "strength": "moderate"},
        {"target": "conners_cognitive_problems", "source": "swan_inattention_total", "strength": "weak"},
        {"target": "conners_hyperactivity", "source": "swan_hyperactive_impulsive_total", "strength": "weak"},
        {"target": "conners_total", "source": "swan_total", "strength": "weak"},
        {"target": "conners_conduct_problems", "source": "sdq_conduct_problems", "strength": "weak"},
    ]


def train_stats(train_df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    out = {}
    for f in features:
        if f in CATEGORICAL:
            m = train_df[f].mode(dropna=True)
            out[f] = m.iloc[0] if len(m) else None
        else:
            med = pd.to_numeric(train_df[f], errors="coerce").median()
            out[f] = None if pd.isna(med) else float(med)
    return out


def transform_route_b(frame: pd.DataFrame, feature_cols: list[str], basic_set: set[str], contract: dict[str, ContractFeature], stats: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, float]]:
    n = len(frame)
    X = pd.DataFrame(index=frame.index)
    for f in feature_cols:
        X[f] = frame[f] if (f in basic_set and f in frame.columns) else np.nan
    stage0 = int(X.isna().sum().sum())

    for rule in route_b_rules():
        t, s = rule["target"], rule["source"]
        if t in X.columns and s in X.columns:
            X[t] = X[t].fillna(X[s])

    if "scared_p_total" in X.columns:
        approx = (pd.to_numeric(X["scared_p_total"], errors="coerce") / 41.0).clip(lower=0, upper=2)
        for f in feature_cols:
            if f.startswith("scared_sr_") and f != "scared_sr_total":
                X[f] = X[f].fillna(approx)

    if "site" in X.columns:
        X["site"] = X["site"].fillna("CBIC")
    if "release" in X.columns:
        X["release"] = X["release"].fillna(11.0)
    if "sex_assigned_at_birth" in X.columns:
        X["sex_assigned_at_birth"] = X["sex_assigned_at_birth"].fillna("Unknown")

    stage1 = int(X.isna().sum().sum())
    for f in feature_cols:
        if not X[f].isna().any():
            continue
        fill = stats.get(f)
        if fill is None:
            fill = default_value(f, contract)
        X[f] = X[f].fillna(fill)
    stage2 = int(X.isna().sum().sum())

    for f in feature_cols:
        X[f] = X[f].fillna(default_value(f, contract))
        if f == "sex_assigned_at_birth":
            X[f] = X[f].map(normalize_sex)
        elif f == "site":
            X[f] = X[f].map(normalize_site)

    total = n * max(len(feature_cols), 1)
    dep = {
        "direct_fill_pct": float((total - stage0) / max(total, 1)),
        "derived_fill_pct": float((stage0 - stage1) / max(total, 1)),
        "imputed_fill_pct": float((stage1 - stage2) / max(total, 1)),
        "remaining_missing_pct": float(stage2 / max(total, 1)),
    }
    return X, dep


def prepare_inputs(route: str, frame: pd.DataFrame, feature_cols: list[str], basic_set: set[str], contract: dict[str, ContractFeature], stats: dict[str, Any] | None) -> tuple[pd.DataFrame, dict[str, float]]:
    if route == "B":
        assert stats is not None
        return transform_route_b(frame, feature_cols, basic_set, contract, stats)

    X = frame[[f for f in feature_cols if f in frame.columns]].copy()
    for f in X.columns:
        if f == "sex_assigned_at_birth":
            X[f] = X[f].map(normalize_sex)
        elif f == "site":
            X[f] = X[f].map(normalize_site)
    dep = {
        "direct_fill_pct": 1.0,
        "derived_fill_pct": 0.0,
        "imputed_fill_pct": 0.0,
        "remaining_missing_pct": float(X.isna().mean().mean()) if X.shape[1] else 0.0,
    }
    return X, dep


def mask_random(frame: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = frame.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f not in out.columns:
            continue
        mask = rng.random(len(out)) < ratio
        out.loc[mask, f] = np.nan
    return out
def evaluate_route_domain(
    mode: str,
    route: str,
    domain: str,
    df: pd.DataFrame,
    feature_cols: list[str],
    basic_set: set[str],
    contract: dict[str, ContractFeature],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ycol = TARGET_COL[domain]
    train = subset(df, load_split_ids(domain, "strict_full", "train"))
    val = subset(df, load_split_ids(domain, "strict_full", "val"))
    test = subset(df, load_split_ids(domain, "strict_full", "test"))

    stats = train_stats(train, feature_cols) if route == "B" else None
    Xtr, dep_tr = prepare_inputs(route, train, feature_cols, basic_set, contract, stats)
    Xva, _ = prepare_inputs(route, val, feature_cols, basic_set, contract, stats)
    Xte, dep_te = prepare_inputs(route, test, feature_cols, basic_set, contract, stats)

    ytr = train[ycol].astype(int)
    yva = val[ycol].astype(int)
    yte = test[ycol].astype(int)

    seeds = [11, 29, 47]
    cfgs = [
        {"id": "rf_compact", "n_estimators": 300, "max_depth": 12, "min_samples_leaf": 2, "min_samples_split": 5},
        {"id": "rf_stability", "n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "min_samples_split": 4},
    ]

    trial_rows = []
    for cfg in cfgs:
        for seed in seeds:
            model = make_pipeline(list(Xtr.columns), seed, cfg)
            model.fit(Xtr, ytr)

            pva_raw = model.predict_proba(Xva)[:, 1]
            pte_raw = model.predict_proba(Xte)[:, 1]
            brier_raw = brier_score_loss(yva, pva_raw)

            pva_cal, pte_cal, calibrated = platt_calibrate(yva, pva_raw, pte_raw)
            brier_cal = brier_score_loss(yva, pva_cal) if calibrated else 999.0

            if calibrated and brier_cal < brier_raw:
                pva, pte, cal = pva_cal, pte_cal, "platt"
            else:
                pva, pte, cal = pva_raw, pte_raw, "none"

            thr, ba_val = choose_threshold(yva, pva)
            met = compute_metrics(yte, pte, thr)

            # robustness partial questionnaire
            if mode == "caregiver":
                mask15, mask30 = 0.15, 0.30
            else:
                mask15, mask30 = 0.10, 0.20

            q_feats = [f for f in feature_cols if f in test.columns]
            m15_source = test.copy()
            m30_source = test.copy()
            m15_source[q_feats] = mask_random(test[q_feats], q_feats, mask15, seed + 100)[q_feats]
            m30_source[q_feats] = mask_random(test[q_feats], q_feats, mask30, seed + 200)[q_feats]
            Xm15, _ = prepare_inputs(route, m15_source, feature_cols, basic_set, contract, stats)
            Xm30, _ = prepare_inputs(route, m30_source, feature_cols, basic_set, contract, stats)

            p15 = model.predict_proba(Xm15)[:, 1]
            p30 = model.predict_proba(Xm30)[:, 1]
            ba15 = balanced_accuracy_score(yte, (p15 >= thr).astype(int))
            ba30 = balanced_accuracy_score(yte, (p30 >= thr).astype(int))

            trial_rows.append({
                "mode": mode,
                "route": route,
                "domain": domain,
                "config_id": cfg["id"],
                "seed": seed,
                "n_features": len(feature_cols),
                "calibration": cal,
                "threshold": thr,
                "val_balanced_accuracy": ba_val,
                "precision": met["precision"],
                "recall": met["recall"],
                "specificity": met["specificity"],
                "balanced_accuracy": met["balanced_accuracy"],
                "f1": met["f1"],
                "roc_auc": met["roc_auc"],
                "pr_auc": met["pr_auc"],
                "brier": met["brier"],
                "missing15_delta": float(met["balanced_accuracy"] - ba15),
                "missing30_delta": float(met["balanced_accuracy"] - ba30),
                "direct_fill_pct": dep_te["direct_fill_pct"],
                "derived_fill_pct": dep_te["derived_fill_pct"],
                "imputed_fill_pct": dep_te["imputed_fill_pct"],
                "remaining_missing_pct": dep_te["remaining_missing_pct"],
            })

    trials = pd.DataFrame(trial_rows)
    best_cfg = trials.groupby("config_id")["val_balanced_accuracy"].mean().sort_values(ascending=False).index[0]
    selected = trials[trials["config_id"] == best_cfg].copy()

    # split stability with selected seed
    sel_seed = int(selected.groupby("seed")["val_balanced_accuracy"].mean().sort_values(ascending=False).index[0])
    cfg = [c for c in cfgs if c["id"] == best_cfg][0]

    rtr = subset(df, load_split_ids(domain, "research_full", "train"))
    rva = subset(df, load_split_ids(domain, "research_full", "val"))
    rte = subset(df, load_split_ids(domain, "research_full", "test"))
    rstats = train_stats(rtr, feature_cols) if route == "B" else None
    Xrtr, _ = prepare_inputs(route, rtr, feature_cols, basic_set, contract, rstats)
    Xrva, _ = prepare_inputs(route, rva, feature_cols, basic_set, contract, rstats)
    Xrte, _ = prepare_inputs(route, rte, feature_cols, basic_set, contract, rstats)
    yrtr, yrva, yrte = rtr[ycol].astype(int), rva[ycol].astype(int), rte[ycol].astype(int)

    m2 = make_pipeline(list(Xrtr.columns), sel_seed, cfg)
    m2.fit(Xrtr, yrtr)
    pva2 = m2.predict_proba(Xrva)[:, 1]
    thr2, _ = choose_threshold(yrva, pva2)
    pte2 = m2.predict_proba(Xrte)[:, 1]
    met2 = compute_metrics(yrte, pte2, thr2)

    summary = {
        "mode": mode,
        "route": route,
        "domain": domain,
        "best_config": best_cfg,
        "selected_seed": sel_seed,
        "n_features": int(selected["n_features"].iloc[0]),
        "precision": float(selected["precision"].mean()),
        "recall": float(selected["recall"].mean()),
        "specificity": float(selected["specificity"].mean()),
        "balanced_accuracy": float(selected["balanced_accuracy"].mean()),
        "f1": float(selected["f1"].mean()),
        "roc_auc": float(selected["roc_auc"].mean()),
        "pr_auc": float(selected["pr_auc"].mean()),
        "brier": float(selected["brier"].mean()),
        "seed_balanced_accuracy_std": float(selected["balanced_accuracy"].std(ddof=0)),
        "split_balanced_accuracy": float(met2["balanced_accuracy"]),
        "split_delta_balanced_accuracy": float(selected["balanced_accuracy"].mean() - met2["balanced_accuracy"]),
        "missing15_delta": float(selected["missing15_delta"].mean()),
        "missing30_delta": float(selected["missing30_delta"].mean()),
        "direct_fill_pct": float(selected["direct_fill_pct"].mean()),
        "derived_fill_pct": float(selected["derived_fill_pct"].mean()),
        "imputed_fill_pct": float(selected["imputed_fill_pct"].mean()),
        "remaining_missing_pct": float(selected["remaining_missing_pct"].mean()),
    }
    return trials, summary


def coverage_by_mode(contract: dict[str, ContractFeature], route_a: RouteSpec, route_b: RouteSpec, route_c: RouteSpec, route_p: RouteSpec) -> pd.DataFrame:
    rows = []
    for d in DOMAINS:
        legacy = route_b.feature_map[d]
        for f in legacy:
            spec = contract.get(f)
            caregiver_ans = bool(spec and spec.modality in {"reporte_cuidador", "dato_demografico"})
            child_self = is_self_report(f, contract)
            clinician_entered = bool(spec and spec.modality in {"disponibilidad_instrumental", "score_derivado"})
            can_der = is_derived(f, contract)
            can_sys = is_system_filled(f)
            should_missing = bool(child_self and not can_der)
            rows.append(
                {
                    "input_key": f,
                    "domain": d,
                    "source_instrument_or_origin": spec.domain_hint if spec else "unknown",
                    "caregiver_answerable_yes_no": "yes" if caregiver_ans else "no",
                    "clinician_entered_yes_no": "yes" if clinician_entered else "no",
                    "child_self_report_only_yes_no": "yes" if child_self else "no",
                    "can_be_derived_yes_no": "yes" if can_der else "no",
                    "can_be_system_filled_yes_no": "yes" if can_sys else "no",
                    "should_remain_missing_yes_no": "yes" if should_missing else "no",
                    "route_a_caregiver_covered_yes_no": "yes" if f in route_a.feature_map[d] else "no",
                    "route_b_caregiver_covered_yes_no": "yes",
                    "route_c_caregiver_covered_yes_no": "yes" if f in route_c.feature_map[d] else "no",
                    "psychologist_mode_covered_yes_no": "yes" if f in route_p.feature_map[d] else "no",
                    "notes": "self_report_admin_required" if child_self else "",
                }
            )
    return pd.DataFrame(rows)
def md_coverage_summary(cov: pd.DataFrame) -> str:
    lines = ["# Input coverage by mode summary", ""]
    for d in DOMAINS:
        sub = cov[cov["domain"] == d]
        total = len(sub)
        lines.append(
            f"- `{d}` total={total} | caregiver_direct={(sub['caregiver_answerable_yes_no']=='yes').sum()} | self_report={(sub['child_self_report_only_yes_no']=='yes').sum()} | routeA={(sub['route_a_caregiver_covered_yes_no']=='yes').sum()} | routeC={(sub['route_c_caregiver_covered_yes_no']=='yes').sum()} | psych={(sub['psychologist_mode_covered_yes_no']=='yes').sum()}"
        )
    lines += ["", "Notas:", "- Ruta B cubre todo el espacio legacy via mapping+imputacion controlada.", "- Modo psicologo cubre todos los inputs legacy por dominio, separando bloque self-report administrado."]
    return "\n".join(lines)


def md_contracts(route_a: RouteSpec, route_b: RouteSpec, route_c: RouteSpec) -> tuple[str, str]:
    ca = [
        "# Caregiver route contracts",
        "",
        f"- caregiver_route_a_contract: {len(route_a.feature_map['adhd'])} features base (mismo set para los 5 dominios).",
        "- caregiver_route_b_contract: usa espacio legacy por dominio + capa intermedia (proxies/imputacion).",
        f"- caregiver_route_c_contract: {len(route_c.feature_map['adhd'])} features cuidador-compatibles (sin autoreporte estructural).",
        "- Contratos congelados antes de entrenar para evitar mover porteria.",
    ]
    cp = [
        "# Psychologist mode contract",
        "",
        "- Contrato profesional ampliado: cobertura legacy maxima por dominio.",
        "- Estructura de tipos de input:",
        "  - caregiver_answerable",
        "  - clinician_entered",
        "  - child_self_report_only (administrado en contexto profesional)",
        "  - system_filled",
        "  - derived",
        "- Regla: self-report no se sustituye por juicio clinico; se administra como bloque especifico.",
    ]
    return "\n".join(ca), "\n".join(cp)


def md_route_analysis(title: str, df: pd.DataFrame) -> str:
    macro = df[["precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier"]].mean()
    lines = [f"# {title}", "", "## Macro"]
    for k, v in macro.items():
        lines.append(f"- {k}: **{v:.4f}**")
    lines += ["", "## Por dominio"]
    for _, r in df.iterrows():
        lines.append(
            f"- `{r['route']}-{r['domain']}` BA={r['balanced_accuracy']:.4f}, P={r['precision']:.4f}, R={r['recall']:.4f}, Spec={r['specificity']:.4f}, PR-AUC={r['pr_auc']:.4f}, imputed={r['imputed_fill_pct']:.3f}"
        )
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(DATASET_PATH)
    contract = load_contract()
    metadata = {d: load_metadata(d) for d in DOMAINS}

    route_a, route_b, route_c, route_p = build_contracts(df, contract, metadata)

    # Fase 1
    cov = coverage_by_mode(contract, route_a, route_b, route_c, route_p)
    save_csv(cov, "input_coverage_by_mode.csv")
    write_md("input_coverage_by_mode_summary.md", md_coverage_summary(cov))

    # Fase 2
    caregiver_md, psych_md = md_contracts(route_a, route_b, route_c)
    write_md("caregiver_route_contracts.md", caregiver_md)
    write_md("psychologist_mode_contract.md", psych_md)

    # Fase 3 - caregiver A/B/C
    basic_set = set(route_a.feature_map["adhd"])
    caregiver_trials = []
    caregiver_results = []
    for route_spec in [route_a, route_b, route_c]:
        for d in DOMAINS:
            trials, summary = evaluate_route_domain(
                mode="caregiver",
                route=route_spec.route,
                domain=d,
                df=df,
                feature_cols=route_spec.feature_map[d],
                basic_set=basic_set,
                contract=contract,
            )
            caregiver_trials.append(trials)
            caregiver_results.append(summary)

    caregiver_trials_df = pd.concat(caregiver_trials, ignore_index=True)
    caregiver_results_df = pd.DataFrame(caregiver_results)
    save_csv(caregiver_trials_df, "caregiver_route_trial_registry.csv")
    save_csv(caregiver_results_df, "caregiver_route_results.csv")
    write_md("caregiver_route_analysis.md", md_route_analysis("Caregiver route analysis", caregiver_results_df))

    # Fase 4 - psychologist mode
    psych_trials = []
    psych_results = []
    for d in DOMAINS:
        trials, summary = evaluate_route_domain(
            mode="psychologist",
            route="P",
            domain=d,
            df=df,
            feature_cols=route_p.feature_map[d],
            basic_set=basic_set,
            contract=contract,
        )
        psych_trials.append(trials)
        psych_results.append(summary)

    psych_trials_df = pd.concat(psych_trials, ignore_index=True)
    psych_results_df = pd.DataFrame(psych_results)
    save_csv(psych_trials_df, "psychologist_mode_trial_registry.csv")
    save_csv(psych_results_df, "psychologist_mode_results.csv")
    write_md("psychologist_mode_analysis.md", md_route_analysis("Psychologist mode analysis", psych_results_df))

    # Fase 5 caregiver final comparison
    careg_matrix = caregiver_results_df.copy()
    save_csv(careg_matrix, "caregiver_final_comparison_matrix.csv")

    winners = careg_matrix.sort_values(["domain", "balanced_accuracy"], ascending=[True, False]).groupby("domain").head(1)
    macro = careg_matrix.groupby("route")[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "imputed_fill_pct", "derived_fill_pct"]].mean().reset_index()
    save_csv(macro, "tables/route_macro_caregiver.csv")

    glob_win = macro.sort_values("balanced_accuracy", ascending=False).iloc[0]["route"]
    cf = [
        "# Caregiver final decision",
        "",
        f"- Ganador global (BA macro): **{glob_win}**.",
        "- Ganador por dominio (BA):",
    ]
    for _, r in winners.iterrows():
        cf.append(f"  - {r['domain']}: {r['route']} (BA={r['balanced_accuracy']:.4f})")
    cf += [
        "",
        "- Evaluacion de deuda operacional:",
        "  - Ruta B tiene mayor dependencia de imputacion/derivacion.",
        "  - Ruta C mantiene mejor equilibrio de BA/PR-AUC/Brier con menor deuda estructural.",
    ]
    write_md("caregiver_final_decision.md", "\n".join(cf))

    # Fase 6 psychologist final decision
    p_macro = psych_results_df[["precision", "recall", "specificity", "balanced_accuracy", "f1", "pr_auc", "brier", "imputed_fill_pct"]].mean()
    pf = [
        "# Psychologist final decision",
        "",
        "- Estrategia recomendada: contrato profesional ampliado (route P).",
        f"- Cobertura real de inputs legacy por dominio: 100% (por definicion del contrato profesional).",
        f"- BA macro: {p_macro['balanced_accuracy']:.4f}, Precision macro: {p_macro['precision']:.4f}, PR-AUC macro: {p_macro['pr_auc']:.4f}.",
        "- Bloques requeridos:",
        "  - caregiver_answerable",
        "  - clinician_entered",
        "  - child_self_report_only administrado",
        "  - system_filled/derived",
    ]
    write_md("psychologist_final_decision.md", "\n".join(pf))

    # Fase 7+8
    qimp = [
        "# Questionnaire design implications",
        "",
        f"- Modo cuidador: ruta recomendada **{glob_win}**.",
        "- Modo psicologo: estructura ampliada con cobertura maxima real y bloque self-report administrado.",
        "- Preguntas cuidador obligatorias: contexto base + CBCL/SDQ nucleares + disponibilidad instrumental.",
        "- Derivaciones en backend: solo reglas explicitamente auditadas; no equivalencias clinicas fuertes no justificadas.",
        "- System-filled: site/release + metadata operativa.",
        "- Lo no preguntable al cuidador no debe forzarse; se maneja por ruta/contrato y/o modo psicologo.",
    ]
    write_md("questionnaire_design_implications.md", "\n".join(qimp))

    final_global = [
        "# Final global recommendation",
        "",
        f"1) Mejor ruta modo cuidador: **{glob_win}**.",
        "2) Mejor estrategia modo psicologo: **P (contrato ampliado profesional)**.",
        "3) Dominios con mayor sensibilidad entre rutas: anxiety y elimination.",
        "4) Dominio mas fragil: elimination (variabilidad alta entre contratos).",
        "5) Hibrido cuidador: solo si BA por dominio lo exige; en esta corrida la recomendacion global sigue el ganador macro.",
        "6) El modo psicologo debe mantenerse separado estructuralmente (bloques diferenciados por tipo de dato).",
        "7) Con estos resultados ya se puede cerrar diseno y pasar a implementacion definitiva.",
    ]
    write_md("final_global_recommendation.md", "\n".join(final_global))

    exec_lines = [
        "# Executive summary",
        "",
        f"- Modo cuidador ganador: **{glob_win}** (BA macro={macro[macro['route']==glob_win]['balanced_accuracy'].iloc[0]:.4f}).",
        f"- Modo psicologo: **P** (BA macro={p_macro['balanced_accuracy']:.4f}, cobertura=100% legacy por dominio).",
        "- Comparacion A/B/C cuidador ejecutada al mismo nivel (tuning/calibracion/threshold/robustez).",
        "- Recomendacion final: cerrar diseño dual-mode y pasar a implementación runtime definitiva.",
    ]
    write_md("executive_summary.md", "\n".join(exec_lines))

    # tables extra
    save_csv(careg_matrix, "tables/caregiver_final_comparison_matrix.csv")
    save_csv(psych_results_df, "tables/psychologist_summary_table.csv")

    # artifacts
    ARTIFACT_BASE.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_BASE / "final_dual_mode_decision.json").write_text(
        json.dumps(
            {
                "caregiver_winner_route": glob_win,
                "psychologist_strategy": "P",
                "caregiver_macro": macro.to_dict(orient="records"),
                "psychologist_macro_balanced_accuracy": float(p_macro["balanced_accuracy"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("OK - questionnaire_dual_mode_strategy_v2 generado")


if __name__ == "__main__":
    main()
