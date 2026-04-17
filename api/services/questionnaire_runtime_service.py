import csv
import json
import random
import re
import string
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from flask import current_app

from api.security import check_password, hash_password, log_audit
from app.models import (
    QRDisclosureVersion,
    QRDomainResult,
    QREvaluation,
    QREvaluationResponse,
    QRExportLog,
    QRNotification,
    QRProcessingJob,
    QRQuestion,
    QRQuestionOption,
    QRQuestionnaireSection,
    QRQuestionnaireTemplate,
    QRQuestionnaireVersion,
    db,
)

DOMAIN_ORDER = ["adhd", "conduct", "elimination", "anxiety", "depression"]

DOMAIN_MODEL_POLICY = {
    "adhd": {
        "model_status": "recovered_generalizing_model",
        "caveat": "Dominio con mejor estabilidad del sistema en esta iteracion.",
    },
    "anxiety": {
        "model_status": "accepted_but_experimental",
        "caveat": "Resultado experimental con buena evidencia interna en entorno simulado.",
    },
    "conduct": {
        "model_status": "accepted_but_experimental",
        "caveat": "Resultado experimental con sesgo potencial a externalizacion global.",
    },
    "depression": {
        "model_status": "accepted_but_experimental",
        "caveat": "Resultado experimental; requiere interpretacion profesional contextual.",
    },
    "elimination": {
        "model_status": "experimental_line_more_useful_not_product_ready",
        "caveat": "Dominio util para tamizaje exploratorio; no product-ready para decision automatica.",
    },
}

DOMAIN_MODEL_REGISTRY = {
    "adhd": "models/champions/rf_adhd_current",
    "anxiety": "models/champions/rf_anxiety_current",
    "conduct": "models/champions/rf_conduct_current",
    "depression": "models/champions/rf_depression_current",
    "elimination": "models/champions/rf_elimination_current",
}

ALLOWED_RESPONSE_TYPES = {
    "single_choice",
    "multi_choice",
    "boolean",
    "integer",
    "likert_single",
    "numeric_range",
    "consent/info_only",
}

ALLOWED_EVALUATION_STATUSES = {
    "draft",
    "submitted",
    "processing",
    "completed",
    "failed",
    "deleted_by_user",
}

REVIEW_TAG_CANONICAL = {
    "sin revisar": "sin_revisar",
    "sin_revisar": "sin_revisar",
    "en revision": "en_revision",
    "en revisión": "en_revision",
    "en_revision": "en_revision",
    "cerrado": "cerrado",
}
ALLOWED_REVIEW_TAGS = set(REVIEW_TAG_CANONICAL.values())
ALLOWED_EXPORT_MODES = {"responses_only", "results_only", "responses_and_results"}
DISCLOSURE_TYPES = {"consent_pre", "disclaimer_pre", "disclaimer_result", "disclaimer_pdf"}

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qr-runtime")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_retention_for_status(status: str) -> datetime:
    now = _utcnow()
    if status == "draft":
        days = int(current_app.config.get("QR_RETENTION_DRAFT_DAYS", 30))
    elif status == "deleted_by_user":
        days = int(current_app.config.get("QR_RETENTION_DELETED_DAYS", 90))
    else:
        days = int(current_app.config.get("QR_RETENTION_COMPLETED_DAYS", 1095))
    return now + timedelta(days=days)


def _notification_expiry() -> datetime:
    days = int(current_app.config.get("QR_RETENTION_NOTIFICATION_DAYS", 180))
    return _utcnow() + timedelta(days=days)


def _generate_reference_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return f"QRY-{''.join(random.choice(alphabet) for _ in range(8))}"


def _unique_reference_id(max_attempts: int = 10) -> str:
    for _ in range(max_attempts):
        candidate = _generate_reference_id()
        if not QREvaluation.query.filter_by(reference_id=candidate).first():
            return candidate
    raise RuntimeError("reference_id_generation_failed")


def _generate_pin() -> str:
    return f"{random.randint(0, 999999):06d}"


def hash_pin(pin: str) -> str:
    return hash_password(pin)


def verify_pin(pin: str, pin_hash: str) -> bool:
    return check_password(pin, pin_hash)


@lru_cache(maxsize=1)
def _feature_contract_map() -> dict[str, dict[str, Any]]:
    path = Path("artifacts/specs/questionnaire_feature_contract.csv")
    contract: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return contract
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feature = (row.get("feature_final") or "").strip()
            if not feature:
                continue
            min_value = None
            max_value = None
            raw_range = (row.get("rango_esperado") or "").strip()
            if "|" in raw_range:
                left, right = raw_range.split("|", 1)
                try:
                    min_value = float(left)
                    max_value = float(right)
                except ValueError:
                    min_value = None
                    max_value = None
            options = (row.get("opciones_permitidas") or "").strip()
            opts = [o.strip() for o in options.split("|") if o.strip()] if options else []
            contract[feature] = {
                "min": min_value,
                "max": max_value,
                "options": opts,
                "domain": (row.get("trastorno_relacionado") or "general").strip() or "general",
                "requiredness": (row.get("requerida_opcional") or "optional").strip() or "optional",
            }
    return contract


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        if raw.lower() in {"true", "false"}:
            return float(1 if raw.lower() == "true" else 0)
        try:
            return float(raw)
        except ValueError:
            return default
    return default


def _default_for_feature(feature: str) -> Any:
    contract = _feature_contract_map().get(feature, {})
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

    min_value = contract.get("min")
    max_value = contract.get("max")
    if min_value is not None and max_value is not None:
        return round((float(min_value) + float(max_value)) / 2.0, 4)

    options = contract.get("options") or []
    if options:
        num = _safe_float(options[0])
        return num if num is not None else options[0]
    return 0.0


def _normalize_sex(value: Any) -> str:
    if value is None:
        return "Unknown"
    raw = str(value).strip().lower()
    if raw in {"m", "male", "masculino", "1"}:
        return "Male"
    if raw in {"f", "female", "femenino", "0"}:
        return "Female"
    return "Unknown"


def _normalize_site(value: Any) -> str:
    if not value:
        return "CBIC"
    raw = str(value).strip()
    if raw in {"CBIC", "CUNY", "RUBIC", "Staten Island"}:
        return raw
    return "CBIC"


def _extract_feature_from_top(top_item: str) -> str | None:
    if top_item.startswith("num__"):
        return top_item.split("num__", 1)[1]
    if top_item.startswith("cat__sex_assigned_at_birth"):
        return "sex_assigned_at_birth"
    if top_item.startswith("cat__site"):
        return "site"
    return None


def _question_type_for_feature(feature: str) -> str:
    if feature in {"sex_assigned_at_birth", "site"}:
        return "single_choice"
    if feature.startswith("has_"):
        return "boolean"

    contract = _feature_contract_map().get(feature, {})
    options = contract.get("options") or []
    min_value = contract.get("min")
    max_value = contract.get("max")

    if options and len(options) <= 6:
        return "single_choice"
    if min_value is not None and max_value is not None:
        if min_value >= 0 and max_value <= 4 and float(min_value).is_integer() and float(max_value).is_integer():
            return "likert_single"
        if float(min_value).is_integer() and float(max_value).is_integer():
            return "integer"
        return "numeric_range"
    if feature.endswith("_total") or feature.endswith("_proxy"):
        return "numeric_range"
    return "numeric_range"


def _question_options_for_feature(feature: str) -> list[dict[str, str]]:
    if feature == "sex_assigned_at_birth":
        return [
            {"value": "Female", "label": "Femenino"},
            {"value": "Male", "label": "Masculino"},
            {"value": "Unknown", "label": "Prefiero no responder"},
        ]
    if feature == "site":
        return [
            {"value": "CBIC", "label": "CBIC"},
            {"value": "CUNY", "label": "CUNY"},
            {"value": "RUBIC", "label": "RUBIC"},
            {"value": "Staten Island", "label": "Staten Island"},
        ]

    contract = _feature_contract_map().get(feature, {})
    options = contract.get("options") or []
    if options:
        return [{"value": str(opt), "label": str(opt)} for opt in options]
    if feature.startswith("has_"):
        return [{"value": "0", "label": "No"}, {"value": "1", "label": "Si"}]
    return []


