
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
BASE_DIR = ROOT / "data" / "questionnaire_strategy_retraining_v2"
INV_DIR = BASE_DIR / "inventory"
ROUTE_A_DIR = BASE_DIR / "route_a"
ROUTE_B_DIR = BASE_DIR / "route_b"
ROUTE_C_DIR = BASE_DIR / "route_c"
TABLES_DIR = BASE_DIR / "tables"
REPORTS_DIR = BASE_DIR / "reports"
CMP_DIR = BASE_DIR / "comparison"
ARTIFACTS_DIR = ROOT / "artifacts" / "questionnaire_strategy_retraining_v2"

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
SYSTEM_FEATURES = {"site", "release"}
CATEGORICAL = {"sex_assigned_at_birth", "site"}
SELF_PATTERNS = ("ysr_", "scared_sr_", "ari_sr_")
CAREGIVER_MODALITIES = {"reporte_cuidador", "dato_demografico", "disponibilidad_instrumental", "score_derivado"}


@dataclass(frozen=True)
class ContractFeature:
    feature: str
    modality: str
    response_type: str
    options: list[str]
    min_value: float | None
    max_value: float | None
    domain_hint: str


def ensure_dirs() -> None:
    for p in [BASE_DIR, INV_DIR, ROUTE_A_DIR, ROUTE_B_DIR, ROUTE_C_DIR, TABLES_DIR, REPORTS_DIR, CMP_DIR, ARTIFACTS_DIR]:
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
def make_base_pipeline(feature_cols: list[str], seed: int, cfg: dict[str, Any]) -> Pipeline:
    cats = [c for c in feature_cols if c in CATEGORICAL]
    nums = [c for c in feature_cols if c not in CATEGORICAL]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), nums),
            (
                "cat",
                Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]),
                cats,
            ),
        ],
        remainder="drop",
    )
    rf = RandomForestClassifier(
        n_estimators=cfg["n_estimators"],
        max_depth=cfg["max_depth"],
        min_samples_leaf=cfg["min_samples_leaf"],
        min_samples_split=cfg["min_samples_split"],
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=seed,
    )
    return Pipeline([("pre", pre), ("rf", rf)])


def route_contracts(df: pd.DataFrame, contract: dict[str, ContractFeature], metadata: dict[str, dict[str, Any]]) -> tuple[list[str], list[str], dict[str, list[str]]]:
    basic = pd.read_csv(BASIC_Q_PATH)["feature_key"].dropna().astype(str).drop_duplicates().tolist()
    basic = [f for f in basic if f in df.columns]

    non_self = []
    for f, spec in contract.items():
        if f in df.columns and spec.modality in CAREGIVER_MODALITIES:
            non_self.append(f)
    # limitar faltantes estructurales para ruta C y mantener sostenibilidad
    c_features = [f for f in sorted(set(non_self)) if df[f].isna().mean() <= 0.20 or f in {"age_years", "sex_assigned_at_birth", "site", "release"}]

    legacy_domain = {d: list(metadata[d]["feature_columns"]) for d in DOMAINS}
    return basic, c_features, legacy_domain


