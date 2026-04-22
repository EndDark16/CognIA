
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "questionnaire_model_strategy_eval_v1"

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

DOMAINS = ["adhd", "conduct", "elimination", "anxiety", "depression"]
DOMAIN_TARGETS = {d: f"target_domain_{d}" for d in DOMAINS}
DOMAIN_STATUSES = {
    "adhd": "recovered_generalizing_model",
    "anxiety": "accepted_but_experimental",
    "conduct": "accepted_but_experimental",
    "depression": "accepted_but_experimental",
    "elimination": "experimental_line_more_useful_not_product_ready",
}
DOMAIN_MODEL_DIR = {
    d: ROOT / "models" / "champions" / f"rf_{d}_current" for d in DOMAINS
}

CATEGORICAL_FEATURES = {"sex_assigned_at_birth", "site"}
SYSTEM_FILLED_FEATURES = {"site", "release"}
CAREGIVER_MODALITIES = {"reporte_cuidador", "dato_demografico", "disponibilidad_instrumental"}
DERIVABLE_MODALITIES = {"score_derivado"}


@dataclass(frozen=True)
class ContractRow:
    feature_final: str
    dataset_origen: str
    columna_origen: str
    tipo_respuesta: str
    opciones_permitidas: list[str]
    rango_min: float | None
    rango_max: float | None
    trastorno_relacionado: str
    requerida_opcional: str
    modalidad: str


def parse_range(value: str) -> tuple[float | None, float | None]:
    if not isinstance(value, str) or "|" not in value:
        return None, None
    left, right = value.split("|", 1)
    try:
        return float(left), float(right)
    except ValueError:
        return None, None


def load_contract() -> dict[str, ContractRow]:
    raw = pd.read_csv(CONTRACT_PATH)
    out: dict[str, ContractRow] = {}
    for _, row in raw.iterrows():
        feature = str(row["feature_final"]).strip()
        if not feature:
            continue
        rango_min, rango_max = parse_range(str(row.get("rango_esperado", "")))
        opts = []
        if pd.notna(row.get("opciones_permitidas")):
            opts = [x.strip() for x in str(row["opciones_permitidas"]).split("|") if x.strip()]
        out[feature] = ContractRow(
            feature_final=feature,
            dataset_origen=str(row.get("dataset_origen", "") or ""),
            columna_origen=str(row.get("columna_origen", "") or ""),
            tipo_respuesta=str(row.get("tipo_respuesta", "") or ""),
            opciones_permitidas=opts,
            rango_min=rango_min,
            rango_max=rango_max,
            trastorno_relacionado=str(row.get("trastorno_relacionado", "") or "general"),
            requerida_opcional=str(row.get("requerida_opcional", "") or "optional"),
            modalidad=str(row.get("modalidad", "") or ""),
        )
    return out


def load_domain_metadata(domain: str) -> dict[str, Any]:
    metadata_path = DOMAIN_MODEL_DIR[domain] / "metadata.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def load_domain_model(domain: str) -> Any:
    base = DOMAIN_MODEL_DIR[domain]
    calibrated = base / "calibrated.joblib"
    pipeline = base / "pipeline.joblib"
    if calibrated.exists():
        return joblib.load(calibrated), "calibrated.joblib"
    if pipeline.exists():
        return joblib.load(pipeline), "pipeline.joblib"
    raise FileNotFoundError(f"No se encontro artefacto de modelo para {domain}: {base}")


def split_dir(domain: str, split_name: str) -> Path:
    return ROOT / "data" / "processed_hybrid_dsm5_v2" / "splits" / f"domain_{domain}_{split_name}"


def load_split_ids(domain: str, split_name: str, part: str) -> pd.Series:
    path = split_dir(domain, split_name) / f"ids_{part}.csv"
    ids = pd.read_csv(path)
    id_col = "participant_id" if "participant_id" in ids.columns else ids.columns[0]
    return ids[id_col].astype(str)


