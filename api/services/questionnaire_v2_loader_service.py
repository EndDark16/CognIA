import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.models import (
    ModelArtifactRegistry,
    ModelConfidenceRegistry,
    ModelMetricsSnapshot,
    ModelModeDomainActivation,
    ModelOperationalCaveat,
    ModelRegistry,
    ModelVersion,
    QuestionnaireDefinition,
    QuestionnaireInternalInput,
    QuestionnaireQuestion,
    QuestionnaireQuestionMode,
    QuestionnaireRepeatMapping,
    QuestionnaireScale,
    QuestionnaireScaleOption,
    QuestionnaireSection,
    QuestionnaireVersion,
    db,
)


ROLE_ALIAS_TO_CANONICAL = {
    "guardian": "guardian",
    "caregiver": "guardian",
    "psychologist": "psychologist",
}

MODE_KEYS = [
    ("guardian", "short", "caregiver_1_3"),
    ("guardian", "medium", "caregiver_2_3"),
    ("guardian", "complete", "caregiver_full"),
    ("psychologist", "short", "psychologist_1_3"),
    ("psychologist", "medium", "psychologist_2_3"),
    ("psychologist", "complete", "psychologist_full"),
]

DEFAULT_DEFINITION_SLUG = "questionnaire_v16_4"
DEFAULT_DEFINITION_NAME = "Cuestionario operacional v16.4"
DEFAULT_VERSION_LABEL = "v16.4"
DEFAULT_SOURCE_DIR = Path("data") / "cuestionario_v16.4"

DEFAULT_ACTIVE_MODELS = Path("data") / "hybrid_active_modes_freeze_v10" / "tables" / "hybrid_active_models_30_modes.csv"
DEFAULT_ACTIVE_SUMMARY = Path("data") / "hybrid_active_modes_freeze_v10" / "tables" / "hybrid_active_modes_summary.csv"
DEFAULT_INPUTS_MASTER = Path("data") / "hybrid_active_modes_freeze_v10" / "tables" / "hybrid_questionnaire_inputs_master.csv"
DEFAULT_OPERATIONAL_CHAMPIONS = Path("data") / "hybrid_operational_freeze_v10" / "tables" / "hybrid_operational_final_champions.csv"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "si", "s", "x"}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _normalize_role(value: Any) -> str:
    raw = _normalize_text(value).lower()
    out = ROLE_ALIAS_TO_CANONICAL.get(raw)
    if out:
        return out
    return raw


def _slugify(value: str) -> str:
    text = re.sub(r"\s+", "_", value.strip().lower())
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "section"


def _parse_options_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


@dataclass
class QuestionnaireSourceBundle:
    source_dir: Path
    master_csv: Path
    visible_csv: Path
    scales_csv: Path
    preview_md: Path | None
    pdf_path: Path | None
    audit_md: Path | None


def resolve_questionnaire_source_bundle(source_dir: Path | None = None) -> QuestionnaireSourceBundle:
    base = source_dir or DEFAULT_SOURCE_DIR
    candidates_master = [
        base / "questionnaire_v16_4_master_excel_utf8.csv",
        base / "questionnaire_v16_4_visible_questions_excel_utf8.csv",
        base / "questionnaire_v16_4_visible_questions_excel_utf8 (1).csv",
    ]
    master = next((p for p in candidates_master if p.exists()), None)
    if not master:
        raise FileNotFoundError("questionnaire master/visible csv not found in data/cuestionario_v16.4")

    visible_candidates = [
        base / "questionnaire_v16_4_visible_questions_excel_utf8.csv",
        base / "questionnaire_v16_4_visible_questions_excel_utf8 (1).csv",
    ]
    visible = next((p for p in visible_candidates if p.exists()), master)

    scales = base / "questionnaire_v16_4_scales_excel_utf8.csv"
    if not scales.exists():
        raise FileNotFoundError("questionnaire scales csv missing")

    preview = base / "questionnaire_v16_4_preview.md"
    pdf = base / "cuestionario_v16_4.pdf"
    audit = base / "questionnaire_v16_4_audit_summary.md"

    return QuestionnaireSourceBundle(
        source_dir=base,
        master_csv=master,
        visible_csv=visible,
        scales_csv=scales,
        preview_md=preview if preview.exists() else None,
        pdf_path=pdf if pdf.exists() else None,
        audit_md=audit if audit.exists() else None,
    )