def route_b_mapping_rules() -> list[dict[str, str]]:
    rules = [
        {"target": "ysr_aggressive_behavior_proxy", "source": "cbcl_aggressive_behavior_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "ysr_anxious_depressed_proxy", "source": "cbcl_anxious_depressed_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "ysr_attention_problems_proxy", "source": "cbcl_attention_problems_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "ysr_externalizing_proxy", "source": "cbcl_externalizing_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "ysr_internalizing_proxy", "source": "cbcl_internalizing_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "ysr_rule_breaking_proxy", "source": "cbcl_rule_breaking_proxy", "type": "proxy_copy", "strength": "moderate"},
        {"target": "has_ysr", "source": "has_cbcl", "type": "availability_proxy", "strength": "moderate"},
        {"target": "ari_sr_symptom_total", "source": "ari_p_symptom_total", "type": "proxy_copy", "strength": "moderate"},
        {"target": "has_ari_sr", "source": "has_ari_p", "type": "availability_proxy", "strength": "moderate"},
        {"target": "has_scared_sr", "source": "has_scared_p", "type": "availability_proxy", "strength": "moderate"},
        {"target": "scared_sr_total", "source": "scared_p_total", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_generalized_anxiety", "source": "scared_p_generalized_anxiety", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_panic_somatic", "source": "scared_p_panic_somatic", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_social_anxiety", "source": "scared_p_social_anxiety", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_separation_anxiety", "source": "scared_p_separation_anxiety", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_school_avoidance", "source": "scared_p_school_avoidance", "type": "proxy_copy", "strength": "moderate"},
        {"target": "scared_sr_possible_anxiety_disorder_cut25", "source": "scared_p_possible_anxiety_disorder_cut25", "type": "proxy_copy", "strength": "moderate"},
        {"target": "conners_cognitive_problems", "source": "swan_inattention_total", "type": "weak_projection", "strength": "weak"},
        {"target": "conners_hyperactivity", "source": "swan_hyperactive_impulsive_total", "type": "weak_projection", "strength": "weak"},
        {"target": "conners_total", "source": "swan_total", "type": "weak_projection", "strength": "weak"},
        {"target": "conners_conduct_problems", "source": "sdq_conduct_problems", "type": "weak_projection", "strength": "weak"},
    ]
    return rules


def transform_route_b(
    source_df: pd.DataFrame,
    feature_cols: list[str],
    basic_features: set[str],
    contract: dict[str, ContractFeature],
    train_stats: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, float]]:
    n = len(source_df)
    X = pd.DataFrame(index=source_df.index)
    for f in feature_cols:
        X[f] = source_df[f] if (f in basic_features and f in source_df.columns) else np.nan

    stage0_na = int(X.isna().sum().sum())
    for rule in route_b_mapping_rules():
        t, s = rule["target"], rule["source"]
        if t not in X.columns or s not in X.columns:
            continue
        X[t] = X[t].fillna(X[s])

    if "scared_p_total" in X.columns:
        avg = (pd.to_numeric(X["scared_p_total"], errors="coerce") / 41.0).clip(lower=0, upper=2)
        for f in feature_cols:
            if f.startswith("scared_sr_") and f != "scared_sr_total":
                X[f] = X[f].fillna(avg)

    if "site" in X.columns:
        X["site"] = X["site"].fillna("CBIC")
    if "release" in X.columns:
        X["release"] = X["release"].fillna(11.0)
    if "sex_assigned_at_birth" in X.columns:
        X["sex_assigned_at_birth"] = X["sex_assigned_at_birth"].fillna("Unknown")

    stage1_na = int(X.isna().sum().sum())
    for f in feature_cols:
        if not X[f].isna().any():
            continue
        stat = train_stats.get(f)
        if stat is None:
            stat = default_value(f, contract)
        X[f] = X[f].fillna(stat)
    stage2_na = int(X.isna().sum().sum())

    for f in feature_cols:
        X[f] = X[f].fillna(default_value(f, contract))
        if f == "sex_assigned_at_birth":
            X[f] = X[f].map(normalize_sex)
        if f == "site":
            X[f] = X[f].map(normalize_site)

    total = n * max(len(feature_cols), 1)
    return X, {
        "direct_fill_pct": float((total - stage0_na) / max(total, 1)),
        "derived_fill_pct": float((stage0_na - stage1_na) / max(total, 1)),
        "imputed_fill_pct": float((stage1_na - stage2_na) / max(total, 1)),
        "remaining_missing_pct": float(stage2_na / max(total, 1)),
    }


def coverage_table(
    basic_features: list[str],
    c_features: list[str],
    legacy_domain: dict[str, list[str]],
    contract: dict[str, ContractFeature],
) -> pd.DataFrame:
    basic_set = set(basic_features)
    c_set = set(c_features)
    map_targets = {r["target"] for r in route_b_mapping_rules()}
    rows = []
    for domain in DOMAINS:
        legacy = legacy_domain[domain]
        total = len(legacy)

        # Ruta A
        direct_a = sum(1 for f in legacy if f in basic_set)
        system_a = sum(1 for f in legacy if f in SYSTEM_FEATURES)
        missing_a = total - direct_a
        rows.append({"route": "A", "domain": domain, "total_inputs": total, "direct_inputs": direct_a, "derived_inputs": 0, "system_filled_inputs": system_a, "imputed_inputs": 0, "missing_structural_inputs": missing_a, "fallback_dependency_pct": missing_a / max(total, 1), "methodological_risk": "high" if missing_a / max(total, 1) > 0.4 else "medium"})

        # Ruta B
        direct_b = sum(1 for f in legacy if f in basic_set)
        derived_b = sum(1 for f in legacy if f in map_targets and f not in basic_set)
        system_b = sum(1 for f in legacy if f in SYSTEM_FEATURES)
        imputed_b = total - direct_b - derived_b
        rows.append({"route": "B", "domain": domain, "total_inputs": total, "direct_inputs": direct_b, "derived_inputs": derived_b, "system_filled_inputs": system_b, "imputed_inputs": imputed_b, "missing_structural_inputs": 0, "fallback_dependency_pct": imputed_b / max(total, 1), "methodological_risk": "medium" if imputed_b / max(total, 1) < 0.5 else "high"})

        # Ruta C
        direct_c = sum(1 for f in legacy if f in c_set)
        derived_c = sum(1 for f in legacy if f in c_set and contract.get(f) and contract[f].modality == "score_derivado")
        system_c = sum(1 for f in legacy if f in SYSTEM_FEATURES)
        missing_c = total - direct_c
        rows.append({"route": "C", "domain": domain, "total_inputs": total, "direct_inputs": direct_c, "derived_inputs": derived_c, "system_filled_inputs": system_c, "imputed_inputs": 0, "missing_structural_inputs": missing_c, "fallback_dependency_pct": missing_c / max(total, 1), "methodological_risk": "low" if missing_c / max(total, 1) < 0.25 else "medium"})

    return pd.DataFrame(rows)
def mask_features(df: pd.DataFrame, features: list[str], ratio: float, seed: int) -> pd.DataFrame:
    out = df.copy()
    rng = np.random.default_rng(seed)
    for f in features:
        if f not in out.columns:
            continue
        m = rng.random(len(out)) < ratio
        out.loc[m, f] = np.nan
    return out


def train_stats_for_features(train_df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    stats = {}
    for f in feature_cols:
        if f in CATEGORICAL:
            mode = train_df[f].mode(dropna=True)
            stats[f] = mode.iloc[0] if len(mode) else None
        else:
            med = pd.to_numeric(train_df[f], errors="coerce").median()
            stats[f] = None if pd.isna(med) else float(med)
    return stats


def prepare_route_data(
    route: str,
    domain: str,
    split_df: pd.DataFrame,
    feature_spec: list[str],
    basic_features: set[str],
    contract: dict[str, ContractFeature],
    train_stats: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if route == "A":
        feats = [f for f in feature_spec if f in split_df.columns]
        X = split_df[feats].copy()
        for f in feats:
            if f == "sex_assigned_at_birth":
                X[f] = X[f].map(normalize_sex)
            elif f == "site":
                X[f] = X[f].map(normalize_site)
        return X, {"direct_fill_pct": 1.0, "derived_fill_pct": 0.0, "imputed_fill_pct": 0.0, "remaining_missing_pct": float(X.isna().mean().mean())}

    if route == "B":
        assert train_stats is not None
        return transform_route_b(split_df, feature_spec, basic_features, contract, train_stats)

    # route C
    feats = [f for f in feature_spec if f in split_df.columns]
    X = split_df[feats].copy()
    for f in feats:
        if f == "sex_assigned_at_birth":
            X[f] = X[f].map(normalize_sex)
        elif f == "site":
            X[f] = X[f].map(normalize_site)
    return X, {"direct_fill_pct": 1.0, "derived_fill_pct": 0.0, "imputed_fill_pct": 0.0, "remaining_missing_pct": float(X.isna().mean().mean())}


def evaluate_route_domain(
    route: str,
    domain: str,
    df: pd.DataFrame,
    feature_spec: list[str],
    basic_features: set[str],
    contract: dict[str, ContractFeature],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    y_col = TARGET_COL[domain]
    train_df = subset(df, load_split_ids(domain, "strict_full", "train"))
    val_df = subset(df, load_split_ids(domain, "strict_full", "val"))
    test_df = subset(df, load_split_ids(domain, "strict_full", "test"))

    train_stats = train_stats_for_features(train_df, feature_spec) if route == "B" else None
    X_train, dep_train = prepare_route_data(route, domain, train_df, feature_spec, basic_features, contract, train_stats)
    X_val, _ = prepare_route_data(route, domain, val_df, feature_spec, basic_features, contract, train_stats)
    X_test, dep_test = prepare_route_data(route, domain, test_df, feature_spec, basic_features, contract, train_stats)

    y_train = train_df[y_col].astype(int)
    y_val = val_df[y_col].astype(int)
    y_test = test_df[y_col].astype(int)

    seeds = [11, 29, 47]
    cfgs = [
        {"config_id": "rf_compact", "n_estimators": 300, "max_depth": 12, "min_samples_leaf": 2, "min_samples_split": 5},
        {"config_id": "rf_stability", "n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "min_samples_split": 4},
    ]

    trial_rows = []
    for cfg in cfgs:
        for seed in seeds:
            pipe = make_base_pipeline(list(X_train.columns), seed, cfg)
            pipe.fit(X_train, y_train)

            val_prob_raw = pipe.predict_proba(X_val)[:, 1]
            test_prob_raw = pipe.predict_proba(X_test)[:, 1]
            val_brier_raw = brier_score_loss(y_val, val_prob_raw)

            val_prob_cal, test_prob_cal, calibrated = platt_calibrate(y_val, val_prob_raw, test_prob_raw)
            val_brier_cal = brier_score_loss(y_val, val_prob_cal) if calibrated else 999.0

            if calibrated and val_brier_cal < val_brier_raw:
                val_prob = val_prob_cal
                test_prob = test_prob_cal
                cal_strategy = "platt_val_fitted"
            else:
                val_prob = val_prob_raw
                test_prob = test_prob_raw
                cal_strategy = "none"

            threshold, val_ba = choose_threshold(y_val, val_prob)
            test_metrics = compute_metrics(y_test, test_prob, threshold)

            # Robustez missingness parcial
            mild_ratio, mod_ratio = 0.15, 0.30
            if route == "A":
                q_features = [f for f in feature_spec if f in test_df.columns]
                mild_source = mask_features(test_df[q_features], q_features, mild_ratio, seed + 100)
                mod_source = mask_features(test_df[q_features], q_features, mod_ratio, seed + 200)
                X_mild = mild_source.copy()
                X_mod = mod_source.copy()
            elif route == "B":
                q_features = [f for f in basic_features if f in test_df.columns]
                mild_raw = test_df.copy()
                mod_raw = test_df.copy()
                mild_raw[q_features] = mask_features(test_df[q_features], q_features, mild_ratio, seed + 100)[q_features]
                mod_raw[q_features] = mask_features(test_df[q_features], q_features, mod_ratio, seed + 200)[q_features]
                X_mild, _ = prepare_route_data("B", domain, mild_raw, feature_spec, basic_features, contract, train_stats)
                X_mod, _ = prepare_route_data("B", domain, mod_raw, feature_spec, basic_features, contract, train_stats)
            else:
                q_features = [f for f in feature_spec if f in test_df.columns]
                mild_source = test_df.copy()
                mod_source = test_df.copy()
                mild_source[q_features] = mask_features(test_df[q_features], q_features, mild_ratio, seed + 100)[q_features]
                mod_source[q_features] = mask_features(test_df[q_features], q_features, mod_ratio, seed + 200)[q_features]
                X_mild, _ = prepare_route_data("C", domain, mild_source, feature_spec, basic_features, contract, train_stats)
                X_mod, _ = prepare_route_data("C", domain, mod_source, feature_spec, basic_features, contract, train_stats)

            prob_mild = pipe.predict_proba(X_mild)[:, 1]
            prob_mod = pipe.predict_proba(X_mod)[:, 1]
            ba_mild = balanced_accuracy_score(y_test, (prob_mild >= threshold).astype(int))
            ba_mod = balanced_accuracy_score(y_test, (prob_mod >= threshold).astype(int))

            trial_rows.append(
                {
                    "route": route,
                    "domain": domain,
                    "config_id": cfg["config_id"],
                    "seed": seed,
                    "n_features": len(X_train.columns),
                    "calibration_strategy": cal_strategy,
                    "threshold": threshold,
                    "val_balanced_accuracy": val_ba,
                    "test_balanced_accuracy": test_metrics["balanced_accuracy"],
                    "test_precision": test_metrics["precision"],
                    "test_recall": test_metrics["recall"],
                    "test_specificity": test_metrics["specificity"],
                    "test_f1": test_metrics["f1"],
                    "test_roc_auc": test_metrics["roc_auc"],
                    "test_pr_auc": test_metrics["pr_auc"],
                    "test_brier": test_metrics["brier"],
                    "robustness_missing15_ba": ba_mild,
                    "robustness_missing30_ba": ba_mod,
                    "robustness_missing15_delta": float(test_metrics["balanced_accuracy"] - ba_mild),
                    "robustness_missing30_delta": float(test_metrics["balanced_accuracy"] - ba_mod),
                    "direct_fill_pct": dep_test["direct_fill_pct"],
                    "derived_fill_pct": dep_test["derived_fill_pct"],
                    "imputed_fill_pct": dep_test["imputed_fill_pct"],
                    "remaining_missing_pct": dep_test["remaining_missing_pct"],
                }
            )

    trials = pd.DataFrame(trial_rows)
    cfg_rank = trials.groupby("config_id")["val_balanced_accuracy"].mean().sort_values(ascending=False)
    best_cfg = cfg_rank.index[0]
    best_trials = trials[trials["config_id"] == best_cfg].copy()

    # split stability (strict vs research) con mejor seed promedio
    seed_rank = best_trials.groupby("seed")["val_balanced_accuracy"].mean().sort_values(ascending=False)
    best_seed = int(seed_rank.index[0])
    cfg = [c for c in cfgs if c["config_id"] == best_cfg][0]

    research_train = subset(df, load_split_ids(domain, "research_full", "train"))
    research_val = subset(df, load_split_ids(domain, "research_full", "val"))
    research_test = subset(df, load_split_ids(domain, "research_full", "test"))
    research_stats = train_stats_for_features(research_train, feature_spec) if route == "B" else None
    Xr_train, _ = prepare_route_data(route, domain, research_train, feature_spec, basic_features, contract, research_stats)
    Xr_val, _ = prepare_route_data(route, domain, research_val, feature_spec, basic_features, contract, research_stats)
    Xr_test, _ = prepare_route_data(route, domain, research_test, feature_spec, basic_features, contract, research_stats)

    yr_train = research_train[y_col].astype(int)
    yr_val = research_val[y_col].astype(int)
    yr_test = research_test[y_col].astype(int)

    pipe_r = make_base_pipeline(list(Xr_train.columns), best_seed, cfg)
    pipe_r.fit(Xr_train, yr_train)
    val_prob_r = pipe_r.predict_proba(Xr_val)[:, 1]
    thr_r, _ = choose_threshold(yr_val, val_prob_r)
    test_prob_r = pipe_r.predict_proba(Xr_test)[:, 1]
    met_r = compute_metrics(yr_test, test_prob_r, thr_r)

    summary = {
        "route": route,
        "domain": domain,
        "best_config": best_cfg,
        "selected_seed": best_seed,
        "n_features": int(best_trials["n_features"].iloc[0]),
        "precision": float(best_trials["test_precision"].mean()),
        "recall": float(best_trials["test_recall"].mean()),
        "specificity": float(best_trials["test_specificity"].mean()),
        "balanced_accuracy": float(best_trials["test_balanced_accuracy"].mean()),
        "f1": float(best_trials["test_f1"].mean()),
        "roc_auc": float(best_trials["test_roc_auc"].mean()),
        "pr_auc": float(best_trials["test_pr_auc"].mean()),
        "brier": float(best_trials["test_brier"].mean()),
        "seed_balanced_accuracy_std": float(best_trials["test_balanced_accuracy"].std(ddof=0)),
        "seed_precision_std": float(best_trials["test_precision"].std(ddof=0)),
        "seed_recall_std": float(best_trials["test_recall"].std(ddof=0)),
        "split_balanced_accuracy": float(met_r["balanced_accuracy"]),
        "split_delta_balanced_accuracy": float(best_trials["test_balanced_accuracy"].mean() - met_r["balanced_accuracy"]),
        "missing15_delta": float(best_trials["robustness_missing15_delta"].mean()),
        "missing30_delta": float(best_trials["robustness_missing30_delta"].mean()),
        "direct_fill_pct": float(best_trials["direct_fill_pct"].mean()),
        "derived_fill_pct": float(best_trials["derived_fill_pct"].mean()),
        "imputed_fill_pct": float(best_trials["imputed_fill_pct"].mean()),
        "remaining_missing_pct": float(best_trials["remaining_missing_pct"].mean()),
    }
    return trials, summary
def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def contracts_report_md(basic: list[str], c_features: list[str], legacy_domain: dict[str, list[str]]) -> str:
    lines = [
        "# Route input contracts",
        "",
        "## Ruta A (baseline control)",
        f"- Contrato congelado: `questionnaire_basic_candidate_v1` ({len(basic)} inputs).",
        "- Sin capa fuerte de derivacion. Faltantes estructurales visibles.",
        "",
        "## Ruta B (basic + capa intermedia)",
        "- Contrato base: mismo cuestionario de Ruta A.",
        "- Capa intermedia congelada: proxies/derivaciones + imputacion controlada train-only.",
        "",
        "## Ruta C (remodelado cuidador-compatible)",
        f"- Contrato cuidador+system congelado: {len(c_features)} inputs (sin self-report).",
        "- Excluye dependencias estructurales de ysr_*, scared_sr_*, ari_sr_*.",
        "",
        "## Legacy runtime esperado por dominio",
    ]
    for d in DOMAINS:
        lines.append(f"- `{d}`: {len(legacy_domain[d])} inputs legacy")
    return "\n".join(lines)


def route_analysis_md(route: str, results: pd.DataFrame) -> str:
    macro = results[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier"]].mean()
    lines = [f"# Route {route} analysis", "", "## Macro", *(f"- {k}: **{v:.4f}**" for k, v in macro.items()), "", "## Por dominio"]
    for _, r in results.iterrows():
        lines.append(
            f"- `{r['domain']}` BA={r['balanced_accuracy']:.4f}, P={r['precision']:.4f}, R={r['recall']:.4f}, Spec={r['specificity']:.4f}, PR-AUC={r['pr_auc']:.4f}, imputed={r['imputed_fill_pct']:.3f}"
        )
    return "\n".join(lines)


def full_comparison_md(per_domain: pd.DataFrame, macro: pd.DataFrame) -> str:
    lines = ["# Full route comparison", "", "## Macro por ruta"]
    for _, r in macro.iterrows():
        lines.append(f"- Ruta {r['route']}: BA={r['balanced_accuracy']:.4f}, P={r['precision']:.4f}, R={r['recall']:.4f}, Spec={r['specificity']:.4f}, PR-AUC={r['pr_auc']:.4f}")
    lines += ["", "## Dominio x ruta (BA)"]
    for d in DOMAINS:
        sub = per_domain[per_domain["domain"] == d]
        pieces = [f"{row['route']}={row['balanced_accuracy']:.4f}" for _, row in sub.iterrows()]
        lines.append(f"- `{d}` -> " + ", ".join(pieces))
    lines += ["", "## Nota", "- `strict_full` y `research_full` comparten IDs en esta version; split stability se interpreta con cautela."]
    return "\n".join(lines)


def hybrid_matrix(per_domain: pd.DataFrame) -> pd.DataFrame:
    complexity_penalty = {"B": 0.03, "C": 0.01}
    rows = []
    for d in DOMAINS:
        sub = per_domain[(per_domain["domain"] == d) & (per_domain["route"].isin(["B", "C"]))].copy()
        sub["adjusted_score"] = (
            sub["balanced_accuracy"] * 0.45
            + sub["precision"] * 0.20
            + sub["recall"] * 0.15
            + sub["specificity"] * 0.10
            + sub["pr_auc"] * 0.10
            - sub["imputed_fill_pct"] * 0.20
            - sub["route"].map(complexity_penalty)
        )
        best_ba = sub.sort_values("balanced_accuracy", ascending=False).iloc[0]
        best_adj = sub.sort_values("adjusted_score", ascending=False).iloc[0]
        rows.append(
            {
                "domain": d,
                "winner_balanced_accuracy": best_ba["route"],
                "winner_adjusted_score": best_adj["route"],
                "recommended_hybrid_route": best_adj["route"],
                "notes": "usar ruta con mejor score ajustado y deuda metodologica controlada",
            }
        )
    return pd.DataFrame(rows)


def final_decision(per_domain: pd.DataFrame, macro: pd.DataFrame, hybrid: pd.DataFrame) -> tuple[str, str]:
    macro_bc = macro[macro["route"].isin(["B", "C"])].copy()
    macro_best = macro_bc.sort_values("balanced_accuracy", ascending=False).iloc[0]["route"]
    winners = hybrid["recommended_hybrid_route"].value_counts().to_dict()
    if winners and len(winners) == 1:
        final = f"{next(iter(winners.keys()))} global"
    else:
        top_route, top_count = sorted(winners.items(), key=lambda x: x[1], reverse=True)[0] if winners else ("C", 0)
        if top_count >= 4 and top_route in {"B", "C"}:
            final = f"{top_route} global"
        elif macro_best == "C" and winners.get("C", 0) >= 3:
            final = "C global"
        else:
            final = "hibrida B/C por dominio"

    rec = [
        "# Final route decision",
        "",
        f"- Ganador macro por BA: **{macro_best}**.",
        f"- Recomendacion final: **{final}**.",
        "- Ruta A queda baseline/control y se descarta como ruta final.",
        "- Ruta B se mantiene fuerte en precision inmediata, pero con mayor deuda de mapping/imputacion.",
        "- Ruta C prioriza alineacion metodologica cuidador-friendly y sostenibilidad.",
    ]
    return final, "\n".join(rec)


def questionnaire_implications_md(final_label: str, hybrid: pd.DataFrame) -> str:
    lines = [
        "# Questionnaire design implications",
        "",
        f"- Decision de estrategia: **{final_label}**.",
        "- Longitud esperada:",
        "  - Si gana B: cuestionario base corto + backend con capa de derivacion/imputacion mas intensa.",
        "  - Si gana C: cuestionario cuidador mas completo, menor dependencia de proxies debiles.",
        "",
        "- No omitir: edad, sexo, bloques nucleares CBCL/SDQ y disponibilidad instrumental clave.",
        "- Puede derivarse en backend: flags `has_*`, site/release, algunos proxies declarados y auditados.",
        "- Missing permitido: campos no respondidos no criticos, con manejo explicito y trazable.",
        "- No permitido: asumir equivalencia clinica fuerte self-report <-> caregiver-report sin etiquetado de aproximacion.",
        "",
        "## Recomendacion operativa",
        "- Mantener un cuestionario unico compatible con la ruta recomendada por dominio.",
        "- Si hay hibrido, mantener contrato unico y resolver diferencias solo en backend/model runtime.",
    ]
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(DATASET_PATH)
    contract = load_contract()
    metadata = {d: load_metadata(d) for d in DOMAINS}

    basic_features, c_features, legacy_domain = route_contracts(df, contract, metadata)

    # Fase 1
    contract_rows = []
    for d in DOMAINS:
        for f in legacy_domain[d]:
            spec = contract.get(f)
            contract_rows.append(
                {
                    "route": "A",
                    "domain": d,
                    "feature": f,
                    "in_contract": "yes" if f in basic_features else "no",
                    "mode": "direct" if f in basic_features else "missing_structural",
                }
            )
            mode_b = "direct" if f in basic_features else ("derived" if any(r["target"] == f for r in route_b_mapping_rules()) else "imputed")
            contract_rows.append({"route": "B", "domain": d, "feature": f, "in_contract": "yes", "mode": mode_b})
            contract_rows.append({"route": "C", "domain": d, "feature": f, "in_contract": "yes" if f in c_features else "no", "mode": "direct" if f in c_features else "excluded_self_or_noncaregiver"})

    save_csv(pd.DataFrame(contract_rows), INV_DIR / "route_input_contract_registry.csv")
    write_md(REPORTS_DIR / "route_input_contracts.md", contracts_report_md(basic_features, c_features, legacy_domain))

    # Fase 2
    cov = coverage_table(basic_features, c_features, legacy_domain, contract)
    save_csv(cov, TABLES_DIR / "route_coverage_and_missingness.csv")
    write_md(
        REPORTS_DIR / "route_coverage_analysis.md",
        "# Route coverage analysis\n\n```\n" + cov.to_string(index=False) + "\n```",
    )

    # Fases 3,4,5
    route_results = []
    route_trials = {"A": [], "B": [], "C": []}

    for d in DOMAINS:
        trials_a, summary_a = evaluate_route_domain("A", d, df, basic_features, set(basic_features), contract)
        route_trials["A"].append(trials_a)
        route_results.append(summary_a)

        trials_b, summary_b = evaluate_route_domain("B", d, df, legacy_domain[d], set(basic_features), contract)
        route_trials["B"].append(trials_b)
        route_results.append(summary_b)

        trials_c, summary_c = evaluate_route_domain("C", d, df, c_features, set(basic_features), contract)
        route_trials["C"].append(trials_c)
        route_results.append(summary_c)

    df_a_trials = pd.concat(route_trials["A"], ignore_index=True)
    df_b_trials = pd.concat(route_trials["B"], ignore_index=True)
    df_c_trials = pd.concat(route_trials["C"], ignore_index=True)

    df_results = pd.DataFrame(route_results)
    res_a = df_results[df_results["route"] == "A"].reset_index(drop=True)
    res_b = df_results[df_results["route"] == "B"].reset_index(drop=True)
    res_c = df_results[df_results["route"] == "C"].reset_index(drop=True)

    save_csv(df_a_trials, ROUTE_A_DIR / "route_a_trial_registry.csv")
    save_csv(res_a, ROUTE_A_DIR / "route_a_results.csv")
    write_md(REPORTS_DIR / "route_a_analysis.md", route_analysis_md("A", res_a))

    save_csv(pd.DataFrame(route_b_mapping_rules()), ROUTE_B_DIR / "route_b_mapping_registry.csv")
    save_csv(df_b_trials, ROUTE_B_DIR / "route_b_trial_registry.csv")
    save_csv(res_b, ROUTE_B_DIR / "route_b_results.csv")
    write_md(REPORTS_DIR / "route_b_analysis.md", route_analysis_md("B", res_b))

    save_csv(pd.DataFrame([{"domain": d, "feature_count": len(c_features), "feature_set": "caregiver_contract_v2"} for d in DOMAINS]), ROUTE_C_DIR / "route_c_dataset_registry.csv")
    save_csv(df_c_trials, ROUTE_C_DIR / "route_c_trial_registry.csv")
    save_csv(res_c, ROUTE_C_DIR / "route_c_results.csv")
    write_md(REPORTS_DIR / "route_c_analysis.md", route_analysis_md("C", res_c))

    # Fase 6
    per_domain = df_results.copy()
    save_csv(per_domain, TABLES_DIR / "per_domain_full_comparison.csv")
    macro = per_domain.groupby("route")[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier", "imputed_fill_pct", "derived_fill_pct"]].mean().reset_index()
    save_csv(macro, TABLES_DIR / "route_macro_comparison.csv")
    write_md(REPORTS_DIR / "full_route_comparison.md", full_comparison_md(per_domain, macro))

    # Fase 7
    hybrid = hybrid_matrix(per_domain)
    save_csv(hybrid, TABLES_DIR / "hybrid_candidate_matrix.csv")
    write_md(
        REPORTS_DIR / "hybrid_strategy_analysis.md",
        "# Hybrid strategy analysis\n\n```\n" + hybrid.to_string(index=False) + "\n```",
    )

    # Fase 8/9
    final_label, final_md = final_decision(per_domain, macro, hybrid)
    write_md(REPORTS_DIR / "final_route_decision.md", final_md)
    exec_md = [
        "# Executive summary",
        "",
        f"- Decision recomendada: **{final_label}**.",
        "- A se conserva como baseline de control.",
        "- B y C fueron reentrenadas bajo mismo estandar (splits, seeds, thresholding, robustez).",
        "- Ver tablas completas en `tables/per_domain_full_comparison.csv` y `tables/route_macro_comparison.csv`.",
    ]
    write_md(REPORTS_DIR / "executive_summary.md", "\n".join(exec_md))
    write_md(REPORTS_DIR / "questionnaire_design_implications.md", questionnaire_implications_md(final_label, hybrid))

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "final_route_decision.json").write_text(
        json.dumps({"final_route_decision": final_label, "generated_from": "questionnaire_strategy_retraining_v2"}, indent=2),
        encoding="utf-8",
    )

    print("OK - questionnaire_strategy_retraining_v2 generado")


if __name__ == "__main__":
    main()