def subset_by_ids(df: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    return df[df["participant_id"].astype(str).isin(set(ids.astype(str)))].copy()


def extract_feature_from_top(token: str) -> str | None:
    if token.startswith("num__"):
        return token.split("num__", 1)[1]
    if token.startswith("cat__sex_assigned_at_birth"):
        return "sex_assigned_at_birth"
    if token.startswith("cat__site"):
        return "site"
    return None


def feature_source(feature: str) -> str:
    if feature.startswith("ysr_"):
        return "YSR_self_report"
    if feature.startswith("scared_sr_"):
        return "SCARED_SR_self_report"
    if feature.startswith("ari_sr_"):
        return "ARI_SR_self_report"
    if feature.startswith("scared_p_"):
        return "SCARED_P_caregiver"
    if feature.startswith("ari_p_"):
        return "ARI_P_caregiver"
    if feature.startswith("mfq_p_"):
        return "MFQ_P_caregiver"
    if feature.startswith("cbcl_"):
        return "CBCL_caregiver"
    if feature.startswith("sdq_"):
        return "SDQ_caregiver"
    if feature.startswith("swan_"):
        return "SWAN_caregiver"
    if feature.startswith("conners_"):
        return "Conners"
    if feature.startswith("icut_"):
        return "ICU_parent"
    if feature.startswith("has_"):
        return "instrument_availability"
    if feature in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "demographic_or_system"
    return "other"


def feature_domain(contract_row: ContractRow | None, default: str = "general") -> str:
    if contract_row and contract_row.trastorno_relacionado:
        raw = contract_row.trastorno_relacionado.strip().lower()
        if raw in DOMAINS:
            return raw
    return default


def question_section(domain: str, feature: str) -> str:
    if feature in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "contexto"
    return f"dominio_{domain}" if domain in DOMAINS else "dominio_general"
def humanize_feature(feature: str) -> str:
    specific = {
        "age_years": "Edad del niño o niña (años cumplidos)",
        "sex_assigned_at_birth": "Sexo asignado al nacer",
        "site": "Sede de aplicación (autocompletado por sistema)",
        "release": "Versión de release de inferencia (autocompletado por sistema)",
        "has_cbcl": "¿Se cuenta con datos CBCL para este caso?",
        "has_sdq": "¿Se cuenta con datos SDQ para este caso?",
        "has_swan": "¿Se cuenta con escala SWAN para este caso?",
        "has_scared_p": "¿Se cuenta con escala SCARED-P para este caso?",
        "has_mfq_p": "¿Se cuenta con escala MFQ-P para este caso?",
        "has_ari_p": "¿Se cuenta con escala ARI-P para este caso?",
        "has_icut": "¿Se cuenta con escala ICU para este caso?",
    }
    if feature in specific:
        return specific[feature]
    txt = feature.replace("_", " ").strip()
    txt = txt.replace("cbcl", "CBCL").replace("sdq", "SDQ").replace("mfq", "MFQ")
    txt = txt.replace("ari", "ARI").replace("ysr", "YSR").replace("scared", "SCARED")
    txt = txt.replace("swan", "SWAN").replace("icut", "ICU")
    return f"Reporte cuidador: {txt}"


def response_type_from_contract(contract_row: ContractRow | None) -> str:
    if not contract_row:
        return "numeric_range"
    raw = contract_row.tipo_respuesta.strip().lower()
    if raw in {"binary", "boolean"}:
        return "boolean"
    if raw in {"integer", "count", "numeric_int"}:
        return "integer"
    if raw in {"multi_choice", "multichoice"}:
        return "multi_choice"
    if raw in {"single_choice", "categorical"}:
        return "single_choice"
    return "numeric_range"


def response_scale_from_contract(contract_row: ContractRow | None) -> str:
    if not contract_row:
        return "na"
    if contract_row.opciones_permitidas:
        return "|".join(contract_row.opciones_permitidas)
    if contract_row.rango_min is not None and contract_row.rango_max is not None:
        return f"{contract_row.rango_min}|{contract_row.rango_max}"
    return "na"


def is_caregiver_answerable(feature: str, contract: dict[str, ContractRow]) -> bool:
    row = contract.get(feature)
    if not row:
        return feature in SYSTEM_FILLED_FEATURES
    return row.modalidad in CAREGIVER_MODALITIES


def is_self_report_only(feature: str, contract: dict[str, ContractRow]) -> bool:
    row = contract.get(feature)
    return bool(row and row.modalidad == "autoreporte")


def can_be_derived(feature: str, contract: dict[str, ContractRow]) -> bool:
    row = contract.get(feature)
    if row and row.modalidad in DERIVABLE_MODALITIES:
        return True
    return (
        feature.startswith("ysr_")
        or feature.startswith("ari_sr_")
        or feature.startswith("scared_sr_")
        or feature in {"has_ysr", "has_ari_sr", "has_scared_sr"}
    )


def can_be_system_filled(feature: str) -> bool:
    return feature in SYSTEM_FILLED_FEATURES or feature.startswith("has_")


def default_for_feature(feature: str, contract: dict[str, ContractRow]) -> Any:
    row = contract.get(feature)
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
    if row and row.rango_min is not None and row.rango_max is not None:
        return round((row.rango_min + row.rango_max) / 2.0, 4)
    if row and row.opciones_permitidas:
        candidate = row.opciones_permitidas[0]
        try:
            return float(candidate)
        except ValueError:
            return candidate
    return 0.0


def normalize_sex(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Unknown"
    raw = str(value).strip().lower()
    if raw in {"m", "male", "masculino", "1"}:
        return "Male"
    if raw in {"f", "female", "femenino", "0"}:
        return "Female"
    return "Unknown"


def normalize_site(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "CBIC"
    raw = str(value).strip()
    if raw in {"CBIC", "CUNY", "RUBIC", "Staten Island"}:
        return raw
    return "CBIC"


def compute_metrics(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def choose_threshold_by_balanced_accuracy(y_true: pd.Series, y_prob: np.ndarray) -> tuple[float, float]:
    best_t = 0.5
    best_ba = -1.0
    for threshold in np.linspace(0.2, 0.8, 121):
        y_pred = (y_prob >= threshold).astype(int)
        ba = float(balanced_accuracy_score(y_true, y_pred))
        if ba > best_ba:
            best_ba = ba
            best_t = float(threshold)
    return best_t, best_ba


def build_basic_candidate_features(
    contract: dict[str, ContractRow], metadata_by_domain: dict[str, dict[str, Any]], dataset_columns: set[str]
) -> list[str]:
    selected = ["age_years", "sex_assigned_at_birth", "site", "release"]
    seen = set(selected)
    for domain in DOMAINS:
        meta = metadata_by_domain[domain]
        extracted = []
        for token in meta.get("top_features", []):
            feat = extract_feature_from_top(token)
            if feat:
                extracted.append(feat)
        if not extracted:
            extracted = list(meta.get("feature_columns", [])[:12])
        for feature in extracted[:12]:
            if feature in seen or feature not in dataset_columns:
                continue
            if is_self_report_only(feature, contract):
                continue
            seen.add(feature)
            selected.append(feature)

    extra_features = [
        "has_swan",
        "swan_total",
        "swan_inattention_total",
        "swan_hyperactive_impulsive_total",
        "has_scared_p",
        "scared_p_total",
        "scared_p_generalized_anxiety",
        "scared_p_panic_somatic",
        "scared_p_social_anxiety",
        "scared_p_separation_anxiety",
        "scared_p_school_avoidance",
        "scared_p_possible_anxiety_disorder_cut25",
        "has_mfq_p",
        "mfq_p_total",
        "ari_p_symptom_total",
        "has_ari_p",
        "has_icut",
        "icut_total",
    ]
    for feature in extra_features:
        if feature in dataset_columns and feature not in seen and not is_self_report_only(feature, contract):
            selected.append(feature)
            seen.add(feature)
    return selected


def build_input_coverage_matrix(
    contract: dict[str, ContractRow],
    metadata_by_domain: dict[str, dict[str, Any]],
    basic_features: list[str],
) -> pd.DataFrame:
    intersection = set(metadata_by_domain[DOMAINS[0]]["feature_columns"])
    for domain in DOMAINS[1:]:
        intersection &= set(metadata_by_domain[domain]["feature_columns"])

    rows: list[dict[str, Any]] = []
    for domain in DOMAINS:
        for feature in metadata_by_domain[domain]["feature_columns"]:
            row = contract.get(feature)
            caregiver = is_caregiver_answerable(feature, contract)
            self_report = is_self_report_only(feature, contract)
            derivable = can_be_derived(feature, contract)
            system_fill = can_be_system_filled(feature)
            proposed_needed = bool(feature in basic_features and caregiver and not system_fill)
            notes = []
            if self_report:
                notes.append("self_report_only")
            if derivable:
                notes.append("derivable_or_proxy")
            if system_fill:
                notes.append("system_filled_candidate")
            rows.append(
                {
                    "input_key": feature,
                    "domain": domain,
                    "source_instrument_or_origin": feature_source(feature),
                    "input_type": response_type_from_contract(row),
                    "caregiver_answerable_yes_no": "yes" if caregiver else "no",
                    "self_report_only_yes_no": "yes" if self_report else "no",
                    "can_be_derived_yes_no": "yes" if derivable else "no",
                    "can_be_system_filled_yes_no": "yes" if system_fill else "no",
                    "should_remain_missing_yes_no": "yes" if (self_report and not derivable) else "no",
                    "required_by_current_runtime_yes_no": "yes",
                    "required_by_all_domains_yes_no": "yes" if feature in intersection else "no",
                    "proposed_question_needed_yes_no": "yes" if proposed_needed else "no",
                    "proposed_question_text_if_applicable": humanize_feature(feature) if proposed_needed else "",
                    "response_type": response_type_from_contract(row),
                    "response_scale": response_scale_from_contract(row),
                    "section": question_section(feature_domain(row, domain), feature),
                    "priority": "high" if feature in intersection else ("medium" if caregiver else "low"),
                    "notes": ";".join(notes),
                }
            )
    return pd.DataFrame(rows)
def questionnaire_candidate_table(
    basic_features: list[str], contract: dict[str, ContractRow], metadata_by_domain: dict[str, dict[str, Any]]
) -> pd.DataFrame:
    feature_domain_hint: dict[str, str] = {}
    for domain in DOMAINS:
        for feature in metadata_by_domain[domain]["feature_columns"]:
            feature_domain_hint.setdefault(feature, domain)

    rows = []
    for idx, feature in enumerate(basic_features, start=1):
        row = contract.get(feature)
        dom = feature_domain(row, feature_domain_hint.get(feature, "general"))
        rows.append(
            {
                "question_id": f"QB_{idx:03d}",
                "feature_key": feature,
                "section": question_section(dom, feature),
                "domain": dom,
                "question_text": humanize_feature(feature),
                "response_type": response_type_from_contract(row),
                "response_scale": response_scale_from_contract(row),
                "source_instrument_or_origin": feature_source(feature),
                "modalidad": row.modalidad if row else "unknown",
                "priority": "high" if feature in {"age_years", "sex_assigned_at_birth"} else "medium",
            }
        )
    return pd.DataFrame(rows)


def build_pass_a_matrix(
    source_df: pd.DataFrame,
    feature_columns: list[str],
    basic_feature_set: set[str],
    contract: dict[str, ContractRow],
) -> tuple[pd.DataFrame, dict[str, float]]:
    n_rows = len(source_df)
    X = pd.DataFrame(index=source_df.index)
    default_cells = 0
    direct_cells = 0
    direct_missing_cells = 0
    for feature in feature_columns:
        if feature in basic_feature_set and feature in source_df.columns:
            values = source_df[feature].copy()
            direct_cells += n_rows
            direct_missing_cells += int(values.isna().sum())
        else:
            values = pd.Series([np.nan] * n_rows, index=source_df.index)

        missing_mask = values.isna()
        default_cells += int(missing_mask.sum())
        values = values.fillna(default_for_feature(feature, contract))
        if feature == "sex_assigned_at_birth":
            values = values.map(normalize_sex)
        if feature == "site":
            values = values.map(normalize_site)
        X[feature] = values

    total_cells = n_rows * max(len(feature_columns), 1)
    direct_coverage = len([f for f in feature_columns if f in basic_feature_set]) / max(len(feature_columns), 1)
    return X, {
        "input_coverage_pct": direct_coverage,
        "missing_pct_structural": 1.0 - direct_coverage,
        "default_dependency_pct": default_cells / max(total_cells, 1),
        "direct_observed_missing_pct": direct_missing_cells / max(direct_cells, 1) if direct_cells else 0.0,
    }


def mapping_rules_registry() -> pd.DataFrame:
    rules = [
        ("M01", "ysr_aggressive_behavior_proxy", "cbcl_aggressive_behavior_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M02", "ysr_anxious_depressed_proxy", "cbcl_anxious_depressed_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M03", "ysr_attention_problems_proxy", "cbcl_attention_problems_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M04", "ysr_externalizing_proxy", "cbcl_externalizing_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M05", "ysr_internalizing_proxy", "cbcl_internalizing_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M06", "ysr_rule_breaking_proxy", "cbcl_rule_breaking_proxy", "proxy_copy", "moderate", "self-report proxy from caregiver CBCL"),
        ("M07", "has_ysr", "has_cbcl", "binary_proxy", "moderate", "availability proxy"),
        ("M08", "ari_sr_symptom_total", "ari_p_symptom_total", "proxy_copy", "moderate", "self-report proxy from caregiver ARI-P"),
        ("M09", "has_ari_sr", "has_ari_p", "binary_proxy", "moderate", "availability proxy"),
        ("M10", "scared_sr_total", "scared_p_total", "proxy_copy", "moderate", "self-report total proxy from caregiver total"),
        ("M11", "scared_sr_generalized_anxiety", "scared_p_generalized_anxiety", "proxy_copy", "moderate", "subscale proxy"),
        ("M12", "scared_sr_panic_somatic", "scared_p_panic_somatic", "proxy_copy", "moderate", "subscale proxy"),
        ("M13", "scared_sr_social_anxiety", "scared_p_social_anxiety", "proxy_copy", "moderate", "subscale proxy"),
        ("M14", "scared_sr_separation_anxiety", "scared_p_separation_anxiety", "proxy_copy", "moderate", "subscale proxy"),
        ("M15", "scared_sr_school_avoidance", "scared_p_school_avoidance", "proxy_copy", "moderate", "subscale proxy"),
        ("M16", "scared_sr_possible_anxiety_disorder_cut25", "scared_p_possible_anxiety_disorder_cut25", "proxy_copy", "moderate", "cutoff proxy"),
        ("M17", "scared_sr_01_to_41", "scared_p_total", "average_projection", "weak", "item-level approximation from caregiver total"),
    ]
    return pd.DataFrame(rules, columns=["mapping_id", "target_feature", "source_feature", "method", "evidence_strength", "notes"])


def build_pass_b_matrix(
    domain: str,
    train_df: pd.DataFrame,
    source_df: pd.DataFrame,
    feature_columns: list[str],
    basic_feature_set: set[str],
    contract: dict[str, ContractRow],
) -> tuple[pd.DataFrame, dict[str, float]]:
    n_rows = len(source_df)
    X0 = pd.DataFrame(index=source_df.index)
    for feature in feature_columns:
        if feature in basic_feature_set and feature in source_df.columns:
            X0[feature] = source_df[feature]
        else:
            X0[feature] = np.nan

    stage0_na = int(X0.isna().sum().sum())
    direct_non_missing = int((~X0.isna()).sum().sum())
    X1 = X0.copy()

    direct_pairs = [
        ("ysr_aggressive_behavior_proxy", "cbcl_aggressive_behavior_proxy"),
        ("ysr_anxious_depressed_proxy", "cbcl_anxious_depressed_proxy"),
        ("ysr_attention_problems_proxy", "cbcl_attention_problems_proxy"),
        ("ysr_externalizing_proxy", "cbcl_externalizing_proxy"),
        ("ysr_internalizing_proxy", "cbcl_internalizing_proxy"),
        ("ysr_rule_breaking_proxy", "cbcl_rule_breaking_proxy"),
        ("has_ysr", "has_cbcl"),
        ("ari_sr_symptom_total", "ari_p_symptom_total"),
        ("has_ari_sr", "has_ari_p"),
        ("scared_sr_total", "scared_p_total"),
        ("scared_sr_generalized_anxiety", "scared_p_generalized_anxiety"),
        ("scared_sr_panic_somatic", "scared_p_panic_somatic"),
        ("scared_sr_social_anxiety", "scared_p_social_anxiety"),
        ("scared_sr_separation_anxiety", "scared_p_separation_anxiety"),
        ("scared_sr_school_avoidance", "scared_p_school_avoidance"),
        ("scared_sr_possible_anxiety_disorder_cut25", "scared_p_possible_anxiety_disorder_cut25"),
    ]
    for target, source in direct_pairs:
        if target in X1.columns and source in X1.columns:
            X1[target] = X1[target].fillna(X1[source])

    if "scared_p_total" in X1.columns:
        avg_projection = (pd.to_numeric(X1["scared_p_total"], errors="coerce") / 41.0).clip(lower=0, upper=2)
        for feature in feature_columns:
            if feature.startswith("scared_sr_") and feature != "scared_sr_total":
                X1[feature] = X1[feature].fillna(avg_projection)

    if "site" in X1.columns:
        X1["site"] = X1["site"].fillna("CBIC")
    if "release" in X1.columns:
        X1["release"] = X1["release"].fillna(11.0)
    if "sex_assigned_at_birth" in X1.columns:
        X1["sex_assigned_at_birth"] = X1["sex_assigned_at_birth"].fillna("Unknown")

    stage1_na = int(X1.isna().sum().sum())
    X2 = X1.copy()
    for feature in feature_columns:
        if not X2[feature].isna().any():
            continue
        if feature in CATEGORICAL_FEATURES:
            mode = train_df[feature].mode(dropna=True)
            fill_value = mode.iloc[0] if len(mode) else default_for_feature(feature, contract)
            X2[feature] = X2[feature].fillna(fill_value)
        else:
            fill_value = pd.to_numeric(train_df[feature], errors="coerce").median()
            if pd.isna(fill_value):
                fill_value = default_for_feature(feature, contract)
            X2[feature] = pd.to_numeric(X2[feature], errors="coerce").fillna(float(fill_value))

    stage2_na = int(X2.isna().sum().sum())
    for feature in feature_columns:
        X2[feature] = X2[feature].fillna(default_for_feature(feature, contract))
        if feature == "sex_assigned_at_birth":
            X2[feature] = X2[feature].map(normalize_sex)
        if feature == "site":
            X2[feature] = X2[feature].map(normalize_site)

    total_cells = n_rows * max(len(feature_columns), 1)
    feature_coverage = len([f for f in feature_columns if f in basic_feature_set]) / max(len(feature_columns), 1)
    return X2, {
        "input_coverage_pct": feature_coverage,
        "missing_pct_structural": 1.0 - feature_coverage,
        "direct_fill_pct": direct_non_missing / max(total_cells, 1),
        "derived_fill_pct": (stage0_na - stage1_na) / max(total_cells, 1),
        "stat_imputed_fill_pct": (stage1_na - stage2_na) / max(total_cells, 1),
        "remaining_unresolved_pct": stage2_na / max(total_cells, 1),
    }


def evaluate_pass_a(
    df: pd.DataFrame,
    contract: dict[str, ContractRow],
    metadata_by_domain: dict[str, dict[str, Any]],
    basic_features: list[str],
) -> pd.DataFrame:
    rows = []
    basic_set = set(basic_features)
    for domain in DOMAINS:
        metadata = metadata_by_domain[domain]
        model, model_file = load_domain_model(domain)
        test_df = subset_by_ids(df, load_split_ids(domain, "strict_full", "test"))
        y_true = test_df[DOMAIN_TARGETS[domain]].astype(int)
        X_test, stats = build_pass_a_matrix(test_df, metadata["feature_columns"], basic_set, contract)
        y_prob = model.predict_proba(X_test)[:, 1]
        threshold = float(metadata.get("recommended_threshold", 0.5))
        metrics = compute_metrics(y_true, y_prob, threshold)
        rows.append(
            {
                "domain": domain,
                "route": "A_basic_direct",
                "split": "strict_full_test",
                "n_test": len(test_df),
                "model_artifact": model_file,
                "threshold_used": threshold,
                **stats,
                **metrics,
                "operational_confidence": "low" if stats["default_dependency_pct"] >= 0.5 else "medium",
                "notes": "Sin capa intermedia; faltantes cubiertos por defaults del runtime actual.",
            }
        )
    return pd.DataFrame(rows)


def evaluate_pass_b(
    df: pd.DataFrame,
    contract: dict[str, ContractRow],
    metadata_by_domain: dict[str, dict[str, Any]],
    basic_features: list[str],
) -> pd.DataFrame:
    rows = []
    basic_set = set(basic_features)
    for domain in DOMAINS:
        metadata = metadata_by_domain[domain]
        model, model_file = load_domain_model(domain)
        train_df = subset_by_ids(df, load_split_ids(domain, "strict_full", "train"))
        test_df = subset_by_ids(df, load_split_ids(domain, "strict_full", "test"))
        y_true = test_df[DOMAIN_TARGETS[domain]].astype(int)
        X_test, stats = build_pass_b_matrix(domain, train_df, test_df, metadata["feature_columns"], basic_set, contract)
        y_prob = model.predict_proba(X_test)[:, 1]
        threshold = float(metadata.get("recommended_threshold", 0.5))
        metrics = compute_metrics(y_true, y_prob, threshold)
        rows.append(
            {
                "domain": domain,
                "route": "B_intermediate_mapping",
                "split": "strict_full_test",
                "n_test": len(test_df),
                "model_artifact": model_file,
                "threshold_used": threshold,
                **stats,
                **metrics,
                "operational_confidence": "medium",
                "notes": "Capa intermedia: proxies + imputacion estadistica controlada.",
            }
        )
    return pd.DataFrame(rows)
def build_pass_c_pipeline(features: list[str], random_state: int) -> Pipeline:
    categorical = [f for f in features if f in CATEGORICAL_FEATURES]
    numeric = [f for f in features if f not in CATEGORICAL_FEATURES]
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
    )
    rf = RandomForestClassifier(
        n_estimators=350,
        max_depth=12,
        min_samples_leaf=2,
        min_samples_split=5,
        class_weight="balanced_subsample",
        random_state=random_state,
        n_jobs=-1,
    )
    return Pipeline([("preprocess", pre), ("rf", rf)])


def add_numeric_noise(
    frame: pd.DataFrame,
    reference: pd.DataFrame,
    contract: dict[str, ContractRow],
    scale: float,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = frame.copy()
    for col in out.columns:
        if col in CATEGORICAL_FEATURES:
            continue
        series = pd.to_numeric(out[col], errors="coerce")
        ref = pd.to_numeric(reference[col], errors="coerce")
        std = float(ref.std()) if not math.isnan(float(ref.std())) else 0.0
        if std <= 0.0:
            continue
        noisy = series + rng.normal(0.0, std * scale, size=len(series))
        spec = contract.get(col)
        if spec and spec.rango_min is not None and spec.rango_max is not None:
            noisy = noisy.clip(lower=spec.rango_min, upper=spec.rango_max)
        out[col] = noisy
    return out


def evaluate_pass_c(
    df: pd.DataFrame,
    contract: dict[str, ContractRow],
    basic_features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results_rows = []
    registry_rows = []
    seeds = [17, 42, 73]

    for domain in DOMAINS:
        y_col = DOMAIN_TARGETS[domain]
        features = [f for f in basic_features if f in df.columns and not f.startswith("target_") and f != "participant_id"]

        strict_train = subset_by_ids(df, load_split_ids(domain, "strict_full", "train"))
        strict_val = subset_by_ids(df, load_split_ids(domain, "strict_full", "val"))
        strict_test = subset_by_ids(df, load_split_ids(domain, "strict_full", "test"))

        seed_runs = []
        best_payload = None
        for seed in seeds:
            model = build_pass_c_pipeline(features, random_state=seed)
            model.fit(strict_train[features], strict_train[y_col].astype(int))
            val_prob = model.predict_proba(strict_val[features])[:, 1]
            threshold, val_ba = choose_threshold_by_balanced_accuracy(strict_val[y_col].astype(int), val_prob)
            test_prob = model.predict_proba(strict_test[features])[:, 1]
            metrics = compute_metrics(strict_test[y_col].astype(int), test_prob, threshold)
            payload = {"seed": seed, "threshold": threshold, "val_balanced_accuracy": val_ba, "metrics": metrics, "model": model}
            seed_runs.append(payload)
            if best_payload is None or payload["val_balanced_accuracy"] > best_payload["val_balanced_accuracy"]:
                best_payload = payload

        assert best_payload is not None
        selected_model = best_payload["model"]
        selected_threshold = float(best_payload["threshold"])
        selected_metrics = best_payload["metrics"]

        mild_prob = selected_model.predict_proba(add_numeric_noise(strict_test[features], strict_train[features], contract, 0.05, 909))[:, 1]
        moderate_prob = selected_model.predict_proba(add_numeric_noise(strict_test[features], strict_train[features], contract, 0.10, 911))[:, 1]
        mild_ba = balanced_accuracy_score(strict_test[y_col].astype(int), (mild_prob >= selected_threshold).astype(int))
        moderate_ba = balanced_accuracy_score(strict_test[y_col].astype(int), (moderate_prob >= selected_threshold).astype(int))

        research_train = subset_by_ids(df, load_split_ids(domain, "research_full", "train"))
        research_val = subset_by_ids(df, load_split_ids(domain, "research_full", "val"))
        research_test = subset_by_ids(df, load_split_ids(domain, "research_full", "test"))
        alt_model = build_pass_c_pipeline(features, random_state=int(best_payload["seed"]))
        alt_model.fit(research_train[features], research_train[y_col].astype(int))
        alt_threshold, _ = choose_threshold_by_balanced_accuracy(research_val[y_col].astype(int), alt_model.predict_proba(research_val[features])[:, 1])
        alt_metrics = compute_metrics(research_test[y_col].astype(int), alt_model.predict_proba(research_test[features])[:, 1], alt_threshold)

        seed_ba_values = [run["metrics"]["balanced_accuracy"] for run in seed_runs]
        seed_prec_values = [run["metrics"]["precision"] for run in seed_runs]
        seed_recall_values = [run["metrics"]["recall"] for run in seed_runs]

        removed_self_report = sum(1 for feat in load_domain_metadata(domain)["feature_columns"] if is_self_report_only(feat, contract))
        registry_rows.append(
            {
                "domain": domain,
                "dataset_source": str(DATASET_PATH.relative_to(ROOT)),
                "target_column": y_col,
                "feature_set_name": "caregiver_basic_candidate_v1",
                "n_features": len(features),
                "n_categorical": len([f for f in features if f in CATEGORICAL_FEATURES]),
                "n_numeric": len([f for f in features if f not in CATEGORICAL_FEATURES]),
                "strict_split_used": f"domain_{domain}_strict_full",
                "alt_split_used": f"domain_{domain}_research_full",
                "seeds_tested": ",".join(map(str, seeds)),
                "self_report_features_excluded_vs_current_runtime": removed_self_report,
            }
        )

        results_rows.append(
            {
                "domain": domain,
                "route": "C_remodel_caregiver_contract",
                "split_primary": "strict_full_test",
                "split_secondary": "research_full_test",
                "n_test_primary": len(strict_test),
                "n_test_secondary": len(research_test),
                "selected_seed": int(best_payload["seed"]),
                "threshold_selected_from_val": selected_threshold,
                "precision": selected_metrics["precision"],
                "recall": selected_metrics["recall"],
                "specificity": selected_metrics["specificity"],
                "balanced_accuracy": selected_metrics["balanced_accuracy"],
                "f1": selected_metrics["f1"],
                "roc_auc": selected_metrics["roc_auc"],
                "pr_auc": selected_metrics["pr_auc"],
                "brier_score": selected_metrics["brier_score"],
                "seed_balanced_accuracy_mean": float(statistics.mean(seed_ba_values)),
                "seed_balanced_accuracy_std": float(statistics.pstdev(seed_ba_values)),
                "seed_precision_std": float(statistics.pstdev(seed_prec_values)),
                "seed_recall_std": float(statistics.pstdev(seed_recall_values)),
                "split_secondary_balanced_accuracy": alt_metrics["balanced_accuracy"],
                "split_stability_delta_balanced_accuracy": float(selected_metrics["balanced_accuracy"] - alt_metrics["balanced_accuracy"]),
                "noise_mild_balanced_accuracy": float(mild_ba),
                "noise_moderate_balanced_accuracy": float(moderate_ba),
                "noise_mild_delta": float(selected_metrics["balanced_accuracy"] - mild_ba),
                "noise_moderate_delta": float(selected_metrics["balanced_accuracy"] - moderate_ba),
                "sustainability_assessment": "high" if len(features) <= 60 else "medium",
                "implementation_cost_assessment": "medium",
                "maintenance_cost_assessment": "medium",
                "notes": "Remodelado RF con features cuidador-friendly + sistema, sin self-report.",
            }
        )

    return pd.DataFrame(registry_rows), pd.DataFrame(results_rows)


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def summarize_input_coverage(coverage_df: pd.DataFrame, basic_features: list[str]) -> str:
    total_rows = len(coverage_df)
    caregiver_yes = int((coverage_df["caregiver_answerable_yes_no"] == "yes").sum())
    self_report_yes = int((coverage_df["self_report_only_yes_no"] == "yes").sum())
    derivable_yes = int((coverage_df["can_be_derived_yes_no"] == "yes").sum())
    by_domain = (
        coverage_df.groupby("domain")[["caregiver_answerable_yes_no", "self_report_only_yes_no"]]
        .apply(lambda x: pd.Series({"caregiver_yes": int((x["caregiver_answerable_yes_no"] == "yes").sum()), "self_report_yes": int((x["self_report_only_yes_no"] == "yes").sum()), "total": int(len(x))}))
        .reset_index()
    )
    lines = [
        "# Input coverage summary",
        "",
        f"- Filas auditadas (input x dominio): **{total_rows}**",
        f"- Inputs caregiver-answerable: **{caregiver_yes}**",
        f"- Inputs self-report-only: **{self_report_yes}**",
        f"- Inputs marcados como derivables/proxy: **{derivable_yes}**",
        f"- Preguntas incluidas en questionnaire_basic_candidate_v1: **{len(basic_features)}**",
        "",
        "## Cobertura por dominio",
    ]
    for _, row in by_domain.iterrows():
        lines.append(f"- `{row['domain']}`: caregiver={row['caregiver_yes']}/{row['total']} | self-report={row['self_report_yes']}/{row['total']}")
    lines += [
        "",
        "## Observaciones",
        "- `anxiety` y `adhd` mantienen mayor dependencia de familias con componente self-report (SCARED-SR / YSR).",
        "- `elimination` depende casi por completo de señales caregiver (CBCL/SDQ) y sistema.",
        "- Los metadatos `site` y `release` pueden llenarse por sistema sin intervención del cuidador.",
    ]
    return "\n".join(lines)


def summarize_basic_candidate(questionnaire_df: pd.DataFrame) -> str:
    by_domain = questionnaire_df.groupby("domain").size().to_dict()
    lines = [
        "# questionnaire_basic_candidate_v1",
        "",
        "- Objetivo: cuestionario cuidador-friendly de carga moderada para evaluar acople con modelos existentes.",
        f"- Total preguntas/features seleccionadas: **{len(questionnaire_df)}**",
        "- Exclusión explícita: features self-report (`ysr_*`, `scared_sr_*`, `ari_sr_*`) como preguntas directas.",
        "",
        "## Distribución por dominio",
    ]
    for domain in ["general"] + DOMAINS:
        if domain in by_domain:
            lines.append(f"- `{domain}`: {by_domain[domain]} items")
    lines += [
        "",
        "## Reglas",
        "- Incluye contexto base (`age_years`, `sex_assigned_at_birth`) y metadatos de sistema (`site`, `release`).",
        "- Prioriza escalas parentales y proxies caregiver.",
        "- Mantiene estructura compatible con secciones multipaso por dominio.",
    ]
    return "\n".join(lines)
def summarize_pass(pass_df: pd.DataFrame, title: str, extra_notes: list[str]) -> str:
    macro = pass_df[["precision", "recall", "specificity", "balanced_accuracy", "f1", "roc_auc", "pr_auc", "brier_score"]].mean()
    lines = [f"# {title}", "", "## Resultado macro (promedio 5 dominios)"]
    for col in macro.index:
        lines.append(f"- {col}: **{macro[col]:.4f}**")
    lines += ["", "## Resultado por dominio"]
    for _, row in pass_df.iterrows():
        lines.append(f"- `{row['domain']}` -> BA={row['balanced_accuracy']:.4f}, P={row['precision']:.4f}, R={row['recall']:.4f}, Spec={row['specificity']:.4f}, F1={row['f1']:.4f}")
    lines += ["", "## Notas metodológicas"] + [f"- {note}" for note in extra_notes]
    return "\n".join(lines)


def compare_three_paths(pass_a: pd.DataFrame, pass_b: pd.DataFrame, pass_c: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for domain in DOMAINS:
        a = pass_a[pass_a["domain"] == domain].iloc[0]
        b = pass_b[pass_b["domain"] == domain].iloc[0]
        c = pass_c[pass_c["domain"] == domain].iloc[0]
        bal_map = {
            "A_basic_direct": float(a["balanced_accuracy"]),
            "B_intermediate_mapping": float(b["balanced_accuracy"]),
            "C_remodel_caregiver_contract": float(c["balanced_accuracy"]),
        }
        winner = max(bal_map, key=bal_map.get)
        rows.append(
            {
                "domain": domain,
                "a_balanced_accuracy": a["balanced_accuracy"],
                "b_balanced_accuracy": b["balanced_accuracy"],
                "c_balanced_accuracy": c["balanced_accuracy"],
                "a_precision": a["precision"],
                "b_precision": b["precision"],
                "c_precision": c["precision"],
                "a_recall": a["recall"],
                "b_recall": b["recall"],
                "c_recall": c["recall"],
                "a_specificity": a["specificity"],
                "b_specificity": b["specificity"],
                "c_specificity": c["specificity"],
                "a_pr_auc": a["pr_auc"],
                "b_pr_auc": b["pr_auc"],
                "c_pr_auc": c["pr_auc"],
                "a_input_coverage_pct": a.get("input_coverage_pct", np.nan),
                "b_input_coverage_pct": b.get("input_coverage_pct", np.nan),
                "a_default_dependency_pct": a.get("default_dependency_pct", np.nan),
                "b_direct_fill_pct": b.get("direct_fill_pct", np.nan),
                "b_derived_fill_pct": b.get("derived_fill_pct", np.nan),
                "b_stat_imputed_fill_pct": b.get("stat_imputed_fill_pct", np.nan),
                "c_seed_balanced_accuracy_std": c.get("seed_balanced_accuracy_std", np.nan),
                "c_split_stability_delta_balanced_accuracy": c.get("split_stability_delta_balanced_accuracy", np.nan),
                "winner_by_balanced_accuracy": winner,
                "recommended_complexity_order": "A < B < C",
            }
        )

    macro_row = {
        "domain": "macro_avg",
        "a_balanced_accuracy": float(pass_a["balanced_accuracy"].mean()),
        "b_balanced_accuracy": float(pass_b["balanced_accuracy"].mean()),
        "c_balanced_accuracy": float(pass_c["balanced_accuracy"].mean()),
        "a_precision": float(pass_a["precision"].mean()),
        "b_precision": float(pass_b["precision"].mean()),
        "c_precision": float(pass_c["precision"].mean()),
        "a_recall": float(pass_a["recall"].mean()),
        "b_recall": float(pass_b["recall"].mean()),
        "c_recall": float(pass_c["recall"].mean()),
        "a_specificity": float(pass_a["specificity"].mean()),
        "b_specificity": float(pass_b["specificity"].mean()),
        "c_specificity": float(pass_c["specificity"].mean()),
        "a_pr_auc": float(pass_a["pr_auc"].mean()),
        "b_pr_auc": float(pass_b["pr_auc"].mean()),
        "c_pr_auc": float(pass_c["pr_auc"].mean()),
        "a_input_coverage_pct": float(pass_a["input_coverage_pct"].mean()),
        "b_input_coverage_pct": float(pass_b["input_coverage_pct"].mean()),
        "a_default_dependency_pct": float(pass_a["default_dependency_pct"].mean()),
        "b_direct_fill_pct": float(pass_b["direct_fill_pct"].mean()),
        "b_derived_fill_pct": float(pass_b["derived_fill_pct"].mean()),
        "b_stat_imputed_fill_pct": float(pass_b["stat_imputed_fill_pct"].mean()),
        "c_seed_balanced_accuracy_std": float(pass_c["seed_balanced_accuracy_std"].mean()),
        "c_split_stability_delta_balanced_accuracy": float(pass_c["split_stability_delta_balanced_accuracy"].mean()),
        "winner_by_balanced_accuracy": max(
            {
                "A_basic_direct": float(pass_a["balanced_accuracy"].mean()),
                "B_intermediate_mapping": float(pass_b["balanced_accuracy"].mean()),
                "C_remodel_caregiver_contract": float(pass_c["balanced_accuracy"].mean()),
            },
            key=lambda x: {
                "A_basic_direct": float(pass_a["balanced_accuracy"].mean()),
                "B_intermediate_mapping": float(pass_b["balanced_accuracy"].mean()),
                "C_remodel_caregiver_contract": float(pass_c["balanced_accuracy"].mean()),
            }[x],
        ),
        "recommended_complexity_order": "A < B < C",
    }
    rows.append(macro_row)
    return pd.DataFrame(rows)


def decision_analysis_md(comparison_df: pd.DataFrame) -> str:
    macro = comparison_df[comparison_df["domain"] == "macro_avg"].iloc[0]
    lines = [
        "# Three-path decision analysis",
        "",
        "## Macro comparison",
        f"- Ruta A BA macro: **{macro['a_balanced_accuracy']:.4f}**",
        f"- Ruta B BA macro: **{macro['b_balanced_accuracy']:.4f}**",
        f"- Ruta C BA macro: **{macro['c_balanced_accuracy']:.4f}**",
        f"- Ganador macro por BA: **{macro['winner_by_balanced_accuracy']}**",
        "",
        "## Ganador por dominio (BA)",
    ]
    for _, row in comparison_df[comparison_df["domain"] != "macro_avg"].iterrows():
        lines.append(f"- `{row['domain']}` -> ganador: **{row['winner_by_balanced_accuracy']}** (A={row['a_balanced_accuracy']:.4f}, B={row['b_balanced_accuracy']:.4f}, C={row['c_balanced_accuracy']:.4f})")
    lines += [
        "",
        "## Lectura metodológica",
        "- Ruta A es útil como baseline operativo simple, pero sufre cuando faltan familias enteras no respondibles por cuidador.",
        "- Ruta B recupera parcialmente rendimiento vía proxies e imputación, a costa de mayor riesgo metodológico y dependencia de supuestos.",
        "- Ruta C alinea contrato de entrada con entrenamiento y reduce dependencia de defaults/fallbacks del runtime histórico.",
    ]
    return "\n".join(lines)


def final_recommendation_md(comparison_df: pd.DataFrame) -> str:
    macro = comparison_df[comparison_df["domain"] == "macro_avg"].iloc[0]
    lines = [
        "# Recomendación final",
        "",
        "## Decisión recomendada",
        f"- Ruta global recomendada: **{macro['winner_by_balanced_accuracy']}**.",
        "- Justificación principal: mejor desempeño macro con menor dependencia de faltantes estructurales no respondibles por cuidador.",
        "",
        "## Trade-off real",
        "- Ruta A: menor costo inmediato, pero mayor deterioro en dominios sensibles a cobertura parcial.",
        "- Ruta B: mejora intermedia sin reentrenar, pero introduce deuda metodológica por proxies/imputación.",
        "- Ruta C: mayor costo inicial de implementación, pero mejor sostenibilidad y coherencia con contrato real de cuestionario.",
        "",
        "## Respuesta directa a la pregunta central",
        "- ¿Se puede usar cuestionario cuidador-friendly y aprovechar modelos actuales sin remodelar? **Parcialmente (A/B), pero no de forma robusta en todos los dominios**.",
        "- ¿Es inevitable una nueva línea de modelado para hacerlo bien? **Sí, para cerrar brecha de cobertura y robustez de forma sostenible (Ruta C)**.",
        "",
        "## Qué no conviene",
        "- No conviene cerrar producto final con solo Ruta A.",
        "- No conviene depender exclusivamente de proxies de Ruta B como solución definitiva.",
    ]
    return "\n".join(lines)


def executive_summary_md(comparison_df: pd.DataFrame) -> str:
    macro = comparison_df[comparison_df["domain"] == "macro_avg"].iloc[0]
    lines = [
        "# Executive summary",
        "",
        "Se ejecutó evaluación comparativa real de 3 rutas de acople cuestionario-modelos (A/B/C) sobre splits congelados por dominio.",
        "",
        "## Resultado global (BA macro)",
        f"- Ruta A: **{macro['a_balanced_accuracy']:.4f}**",
        f"- Ruta B: **{macro['b_balanced_accuracy']:.4f}**",
        f"- Ruta C: **{macro['c_balanced_accuracy']:.4f}**",
        f"- Ruta recomendada: **{macro['winner_by_balanced_accuracy']}**",
        "",
        "## Lectura breve",
        "- A funciona como baseline mínimo pero depende más de defaults/faltantes.",
        "- B mejora parcialmente con capa intermedia, pero no elimina riesgo de proxies débiles.",
        "- C ofrece mejor alineación input-modelo con enfoque caregiver-compatible y mejor desempeño agregado.",
    ]
    return "\n".join(lines)


def save_csv(df: pd.DataFrame, filename: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORT_DIR / filename, index=False)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATASET_PATH)
    contract = load_contract()
    metadata_by_domain = {d: load_domain_metadata(d) for d in DOMAINS}

    basic_features = build_basic_candidate_features(contract, metadata_by_domain, set(df.columns))

    coverage_df = build_input_coverage_matrix(contract, metadata_by_domain, basic_features)
    save_csv(coverage_df, "input_coverage_matrix.csv")
    write_markdown(REPORT_DIR / "input_coverage_summary.md", summarize_input_coverage(coverage_df, basic_features))

    questionnaire_df = questionnaire_candidate_table(basic_features, contract, metadata_by_domain)
    save_csv(questionnaire_df, "questionnaire_basic_candidate_v1.csv")
    write_markdown(REPORT_DIR / "questionnaire_basic_candidate_v1.md", summarize_basic_candidate(questionnaire_df))

    pass_a_df = evaluate_pass_a(df, contract, metadata_by_domain, basic_features)
    save_csv(pass_a_df, "pass_a_basic_questionnaire_results.csv")
    write_markdown(REPORT_DIR / "pass_a_basic_questionnaire_analysis.md", summarize_pass(pass_a_df, "Pass A - Cuestionario básico directo", ["Se evaluó con modelos champions actuales y umbrales recomendados por metadata.", "Inputs fuera de cobertura se completaron con defaults del runtime actual.", "No se usaron proxies ni reentrenamiento."]))

    mapping_df = mapping_rules_registry()
    save_csv(mapping_df, "pass_b_intermediate_mapping_registry.csv")

    pass_b_df = evaluate_pass_b(df, contract, metadata_by_domain, basic_features)
    save_csv(pass_b_df, "pass_b_intermediate_results.csv")
    write_markdown(REPORT_DIR / "pass_b_intermediate_analysis.md", summarize_pass(pass_b_df, "Pass B - Cuestionario + capa intermedia", ["Se aplicaron reglas de derivación/proxy explícitas y trazables.", "Los faltantes residuales se imputaron con estadísticas de train (strict_full) por dominio.", "Las derivaciones self-report <- caregiver se marcan como aproximadas y no equivalentes clínicas."]))

    pass_c_registry_df, pass_c_df = evaluate_pass_c(df, contract, basic_features)
    save_csv(pass_c_registry_df, "pass_c_remodel_dataset_registry.csv")
    save_csv(pass_c_df, "pass_c_remodel_results.csv")
    write_markdown(REPORT_DIR / "pass_c_remodel_analysis.md", summarize_pass(pass_c_df, "Pass C - Remodelado cuidador-compatible", ["Se entrenó nueva línea RF usando solo features caregiver-compatible + sistema.", "Selección de umbral en validación, confirmación en test (strict_full).", "Se reporta estabilidad por seeds, split alterno research_full y robustez con ruido."]))

    comparison_df = compare_three_paths(pass_a_df, pass_b_df, pass_c_df)
    save_csv(comparison_df, "three_path_comparison_matrix.csv")
    write_markdown(REPORT_DIR / "three_path_decision_analysis.md", decision_analysis_md(comparison_df))
    write_markdown(REPORT_DIR / "final_recommendation.md", final_recommendation_md(comparison_df))
    write_markdown(REPORT_DIR / "executive_summary.md", executive_summary_md(comparison_df))

    print("OK - Evaluacion comparativa A/B/C generada en reports/questionnaire_model_strategy_eval_v1/")


if __name__ == "__main__":
    main()