def _ensure_definition(created_by: uuid.UUID | None) -> QuestionnaireDefinition:
    row = QuestionnaireDefinition.query.filter_by(slug=DEFAULT_DEFINITION_SLUG).first()
    if row:
        row.name = DEFAULT_DEFINITION_NAME
        row.is_active = True
        row.updated_at = _utcnow()
        db.session.add(row)
        return row

    row = QuestionnaireDefinition(
        slug=DEFAULT_DEFINITION_SLUG,
        name=DEFAULT_DEFINITION_NAME,
        description="Cuestionario versionado para backend operacional v2",
        is_active=True,
        created_by_user_id=created_by,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _ensure_version(definition: QuestionnaireDefinition, bundle: QuestionnaireSourceBundle) -> QuestionnaireVersion:
    row = QuestionnaireVersion.query.filter_by(definition_id=definition.id, version_label=DEFAULT_VERSION_LABEL).first()
    payload = {
        "source_folder": str(bundle.source_dir),
        "source_master_csv": str(bundle.master_csv),
        "source_visible_csv": str(bundle.visible_csv),
        "source_scales_csv": str(bundle.scales_csv),
        "source_preview_md": str(bundle.preview_md) if bundle.preview_md else None,
        "source_pdf": str(bundle.pdf_path) if bundle.pdf_path else None,
        "source_audit_md": str(bundle.audit_md) if bundle.audit_md else None,
        "questionnaire_version_final": "questionnaire_v16_4",
        "scales_version_label": "questionnaire_v16_4_scales",
        "metadata_json": {
            "source_truth": "data/cuestionario_v16.4",
            "loaded_at": _utcnow().isoformat(),
        },
        "is_active": True,
        "published_at": _utcnow(),
    }

    if row:
        for key, value in payload.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()
        db.session.add(row)
        db.session.flush()
        return row

    row = QuestionnaireVersion(definition_id=definition.id, version_label=DEFAULT_VERSION_LABEL, **payload)
    db.session.add(row)
    db.session.flush()
    return row


def _deactivate_other_versions(definition_id: uuid.UUID, active_version_id: uuid.UUID) -> None:
    QuestionnaireVersion.query.filter(
        QuestionnaireVersion.definition_id == definition_id,
        QuestionnaireVersion.id != active_version_id,
    ).update({"is_active": False}, synchronize_session=False)


def _upsert_scales(version_id: uuid.UUID, scales_df: pd.DataFrame) -> dict[str, QuestionnaireScale]:
    out: dict[str, QuestionnaireScale] = {}
    for row in scales_df.to_dict(orient="records"):
        scale_key = _normalize_text(row.get("scale_id"))
        if not scale_key:
            continue
        scale = QuestionnaireScale.query.filter_by(version_id=version_id, scale_id=scale_key).first()
        if not scale:
            scale = QuestionnaireScale(version_id=version_id, scale_id=scale_key)
        scale.scale_name = _normalize_text(row.get("scale_name")) or scale_key
        scale.response_type = _normalize_text(row.get("response_type")) or "single_choice"
        scale.min_value = _to_float(row.get("min_value"))
        scale.max_value = _to_float(row.get("max_value"))
        scale.unit = _normalize_text(row.get("unit")) or None
        scale.scale_guidance = _normalize_text(row.get("scale_guidance")) or None
        options = _parse_options_json(row.get("response_options_json"))
        scale.options_json = options
        scale.updated_at = _utcnow()
        db.session.add(scale)
        db.session.flush()

        if isinstance(options, list):
            QuestionnaireScaleOption.query.filter_by(scale_ref_id=scale.id).delete(synchronize_session=False)
            for idx, opt in enumerate(options, start=1):
                if isinstance(opt, dict):
                    value = _normalize_text(opt.get("value"))
                    label = _normalize_text(opt.get("label")) or value
                else:
                    value = _normalize_text(opt)
                    label = value
                if not value:
                    continue
                db.session.add(
                    QuestionnaireScaleOption(
                        scale_ref_id=scale.id,
                        option_value=value,
                        option_label=label,
                        position=idx,
                    )
                )

        out[scale_key] = scale
    return out


def _mode_inclusion(row: dict[str, Any], mode_key: str) -> tuple[bool, float | None, str | None]:
    include_col = f"include_{mode_key}"
    include = _to_bool(row.get(include_col))
    rank_role = "caregiver" if mode_key.startswith("caregiver") else "psychologist"
    rank_col = f"{rank_role}_rank"
    bucket_col = f"{rank_role}_priority_bucket"
    rank = _to_float(row.get(rank_col))
    bucket = _normalize_text(row.get(bucket_col)) or None
    return include, rank, bucket


def _delivery_from_mode_key(mode_key: str) -> str:
    if mode_key.endswith("1_3"):
        return "short"
    if mode_key.endswith("2_3"):
        return "medium"
    return "complete"


def _section_for_row(version_id: uuid.UUID, sections_cache: dict[str, QuestionnaireSection], row: dict[str, Any], default_pos: int) -> QuestionnaireSection:
    section_raw = _normalize_text(row.get("questionnaire_section_suggested")) or _normalize_text(row.get("section_name"))
    subsection_raw = _normalize_text(row.get("questionnaire_subsection_suggested")) or _normalize_text(row.get("subsection_name"))
    section_title = section_raw or "General"
    section_key = _slugify(f"{section_title} {subsection_raw}" if subsection_raw else section_title)
    existing = sections_cache.get(section_key)
    if existing:
        return existing
    section = QuestionnaireSection.query.filter_by(version_id=version_id, section_key=section_key).first()
    if not section:
        section = QuestionnaireSection(version_id=version_id, section_key=section_key)
    section.title = section_title
    section.description = subsection_raw or None
    section.position = default_pos
    section.is_visible = True
    section.updated_at = _utcnow()
    db.session.add(section)
    db.session.flush()
    sections_cache[section_key] = section
    return section


def _set_question_modes(question: QuestionnaireQuestion, row: dict[str, Any]) -> None:
    QuestionnaireQuestionMode.query.filter_by(question_id=question.id).delete(synchronize_session=False)
    for role, delivery_mode, mode_key in MODE_KEYS:
        include, rank, bucket = _mode_inclusion(row, mode_key)
        db.session.add(
            QuestionnaireQuestionMode(
                question_id=question.id,
                mode_key=mode_key,
                role=role,
                delivery_mode=delivery_mode,
                is_included=include,
                priority_rank=rank,
                priority_bucket=bucket,
            )
        )


def _upsert_questions(version_id: uuid.UUID, master_df: pd.DataFrame) -> dict[str, QuestionnaireQuestion]:
    sections_cache: dict[str, QuestionnaireSection] = {}
    question_by_code: dict[str, QuestionnaireQuestion] = {}

    for index, row in enumerate(master_df.to_dict(orient="records"), start=1):
        code = _normalize_text(row.get("questionnaire_item_id")) or _normalize_text(row.get("feature")) or f"AUTO_{index:04d}"
        feature_key = _normalize_text(row.get("feature")) or code.lower()
        section = _section_for_row(version_id, sections_cache, row, default_pos=index)

        question = QuestionnaireQuestion.query.filter_by(version_id=version_id, question_code=code).first()
        if not question:
            question = QuestionnaireQuestion(version_id=version_id, question_code=code)

        question.section_id = section.id
        question.feature_key = feature_key
        question.canonical_question_code = _normalize_text(row.get("canonical_question_id")) or None
        question.question_text_primary = _normalize_text(row.get("question_text_primary")) or None
        question.caregiver_question = _normalize_text(row.get("caregiver_question")) or None
        question.psychologist_question = _normalize_text(row.get("psychologist_question")) or None
        question.help_text = _normalize_text(row.get("help_text")) or None
        question.layer = _normalize_text(row.get("layer")) or None
        question.domain = (_normalize_text(row.get("domain")) or "general").lower()
        question.domains_final = _normalize_text(row.get("domains_final")) or None
        question.module = _normalize_text(row.get("module")) or None
        question.criterion_ref = _normalize_text(row.get("criterion_ref")) or None
        question.instrument_or_source = _normalize_text(row.get("instrument_or_source")) or None
        question.feature_type = _normalize_text(row.get("feature_type")) or None
        question.feature_role = _normalize_text(row.get("feature_role")) or None
        question.respondent_expected = _normalize_text(row.get("respondent_expected")) or None
        question.administered_by = _normalize_text(row.get("administered_by")) or None
        question.response_type = _normalize_text(row.get("response_type")) or "single_choice"
        question.scale_id = _normalize_text(row.get("scale_id")) or None
        question.response_options_json = _parse_options_json(row.get("response_options_json"))
        question.min_value = _to_float(row.get("min_value"))
        question.max_value = _to_float(row.get("max_value"))
        question.unit = _normalize_text(row.get("unit")) or None
        question.visible_question = _to_bool(row.get("visible_question_yes_no")) or _to_bool(row.get("show_in_questionnaire_yes_no"))
        question.generated_input = _to_bool(row.get("generated_input_yes_no"))
        question.is_internal_input = not question.visible_question
        question.is_transparent_derived = _to_bool(row.get("is_transparent_derived"))
        question.requires_internal_scoring = _to_bool(row.get("requires_internal_scoring"))
        question.requires_exact_item_wording = _to_bool(row.get("requires_exact_item_wording"))
        question.requires_clinician_administration = _to_bool(row.get("requires_clinician_administration"))
        question.requires_child_self_report = _to_bool(row.get("requires_child_self_report"))
        question.display_order = index
        question.question_audit_status = _normalize_text(row.get("question_audit_status")) or None
        question.updated_at = _utcnow()

        db.session.add(question)
        db.session.flush()
        question_by_code[code] = question

        _set_question_modes(question, row)

        if question.is_internal_input or question.is_transparent_derived or question.requires_internal_scoring:
            internal = QuestionnaireInternalInput.query.filter_by(version_id=version_id, feature_key=feature_key).first()
            if not internal:
                internal = QuestionnaireInternalInput(version_id=version_id, feature_key=feature_key)
            internal.source_question_id = question.id
            derived_from = _normalize_text(row.get("derived_from_features"))
            internal.derived_from_features = [item.strip() for item in derived_from.split("|") if item.strip()] if derived_from else None
            internal.internal_scoring_formula_summary = _normalize_text(row.get("internal_scoring_formula_summary")) or None
            internal.storage_type = "numeric" if question.response_type not in {"single_choice", "text"} else "categorical"
            internal.is_required = _to_bool(row.get("is_direct_input")) or question.requires_internal_scoring
            internal.requires_internal_scoring = question.requires_internal_scoring
            internal.notes = _normalize_text(row.get("notes")) or None
            internal.updated_at = _utcnow()
            db.session.add(internal)

    for row in master_df.to_dict(orient="records"):
        repeated_code = _normalize_text(row.get("questionnaire_item_id")) or _normalize_text(row.get("feature"))
        canonical_code = _normalize_text(row.get("reuse_answer_from_question_id")) or _normalize_text(row.get("canonical_question_id"))
        if not repeated_code or not canonical_code or repeated_code == canonical_code:
            continue
        repeated_q = question_by_code.get(repeated_code)
        canonical_q = question_by_code.get(canonical_code)
        if not repeated_q or not canonical_q:
            continue
        mapping = QuestionnaireRepeatMapping.query.filter_by(
            version_id=version_id,
            repeated_question_id=repeated_q.id,
        ).first()
        if not mapping:
            mapping = QuestionnaireRepeatMapping(version_id=version_id, repeated_question_id=repeated_q.id)
        mapping.canonical_question_id = canonical_q.id
        mapping.reuse_answer = True
        mapping.mapping_notes = "synced_from_questionnaire_v16_4"
        mapping.updated_at = _utcnow()
        db.session.add(mapping)

    return question_by_code


def _resolve_mode_key(role: str, mode: str) -> str:
    role = _normalize_role(role)
    for row_role, row_mode, mode_key in MODE_KEYS:
        if row_role == role and row_mode == mode:
            return mode_key
    raise ValueError(f"invalid role/mode pair: {role}/{mode}")


def _resolve_artifact_path(domain: str, model_key: str) -> tuple[str | None, str | None]:
    domain = domain.lower()
    preferred = [
        Path("models") / "active_modes" / model_key / "calibrated.joblib",
        Path("models") / "active_modes" / model_key / "pipeline.joblib",
    ]
    for path in preferred:
        if path.exists():
            return str(path), None

    fallback_candidates = [
        Path("models") / "champions" / f"rf_{domain}_current" / "calibrated.joblib",
        Path("models") / "champions" / f"rf_{domain}_current" / "pipeline.joblib",
    ]
    fallback = next((str(path) for path in fallback_candidates if path.exists()), None)
    return None, fallback


def sync_active_models() -> dict[str, Any]:
    if not DEFAULT_ACTIVE_MODELS.exists():
        raise FileNotFoundError("missing active models csv")

    active_df = pd.read_csv(DEFAULT_ACTIVE_MODELS)
    metrics_count = 0
    activation_count = 0

    for row in active_df.to_dict(orient="records"):
        model_key = _normalize_text(row.get("active_model_id"))
        if not model_key:
            continue
        domain = _normalize_text(row.get("domain")).lower()
        mode_key = _normalize_text(row.get("mode"))
        role = _normalize_role(row.get("role"))

        # A mode already encodes the respondent side (`caregiver_*` or
        # `psychologist_*`). Clear the whole domain/mode slot so historical
        # rows that used the pre-normalized `caregiver` role cannot remain
        # active next to the current canonical `guardian` row.
        stale_registries = ModelRegistry.query.filter_by(domain=domain, mode_key=mode_key).all()
        for stale_registry in stale_registries:
            stale_registry.is_active = False
            stale_registry.updated_at = _utcnow()
            db.session.add(stale_registry)
            ModelVersion.query.filter_by(model_registry_id=stale_registry.id).update(
                {"is_active": False, "updated_at": _utcnow()},
                synchronize_session=False,
            )
        ModelModeDomainActivation.query.filter_by(
            domain=domain,
            mode_key=mode_key,
        ).delete(synchronize_session=False)

        registry = ModelRegistry.query.filter_by(model_key=model_key).first()
        if not registry:
            registry = ModelRegistry(model_key=model_key)
        registry.domain = domain
        registry.mode_key = mode_key
        registry.role = role
        registry.source_line = _normalize_text(row.get("source_line")) or None
        registry.source_campaign = _normalize_text(row.get("source_campaign")) or None
        registry.model_family = _normalize_text(row.get("model_family")) or None
        registry.feature_set_id = _normalize_text(row.get("feature_set_id")) or None
        registry.config_id = _normalize_text(row.get("config_id")) or None
        registry.is_active = True
        registry.valid_from = _utcnow()
        registry.updated_at = _utcnow()
        db.session.add(registry)
        db.session.flush()

        version_tag = _normalize_text(row.get("source_campaign")) or "active_line"
        version = ModelVersion.query.filter_by(model_registry_id=registry.id, model_version_tag=version_tag).first()
        if not version:
            version = ModelVersion(model_registry_id=registry.id, model_version_tag=version_tag)

        artifact_path, fallback_path = _resolve_artifact_path(domain, model_key)
        version.artifact_path = artifact_path
        version.fallback_artifact_path = fallback_path
        version.calibration = _normalize_text(row.get("calibration")) or None
        version.threshold_policy = _normalize_text(row.get("threshold_policy")) or None
        version.threshold = _to_float(row.get("threshold"))
        version.seed = _normalize_text(row.get("seed")) or None
        version.n_features = int(_to_float(row.get("n_features")) or 0) or None
        feature_columns = [
            item.strip()
            for item in str(row.get("feature_list_pipe") or "").split("|")
            if item.strip() and item.strip().lower() != "nan"
        ]
        version.metadata_json = {
            "source_csv": str(DEFAULT_ACTIVE_MODELS),
            "feature_columns": feature_columns,
            "notes": _normalize_text(row.get("notes")) or None,
            "por_confirmar": artifact_path is None,
        }
        version.is_active = True
        version.updated_at = _utcnow()
        db.session.add(version)
        db.session.flush()

        activation = ModelModeDomainActivation(
            domain=domain,
            mode_key=mode_key,
            role=role,
            model_registry_id=registry.id,
            model_version_id=version.id,
            active_flag=True,
            source_campaign=_normalize_text(row.get("source_campaign")) or None,
            valid_from=_utcnow(),
        )
        db.session.add(activation)
        db.session.flush()
        activation_count += 1

        metrics = ModelMetricsSnapshot(
            model_version_id=version.id,
            precision=_to_float(row.get("precision")),
            recall=_to_float(row.get("recall")),
            specificity=_to_float(row.get("specificity")),
            balanced_accuracy=_to_float(row.get("balanced_accuracy")),
            f1=_to_float(row.get("f1")),
            roc_auc=_to_float(row.get("roc_auc")),
            pr_auc=_to_float(row.get("pr_auc")),
            brier=_to_float(row.get("brier")),
            overfit_flag=_normalize_text(row.get("overfit_flag")) or None,
            generalization_flag=_normalize_text(row.get("generalization_flag")) or None,
            dataset_ease_flag=_normalize_text(row.get("dataset_ease_flag")) or None,
            quality_label=_normalize_text(row.get("final_operational_class")) or None,
            metrics_json={"row": row},
            captured_at=_utcnow(),
        )
        db.session.add(metrics)
        metrics_count += 1

        db.session.add(
            ModelConfidenceRegistry(
                activation_id=activation.id,
                confidence_pct=_to_float(row.get("confidence_pct")),
                confidence_band=_normalize_text(row.get("confidence_band")) or None,
                operational_class=_normalize_text(row.get("final_operational_class")) or None,
                recommended_for_default_use=_to_bool(row.get("recommended_for_default_use")),
                notes=_normalize_text(row.get("notes")) or None,
            )
        )

        caveat = _normalize_text(row.get("operational_caveat"))
        if caveat and caveat.lower() != "none":
            db.session.add(
                ModelOperationalCaveat(
                    activation_id=activation.id,
                    caveat=caveat,
                    severity="medium",
                    is_blocking=False,
                )
            )

        artifact = ModelArtifactRegistry.query.filter_by(
            model_version_id=version.id,
            artifact_kind="runtime_model",
        ).first()
        if not artifact:
            artifact = ModelArtifactRegistry(
                model_version_id=version.id,
                artifact_kind="runtime_model",
            )
        artifact.artifact_locator = artifact_path or fallback_path or "por_confirmar"
        artifact.is_available = bool(artifact_path or fallback_path)
        artifact.metadata_json = {"source": "active_modes_sync"}
        db.session.add(artifact)

    return {
        "models_synced": int(active_df.shape[0]),
        "activations_created": activation_count,
        "metrics_snapshots_created": metrics_count,
    }


def sync_questionnaire_catalog(created_by: uuid.UUID | None = None, source_dir: Path | None = None) -> dict[str, Any]:
    bundle = resolve_questionnaire_source_bundle(source_dir=source_dir)

    definition = _ensure_definition(created_by)
    version = _ensure_version(definition, bundle)
    _deactivate_other_versions(definition.id, version.id)

    scales_df = pd.read_csv(bundle.scales_csv)
    master_df = pd.read_csv(bundle.master_csv)

    scales = _upsert_scales(version.id, scales_df)
    questions = _upsert_questions(version.id, master_df)

    return {
        "definition_id": str(definition.id),
        "version_id": str(version.id),
        "scales": len(scales),
        "questions": len(questions),
        "source_master_csv": str(bundle.master_csv),
        "source_scales_csv": str(bundle.scales_csv),
    }


def bootstrap_questionnaire_backend_v2(created_by: uuid.UUID | None = None, source_dir: Path | None = None) -> dict[str, Any]:
    questionnaire_stats = sync_questionnaire_catalog(created_by=created_by, source_dir=source_dir)
    model_stats = sync_active_models()

    db.session.commit()

    return {
        "questionnaire": questionnaire_stats,
        "models": model_stats,
    }


def ensure_catalog_loaded() -> QuestionnaireVersion:
    version = (
        QuestionnaireVersion.query.join(
            QuestionnaireDefinition,
            QuestionnaireVersion.definition_id == QuestionnaireDefinition.id,
        )
        .filter(QuestionnaireDefinition.slug == DEFAULT_DEFINITION_SLUG)
        .filter(QuestionnaireVersion.is_active.is_(True))
        .order_by(QuestionnaireVersion.published_at.desc(), QuestionnaireVersion.created_at.desc())
        .first()
    )
    if version:
        return version

    result = bootstrap_questionnaire_backend_v2()
    version_id = result["questionnaire"]["version_id"]
    row = db.session.get(QuestionnaireVersion, uuid.UUID(version_id))
    if not row:
        raise RuntimeError("failed_to_bootstrap_questionnaire_catalog")
    return row


def get_active_activation(domain: str, mode_key: str, role: str) -> ModelModeDomainActivation:
    canonical_role = _normalize_role(role)
    candidates = [canonical_role]
    if canonical_role == "guardian":
        candidates.append("caregiver")

    for role_candidate in candidates:
        row = ModelModeDomainActivation.query.filter_by(
            domain=domain,
            mode_key=mode_key,
            role=role_candidate,
            active_flag=True,
        ).order_by(ModelModeDomainActivation.valid_from.desc()).first()
        if row:
            return row

    sync_active_models()
    db.session.commit()

    for role_candidate in candidates:
        row = ModelModeDomainActivation.query.filter_by(
            domain=domain,
            mode_key=mode_key,
            role=role_candidate,
            active_flag=True,
        ).order_by(ModelModeDomainActivation.valid_from.desc()).first()
        if row:
            return row

    raise LookupError(f"activation_not_found:{domain}:{mode_key}:{canonical_role}")