def _question_prompt_from_feature(feature: str) -> str:
    text = feature.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return f"Reporte el valor para {text}."


def _feature_domain(feature: str) -> str:
    contract = _feature_contract_map().get(feature, {})
    domain = (contract.get("domain") or "general").strip().lower()
    if domain in {"adhd", "conduct", "anxiety", "depression", "elimination"}:
        return domain
    if feature.startswith(("conners", "swan", "ysr")):
        return "adhd"
    if feature.startswith(("ari", "icut")):
        return "conduct"
    if feature.startswith(("scared",)):
        return "anxiety"
    if feature.startswith(("mfq", "cdi")):
        return "depression"
    if feature.startswith(("cbcl", "sdq")):
        return "elimination"
    return "general"


def _coerce_answer(feature: str, response_type: str, value: Any) -> tuple[Any, str]:
    if response_type == "single_choice":
        if feature == "sex_assigned_at_birth":
            normalized = _normalize_sex(value)
            return normalized, normalized
        if feature == "site":
            normalized = _normalize_site(value)
            return normalized, normalized
        normalized = str(value)
        return normalized, normalized
    if response_type == "multi_choice":
        if not isinstance(value, list):
            raise ValueError("multi_choice_invalid")
        normalized = [str(v) for v in value]
        return normalized, json.dumps(normalized)
    if response_type == "boolean":
        raw = str(value).strip().lower()
        if raw in {"1", "true", "si", "yes"}:
            return 1, "1"
        if raw in {"0", "false", "no"}:
            return 0, "0"
        numeric = _safe_float(value)
        if numeric in {0.0, 1.0}:
            return int(numeric), str(int(numeric))
        raise ValueError("boolean_invalid")
    if response_type in {"integer", "likert_single"}:
        numeric = _safe_float(value)
        if numeric is None:
            raise ValueError("integer_invalid")
        return int(round(numeric)), str(int(round(numeric)))
    if response_type == "numeric_range":
        numeric = _safe_float(value)
        if numeric is None:
            raise ValueError("numeric_invalid")
        return float(numeric), str(float(numeric))
    if response_type == "consent/info_only":
        return str(value), str(value)
    raise ValueError("unsupported_response_type")


class DomainRuntime:
    def __init__(self, domain: str, model: Any, metadata: dict[str, Any], model_path: str, model_kind: str):
        self.domain = domain
        self.model = model
        self.metadata = metadata
        self.model_path = model_path
        self.model_kind = model_kind
        self.feature_columns = metadata.get("feature_columns") or []
        self.threshold = float(metadata.get("recommended_threshold", 0.5))
        self.risk_band_policy = metadata.get("risk_band_policy") or {"low_lt": 0.33, "moderate_lt": 0.66, "high_ge": 0.66}
        self.top_features = metadata.get("top_features") or []
        self.version = metadata.get("version") or metadata.get("version_tag") or "unknown"


class _TestingBinaryModel:
    def __init__(self, positive_probability: float = 0.35):
        self.positive_probability = float(positive_probability)

    def predict_proba(self, X):
        rows = len(X.index) if hasattr(X, "index") else len(X)
        negative = max(0.0, min(1.0, 1.0 - self.positive_probability))
        return [[negative, self.positive_probability] for _ in range(rows)]


_TESTING_FEATURE_BY_DOMAIN = {
    "adhd": "conners_attention_proxy",
    "conduct": "ari_behavior_proxy",
    "elimination": "cbcl_elimination_proxy",
    "anxiety": "scared_anxiety_proxy",
    "depression": "mfq_mood_proxy",
}


def _testing_runtime_fallback(domain: str, reason: str) -> DomainRuntime:
    feature_name = _TESTING_FEATURE_BY_DOMAIN.get(domain, f"{domain}_proxy_feature")
    metadata = {
        "feature_columns": ["age_years", "sex_assigned_at_birth", "site", "release", feature_name],
        "recommended_threshold": 0.5,
        "risk_band_policy": {"low_lt": 0.33, "moderate_lt": 0.66, "high_ge": 0.66},
        "top_features": [f"num__{feature_name}"],
        "version": "testing_fallback",
        "fallback_reason": reason,
    }
    return DomainRuntime(
        domain=domain,
        model=_TestingBinaryModel(),
        metadata=metadata,
        model_path=f"testing_fallback:{domain}",
        model_kind="testing_fallback",
    )


@lru_cache(maxsize=16)
def load_domain_runtime(domain: str) -> DomainRuntime:
    base_dir = DOMAIN_MODEL_REGISTRY[domain]
    metadata_path = Path(base_dir) / "metadata.json"
    if not metadata_path.exists():
        if current_app.testing:
            current_app.logger.warning("Using testing fallback runtime for %s: metadata missing", domain)
            return _testing_runtime_fallback(domain, f"metadata_not_found:{metadata_path}")
        raise FileNotFoundError(f"metadata_not_found:{metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    calibrated_path = Path(base_dir) / "calibrated.joblib"
    pipeline_path = Path(base_dir) / "pipeline.joblib"
    if calibrated_path.exists():
        model = joblib.load(calibrated_path)
        model_path = str(calibrated_path)
        model_kind = "calibrated"
    elif pipeline_path.exists():
        model = joblib.load(pipeline_path)
        model_path = str(pipeline_path)
        model_kind = "pipeline"
    else:
        if current_app.testing:
            current_app.logger.warning("Using testing fallback runtime for %s: model artifact missing", domain)
            return _testing_runtime_fallback(domain, f"model_artifact_not_found:{base_dir}")
        raise FileNotFoundError(f"model_artifact_not_found:{base_dir}")
    return DomainRuntime(domain, model, metadata, model_path, model_kind)


def _runtime_bundle_version() -> str:
    return "questionnaire_runtime_v1"


def _risk_band(probability: float, policy: dict[str, Any]) -> str:
    low_lt = float(policy.get("low_lt", 0.33))
    moderate_lt = float(policy.get("moderate_lt", 0.66))
    high_ge = float(policy.get("high_ge", moderate_lt))
    if probability < low_lt:
        return "low"
    if probability < moderate_lt:
        return "moderate"
    if probability >= high_ge:
        return "high"
    return "moderate"


def _confidence_level(probability: float, threshold: float) -> str:
    delta = abs(probability - threshold)
    if delta >= 0.25:
        return "high"
    if delta >= 0.12:
        return "medium"
    return "low"


def _uncertainty(probability: float, threshold: float) -> bool:
    return abs(probability - threshold) < 0.08


def _evidence_level(feature_map: dict[str, Any], feature_columns: list[str]) -> str:
    if not feature_columns:
        return "weak"
    answered = 0
    for col in feature_columns:
        val = feature_map.get(col)
        default = _default_for_feature(col)
        if val is None:
            continue
        if str(val) != str(default):
            answered += 1
    ratio = answered / max(len(feature_columns), 1)
    if ratio >= 0.5:
        return "strong"
    if ratio >= 0.25:
        return "medium"
    return "weak"


def _build_feature_vector(feature_map: dict[str, Any], feature_columns: list[str]) -> dict[str, Any]:
    vector = {}
    for col in feature_columns:
        if col in feature_map:
            val = feature_map[col]
        else:
            val = _default_for_feature(col)

        if col == "sex_assigned_at_birth":
            val = _normalize_sex(val)
        elif col == "site":
            val = _normalize_site(val)
        elif isinstance(val, str):
            maybe = _safe_float(val)
            if maybe is not None and col not in {"sex_assigned_at_birth", "site"}:
                val = maybe
        vector[col] = val
    return vector


def _explanation(runtime: DomainRuntime, vector: dict[str, Any], threshold: float, probability: float) -> tuple[str, list[dict[str, Any]]]:
    extracted = []
    for feat in runtime.top_features:
        base = _extract_feature_from_top(feat)
        if base and base in vector:
            extracted.append(base)
    if not extracted:
        extracted = [c for c in runtime.feature_columns[:5]]
    contributors = []
    for key in extracted[:5]:
        contributors.append({"feature": key, "value": vector.get(key), "default_used": str(vector.get(key)) == str(_default_for_feature(key))})
    if _uncertainty(probability, threshold):
        explanation = "Resultado cercano al umbral; se recomienda revision profesional y mayor evidencia."
    elif probability >= threshold:
        explanation = "El patron de respuestas es compatible con riesgo elevado para este dominio."
    else:
        explanation = "El patron de respuestas no supera el umbral de riesgo para este dominio."
    return explanation, contributors


def _domain_recommendation(domain: str, probability: float, threshold: float, uncertainty: bool) -> str:
    if uncertainty:
        return f"{domain.upper()}: salida incierta. Recolecte informacion adicional y priorice revision por profesional."
    if probability >= threshold:
        return f"{domain.upper()}: riesgo elevado. Use este resultado como alerta temprana y consulte profesional."
    return f"{domain.upper()}: riesgo no elevado en esta evaluacion simulada. Mantenga seguimiento preventivo."


def run_runtime_inference(feature_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    domain_results: dict[str, dict[str, Any]] = {}
    for domain in DOMAIN_ORDER:
        runtime = load_domain_runtime(domain)
        vector = _build_feature_vector(feature_map, runtime.feature_columns)
        X = pd.DataFrame([vector], columns=runtime.feature_columns)
        if not hasattr(runtime.model, "predict_proba"):
            raise RuntimeError(f"model_without_predict_proba:{domain}")
        probability = float(runtime.model.predict_proba(X)[0][1])
        threshold = float(runtime.threshold)
        risk_band = _risk_band(probability, runtime.risk_band_policy)
        confidence = _confidence_level(probability, threshold)
        uncertainty_flag = _uncertainty(probability, threshold)
        evidence_level = _evidence_level(feature_map, runtime.feature_columns)
        explanation, contributors = _explanation(runtime, vector, threshold, probability)
        recommendation = _domain_recommendation(domain, probability, threshold, uncertainty_flag)
        model_policy = DOMAIN_MODEL_POLICY[domain]
        domain_results[domain] = {
            "domain": domain,
            "probability": probability,
            "threshold_used": threshold,
            "risk_band": risk_band,
            "confidence_level": confidence,
            "evidence_level": evidence_level,
            "uncertainty_flag": uncertainty_flag,
            "abstention_flag": uncertainty_flag,
            "recommendation_text": recommendation,
            "explanation_short": explanation,
            "contributors": contributors,
            "model_name": Path(runtime.model_path).name,
            "model_version": runtime.version,
            "model_status": model_policy["model_status"],
            "caveats": [model_policy["caveat"]],
        }
    return domain_results


DEFAULT_DISCLOSURES = {
    "consent_pre": {
        "title": "Consentimiento informado para tamizaje digital",
        "content_markdown": (
            "Declaro que respondo este cuestionario como cuidador responsable y autorizo el "
            "uso de las respuestas para una evaluacion digital de alerta temprana. Entiendo "
            "que esta herramienta no reemplaza la valoracion clinica presencial."
        ),
    },
    "disclaimer_pre": {
        "title": "Aviso previo de uso",
        "content_markdown": (
            "Este cuestionario es un instrumento de tamizaje experimental basado en datos "
            "simulados. No constituye diagnostico clinico definitivo ni indicacion terapeutica."
        ),
    },
    "disclaimer_result": {
        "title": "Interpretacion de resultados",
        "content_markdown": (
            "Los resultados representan estimaciones probabilisticas por dominio y deben "
            "interpretarse junto con evaluacion profesional. Ante riesgo moderado/alto o "
            "salida incierta, se recomienda consulta clinica."
        ),
    },
    "disclaimer_pdf": {
        "title": "Uso del reporte exportado",
        "content_markdown": (
            "Este reporte es de apoyo para seguimiento y comunicacion profesional. No equivale "
            "a un diagnostico medico o psicologico definitivo."
        ),
    },
}


def canonical_review_tag(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in REVIEW_TAG_CANONICAL:
        raise ValueError("invalid_review_tag")
    return REVIEW_TAG_CANONICAL[key]


def _serialize_disclosures(version_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    items = (
        QRDisclosureVersion.query.filter_by(questionnaire_version_id=version_id, is_active=True)
        .order_by(QRDisclosureVersion.created_at.desc())
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in items:
        if row.disclosure_type in out:
            continue
        out[row.disclosure_type] = {
            "id": str(row.id),
            "type": row.disclosure_type,
            "version_label": row.version_label,
            "title": row.title,
            "content_markdown": row.content_markdown,
        }
    return out


def _active_version() -> QRQuestionnaireVersion | None:
    return (
        QRQuestionnaireVersion.query.filter_by(is_published=True, status="published")
        .order_by(QRQuestionnaireVersion.published_at.desc(), QRQuestionnaireVersion.created_at.desc())
        .first()
    )


def _default_question_features() -> list[str]:
    selected: list[str] = ["age_years", "sex_assigned_at_birth", "site", "release"]
    seen = set(selected)
    for domain in DOMAIN_ORDER:
        runtime = load_domain_runtime(domain)
        top = runtime.top_features or []
        extracted = []
        for feat in top:
            base = _extract_feature_from_top(feat)
            if base:
                extracted.append(base)
        if not extracted:
            extracted = runtime.feature_columns[:12]
        for feat in extracted[:12]:
            if feat and feat not in seen:
                seen.add(feat)
                selected.append(feat)
    return selected


def _domain_section_key(feature: str) -> str:
    if feature in {"age_years", "sex_assigned_at_birth", "site", "release"}:
        return "contexto"
    domain = _feature_domain(feature)
    if domain in DOMAIN_ORDER:
        return f"dominio_{domain}"
    return "dominio_general"


def _visibility_rule_for_feature(feature: str, all_features: set[str]) -> dict[str, Any] | None:
    instrument_pairs = [
        ("cbcl_", "has_cbcl"),
        ("conners_", "has_conners"),
        ("swan_", "has_swan"),
        ("scared_", "has_scared_p"),
        ("mfq_", "has_mfq_p"),
        ("ari_", "has_ari_p"),
        ("icut_", "has_icut"),
        ("ysr_", "has_ysr"),
        ("cdi_", "has_cdi"),
        ("sdq_", "has_sdq"),
    ]
    for prefix, gate in instrument_pairs:
        if feature.startswith(prefix) and gate in all_features:
            return {"all": [{"feature_key": gate, "operator": "==", "value": 1}]}
    return None


def _build_default_questionnaire_version(version: QRQuestionnaireVersion, created_by: uuid.UUID | None) -> None:
    features = _default_question_features()
    feature_set = set(features)
    section_defs = [
        ("contexto", "Contexto base", "Datos minimos para iniciar la evaluacion."),
        ("dominio_adhd", "Dominio ADHD", "Seccion de senales relacionadas con atencion e impulsividad."),
        ("dominio_conduct", "Dominio Conduct", "Seccion de comportamiento disruptivo y regulacion conductual."),
        ("dominio_elimination", "Dominio Elimination", "Seccion de senales de eliminacion con cautela clinica."),
        ("dominio_anxiety", "Dominio Anxiety", "Seccion de ansiedad y evitacion."),
        ("dominio_depression", "Dominio Depression", "Seccion de animo y sintomas depresivos."),
        ("dominio_general", "Senales generales", "Indicadores transversales de apoyo al modelo."),
    ]
    section_map: dict[str, QRQuestionnaireSection] = {}
    for pos, (key, title, desc) in enumerate(section_defs, start=1):
        section = QRQuestionnaireSection(
            questionnaire_version_id=version.id,
            key=key,
            title=title,
            description=desc,
            position=pos,
            is_required=True,
        )
        db.session.add(section)
        section_map[key] = section
    db.session.flush()

    question_pos_by_section: dict[str, int] = {k: 0 for k in section_map}
    for feature in features:
        section_key = _domain_section_key(feature)
        if section_key not in section_map:
            section_key = "dominio_general"
        question_pos_by_section[section_key] += 1
        response_type = _question_type_for_feature(feature)
        if response_type not in ALLOWED_RESPONSE_TYPES:
            response_type = "numeric_range"
        question = QRQuestion(
            section_id=section_map[section_key].id,
            key=f"q_{feature}",
            feature_key=feature,
            domain=_feature_domain(feature),
            prompt=_question_prompt_from_feature(feature),
            help_text="Respuesta de tamizaje para inferencia probabilistica.",
            response_type=response_type,
            requiredness="required" if feature in {"age_years", "sex_assigned_at_birth"} else "optional",
            position=question_pos_by_section[section_key],
            min_value=_feature_contract_map().get(feature, {}).get("min"),
            max_value=_feature_contract_map().get(feature, {}).get("max"),
            step_value=1.0,
            allowed_values=[o["value"] for o in _question_options_for_feature(feature)] or None,
            visibility_rule=_visibility_rule_for_feature(feature, feature_set),
            is_active=True,
        )
        db.session.add(question)
        db.session.flush()
        options = _question_options_for_feature(feature)
        for opt_pos, opt in enumerate(options, start=1):
            db.session.add(
                QRQuestionOption(
                    question_id=question.id,
                    option_value=str(opt["value"]),
                    option_label=str(opt["label"]),
                    position=opt_pos,
                )
            )


def _ensure_disclosures(version: QRQuestionnaireVersion, created_by: uuid.UUID | None) -> None:
    existing = _serialize_disclosures(version.id)
    for disclosure_type in DISCLOSURE_TYPES:
        if disclosure_type in existing:
            continue
        spec = DEFAULT_DISCLOSURES[disclosure_type]
        row = QRDisclosureVersion(
            questionnaire_version_id=version.id,
            disclosure_type=disclosure_type,
            version_label="v1",
            title=spec["title"],
            content_markdown=spec["content_markdown"],
            is_active=True,
            created_by_user_id=created_by,
        )
        db.session.add(row)


def ensure_runtime_bootstrap(created_by: uuid.UUID | None = None) -> QRQuestionnaireVersion:
    active = _active_version()
    if active:
        return active

    template = QRQuestionnaireTemplate.query.filter_by(slug="cuestionario-real-v1").first()
    if not template:
        template = QRQuestionnaireTemplate(
            slug="cuestionario-real-v1",
            name="Cuestionario real CognIA v1",
            description="Version operativa multipaso para tamizaje de 5 dominios.",
            is_active=True,
            created_by_user_id=created_by,
        )
        db.session.add(template)
        db.session.flush()

    version = QRQuestionnaireVersion(
        template_id=template.id,
        version_label="v1.0.0",
        changelog="Version inicial operativa del cuestionario real.",
        status="published",
        is_published=True,
        published_at=_utcnow(),
        created_by_user_id=created_by,
    )
    db.session.add(version)
    db.session.flush()

    _build_default_questionnaire_version(version, created_by)
    _ensure_disclosures(version, created_by)
    db.session.commit()
    return version


def serialize_questionnaire(version: QRQuestionnaireVersion) -> dict[str, Any]:
    sections = (
        QRQuestionnaireSection.query.filter_by(questionnaire_version_id=version.id)
        .order_by(QRQuestionnaireSection.position.asc())
        .all()
    )
    questions = (
        QRQuestion.query.join(QRQuestionnaireSection, QRQuestion.section_id == QRQuestionnaireSection.id)
        .filter(QRQuestionnaireSection.questionnaire_version_id == version.id, QRQuestion.is_active.is_(True))
        .order_by(QRQuestionnaireSection.position.asc(), QRQuestion.position.asc())
        .all()
    )
    options_by_question: dict[uuid.UUID, list[dict[str, Any]]] = {}
    if questions:
        q_ids = [q.id for q in questions]
        options = (
            QRQuestionOption.query.filter(QRQuestionOption.question_id.in_(q_ids))
            .order_by(QRQuestionOption.question_id.asc(), QRQuestionOption.position.asc())
            .all()
        )
        for option in options:
            options_by_question.setdefault(option.question_id, []).append(
                {
                    "value": option.option_value,
                    "label": option.option_label,
                    "position": option.position,
                }
            )

    section_map: dict[uuid.UUID, dict[str, Any]] = {}
    for section in sections:
        section_map[section.id] = {
            "id": str(section.id),
            "key": section.key,
            "title": section.title,
            "description": section.description,
            "position": section.position,
            "is_required": section.is_required,
            "questions": [],
        }
    for question in questions:
        section_map[question.section_id]["questions"].append(
            {
                "id": str(question.id),
                "key": question.key,
                "feature_key": question.feature_key,
                "domain": question.domain,
                "prompt": question.prompt,
                "help_text": question.help_text,
                "response_type": question.response_type,
                "requiredness": question.requiredness,
                "position": question.position,
                "min_value": question.min_value,
                "max_value": question.max_value,
                "step_value": question.step_value,
                "allowed_values": question.allowed_values,
                "visibility_rule": question.visibility_rule,
                "options": options_by_question.get(question.id, []),
            }
        )

    disclosures = _serialize_disclosures(version.id)
    return {
        "template_version": {
            "id": str(version.id),
            "template_id": str(version.template_id),
            "version_label": version.version_label,
            "status": version.status,
            "is_published": bool(version.is_published),
            "published_at": version.published_at.isoformat() if version.published_at else None,
        },
        "disclosures": disclosures,
        "sections": list(section_map.values()),
    }


def get_active_questionnaire_payload() -> dict[str, Any]:
    version = ensure_runtime_bootstrap()
    return serialize_questionnaire(version)


def create_template(payload: dict[str, Any], created_by: uuid.UUID | None) -> QRQuestionnaireTemplate:
    slug = (payload.get("slug") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    if not slug or not name:
        raise ValueError("invalid_template_payload")
    if QRQuestionnaireTemplate.query.filter_by(slug=slug).first():
        raise ValueError("template_slug_exists")
    template = QRQuestionnaireTemplate(
        slug=slug,
        name=name,
        description=(payload.get("description") or "").strip() or None,
        is_active=bool(payload.get("is_active", True)),
        created_by_user_id=created_by,
    )
    db.session.add(template)
    db.session.commit()
    return template


def create_template_version(
    template_id: uuid.UUID,
    payload: dict[str, Any],
    created_by: uuid.UUID | None,
) -> QRQuestionnaireVersion:
    template = db.session.get(QRQuestionnaireTemplate, template_id)
    if not template:
        raise LookupError("template_not_found")
    version_label = (payload.get("version_label") or "").strip()
    if not version_label:
        raise ValueError("invalid_version_label")
    if QRQuestionnaireVersion.query.filter_by(template_id=template.id, version_label=version_label).first():
        raise ValueError("template_version_exists")
    version = QRQuestionnaireVersion(
        template_id=template.id,
        version_label=version_label,
        changelog=(payload.get("changelog") or "").strip() or None,
        status="draft",
        is_published=False,
        created_by_user_id=created_by,
    )
    db.session.add(version)
    db.session.flush()

    if payload.get("clone_from_active", False):
        source = _active_version()
        if source:
            source_sections = (
                QRQuestionnaireSection.query.filter_by(questionnaire_version_id=source.id)
                .order_by(QRQuestionnaireSection.position.asc())
                .all()
            )
            source_questions = (
                QRQuestion.query.join(QRQuestionnaireSection, QRQuestion.section_id == QRQuestionnaireSection.id)
                .filter(QRQuestionnaireSection.questionnaire_version_id == source.id)
                .order_by(QRQuestionnaireSection.position.asc(), QRQuestion.position.asc())
                .all()
            )
            section_id_map: dict[uuid.UUID, uuid.UUID] = {}
            for section in source_sections:
                copy = QRQuestionnaireSection(
                    questionnaire_version_id=version.id,
                    key=section.key,
                    title=section.title,
                    description=section.description,
                    position=section.position,
                    is_required=section.is_required,
                )
                db.session.add(copy)
                db.session.flush()
                section_id_map[section.id] = copy.id
            question_id_map: dict[uuid.UUID, uuid.UUID] = {}
            for question in source_questions:
                copy_q = QRQuestion(
                    section_id=section_id_map[question.section_id],
                    key=question.key,
                    feature_key=question.feature_key,
                    domain=question.domain,
                    prompt=question.prompt,
                    help_text=question.help_text,
                    response_type=question.response_type,
                    requiredness=question.requiredness,
                    position=question.position,
                    min_value=question.min_value,
                    max_value=question.max_value,
                    step_value=question.step_value,
                    allowed_values=question.allowed_values,
                    visibility_rule=question.visibility_rule,
                    is_active=question.is_active,
                )
                db.session.add(copy_q)
                db.session.flush()
                question_id_map[question.id] = copy_q.id
            if question_id_map:
                source_options = QRQuestionOption.query.filter(
                    QRQuestionOption.question_id.in_(list(question_id_map.keys()))
                ).all()
                for opt in source_options:
                    db.session.add(
                        QRQuestionOption(
                            question_id=question_id_map[opt.question_id],
                            option_value=opt.option_value,
                            option_label=opt.option_label,
                            position=opt.position,
                        )
                    )
            source_disclosures = QRDisclosureVersion.query.filter_by(
                questionnaire_version_id=source.id, is_active=True
            ).all()
            for disc in source_disclosures:
                db.session.add(
                    QRDisclosureVersion(
                        questionnaire_version_id=version.id,
                        disclosure_type=disc.disclosure_type,
                        version_label=disc.version_label,
                        title=disc.title,
                        content_markdown=disc.content_markdown,
                        is_active=True,
                        created_by_user_id=created_by,
                    )
                )

    _ensure_disclosures(version, created_by)
    db.session.commit()
    return version


def publish_template_version(version_id: uuid.UUID) -> QRQuestionnaireVersion:
    version = db.session.get(QRQuestionnaireVersion, version_id)
    if not version:
        raise LookupError("version_not_found")

    has_sections = QRQuestionnaireSection.query.filter_by(questionnaire_version_id=version.id).count() > 0
    if not has_sections:
        raise ValueError("version_without_sections")
    has_questions = (
        QRQuestion.query.join(QRQuestionnaireSection, QRQuestion.section_id == QRQuestionnaireSection.id)
        .filter(QRQuestionnaireSection.questionnaire_version_id == version.id)
        .count()
        > 0
    )
    if not has_questions:
        raise ValueError("version_without_questions")

    disclosures = _serialize_disclosures(version.id)
    missing = DISCLOSURE_TYPES.difference(disclosures.keys())
    if missing:
        raise ValueError("missing_disclosures")

    QRQuestionnaireVersion.query.filter(
        QRQuestionnaireVersion.template_id == version.template_id,
        QRQuestionnaireVersion.id != version.id,
        QRQuestionnaireVersion.is_published.is_(True),
    ).update({"is_published": False, "status": "archived"}, synchronize_session=False)

    version.is_published = True
    version.status = "published"
    version.published_at = _utcnow()
    db.session.add(version)
    db.session.commit()
    return version


def create_or_update_disclosure(
    questionnaire_version_id: uuid.UUID,
    payload: dict[str, Any],
    created_by: uuid.UUID | None,
) -> QRDisclosureVersion:
    disclosure_type = (payload.get("disclosure_type") or "").strip()
    if disclosure_type not in DISCLOSURE_TYPES:
        raise ValueError("invalid_disclosure_type")
    version_label = (payload.get("version_label") or "").strip() or "v1"
    title = (payload.get("title") or "").strip()
    content_markdown = (payload.get("content_markdown") or "").strip()
    if not title or not content_markdown:
        raise ValueError("invalid_disclosure_payload")

    version = db.session.get(QRQuestionnaireVersion, questionnaire_version_id)
    if not version:
        raise LookupError("version_not_found")

    row = (
        QRDisclosureVersion.query.filter_by(
            questionnaire_version_id=questionnaire_version_id,
            disclosure_type=disclosure_type,
            version_label=version_label,
        ).first()
    )
    if row:
        row.title = title
        row.content_markdown = content_markdown
        row.is_active = True
    else:
        row = QRDisclosureVersion(
            questionnaire_version_id=questionnaire_version_id,
            disclosure_type=disclosure_type,
            version_label=version_label,
            title=title,
            content_markdown=content_markdown,
            is_active=True,
            created_by_user_id=created_by,
        )
        db.session.add(row)
    db.session.commit()
    return row


def create_section(questionnaire_version_id: uuid.UUID, payload: dict[str, Any]) -> QRQuestionnaireSection:
    version = db.session.get(QRQuestionnaireVersion, questionnaire_version_id)
    if not version:
        raise LookupError("version_not_found")
    section = QRQuestionnaireSection(
        questionnaire_version_id=questionnaire_version_id,
        key=(payload.get("key") or "").strip(),
        title=(payload.get("title") or "").strip(),
        description=(payload.get("description") or "").strip() or None,
        position=int(payload.get("position", 1)),
        is_required=bool(payload.get("is_required", True)),
    )
    if not section.key or not section.title:
        raise ValueError("invalid_section_payload")
    db.session.add(section)
    db.session.commit()
    return section


def create_question(section_id: uuid.UUID, payload: dict[str, Any]) -> QRQuestion:
    section = db.session.get(QRQuestionnaireSection, section_id)
    if not section:
        raise LookupError("section_not_found")
    response_type = (payload.get("response_type") or "").strip()
    if response_type not in ALLOWED_RESPONSE_TYPES:
        raise ValueError("invalid_response_type")
    question = QRQuestion(
        section_id=section_id,
        key=(payload.get("key") or "").strip(),
        feature_key=(payload.get("feature_key") or "").strip(),
        domain=(payload.get("domain") or "general").strip().lower(),
        prompt=(payload.get("prompt") or "").strip(),
        help_text=(payload.get("help_text") or "").strip() or None,
        response_type=response_type,
        requiredness=(payload.get("requiredness") or "required").strip(),
        position=int(payload.get("position", 1)),
        min_value=_safe_float(payload.get("min_value")),
        max_value=_safe_float(payload.get("max_value")),
        step_value=_safe_float(payload.get("step_value")),
        allowed_values=payload.get("allowed_values"),
        visibility_rule=payload.get("visibility_rule"),
        is_active=bool(payload.get("is_active", True)),
    )
    if not question.key or not question.feature_key or not question.prompt:
        raise ValueError("invalid_question_payload")
    db.session.add(question)
    db.session.flush()
    options = payload.get("options") or []
    for idx, opt in enumerate(options, start=1):
        value = str(opt.get("value", "")).strip()
        label = str(opt.get("label", "")).strip()
        if not value or not label:
            continue
        db.session.add(
            QRQuestionOption(
                question_id=question.id,
                option_value=value,
                option_label=label,
                position=idx,
            )
        )
    db.session.commit()
    return question


def list_template_versions(template_id: uuid.UUID) -> list[dict[str, Any]]:
    versions = (
        QRQuestionnaireVersion.query.filter_by(template_id=template_id)
        .order_by(QRQuestionnaireVersion.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(v.id),
            "template_id": str(v.template_id),
            "version_label": v.version_label,
            "status": v.status,
            "is_published": bool(v.is_published),
            "published_at": v.published_at.isoformat() if v.published_at else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


def set_template_active(template_id: uuid.UUID, is_active: bool) -> QRQuestionnaireTemplate:
    template = db.session.get(QRQuestionnaireTemplate, template_id)
    if not template:
        raise LookupError("template_not_found")
    if is_active:
        QRQuestionnaireTemplate.query.filter(
            QRQuestionnaireTemplate.id != template.id
        ).update({"is_active": False}, synchronize_session=False)
    template.is_active = bool(is_active)
    db.session.add(template)
    db.session.commit()
    return template


def _questionnaire_question_index(version_id: uuid.UUID) -> dict[str, QRQuestion]:
    questions = (
        QRQuestion.query.join(QRQuestionnaireSection, QRQuestion.section_id == QRQuestionnaireSection.id)
        .filter(QRQuestionnaireSection.questionnaire_version_id == version_id, QRQuestion.is_active.is_(True))
        .all()
    )
    out: dict[str, QRQuestion] = {}
    for q in questions:
        out[str(q.id)] = q
        out[q.key] = q
        out[q.feature_key] = q
    return out


def _resolve_answer_items(
    evaluation: QREvaluation, answers: list[dict[str, Any]]
) -> list[tuple[QRQuestion, Any, str]]:
    index = _questionnaire_question_index(evaluation.questionnaire_version_id)
    resolved: list[tuple[QRQuestion, Any, str]] = []
    for item in answers:
        identifier = item.get("question_id") or item.get("question_key") or item.get("feature_key")
        if not identifier:
            raise ValueError("missing_question_identifier")
        question = index.get(str(identifier))
        if not question:
            raise ValueError("invalid_question_identifier")
        raw_answer = item.get("value")
        normalized_raw, normalized_txt = _coerce_answer(question.feature_key, question.response_type, raw_answer)
        resolved.append((question, normalized_raw, normalized_txt))
    return resolved


def _disclosures_for_new_evaluation(version_id: uuid.UUID) -> dict[str, uuid.UUID]:
    rows = _serialize_disclosures(version_id)
    missing = DISCLOSURE_TYPES.difference(rows.keys())
    if missing:
        raise ValueError("missing_disclosures")
    return {key: uuid.UUID(value["id"]) for key, value in rows.items()}


def _status_payload(evaluation: QREvaluation) -> dict[str, Any]:
    return {
        "evaluation_id": str(evaluation.id),
        "status": evaluation.status,
        "reference_id": evaluation.reference_id,
        "review_tag": evaluation.review_tag,
        "deleted_by_user": bool(evaluation.deleted_by_user),
        "processing_error": evaluation.processing_error,
        "processing_started_at": evaluation.processing_started_at.isoformat() if evaluation.processing_started_at else None,
        "processing_finished_at": evaluation.processing_finished_at.isoformat() if evaluation.processing_finished_at else None,
        "updated_at": evaluation.updated_at.isoformat() if evaluation.updated_at else None,
    }


def create_evaluation_draft(user_id: uuid.UUID, payload: dict[str, Any]) -> tuple[QREvaluation, str]:
    version = _active_version() or ensure_runtime_bootstrap(created_by=user_id)
    age = int(payload.get("child_age_years", 0))
    if age < int(current_app.config.get("EVALUATION_MIN_AGE", 6)) or age > int(
        current_app.config.get("EVALUATION_MAX_AGE", 11)
    ):
        raise ValueError("invalid_child_age")
    respondent_type = (payload.get("respondent_type") or "caregiver").strip().lower()
    if respondent_type not in {"caregiver", "psychologist"}:
        raise ValueError("invalid_respondent_type")

    disclosures = _disclosures_for_new_evaluation(version.id)
    pin_plain = _generate_pin()
    pin_hash = hash_pin(pin_plain)

    evaluation = QREvaluation(
        questionnaire_version_id=version.id,
        requested_by_user_id=user_id,
        respondent_type=respondent_type,
        child_age_years=age,
        child_sex_assigned_at_birth=_normalize_sex(payload.get("child_sex_assigned_at_birth")),
        status="draft",
        review_tag="sin_revisar",
        deleted_by_user=False,
        reference_id=_unique_reference_id(),
        pin_hash=pin_hash,
        pin_failed_attempts=0,
        pin_locked_until=None,
        consent_disclosure_id=disclosures["consent_pre"],
        pre_disclaimer_id=disclosures["disclaimer_pre"],
        result_disclaimer_id=disclosures["disclaimer_result"],
        pdf_disclaimer_id=disclosures["disclaimer_pdf"],
        consent_accepted_at=_utcnow() if payload.get("consent_accepted", False) else None,
        runtime_scope_version=_runtime_bundle_version(),
        model_runtime_bundle="champions_runtime_bundle_v1",
        processing_attempts=0,
        is_waiting_live_result=bool(payload.get("is_waiting_live_result", True)),
        last_presence_heartbeat_at=_utcnow() if payload.get("is_waiting_live_result", True) else None,
        notify_if_user_offline=True,
        retention_until=_default_retention_for_status("draft"),
    )
    db.session.add(evaluation)
    db.session.flush()

    answers = payload.get("answers") or []
    if answers:
        resolved = _resolve_answer_items(evaluation, answers)
        for question, normalized_raw, normalized_txt in resolved:
            db.session.add(
                QREvaluationResponse(
                    evaluation_id=evaluation.id,
                    question_id=question.id,
                    section_id=question.section_id,
                    answer_raw=normalized_raw if isinstance(normalized_raw, (dict, list, int, float)) else str(normalized_raw),
                    answer_normalized=normalized_txt,
                )
            )

    log_audit(user_id, "QR_EVALUATION_DRAFT_CREATED", "questionnaire_runtime", {"evaluation_id": str(evaluation.id)})
    db.session.commit()
    return evaluation, pin_plain


def get_user_evaluation_or_404(
    evaluation_id: uuid.UUID,
    user_id: uuid.UUID,
    allow_deleted: bool = False,
) -> QREvaluation:
    evaluation = db.session.get(QREvaluation, evaluation_id)
    if not evaluation:
        raise LookupError("evaluation_not_found")
    if evaluation.requested_by_user_id != user_id:
        raise PermissionError("forbidden_evaluation")
    if evaluation.deleted_by_user and not allow_deleted:
        raise FileNotFoundError("evaluation_deleted_by_user")
    return evaluation


def save_draft_answers(
    evaluation: QREvaluation,
    answers: list[dict[str, Any]],
    consent_accepted: bool | None = None,
) -> None:
    if evaluation.status not in {"draft", "submitted", "failed"}:
        raise ValueError("invalid_status_for_draft_save")
    resolved = _resolve_answer_items(evaluation, answers)
    for question, normalized_raw, normalized_txt in resolved:
        row = QREvaluationResponse.query.filter_by(evaluation_id=evaluation.id, question_id=question.id).first()
        if row:
            row.answer_raw = normalized_raw if isinstance(normalized_raw, (dict, list, int, float)) else str(normalized_raw)
            row.answer_normalized = normalized_txt
            row.updated_at = _utcnow()
        else:
            db.session.add(
                QREvaluationResponse(
                    evaluation_id=evaluation.id,
                    question_id=question.id,
                    section_id=question.section_id,
                    answer_raw=normalized_raw if isinstance(normalized_raw, (dict, list, int, float)) else str(normalized_raw),
                    answer_normalized=normalized_txt,
                )
            )
    evaluation.status = "draft"
    if consent_accepted is True and not evaluation.consent_accepted_at:
        evaluation.consent_accepted_at = _utcnow()
    evaluation.updated_at = _utcnow()
    evaluation.retention_until = _default_retention_for_status("draft")
    db.session.add(evaluation)
    db.session.commit()


def evaluate_section_completeness(evaluation: QREvaluation, section_key: str) -> dict[str, Any]:
    section = (
        QRQuestionnaireSection.query.filter_by(questionnaire_version_id=evaluation.questionnaire_version_id, key=section_key).first()
    )
    if not section:
        raise LookupError("section_not_found")
    questions = (
        QRQuestion.query.filter_by(section_id=section.id, is_active=True)
        .order_by(QRQuestion.position.asc())
        .all()
    )
    existing = {
        str(row.question_id): row
        for row in QREvaluationResponse.query.filter_by(evaluation_id=evaluation.id, section_id=section.id).all()
    }
    missing_required = []
    answered = 0
    for question in questions:
        row = existing.get(str(question.id))
        if row:
            answered += 1
        if question.requiredness == "required" and not row:
            missing_required.append(question.key)
    return {
        "section_key": section.key,
        "total_questions": len(questions),
        "answered_questions": answered,
        "missing_required": missing_required,
        "is_valid": len(missing_required) == 0,
    }


def _build_feature_map_from_responses(evaluation: QREvaluation) -> dict[str, Any]:
    responses = (
        db.session.query(QREvaluationResponse, QRQuestion)
        .join(QRQuestion, QREvaluationResponse.question_id == QRQuestion.id)
        .filter(QREvaluationResponse.evaluation_id == evaluation.id)
        .all()
    )
    feature_map: dict[str, Any] = {
        "age_years": float(evaluation.child_age_years),
        "sex_assigned_at_birth": evaluation.child_sex_assigned_at_birth,
        "site": "CBIC",
        "release": 11.0,
    }
    for row, question in responses:
        value: Any = row.answer_raw
        if isinstance(value, str) and question.response_type not in {"single_choice", "consent/info_only"}:
            maybe = _safe_float(value)
            value = maybe if maybe is not None else value
        feature_map[question.feature_key] = value
    return feature_map


def _should_create_notification(evaluation: QREvaluation) -> bool:
    if not evaluation.notify_if_user_offline:
        return False
    if not evaluation.is_waiting_live_result:
        return True
    heartbeat = evaluation.last_presence_heartbeat_at
    if not heartbeat:
        return True
    grace = int(current_app.config.get("QR_LIVE_HEARTBEAT_GRACE_SECONDS", 45))
    return (_utcnow() - heartbeat) > timedelta(seconds=grace)


def _create_notification(
    user_id: uuid.UUID,
    evaluation_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    payload_json: dict[str, Any] | None = None,
) -> QRNotification:
    row = QRNotification(
        user_id=user_id,
        evaluation_id=evaluation_id,
        notification_type=notification_type,
        title=title,
        body=body,
        payload_json=payload_json or {},
        is_read=False,
        expires_at=_notification_expiry(),
    )
    db.session.add(row)
    return row


def _persist_domain_results(evaluation: QREvaluation, domain_results: dict[str, dict[str, Any]]) -> None:
    QRDomainResult.query.filter_by(evaluation_id=evaluation.id).delete(synchronize_session=False)
    for domain in DOMAIN_ORDER:
        payload = domain_results[domain]
        row = QRDomainResult(
            evaluation_id=evaluation.id,
            domain=domain,
            model_name=payload["model_name"],
            model_version=str(payload["model_version"]),
            model_status=payload["model_status"],
            probability=payload["probability"],
            threshold_used=payload["threshold_used"],
            risk_band=payload["risk_band"],
            confidence_level=payload["confidence_level"],
            evidence_level=payload["evidence_level"],
            uncertainty_flag=bool(payload["uncertainty_flag"]),
            abstention_flag=bool(payload["abstention_flag"]),
            recommendation_text=payload["recommendation_text"],
            explanation_short=payload["explanation_short"],
            contributors_json=payload["contributors"],
            caveats_json=payload.get("caveats", []),
        )
        db.session.add(row)


def process_evaluation_sync(evaluation_id: uuid.UUID) -> None:
    evaluation = db.session.get(QREvaluation, evaluation_id)
    if not evaluation:
        raise LookupError("evaluation_not_found")
    if evaluation.status not in {"submitted", "processing"}:
        raise ValueError("invalid_status_for_processing")

    job = QRProcessingJob.query.filter_by(evaluation_id=evaluation.id).first()
    if not job:
        job = QRProcessingJob(evaluation_id=evaluation.id, status="queued")
        db.session.add(job)
        db.session.flush()

    evaluation.status = "processing"
    evaluation.processing_attempts = int(evaluation.processing_attempts or 0) + 1
    evaluation.processing_started_at = _utcnow()
    evaluation.processing_error = None
    job.status = "running"
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.started_at = _utcnow()
    db.session.add(evaluation)
    db.session.add(job)
    db.session.commit()

    try:
        feature_map = _build_feature_map_from_responses(evaluation)
        domain_results = run_runtime_inference(feature_map)
        _persist_domain_results(evaluation, domain_results)

        evaluation.status = "completed"
        evaluation.processing_finished_at = _utcnow()
        evaluation.processing_error = None
        evaluation.retention_until = _default_retention_for_status("completed")
        job.status = "completed"
        job.finished_at = _utcnow()
        db.session.add(evaluation)
        db.session.add(job)

        if _should_create_notification(evaluation):
            _create_notification(
                user_id=evaluation.requested_by_user_id,
                evaluation_id=evaluation.id,
                notification_type="evaluation_completed",
                title="Resultado disponible",
                body="Tu evaluacion fue procesada y ya puedes consultar los resultados.",
                payload_json={"evaluation_id": str(evaluation.id)},
            )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        evaluation = db.session.get(QREvaluation, evaluation_id)
        job = QRProcessingJob.query.filter_by(evaluation_id=evaluation_id).first()
        if evaluation:
            evaluation.status = "failed"
            evaluation.processing_finished_at = _utcnow()
            evaluation.processing_error = str(exc)
            evaluation.retention_until = _default_retention_for_status("completed")
            db.session.add(evaluation)
        if job:
            job.status = "failed"
            job.last_error = str(exc)
            job.finished_at = _utcnow()
            db.session.add(job)
        if evaluation:
            _create_notification(
                user_id=evaluation.requested_by_user_id,
                evaluation_id=evaluation.id,
                notification_type="evaluation_failed",
                title="No se pudo completar el procesamiento",
                body="Hubo un error procesando tu evaluacion. Puedes reintentar el envio.",
                payload_json={"evaluation_id": str(evaluation.id), "error": str(exc)},
            )
        db.session.commit()
        raise


def _process_evaluation_async(app, evaluation_id: uuid.UUID) -> None:
    with app.app_context():
        try:
            process_evaluation_sync(evaluation_id)
        except Exception:
            current_app.logger.exception("QR processing failed for %s", evaluation_id)


def submit_evaluation(evaluation: QREvaluation, wait_live_result: bool = True) -> dict[str, Any]:
    if evaluation.deleted_by_user:
        raise ValueError("evaluation_deleted")
    if evaluation.status not in {"draft", "failed", "submitted"}:
        raise ValueError("invalid_status_for_submit")
    if not evaluation.consent_accepted_at:
        raise ValueError("consent_required")
    answers_count = QREvaluationResponse.query.filter_by(evaluation_id=evaluation.id).count()
    if answers_count == 0:
        raise ValueError("empty_answers")

    evaluation.status = "submitted"
    evaluation.is_waiting_live_result = bool(wait_live_result)
    evaluation.last_presence_heartbeat_at = _utcnow() if wait_live_result else None
    evaluation.processing_error = None
    evaluation.updated_at = _utcnow()
    db.session.add(evaluation)

    job = QRProcessingJob.query.filter_by(evaluation_id=evaluation.id).first()
    if not job:
        job = QRProcessingJob(evaluation_id=evaluation.id, status="queued", attempt_count=0, enqueued_at=_utcnow())
        db.session.add(job)
    else:
        job.status = "queued"
        job.last_error = None
        job.enqueued_at = _utcnow()
        job.finished_at = None
        db.session.add(job)
    db.session.commit()

    if bool(current_app.config.get("QR_PROCESS_ASYNC", True)):
        app_obj = current_app._get_current_object()
        EXECUTOR.submit(_process_evaluation_async, app_obj, evaluation.id)
    else:
        process_evaluation_sync(evaluation.id)

    return _status_payload(db.session.get(QREvaluation, evaluation.id))


def heartbeat_presence(evaluation: QREvaluation) -> None:
    if evaluation.status in {"submitted", "processing"}:
        evaluation.last_presence_heartbeat_at = _utcnow()
        evaluation.is_waiting_live_result = True
        db.session.add(evaluation)
        db.session.commit()


def soft_delete_evaluation(evaluation: QREvaluation) -> None:
    evaluation.deleted_by_user = True
    evaluation.deleted_at = _utcnow()
    evaluation.status = "deleted_by_user"
    evaluation.retention_until = _default_retention_for_status("deleted_by_user")
    db.session.add(evaluation)
    if evaluation.psychologist_user_id:
        _create_notification(
            user_id=evaluation.psychologist_user_id,
            evaluation_id=evaluation.id,
            notification_type="evaluation_deleted_by_user",
            title="Evaluacion eliminada por el usuario",
            body="El propietario elimino esta evaluacion. Queda visible solo para trazabilidad.",
            payload_json={"evaluation_id": str(evaluation.id)},
        )
    db.session.commit()


def _result_rows(evaluation_id: uuid.UUID) -> list[QRDomainResult]:
    return QRDomainResult.query.filter_by(evaluation_id=evaluation_id).order_by(QRDomainResult.domain.asc()).all()


def get_results_payload(evaluation: QREvaluation, audience: str = "user") -> dict[str, Any]:
    rows = _result_rows(evaluation.id)
    if not rows and evaluation.status == "completed":
        raise LookupError("results_not_found")
    disclaimers = _serialize_disclosures(evaluation.questionnaire_version_id)
    domains: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "domain": row.domain,
            "risk_band": row.risk_band,
            "confidence_level": row.confidence_level,
            "evidence_level": row.evidence_level,
            "uncertainty_flag": bool(row.uncertainty_flag),
            "abstention_flag": bool(row.abstention_flag),
            "recommendation_text": row.recommendation_text,
            "explanation_short": row.explanation_short,
            "model_status": row.model_status,
            "caveats": row.caveats_json or [],
        }
        if audience == "professional":
            base.update(
                {
                    "probability": float(row.probability),
                    "threshold_used": float(row.threshold_used),
                    "model_name": row.model_name,
                    "model_version": row.model_version,
                    "contributors": row.contributors_json or [],
                }
            )
        else:
            base.update({"confidence_percent": round(float(row.probability) * 100.0, 2)})
        domains.append(base)

    return {
        "evaluation": _status_payload(evaluation),
        "audience": audience,
        "results": domains,
        "disclaimer_result": disclaimers.get("disclaimer_result"),
    }


def get_responses_payload(evaluation: QREvaluation) -> dict[str, Any]:
    rows = (
        db.session.query(QREvaluationResponse, QRQuestion, QRQuestionnaireSection)
        .join(QRQuestion, QREvaluationResponse.question_id == QRQuestion.id)
        .join(QRQuestionnaireSection, QRQuestion.section_id == QRQuestionnaireSection.id)
        .filter(QREvaluationResponse.evaluation_id == evaluation.id)
        .order_by(QRQuestionnaireSection.position.asc(), QRQuestion.position.asc())
        .all()
    )
    answers = []
    for response, question, section in rows:
        answers.append(
            {
                "section_key": section.key,
                "section_title": section.title,
                "question_key": question.key,
                "feature_key": question.feature_key,
                "prompt": question.prompt,
                "value": response.answer_raw,
                "normalized": response.answer_normalized,
                "answered_at": response.answered_at.isoformat() if response.answered_at else None,
            }
        )
    return {"evaluation": _status_payload(evaluation), "answers": answers}


def list_user_evaluations(user_id: uuid.UUID, include_deleted: bool = False) -> list[dict[str, Any]]:
    query = QREvaluation.query.filter_by(requested_by_user_id=user_id)
    if not include_deleted:
        query = query.filter(QREvaluation.deleted_by_user.is_(False))
    rows = query.order_by(QREvaluation.created_at.desc()).all()
    return [_status_payload(row) for row in rows]


def professional_access(reference_id: str, pin: str, psychologist_user_id: uuid.UUID) -> QREvaluation:
    evaluation = QREvaluation.query.filter_by(reference_id=reference_id).first()
    if not evaluation:
        raise LookupError("reference_not_found")

    now = _utcnow()
    if evaluation.pin_locked_until and evaluation.pin_locked_until > now:
        raise PermissionError("pin_temporarily_locked")
    if not verify_pin(pin, evaluation.pin_hash):
        evaluation.pin_failed_attempts = int(evaluation.pin_failed_attempts or 0) + 1
        if evaluation.pin_failed_attempts >= int(current_app.config.get("QR_PIN_MAX_ATTEMPTS", 5)):
            lock_minutes = int(current_app.config.get("QR_PIN_LOCK_MINUTES", 10))
            evaluation.pin_locked_until = now + timedelta(minutes=lock_minutes)
            evaluation.pin_failed_attempts = 0
        db.session.add(evaluation)
        db.session.commit()
        raise PermissionError("invalid_pin")

    if evaluation.deleted_by_user:
        evaluation.psychologist_user_id = psychologist_user_id
        db.session.add(evaluation)
        db.session.commit()
        raise FileNotFoundError("evaluation_deleted_by_user")

    if evaluation.psychologist_user_id and evaluation.psychologist_user_id != psychologist_user_id:
        raise PermissionError("evaluation_already_claimed")
    evaluation.psychologist_user_id = psychologist_user_id
    evaluation.pin_failed_attempts = 0
    evaluation.pin_locked_until = None
    db.session.add(evaluation)
    db.session.commit()
    return evaluation


def professional_guard(evaluation_id: uuid.UUID, psychologist_user_id: uuid.UUID) -> QREvaluation:
    evaluation = db.session.get(QREvaluation, evaluation_id)
    if not evaluation:
        raise LookupError("evaluation_not_found")
    if evaluation.psychologist_user_id != psychologist_user_id:
        raise PermissionError("forbidden_professional_access")
    return evaluation


def set_professional_tag(evaluation: QREvaluation, tag: str) -> QREvaluation:
    canonical = canonical_review_tag(tag)
    evaluation.review_tag = canonical
    db.session.add(evaluation)
    db.session.commit()
    return evaluation


def release_professional_access(evaluation: QREvaluation, psychologist_user_id: uuid.UUID) -> None:
    if evaluation.psychologist_user_id != psychologist_user_id:
        raise PermissionError("forbidden_professional_access")
    evaluation.psychologist_user_id = None
    db.session.add(evaluation)
    db.session.commit()


def list_notifications(user_id: uuid.UUID, unread_only: bool = False) -> list[dict[str, Any]]:
    query = QRNotification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter(QRNotification.is_read.is_(False))
    rows = query.order_by(QRNotification.created_at.desc()).all()
    out = []
    for row in rows:
        out.append(
            {
                "id": str(row.id),
                "evaluation_id": str(row.evaluation_id),
                "type": row.notification_type,
                "title": row.title,
                "body": row.body,
                "payload": row.payload_json or {},
                "is_read": bool(row.is_read),
                "read_at": row.read_at.isoformat() if row.read_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out


def mark_notification_read(notification_id: uuid.UUID, user_id: uuid.UUID) -> QRNotification:
    row = db.session.get(QRNotification, notification_id)
    if not row:
        raise LookupError("notification_not_found")
    if row.user_id != user_id:
        raise PermissionError("forbidden_notification")
    row.is_read = True
    row.read_at = _utcnow()
    db.session.add(row)
    db.session.commit()
    return row


def export_evaluation_payload(
    evaluation: QREvaluation,
    requested_by_user_id: uuid.UUID,
    export_mode: str,
    audience: str = "user",
) -> dict[str, Any]:
    mode = (export_mode or "").strip()
    if mode not in ALLOWED_EXPORT_MODES:
        raise ValueError("invalid_export_mode")
    response_payload = get_responses_payload(evaluation)
    result_payload = get_results_payload(evaluation, audience=audience) if evaluation.status == "completed" else None
    disclaimers = _serialize_disclosures(evaluation.questionnaire_version_id)
    payload: dict[str, Any] = {
        "metadata": {
            "reference_id": evaluation.reference_id,
            "evaluation_id": str(evaluation.id),
            "generated_at": _utcnow().isoformat(),
            "questionnaire_version_id": str(evaluation.questionnaire_version_id),
            "respondent_type": evaluation.respondent_type,
            "status": evaluation.status,
            "audience": audience,
        },
        "disclaimer_pdf": disclaimers.get("disclaimer_pdf"),
    }
    if mode in {"responses_only", "responses_and_results"}:
        payload["responses"] = response_payload["answers"]
    if mode in {"results_only", "responses_and_results"}:
        payload["results"] = (result_payload or {}).get("results", [])
        payload["result_context"] = (result_payload or {}).get("evaluation")

    db.session.add(
        QRExportLog(
            evaluation_id=evaluation.id,
            requested_by_user_id=requested_by_user_id,
            export_mode=mode,
            export_format="json",
        )
    )
    db.session.commit()
    return payload
