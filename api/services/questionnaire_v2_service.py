import json
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from flask import current_app
from sqlalchemy import case, func, or_

from api.cache import (
    qv2_activation_snapshot_cache,
    qv2_active_payload_cache,
    qv2_question_bank_cache,
)
from api.security import check_password, hash_password
from api.services import crypto_service
from api.services import questionnaire_v2_loader_service as loader
from app.models import (
    AppUser,
    GeneratedReport,
    ModelConfidenceRegistry,
    ModelOperationalCaveat,
    ModelVersion,
    QuestionnaireAccessGrant,
    QuestionnaireAuditEvent,
    QuestionnaireQuestion,
    QuestionnaireQuestionMode,
    QuestionnaireRepeatMapping,
    QuestionnaireSession,
    QuestionnaireSessionAccessLink,
    QuestionnaireSessionAnswer,
    QuestionnaireSessionInternalFeature,
    QuestionnaireSessionItem,
    QuestionnaireSessionPdfExport,
    QuestionnaireSessionResult,
    QuestionnaireSessionResultComorbidity,
    QuestionnaireSessionResultDomain,
    QuestionnaireSessionTag,
    QuestionnaireShareCode,
    QuestionnaireTag,
    QuestionnaireInternalInput,
    QuestionnaireVersion,
    ReportJob,
    db,
)


DOMAIN_ORDER = ["adhd", "conduct", "elimination", "anxiety", "depression"]
ROLE_ALIAS_TO_CANONICAL = {
    "guardian": "guardian",
    "caregiver": "guardian",
    "psychologist": "psychologist",
}
MODE_TO_MODEL_KEY = {
    ("guardian", "short"): "caregiver_1_3",
    ("guardian", "medium"): "caregiver_2_3",
    ("guardian", "complete"): "caregiver_full",
    ("psychologist", "short"): "psychologist_1_3",
    ("psychologist", "medium"): "psychologist_2_3",
    ("psychologist", "complete"): "psychologist_full",
}

SESSION_STATUSES = {
    "draft",
    "in_progress",
    "submitted",
    "processed",
    "failed",
    "archived",
}

CLINICAL_SUMMARY_DISCLAIMER = (
    "Este resultado no constituye un diagnostico clinico ni reemplaza una evaluacion psicologica o medica formal. "
    "Se trata de una simulacion automatizada de apoyo al tamizaje y alerta temprana, basada en la informacion "
    "registrada en el cuestionario y en modelos estadisticos. Los resultados deben ser revisados por un profesional "
    "calificado antes de tomar decisiones clinicas, educativas o terapeuticas."
)


class RuntimeArtifactResolutionError(RuntimeError):
    """Raised when an active champion artifact cannot be resolved/executed."""


def _encrypt_json(value: Any, purpose: str) -> Any:
    return crypto_service.encrypt_json(value, purpose=purpose)


def _decrypt_json(value: Any, purpose: str) -> Any:
    return crypto_service.decrypt_json(value, purpose=purpose)


def _encrypt_text(value: str | None, purpose: str) -> str | None:
    return crypto_service.encrypt_text(value, purpose=purpose)


def _decrypt_text(value: str | None, purpose: str) -> str | None:
    return crypto_service.decrypt_text(value, purpose=purpose)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def _pdf_plot_backend():
    from matplotlib import pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    return plt, PdfPages


def _new_public_id() -> str:
    return f"QV2-{secrets.token_hex(6).upper()}"


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _default_feature_value(feature: str) -> Any:
    lowered = feature.lower()
    if lowered in {"sex_assigned_at_birth", "sex"}:
        return "unknown"
    if lowered in {"site"}:
        return "CBIC"
    if lowered in {"age_years", "age"}:
        return 9.0
    return 0.0


def _json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return text
    return str(value)


def _alert_level(probability: float) -> str:
    thresholds = current_app.config.get(
        "QV2_ALERT_THRESHOLDS",
        {
            "moderate": 0.35,
            "elevated": 0.55,
            "high": 0.75,
            "critical_review": 0.9,
        },
    )
    if probability >= float(thresholds.get("critical_review", 0.9)):
        return "critical_review"
    if probability >= float(thresholds.get("high", 0.75)):
        return "high"
    if probability >= float(thresholds.get("elevated", 0.55)):
        return "elevated"
    if probability >= float(thresholds.get("moderate", 0.35)):
        return "moderate"
    return "low"


def _normalize_role(role: str) -> str:
    out = ROLE_ALIAS_TO_CANONICAL.get(str(role or "").strip().lower())
    if not out:
        raise ValueError("invalid_role")
    return out


def _get_mode_key(role: str, mode: str) -> str:
    canonical_role = _normalize_role(role)
    key = MODE_TO_MODEL_KEY.get((canonical_role, mode))
    if not key:
        raise ValueError("invalid_mode_role")
    return key


def _active_version_snapshot() -> dict[str, Any]:
    return loader.get_active_version_snapshot(force_refresh=False)


def _active_version() -> QuestionnaireVersion:
    return loader.ensure_catalog_loaded()


def _active_model_pipeline_version() -> str:
    try:
        return Path(loader.DEFAULT_ACTIVE_MODELS).parent.parent.name
    except Exception:
        return "hybrid_active_modes_freeze_v16"


def _active_payload_cache_ttl_seconds() -> int:
    try:
        return max(0, int(current_app.config.get("QV2_ACTIVE_PAYLOAD_CACHE_TTL_SECONDS", 300)))
    except Exception:
        return 300


def _active_activation_cache_ttl_seconds() -> int:
    try:
        return max(0, int(current_app.config.get("QV2_ACTIVE_ACTIVATION_CACHE_TTL_SECONDS", 300)))
    except Exception:
        return 300


def invalidate_active_questionnaire_cache() -> None:
    qv2_active_payload_cache.clear()
    qv2_activation_snapshot_cache.clear()
    qv2_question_bank_cache.clear()
    _load_feature_contract_cached.cache_clear()
    _load_model_artifact.cache_clear()


def _access_grant_for_user(session_id: uuid.UUID, user_id: uuid.UUID) -> QuestionnaireAccessGrant | None:
    now = _utcnow()
    return (
        QuestionnaireAccessGrant.query.filter_by(session_id=session_id, grantee_user_id=user_id)
        .filter(QuestionnaireAccessGrant.revoked_at.is_(None))
        .filter(or_(QuestionnaireAccessGrant.expires_at.is_(None), QuestionnaireAccessGrant.expires_at > now))
        .order_by(QuestionnaireAccessGrant.created_at.desc())
        .first()
    )


def _can_view_session(session: QuestionnaireSession, user_id: uuid.UUID) -> bool:
    if session.owner_user_id == user_id:
        return True
    grant = _access_grant_for_user(session.id, user_id)
    return bool(grant and grant.can_view)


def _can_tag_session(session: QuestionnaireSession, user_id: uuid.UUID) -> bool:
    if session.owner_user_id == user_id:
        return True
    grant = _access_grant_for_user(session.id, user_id)
    return bool(grant and grant.can_tag)


def _can_download_pdf(session: QuestionnaireSession, user_id: uuid.UUID) -> bool:
    if session.owner_user_id == user_id:
        return True
    grant = _access_grant_for_user(session.id, user_id)
    return bool(grant and grant.can_download_pdf)


def ensure_view_access(session: QuestionnaireSession, user_id: uuid.UUID) -> None:
    if not _can_view_session(session, user_id):
        raise PermissionError("forbidden_session_access")


def ensure_tag_access(session: QuestionnaireSession, user_id: uuid.UUID) -> None:
    if not _can_tag_session(session, user_id):
        raise PermissionError("forbidden_session_tag")


def ensure_pdf_access(session: QuestionnaireSession, user_id: uuid.UUID) -> None:
    if not _can_download_pdf(session, user_id):
        raise PermissionError("forbidden_session_pdf")


def _audit(session_id: uuid.UUID | None, actor_user_id: uuid.UUID | None, event_type: str, payload: dict[str, Any] | None = None) -> None:
    db.session.add(
        QuestionnaireAuditEvent(
            session_id=session_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            payload_json=payload or {},
        )
    )


def _record_access(
    session_id: uuid.UUID,
    access_type: str,
    user_id: uuid.UUID | None,
    success: bool,
    share_code_id: uuid.UUID | None = None,
    access_grant_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> None:
    db.session.add(
        QuestionnaireSessionAccessLink(
            session_id=session_id,
            access_type=access_type,
            actor_user_id=user_id,
            share_code_id=share_code_id,
            access_grant_id=access_grant_id,
            success=success,
            notes=notes,
        )
    )


def _confidence_for_activation(activation_id: uuid.UUID) -> tuple[float, str, str | None]:
    row = ModelConfidenceRegistry.query.filter_by(activation_id=activation_id).order_by(
        ModelConfidenceRegistry.created_at.desc()
    ).first()
    if not row:
        return 50.0, "moderate", None
    return float(row.confidence_pct or 50.0), row.confidence_band or "moderate", row.operational_class


def _caveat_for_activation(activation_id: uuid.UUID) -> str | None:
    row = ModelOperationalCaveat.query.filter_by(activation_id=activation_id).order_by(
        ModelOperationalCaveat.created_at.desc()
    ).first()
    return row.caveat if row else None


@lru_cache(maxsize=64)
def _load_model_artifact(artifact_path: str):
    return joblib.load(artifact_path)


@lru_cache(maxsize=256)
def _load_feature_contract_cached(
    model_version_id: str,
    artifact_path: str | None,
    metadata_signature: str,
) -> tuple[list[str], dict[str, Any]]:
    metadata = {}
    if metadata_signature:
        try:
            metadata = json.loads(metadata_signature)
        except Exception:
            metadata = {}
    feature_columns = metadata.get("feature_columns") or []

    if artifact_path:
        meta_path = Path(artifact_path).parent / "metadata.json"
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                metadata = {**data, **metadata}
                if not feature_columns:
                    feature_columns = data.get("feature_columns") or []
            except Exception:
                pass

    return list(feature_columns), metadata


def _load_feature_contract(model_version: ModelVersion) -> tuple[list[str], dict[str, Any]]:
    metadata = model_version.metadata_json or {}
    artifact_path = model_version.artifact_path or model_version.fallback_artifact_path
    try:
        metadata_signature = json.dumps(metadata, sort_keys=True, ensure_ascii=True)
    except Exception:
        metadata_signature = "{}"
    return _load_feature_contract_cached(
        str(model_version.id),
        artifact_path,
        metadata_signature,
    )


def _normalize_answer(question: QuestionnaireQuestion, answer: Any) -> tuple[Any, str]:
    response_type = (question.response_type or "").strip().lower()
    if response_type in {"integer"}:
        value = int(round(float(answer)))
        if question.min_value is not None and value < float(question.min_value):
            raise ValueError("answer_below_min")
        if question.max_value is not None and value > float(question.max_value):
            raise ValueError("answer_above_max")
        return value, str(value)

    if response_type in {"decimal", "numeric_range"}:
        value = float(answer)
        if question.min_value is not None and value < float(question.min_value):
            raise ValueError("answer_below_min")
        if question.max_value is not None and value > float(question.max_value):
            raise ValueError("answer_above_max")
        return value, str(value)

    if response_type in {"single_choice", "likert_single", "boolean"}:
        options = _json(question.response_options_json)
        if isinstance(options, list) and options:
            allowed = set()
            for opt in options:
                if isinstance(opt, dict):
                    allowed.add(str(opt.get("value")))
                else:
                    allowed.add(str(opt))
            if str(answer) not in allowed:
                raise ValueError("answer_not_allowed")
        return answer, str(answer)

    return answer, str(answer)


def _session_item_question_ids(session_id: uuid.UUID) -> set[uuid.UUID]:
    rows = QuestionnaireSessionItem.query.filter_by(session_id=session_id).all()
    return {row.question_id for row in rows}


def _mark_item_answered(session_id: uuid.UUID, question_id: uuid.UUID) -> None:
    row = QuestionnaireSessionItem.query.filter_by(session_id=session_id, question_id=question_id).first()
    if not row:
        return
    row.answered = True
    row.answered_at = _utcnow()
    row.updated_at = _utcnow()
    db.session.add(row)


def _recompute_progress(session: QuestionnaireSession) -> None:
    total, answered = (
        db.session.query(
            func.count(QuestionnaireSessionItem.id),
            func.coalesce(
                func.sum(
                    case(
                        (QuestionnaireSessionItem.answered.is_(True), 1),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .filter(
            QuestionnaireSessionItem.session_id == session.id,
            QuestionnaireSessionItem.is_visible.is_(True),
        )
        .one()
    )
    total = int(total or 0)
    answered = int(answered or 0)
    progress = (answered / total) * 100.0 if total > 0 else 0.0
    session.progress_pct = round(progress, 2)
    if session.status == "draft" and answered > 0:
        session.status = "in_progress"
    session.updated_at = _utcnow()
    db.session.add(session)


def _session_sections(session_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.session.query(QuestionnaireSessionItem, QuestionnaireQuestion)
        .join(QuestionnaireQuestion, QuestionnaireSessionItem.question_id == QuestionnaireQuestion.id)
        .filter(QuestionnaireSessionItem.session_id == session_id)
        .filter(QuestionnaireSessionItem.is_visible.is_(True))
        .order_by(QuestionnaireSessionItem.page_number.asc(), QuestionnaireSessionItem.display_order.asc())
        .all()
    )

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item, question in rows:
        grouped[item.page_number].append(
            {
                "session_item_id": str(item.id),
                "question_id": str(question.id),
                "question_code": question.question_code,
                "feature": question.feature_key,
                "prompt": question.caregiver_question or question.psychologist_question or question.question_text_primary,
                "help_text": question.help_text,
                "response_type": question.response_type,
                "scale_id": question.scale_id,
                "response_options": question.response_options_json,
                "min_value": question.min_value,
                "max_value": question.max_value,
                "answered": bool(item.answered),
            }
        )

    out = []
    for page_number in sorted(grouped):
        out.append(
            {
                "page_number": page_number,
                "questions": grouped[page_number],
            }
        )
    return out


def _load_mode_question_bank(version_id: uuid.UUID, mode_key: str) -> list[dict[str, Any]]:
    cache_ttl = _active_payload_cache_ttl_seconds()
    cache_key = f"{version_id}:{mode_key}"
    if cache_ttl > 0:
        cached = qv2_question_bank_cache.get(cache_key)
        if isinstance(cached, list):
            return cached

    repeated_ids = {
        row.repeated_question_id
        for row in QuestionnaireRepeatMapping.query.filter_by(version_id=version_id, reuse_answer=True).all()
    }

    rows = (
        db.session.query(QuestionnaireQuestion)
        .join(QuestionnaireQuestionMode, QuestionnaireQuestionMode.question_id == QuestionnaireQuestion.id)
        .filter(QuestionnaireQuestion.version_id == version_id)
        .filter(QuestionnaireQuestion.visible_question.is_(True))
        .filter(QuestionnaireQuestionMode.mode_key == mode_key)
        .filter(QuestionnaireQuestionMode.is_included.is_(True))
        .order_by(QuestionnaireQuestion.display_order.asc())
        .all()
    )

    visible = [q for q in rows if q.id not in repeated_ids]
    questions_payload = []
    for question in visible:
        questions_payload.append(
            {
                "question_id": str(question.id),
                "question_code": question.question_code,
                "feature": question.feature_key,
                "prompt": question.caregiver_question or question.psychologist_question or question.question_text_primary,
                "help_text": question.help_text,
                "response_type": question.response_type,
                "scale_id": question.scale_id,
                "response_options": question.response_options_json,
                "min_value": question.min_value,
                "max_value": question.max_value,
                "requires_internal_scoring": bool(question.requires_internal_scoring),
                "requires_exact_item_wording": bool(question.requires_exact_item_wording),
                "requires_clinician_administration": bool(question.requires_clinician_administration),
                "requires_child_self_report": bool(question.requires_child_self_report),
            }
        )

    if cache_ttl > 0:
        qv2_question_bank_cache.set(cache_key, questions_payload, ttl_seconds=cache_ttl)
    return questions_payload


def _load_confidence_by_domain(
    *,
    version_id: str,
    pipeline_version: str,
    mode_key: str,
    canonical_role: str,
) -> dict[str, dict[str, Any]]:
    cache_key = (version_id, pipeline_version, mode_key, canonical_role)
    cache_ttl = _active_activation_cache_ttl_seconds()
    if cache_ttl > 0:
        cached = qv2_activation_snapshot_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

    activations = {
        domain: loader.get_active_activation(
            domain=domain,
            mode_key=mode_key,
            role=canonical_role,
        )
        for domain in DOMAIN_ORDER
    }
    activation_ids = [activation.id for activation in activations.values()]

    confidence_latest: dict[uuid.UUID, ModelConfidenceRegistry] = {}
    confidence_rows = (
        ModelConfidenceRegistry.query.filter(
            ModelConfidenceRegistry.activation_id.in_(activation_ids)
        )
        .order_by(
            ModelConfidenceRegistry.activation_id.asc(),
            ModelConfidenceRegistry.created_at.desc(),
        )
        .all()
    )
    for row in confidence_rows:
        if row.activation_id not in confidence_latest:
            confidence_latest[row.activation_id] = row

    confidence_by_domain: dict[str, dict[str, Any]] = {}
    for domain in DOMAIN_ORDER:
        activation = activations[domain]
        confidence_row = confidence_latest.get(activation.id)
        if confidence_row:
            confidence_pct = float(confidence_row.confidence_pct or 50.0)
            band = confidence_row.confidence_band or "moderate"
            operational_class = confidence_row.operational_class
        else:
            confidence_pct, band, operational_class = 50.0, "moderate", None
        confidence_by_domain[domain] = {
            "confidence_pct": confidence_pct,
            "confidence_band": band,
            "operational_class": operational_class,
        }

    if cache_ttl > 0:
        qv2_activation_snapshot_cache.set(cache_key, confidence_by_domain, ttl_seconds=cache_ttl)
    return confidence_by_domain


def get_active_questionnaire_payload(mode: str, role: str, include_full: bool = False, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    version_snapshot = _active_version_snapshot()
    version_id = str(version_snapshot.get("id") or "")
    if not version_id:
        version = _active_version()
        version_id = str(version.id)
        version_snapshot = {
            "id": version_id,
            "version_label": version.version_label,
            "questionnaire_version_final": version.questionnaire_version_final,
            "scales_version_label": version.scales_version_label,
            "definition_slug": loader.DEFAULT_DEFINITION_SLUG,
        }

    canonical_role = _normalize_role(role)
    mode_key = _get_mode_key(canonical_role, mode)
    pipeline_version = _active_model_pipeline_version()

    cache_key = (
        version_id,
        pipeline_version,
        mode,
        canonical_role,
        bool(include_full),
        int(page),
        int(page_size),
    )
    cache_ttl = _active_payload_cache_ttl_seconds()
    if cache_ttl > 0:
        cached = qv2_active_payload_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

    version = _active_version()
    questions_payload = _load_mode_question_bank(version.id, mode_key)
    confidence_by_domain = _load_confidence_by_domain(
        version_id=version_id,
        pipeline_version=pipeline_version,
        mode_key=mode_key,
        canonical_role=canonical_role,
    )

    total = len(questions_payload)
    if include_full:
        paged = questions_payload
    else:
        start = (page - 1) * page_size
        paged = questions_payload[start : start + page_size]

    payload = {
        "questionnaire": {
            "definition_slug": version_snapshot.get("definition_slug") or loader.DEFAULT_DEFINITION_SLUG,
            "version_label": version_snapshot.get("version_label") or version.version_label,
            "questionnaire_version_final": version_snapshot.get("questionnaire_version_final") or version.questionnaire_version_final,
            "scales_version_label": version_snapshot.get("scales_version_label") or version.scales_version_label,
            "mode": mode,
            "role": canonical_role,
            "mode_key": mode_key,
            "supported_domains": DOMAIN_ORDER,
            "confidence_by_domain": confidence_by_domain,
            "has_repeat_mapping": True,
        },
        "questions": paged,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
    }

    if cache_ttl > 0:
        qv2_active_payload_cache.set(cache_key, payload, ttl_seconds=cache_ttl)
    return payload


def create_session(owner_user_id: uuid.UUID, payload: dict[str, Any]) -> QuestionnaireSession:
    mode = str(payload.get("mode") or "").strip().lower()
    role = _normalize_role(str(payload.get("role") or "").strip().lower())
    mode_key = _get_mode_key(role, mode)
    version = _active_version()

    session_metadata = {
        "child_age_years": payload.get("child_age_years"),
        "child_sex_assigned_at_birth": payload.get("child_sex_assigned_at_birth"),
        "metadata": payload.get("metadata") or {},
    }

    session = QuestionnaireSession(
        questionnaire_public_id=_new_public_id(),
        version_id=version.id,
        owner_user_id=owner_user_id,
        respondent_role=role,
        mode=mode,
        mode_key=mode_key,
        status="draft",
        progress_pct=0,
        questionnaire_version_label=version.version_label,
        scales_version_label=version.scales_version_label,
        model_pipeline_version=_active_model_pipeline_version(),
        metadata_json=_encrypt_json(session_metadata, "questionnaire_session.metadata_json"),
    )
    db.session.add(session)
    db.session.flush()

    repeated_ids = {
        row.repeated_question_id
        for row in QuestionnaireRepeatMapping.query.filter_by(version_id=version.id, reuse_answer=True).all()
    }

    rows = (
        db.session.query(QuestionnaireQuestion, QuestionnaireQuestionMode)
        .join(QuestionnaireQuestionMode, QuestionnaireQuestionMode.question_id == QuestionnaireQuestion.id)
        .filter(QuestionnaireQuestion.version_id == version.id)
        .filter(QuestionnaireQuestion.visible_question.is_(True))
        .filter(QuestionnaireQuestionMode.mode_key == mode_key)
        .filter(QuestionnaireQuestionMode.is_included.is_(True))
        .order_by(QuestionnaireQuestion.display_order.asc())
        .all()
    )

    page_tracker: dict[uuid.UUID | None, int] = {}
    next_page = 1
    session_items: list[QuestionnaireSessionItem] = []
    for order, (question, _) in enumerate(rows, start=1):
        if question.id in repeated_ids:
            continue
        section_id = question.section_id
        if section_id not in page_tracker:
            page_tracker[section_id] = next_page
            next_page += 1
        page_number = page_tracker[section_id]
        session_items.append(
            QuestionnaireSessionItem(
                session_id=session.id,
                section_id=section_id,
                question_id=question.id,
                page_number=page_number,
                display_order=order,
                is_visible=True,
                is_required=True,
                answered=False,
            )
        )
    if session_items:
        db.session.add_all(session_items)

    _audit(session.id, owner_user_id, "session_created", {"mode": mode, "role": role, "mode_key": mode_key})
    db.session.commit()
    return session


def get_session_or_404(session_id: uuid.UUID) -> QuestionnaireSession:
    row = db.session.get(QuestionnaireSession, session_id)
    if not row:
        raise LookupError("session_not_found")
    return row


def get_session_payload(session: QuestionnaireSession) -> dict[str, Any]:
    return {
        "session_id": str(session.id),
        "questionnaire_id": session.questionnaire_public_id,
        "status": session.status,
        "mode": session.mode,
        "role": _normalize_role(session.respondent_role),
        "mode_key": session.mode_key,
        "progress_pct": float(session.progress_pct or 0),
        "version": session.questionnaire_version_label,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def get_session_page_payload(session: QuestionnaireSession, page: int, page_size: int) -> dict[str, Any]:
    base_query = QuestionnaireSessionItem.query.filter(
        QuestionnaireSessionItem.session_id == session.id,
        QuestionnaireSessionItem.is_visible.is_(True),
    )
    total = (
        db.session.query(func.count(func.distinct(QuestionnaireSessionItem.page_number)))
        .filter(
            QuestionnaireSessionItem.session_id == session.id,
            QuestionnaireSessionItem.is_visible.is_(True),
        )
        .scalar()
        or 0
    )

    page_numbers = [
        row[0]
        for row in base_query.with_entities(QuestionnaireSessionItem.page_number)
        .group_by(QuestionnaireSessionItem.page_number)
        .order_by(QuestionnaireSessionItem.page_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    ]

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if page_numbers:
        rows = (
            db.session.query(QuestionnaireSessionItem, QuestionnaireQuestion)
            .join(
                QuestionnaireQuestion,
                QuestionnaireSessionItem.question_id == QuestionnaireQuestion.id,
            )
            .filter(QuestionnaireSessionItem.session_id == session.id)
            .filter(QuestionnaireSessionItem.is_visible.is_(True))
            .filter(QuestionnaireSessionItem.page_number.in_(page_numbers))
            .order_by(
                QuestionnaireSessionItem.page_number.asc(),
                QuestionnaireSessionItem.display_order.asc(),
            )
            .all()
        )
        for item, question in rows:
            grouped[item.page_number].append(
                {
                    "session_item_id": str(item.id),
                    "question_id": str(question.id),
                    "question_code": question.question_code,
                    "feature": question.feature_key,
                    "prompt": question.caregiver_question
                    or question.psychologist_question
                    or question.question_text_primary,
                    "help_text": question.help_text,
                    "response_type": question.response_type,
                    "scale_id": question.scale_id,
                    "response_options": question.response_options_json,
                    "min_value": question.min_value,
                    "max_value": question.max_value,
                    "answered": bool(item.answered),
                }
            )

    sections = [
        {
            "page_number": page_number,
            "questions": grouped.get(page_number, []),
        }
        for page_number in page_numbers
    ]
    return {
        "session": get_session_payload(session),
        "pages": sections,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
    }


def save_answers(session: QuestionnaireSession, user_id: uuid.UUID, answers: list[dict[str, Any]], mark_final: bool = False) -> dict[str, Any]:
    if session.status in {"submitted", "processed", "archived"}:
        raise ValueError("session_not_editable")

    allowed_ids = _session_item_question_ids(session.id)
    normalized_items: list[tuple[uuid.UUID, Any]] = []
    for item in answers:
        question_id = (
            item["question_id"]
            if isinstance(item["question_id"], uuid.UUID)
            else uuid.UUID(str(item["question_id"]))
        )
        if question_id not in allowed_ids:
            raise ValueError(f"question_not_in_session:{question_id}")
        normalized_items.append((question_id, item.get("answer")))

    question_ids = [question_id for question_id, _ in normalized_items]
    questions = QuestionnaireQuestion.query.filter(QuestionnaireQuestion.id.in_(question_ids)).all()
    questions_by_id = {row.id: row for row in questions}

    existing_answers = QuestionnaireSessionAnswer.query.filter(
        QuestionnaireSessionAnswer.session_id == session.id,
        QuestionnaireSessionAnswer.question_id.in_(question_ids),
    ).all()
    answers_by_question_id = {row.question_id: row for row in existing_answers}

    session_items = QuestionnaireSessionItem.query.filter(
        QuestionnaireSessionItem.session_id == session.id,
        QuestionnaireSessionItem.question_id.in_(question_ids),
    ).all()
    session_items_by_question_id = {row.question_id: row for row in session_items}

    repeat_mappings = QuestionnaireRepeatMapping.query.filter(
        QuestionnaireRepeatMapping.version_id == session.version_id,
        QuestionnaireRepeatMapping.canonical_question_id.in_(question_ids),
        QuestionnaireRepeatMapping.reuse_answer.is_(True),
    ).all()
    repeated_ids: set[uuid.UUID] = set()
    repeated_by_canonical: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for mapping in repeat_mappings:
        repeated_by_canonical[mapping.canonical_question_id].append(mapping.repeated_question_id)
        repeated_ids.add(mapping.repeated_question_id)

    existing_repeated_answers: dict[uuid.UUID, QuestionnaireSessionAnswer] = {}
    if repeated_ids:
        repeated_rows = QuestionnaireSessionAnswer.query.filter(
            QuestionnaireSessionAnswer.session_id == session.id,
            QuestionnaireSessionAnswer.question_id.in_(repeated_ids),
        ).all()
        existing_repeated_answers = {row.question_id: row for row in repeated_rows}

    for question_id, answer in normalized_items:
        question = questions_by_id.get(question_id)
        if not question:
            raise LookupError("question_not_found")

        raw, normalized = _normalize_answer(question, answer)
        answer_row = answers_by_question_id.get(question_id)
        if not answer_row:
            answer_row = QuestionnaireSessionAnswer(session_id=session.id, question_id=question_id)
            answers_by_question_id[question_id] = answer_row
        answer_row.canonical_question_id = question_id
        answer_row.answer_raw = _encrypt_json(
            _json(raw),
            "questionnaire_session_answer.answer_raw",
        )
        answer_row.answer_normalized = _encrypt_text(
            normalized,
            "questionnaire_session_answer.answer_normalized",
        ) or ""
        answer_row.answered_by_user_id = user_id
        answer_row.is_final = bool(mark_final)
        answer_row.source = "user"
        answer_row.updated_at = _utcnow()
        db.session.add(answer_row)

        session_item = session_items_by_question_id.get(question_id)
        if session_item:
            session_item.answered = True
            session_item.answered_at = _utcnow()
            session_item.updated_at = _utcnow()
            db.session.add(session_item)

        for repeated_question_id in repeated_by_canonical.get(question_id, []):
            hidden = existing_repeated_answers.get(repeated_question_id)
            if not hidden:
                hidden = QuestionnaireSessionAnswer(
                    session_id=session.id,
                    question_id=repeated_question_id,
                )
                existing_repeated_answers[repeated_question_id] = hidden
            hidden.canonical_question_id = question_id
            hidden.answer_raw = _encrypt_json(
                _json(raw),
                "questionnaire_session_answer.answer_raw",
            )
            hidden.answer_normalized = _encrypt_text(
                normalized,
                "questionnaire_session_answer.answer_normalized",
            ) or ""
            hidden.answered_by_user_id = user_id
            hidden.is_final = bool(mark_final)
            hidden.source = "repeat_mapping"
            hidden.updated_at = _utcnow()
            db.session.add(hidden)

    _recompute_progress(session)
    _audit(session.id, user_id, "answers_saved", {"count": len(answers), "mark_final": mark_final})
    db.session.commit()

    return {
        "session": get_session_payload(session),
        "saved_answers": len(answers),
    }


def _answers_to_feature_map(session: QuestionnaireSession) -> dict[str, Any]:
    rows = (
        db.session.query(QuestionnaireSessionAnswer, QuestionnaireQuestion)
        .join(QuestionnaireQuestion, QuestionnaireSessionAnswer.question_id == QuestionnaireQuestion.id)
        .filter(QuestionnaireSessionAnswer.session_id == session.id)
        .all()
    )

    feature_map: dict[str, Any] = {}
    for answer, question in rows:
        feature_map[question.feature_key] = _decrypt_json(
            answer.answer_raw,
            "questionnaire_session_answer.answer_raw",
        )

    meta = _decrypt_json(session.metadata_json, "questionnaire_session.metadata_json") or {}
    if meta.get("child_age_years") is not None:
        feature_map.setdefault("age_years", float(meta["child_age_years"]))
    if meta.get("child_sex_assigned_at_birth"):
        feature_map.setdefault("sex_assigned_at_birth", str(meta["child_sex_assigned_at_birth"]).lower())

    return feature_map


def _derive_internal_features(session: QuestionnaireSession, feature_map: dict[str, Any]) -> dict[str, Any]:
    QuestionnaireSessionInternalFeature.query.filter_by(session_id=session.id).delete(synchronize_session=False)

    internals = QuestionnaireInternalInput.query.filter_by(version_id=session.version_id).all()
    derived: dict[str, Any] = dict(feature_map)

    for internal in internals:
        value = derived.get(internal.feature_key)
        source_type = "direct"
        formula = (internal.internal_scoring_formula_summary or "").lower()
        sources = internal.derived_from_features or []
        if value is None and sources:
            nums = [_to_float(derived.get(src), 0.0) or 0.0 for src in sources]
            if "count" in formula:
                value = float(sum(1 for n in nums if n > 0))
            elif "threshold" in formula:
                value = 1.0 if (sum(nums) / max(len(nums), 1)) >= 1.0 else 0.0
            else:
                value = float(sum(nums) / max(len(nums), 1))
            source_type = "derived"

        if value is None:
            value = _default_feature_value(internal.feature_key)
            source_type = "default"

        derived[internal.feature_key] = value

        numeric_value = _to_float(value)
        text_value = None if numeric_value is not None else str(value)
        encrypted_feature_payload = _encrypt_json(
            {"numeric": numeric_value, "text": text_value},
            "questionnaire_session_internal_feature.feature_value",
        )
        encrypted_feature_text = _encrypt_text(
            json.dumps({"numeric": numeric_value, "text": text_value}, ensure_ascii=False),
            "questionnaire_session_internal_feature.feature_value_text",
        )

        db.session.add(
            QuestionnaireSessionInternalFeature(
                session_id=session.id,
                feature_key=internal.feature_key,
                feature_value_numeric=None if crypto_service.is_field_encryption_enabled() else numeric_value,
                feature_value_text=encrypted_feature_text if crypto_service.is_field_encryption_enabled() else text_value,
                source_type=source_type,
                source_question_id=internal.source_question_id,
                metadata_json={
                    "formula": internal.internal_scoring_formula_summary,
                    "sources": sources,
                    "encrypted_feature_payload": encrypted_feature_payload if crypto_service.is_field_encryption_enabled() else None,
                },
            )
        )

    return derived


def _heuristic_domain_probability(domain: str, feature_map: dict[str, Any]) -> float:
    candidates = []
    for key, value in feature_map.items():
        if domain in key.lower():
            numeric = _to_float(value)
            if numeric is not None:
                candidates.append(max(0.0, min(4.0, numeric)) / 4.0)
    if not candidates:
        return 0.5
    return max(0.01, min(0.99, sum(candidates) / len(candidates)))


def _model_probability(model_version: ModelVersion, feature_map: dict[str, Any], domain: str) -> float:
    artifact_path = model_version.artifact_path or model_version.fallback_artifact_path
    allow_testing_heuristic = bool(current_app.config.get("TESTING"))
    if not artifact_path:
        if allow_testing_heuristic:
            return _heuristic_domain_probability(domain, feature_map)
        raise RuntimeArtifactResolutionError(
            f"active_artifact_missing_path:{domain}:{model_version.model_registry_id}"
        )
    if not Path(artifact_path).exists():
        if allow_testing_heuristic:
            return _heuristic_domain_probability(domain, feature_map)
        raise RuntimeArtifactResolutionError(
            f"active_artifact_not_found:{domain}:{artifact_path}"
        )

    feature_columns, _ = _load_feature_contract(model_version)
    if not feature_columns:
        raise RuntimeArtifactResolutionError(
            f"active_feature_contract_missing:{domain}:{model_version.model_registry_id}"
        )

    vector = {}
    for col in feature_columns:
        value = feature_map.get(col, _default_feature_value(col))
        if isinstance(value, str):
            parsed = _to_float(value)
            value = parsed if parsed is not None else value
        vector[col] = value

    try:
        model = _load_model_artifact(artifact_path)
        X = pd.DataFrame([vector], columns=feature_columns)
        if not hasattr(model, "predict_proba"):
            raise RuntimeArtifactResolutionError(
                f"active_artifact_without_predict_proba:{domain}:{artifact_path}"
            )
        probability = float(model.predict_proba(X)[0][1])
        return max(0.0, min(1.0, probability))
    except RuntimeArtifactResolutionError:
        raise
    except Exception as exc:
        if allow_testing_heuristic:
            return _heuristic_domain_probability(domain, feature_map)
        raise RuntimeArtifactResolutionError(
            f"active_artifact_inference_failed:{domain}:{artifact_path}:{type(exc).__name__}"
        ) from exc


def _comorbidity_rows(domain_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    elevated = [row for row in domain_rows if row["probability"] >= 0.55]
    elevated = sorted(elevated, key=lambda row: row["probability"], reverse=True)
    out: list[dict[str, Any]] = []

    for i in range(len(elevated)):
        for j in range(i + 1, len(elevated)):
            left = elevated[i]
            right = elevated[j]
            score = round((left["probability"] + right["probability"]) / 2.0, 4)
            level = "high" if score >= 0.75 else "moderate"
            out.append(
                {
                    "coexistence_key": f"{left['domain']}+{right['domain']}",
                    "domains": [left["domain"], right["domain"]],
                    "combined_risk_score": score,
                    "coexistence_level": level,
                    "summary": (
                        f"Posible coexistencia operativa entre {left['domain']} y {right['domain']} "
                        "(tamizaje no diagnostico)."
                    ),
                }
            )

    return out[:6]


def _summary_from_domains(domain_rows: list[dict[str, Any]]) -> tuple[str, str, bool]:
    highest = sorted(domain_rows, key=lambda item: item["probability"], reverse=True)
    top = highest[0] if highest else None
    if not top:
        return (
            "No hay resultados de dominio disponibles.",
            "Requiere nuevo procesamiento.",
            True,
        )

    if top["alert_level"] in {"critical_review", "high"}:
        summary = "Se observan dominios con alerta elevada que requieren revision profesional prioritaria."
        recommendation = "Escalar a revision profesional; usar este resultado solo como apoyo de screening."
        needs_review = True
    elif top["alert_level"] == "elevated":
        summary = "Hay senales elevadas en uno o mas dominios; se recomienda seguimiento cercano."
        recommendation = "Programar revision profesional y seguimiento estructurado."
        needs_review = True
    else:
        summary = "No se detectan alertas elevadas dominantes en esta corrida de screening."
        recommendation = "Mantener monitoreo preventivo y repetir cuestionario ante cambios relevantes."
        needs_review = False

    return summary, recommendation, needs_review


def submit_session(session: QuestionnaireSession, user_id: uuid.UUID, force_reprocess: bool = False) -> dict[str, Any]:
    if session.status in {"processed", "archived"} and not force_reprocess:
        raise ValueError("session_already_processed")

    if session.status not in {"draft", "in_progress", "failed", "submitted", "processed"}:
        raise ValueError("invalid_session_status")

    answers_count = QuestionnaireSessionAnswer.query.filter_by(session_id=session.id).count()
    if answers_count <= 0:
        raise ValueError("empty_answers")

    session.status = "submitted"
    session.submitted_at = _utcnow()
    db.session.add(session)

    feature_map = _answers_to_feature_map(session)
    feature_map = _derive_internal_features(session, feature_map)

    QuestionnaireSessionResultDomain.query.filter_by(session_id=session.id).delete(synchronize_session=False)
    QuestionnaireSessionResultComorbidity.query.filter_by(session_id=session.id).delete(synchronize_session=False)

    existing_result = QuestionnaireSessionResult.query.filter_by(session_id=session.id).first()
    if existing_result:
        result = existing_result
    else:
        result = QuestionnaireSessionResult(session_id=session.id)

    domain_rows: list[dict[str, Any]] = []
    role_for_lookup = _normalize_role(session.respondent_role)

    for domain in DOMAIN_ORDER:
        activation = loader.get_active_activation(domain=domain, mode_key=session.mode_key, role=role_for_lookup)
        model_version = db.session.get(ModelVersion, activation.model_version_id)
        if not model_version:
            raise LookupError(f"model_version_missing:{activation.model_version_id}")

        probability = _model_probability(model_version=model_version, feature_map=feature_map, domain=domain)
        alert = _alert_level(probability)
        confidence_pct, confidence_band, operational_class = _confidence_for_activation(activation.id)
        caveat = _caveat_for_activation(activation.id)
        needs_review = alert in {"elevated", "high", "critical_review"} or confidence_band in {"limited", "low"}

        summary = (
            f"{domain.upper()}: probabilidad {round(probability * 100, 2)}%, alerta {alert}. "
            "Salida para apoyo de screening en entorno simulado; no diagnostico automatico."
        )

        row_payload = {
            "domain": domain,
            "probability": probability,
            "alert_level": alert,
            "confidence_pct": confidence_pct,
            "confidence_band": confidence_band,
            "model_id": model_version.model_registry_id,
            "model_version": model_version.model_version_tag,
            "mode": session.mode_key,
            "operational_class": operational_class,
            "operational_caveat": caveat,
            "result_summary": summary,
            "needs_professional_review": needs_review,
        }
        domain_rows.append(row_payload)

    overall_summary, recommendation, needs_review = _summary_from_domains(domain_rows)

    result.summary_text = _encrypt_text(
        overall_summary,
        "questionnaire_session_result.summary_text",
    ) or ""
    result.operational_recommendation = _encrypt_text(
        recommendation,
        "questionnaire_session_result.operational_recommendation",
    ) or ""
    result.completion_quality_score = round(float(session.progress_pct or 0) / 100.0, 4)
    result.missingness_score = round(1.0 - float(result.completion_quality_score or 0.0), 4)
    result.inconsistency_flags_json = {}
    result.needs_professional_review = needs_review
    result.runtime_ms = None
    result.model_bundle_version = _active_model_pipeline_version()
    result.questionnaire_version_label = session.questionnaire_version_label
    result.scales_version_label = session.scales_version_label
    result.metadata_json = _encrypt_json(
        {
            "mode": session.mode,
            "mode_key": session.mode_key,
            "role": role_for_lookup,
        },
        "questionnaire_session_result.metadata_json",
    )
    result.processed_at = _utcnow()
    result.updated_at = _utcnow()
    db.session.add(result)
    db.session.flush()

    for domain_row in domain_rows:
        db.session.add(
            QuestionnaireSessionResultDomain(
                result_id=result.id,
                session_id=session.id,
                domain=domain_row["domain"],
                probability=domain_row["probability"],
                alert_level=domain_row["alert_level"],
                confidence_pct=domain_row["confidence_pct"],
                confidence_band=domain_row["confidence_band"],
                model_id=str(domain_row["model_id"]),
                model_version=domain_row["model_version"],
                mode=domain_row["mode"],
                operational_class=domain_row["operational_class"],
                operational_caveat=domain_row["operational_caveat"],
                result_summary=_encrypt_text(
                    domain_row["result_summary"],
                    "questionnaire_session_result_domain.result_summary",
                ) or "",
                needs_professional_review=domain_row["needs_professional_review"],
                metadata_json=_encrypt_json(
                    {"source": "runtime_v2"},
                    "questionnaire_session_result_domain.metadata_json",
                ),
            )
        )

    for item in _comorbidity_rows(domain_rows):
        db.session.add(
            QuestionnaireSessionResultComorbidity(
                result_id=result.id,
                session_id=session.id,
                coexistence_key=item["coexistence_key"],
                domains_json=_encrypt_json(
                    item["domains"],
                    "questionnaire_session_result_comorbidity.domains_json",
                ),
                combined_risk_score=item["combined_risk_score"],
                coexistence_level=item["coexistence_level"],
                summary=_encrypt_text(
                    item["summary"],
                    "questionnaire_session_result_comorbidity.summary",
                ) or "",
            )
        )

    session.status = "processed"
    session.processed_at = _utcnow()
    session.completion_quality_score = result.completion_quality_score
    session.missingness_score = result.missingness_score
    session.inconsistency_flags_json = result.inconsistency_flags_json
    session.updated_at = _utcnow()
    db.session.add(session)

    _audit(session.id, user_id, "session_submitted", {"force_reprocess": force_reprocess})
    db.session.commit()

    return get_results_payload(session)


def get_results_payload(session: QuestionnaireSession) -> dict[str, Any]:
    result = QuestionnaireSessionResult.query.filter_by(session_id=session.id).first()
    domains = QuestionnaireSessionResultDomain.query.filter_by(session_id=session.id).order_by(
        QuestionnaireSessionResultDomain.domain.asc()
    ).all()
    comorbidity = QuestionnaireSessionResultComorbidity.query.filter_by(session_id=session.id).all()

    if result:
        result_summary = _decrypt_text(
            result.summary_text,
            "questionnaire_session_result.summary_text",
        )
        result_recommendation = _decrypt_text(
            result.operational_recommendation,
            "questionnaire_session_result.operational_recommendation",
        )
    else:
        result_summary = None
        result_recommendation = None

    return {
        "session": get_session_payload(session),
        "result": {
            "summary": result_summary,
            "operational_recommendation": result_recommendation,
            "completion_quality_score": result.completion_quality_score if result else None,
            "missingness_score": result.missingness_score if result else None,
            "needs_professional_review": result.needs_professional_review if result else None,
        },
        "domains": [
            {
                "domain": row.domain,
                "probability": row.probability,
                "alert_level": row.alert_level,
                "confidence_pct": row.confidence_pct,
                "confidence_band": row.confidence_band,
                "model_id": row.model_id,
                "model_version": row.model_version,
                "mode": row.mode,
                "operational_class": row.operational_class,
                "operational_caveat": row.operational_caveat,
                "result_summary": _decrypt_text(
                    row.result_summary,
                    "questionnaire_session_result_domain.result_summary",
                ),
                "needs_professional_review": row.needs_professional_review,
            }
            for row in domains
        ],
        "comorbidity": [
            {
                "coexistence_key": row.coexistence_key,
                "domains": _decrypt_json(
                    row.domains_json,
                    "questionnaire_session_result_comorbidity.domains_json",
                ),
                "combined_risk_score": row.combined_risk_score,
                "coexistence_level": row.coexistence_level,
                "summary": _decrypt_text(
                    row.summary,
                    "questionnaire_session_result_comorbidity.summary",
                ),
            }
            for row in comorbidity
        ],
    }


def _risk_level_from_probability(probability: float) -> str:
    if probability >= 0.75:
        return "alta"
    if probability >= 0.55:
        return "relevante"
    if probability >= 0.35:
        return "intermedia"
    return "baja"


def _overall_risk_level(domains: list[dict[str, Any]]) -> str:
    if not domains:
        return "intermedia"
    max_probability = max(float(item.get("probability") or 0.0) for item in domains)
    elevated_count = sum(
        1 for item in domains if str(item.get("risk_level")) in {"relevante", "alta"}
    )
    if max_probability >= 0.75 and elevated_count >= 2:
        return "alta"
    if max_probability >= 0.55 or elevated_count >= 1:
        return "relevante"
    if max_probability >= 0.35:
        return "intermedia"
    return "baja"


def _format_indicator_value(value: Any) -> str:
    if value is None:
        return "sin valor"
    numeric = _to_float(value)
    if numeric is not None:
        return f"{numeric:.2f}"
    text = str(value).strip()
    return text[:120] if text else "sin valor"


def _domain_main_indicators(session_id: uuid.UUID, domain: str, limit: int = 5) -> list[str]:
    rows = (
        db.session.query(QuestionnaireSessionAnswer, QuestionnaireQuestion)
        .join(QuestionnaireQuestion, QuestionnaireSessionAnswer.question_id == QuestionnaireQuestion.id)
        .filter(QuestionnaireSessionAnswer.session_id == session_id)
        .filter(QuestionnaireQuestion.domain == domain)
        .all()
    )
    candidates: list[tuple[float, str]] = []
    for answer, question in rows:
        raw_value = _decrypt_json(
            answer.answer_raw,
            "questionnaire_session_answer.answer_raw",
        )
        numeric = _to_float(raw_value)
        score = abs(float(numeric)) if numeric is not None else 0.0
        label = f"{question.feature_key}: {_format_indicator_value(raw_value)}"
        candidates.append((score, label))

    candidates.sort(key=lambda item: item[0], reverse=True)
    out = [label for _, label in candidates[:limit] if label]
    if out:
        return out
    return ["Evidencia directa insuficiente en respuestas visibles para este dominio."]


def get_clinical_summary_payload(session: QuestionnaireSession) -> dict[str, Any]:
    results_payload = get_results_payload(session)
    raw_domains = results_payload.get("domains") or []
    domains: list[dict[str, Any]] = []

    for raw in raw_domains:
        probability = float(raw.get("probability") or 0.0)
        risk_level = _risk_level_from_probability(probability)
        main_indicators = _domain_main_indicators(session.id, raw.get("domain"), limit=5)
        domains.append(
            {
                "domain": str(raw.get("domain")),
                "probability": probability,
                "compatibility_level": risk_level,
                "risk_level": risk_level,
                "confidence_pct": raw.get("confidence_pct"),
                "confidence_band": raw.get("confidence_band"),
                "operational_class": raw.get("operational_class"),
                "caveat": raw.get("operational_caveat"),
                "main_indicators": main_indicators,
            }
        )

    domain_lookup = {item["domain"]: item for item in domains}
    ordered_domains = []
    for key in DOMAIN_ORDER:
        if key in domain_lookup:
            ordered_domains.append(domain_lookup[key])
    for item in domains:
        if item["domain"] not in DOMAIN_ORDER:
            ordered_domains.append(item)

    top_domains = sorted(ordered_domains, key=lambda item: item["probability"], reverse=True)
    elevated_domains = [item for item in top_domains if item["risk_level"] in {"relevante", "alta"}]
    monitor_domains = [item for item in top_domains if item["risk_level"] in {"intermedia", "relevante", "alta"}]
    overall_risk = _overall_risk_level(ordered_domains)

    if top_domains:
        top_phrase = ", ".join(
            f"{item['domain'].upper()} ({item['risk_level']})"
            for item in top_domains[:3]
        )
    else:
        top_phrase = "sin dominios procesados"

    has_comorbidity_signal = len(elevated_domains) >= 2 or (
        overall_risk in {"relevante", "alta"} and len(monitor_domains) >= 2
    )
    if elevated_domains:
        comorbidity_domains = [item["domain"] for item in elevated_domains]
    else:
        comorbidity_domains = [item["domain"] for item in monitor_domains[:3]]
    if has_comorbidity_signal:
        comorbidity_summary = (
            "Se observan senales concurrentes en multiples dominios, compatibles con posible comorbilidad "
            "en tamizaje. Se recomienda priorizar evaluacion profesional integral."
        )
    else:
        comorbidity_summary = (
            "No se observan senales concurrentes fuertes de comorbilidad en esta corrida de tamizaje."
        )

    sintesis_general = (
        f"Patron general de tamizaje con mayor compatibilidad en {top_phrase}. "
        f"Nivel global estimado: {overall_risk}. "
        + (
            "Existe coexistencia posible de senales entre dominios y requiere revision profesional."
            if has_comorbidity_signal
            else "No se detecta coexistencia dominante de senales elevadas."
        )
    )

    niveles_text = "; ".join(
        f"{item['domain'].upper()}: prob={item['probability']:.3f}, riesgo={item['risk_level']}"
        for item in ordered_domains
    ) or "Sin dominios disponibles."

    indicator_lines = []
    for item in ordered_domains:
        if item["risk_level"] in {"intermedia", "relevante", "alta"}:
            indicator_lines.append(
                f"{item['domain'].upper()}: " + ", ".join(item["main_indicators"][:3])
            )
    if not indicator_lines:
        indicator_lines.append(
            "No se identifican indicadores dominantes en nivel intermedio o superior dentro de la sesion."
        )
    indicadores_text = " | ".join(indicator_lines)

    if overall_risk in {"alta", "relevante"}:
        impacto_funcional = (
            "El patron observado puede asociarse con impacto funcional en contextos escolar, familiar, social o "
            "emocional. Esta salida es de tamizaje y requiere correlacion profesional."
        )
    elif overall_risk == "intermedia":
        impacto_funcional = (
            "Se observan senales moderadas que podrian afectar funcionamiento cotidiano si persisten en el tiempo. "
            "Se recomienda monitoreo estructurado."
        )
    else:
        impacto_funcional = (
            "No se observan senales fuertes de impacto funcional en esta corrida. Mantener observacion preventiva."
        )

    if overall_risk == "alta":
        recomendacion = (
            "Recomendacion prioritaria: evaluacion profesional integral en el corto plazo."
        )
    elif overall_risk == "relevante":
        recomendacion = (
            "Recomendacion: valoracion profesional pronta y plan de seguimiento."
        )
    elif overall_risk == "intermedia":
        recomendacion = (
            "Recomendacion: seguimiento cercano y valoracion profesional si las senales persisten."
        )
    else:
        recomendacion = (
            "Recomendacion: observacion preventiva y reevaluacion ante cambios relevantes."
        )

    payload = {
        "session_id": str(session.id),
        "report_version": "clinical_summary_v1",
        "generated_at": _utcnow().isoformat(),
        "overall_risk_level": overall_risk,
        "simulated_diagnostic_text": {
            "sintesis_general": sintesis_general,
            "niveles_de_compatibilidad": niveles_text,
            "indicadores_principales_observados": indicadores_text,
            "impacto_funcional": impacto_funcional,
            "recomendacion_profesional": recomendacion,
            "aclaracion_importante": CLINICAL_SUMMARY_DISCLAIMER,
        },
        "domains": ordered_domains,
        "comorbidity": {
            "has_comorbidity_signal": has_comorbidity_signal,
            "domains": comorbidity_domains,
            "summary": comorbidity_summary,
        },
        "disclaimer": CLINICAL_SUMMARY_DISCLAIMER,
    }
    return payload


def persist_clinical_summary_payload(session: QuestionnaireSession, clinical_payload: dict[str, Any]) -> None:
    result = QuestionnaireSessionResult.query.filter_by(session_id=session.id).first()
    if not result:
        return
    meta = _decrypt_json(
        result.metadata_json,
        "questionnaire_session_result.metadata_json",
    ) or {}
    meta["clinical_summary_v1"] = clinical_payload
    result.metadata_json = _encrypt_json(
        meta,
        "questionnaire_session_result.metadata_json",
    )
    result.updated_at = _utcnow()
    db.session.add(result)
    db.session.commit()


def list_history(user_id: uuid.UUID, status: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    query = QuestionnaireSession.query.filter(
        or_(
            QuestionnaireSession.owner_user_id == user_id,
            QuestionnaireSession.id.in_(
                db.session.query(QuestionnaireAccessGrant.session_id).filter(
                    QuestionnaireAccessGrant.grantee_user_id == user_id,
                    QuestionnaireAccessGrant.revoked_at.is_(None),
                )
            ),
        )
    )

    if status:
        query = query.filter(QuestionnaireSession.status == status)

    total = query.count()
    rows = (
        query.order_by(QuestionnaireSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    session_ids = [session.id for session in rows]
    summary_by_session_id: dict[uuid.UUID, tuple[str | None, bool | None]] = {}
    if session_ids:
        result_rows = QuestionnaireSessionResult.query.filter(
            QuestionnaireSessionResult.session_id.in_(session_ids)
        ).all()
        summary_by_session_id = {
            row.session_id: (row.summary_text, row.needs_professional_review)
            for row in result_rows
        }

    items = []
    for session in rows:
        item = get_session_payload(session)
        summary_info = summary_by_session_id.get(session.id)
        if summary_info is not None:
            item["summary"] = summary_info[0]
            item["needs_professional_review"] = summary_info[1]
        items.append(item)

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
    }


def upsert_tag(session: QuestionnaireSession, user_id: uuid.UUID, tag: str, color: str | None, visibility: str | None) -> list[dict[str, Any]]:
    tag_name = tag.strip()
    if not tag_name:
        raise ValueError("empty_tag")

    existing = QuestionnaireTag.query.filter_by(owner_user_id=user_id, name=tag_name).first()
    if not existing:
        existing = QuestionnaireTag(owner_user_id=user_id, name=tag_name)

    if color:
        existing.color = color
    if visibility:
        existing.visibility = visibility
    existing.updated_at = _utcnow()
    db.session.add(existing)
    db.session.flush()

    attached = QuestionnaireSessionTag.query.filter_by(
        session_id=session.id,
        tag_id=existing.id,
        assigned_by_user_id=user_id,
    ).first()
    if not attached:
        db.session.add(
            QuestionnaireSessionTag(session_id=session.id, tag_id=existing.id, assigned_by_user_id=user_id)
        )

    _audit(session.id, user_id, "tag_upserted", {"tag": tag_name})
    db.session.commit()

    return list_session_tags(session.id)


def remove_tag(session_id: uuid.UUID, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
    row = QuestionnaireSessionTag.query.filter_by(
        session_id=session_id,
        tag_id=tag_id,
        assigned_by_user_id=user_id,
    ).first()
    if not row:
        raise LookupError("session_tag_not_found")
    db.session.delete(row)
    _audit(session_id, user_id, "tag_removed", {"tag_id": str(tag_id)})
    db.session.commit()


def list_session_tags(session_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.session.query(QuestionnaireSessionTag, QuestionnaireTag)
        .join(QuestionnaireTag, QuestionnaireTag.id == QuestionnaireSessionTag.tag_id)
        .filter(QuestionnaireSessionTag.session_id == session_id)
        .order_by(QuestionnaireSessionTag.created_at.asc())
        .all()
    )
    return [
        {
            "tag_id": str(tag.id),
            "name": tag.name,
            "color": tag.color,
            "visibility": tag.visibility,
            "owner_user_id": str(tag.owner_user_id),
        }
        for _, tag in rows
    ]


def create_share(session: QuestionnaireSession, user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    raw_code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
    code_hash = hash_password(raw_code)

    expires_in_hours = payload.get("expires_in_hours")
    expires_at = _utcnow() + timedelta(hours=int(expires_in_hours)) if expires_in_hours else None

    row = QuestionnaireShareCode(
        session_id=session.id,
        code_hash=code_hash,
        code_hint=raw_code[-4:],
        created_by_user_id=user_id,
        expires_at=expires_at,
        max_uses=payload.get("max_uses"),
        used_count=0,
        is_active=True,
    )
    db.session.add(row)
    db.session.flush()

    grantee_id = payload.get("grantee_user_id")
    if grantee_id:
        if not db.session.get(AppUser, grantee_id):
            raise ValueError("grantee_not_found")
        grant = QuestionnaireAccessGrant.query.filter_by(session_id=session.id, grantee_user_id=grantee_id).first()
        if not grant:
            grant = QuestionnaireAccessGrant(session_id=session.id, owner_user_id=user_id, grantee_user_id=grantee_id)
        grant.grant_type = "share_code"
        grant.can_view = True
        grant.can_tag = bool(payload.get("grant_can_tag", True))
        grant.can_download_pdf = bool(payload.get("grant_can_download_pdf", True))
        grant.expires_at = expires_at
        grant.revoked_at = None
        grant.updated_at = _utcnow()
        db.session.add(grant)

    _audit(session.id, user_id, "share_created", {"share_code_id": str(row.id)})
    db.session.commit()

    return {
        "questionnaire_id": session.questionnaire_public_id,
        "share_code": raw_code,
        "share_code_id": str(row.id),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def get_shared_session(questionnaire_id: str, share_code: str) -> QuestionnaireSession:
    session = QuestionnaireSession.query.filter_by(questionnaire_public_id=questionnaire_id).first()
    if not session:
        raise LookupError("session_not_found")

    now = _utcnow()
    rows = QuestionnaireShareCode.query.filter_by(session_id=session.id, is_active=True).all()
    for row in rows:
        expires_at = row.expires_at
        if expires_at is not None:
            compare_now = now
            if getattr(expires_at, "tzinfo", None) is None:
                compare_now = now.replace(tzinfo=None)
            if expires_at < compare_now:
                continue
        if row.max_uses is not None and row.used_count >= row.max_uses:
            continue
        if check_password(share_code, row.code_hash):
            row.used_count = int(row.used_count or 0) + 1
            db.session.add(row)
            _record_access(session.id, "share_code", None, True, share_code_id=row.id)
            _audit(session.id, None, "share_accessed", {"share_code_id": str(row.id)})
            db.session.commit()
            return session

    _record_access(session.id, "share_code", None, False, notes="invalid_or_expired_code")
    db.session.commit()
    raise PermissionError("invalid_share_code")


def _pdf_output_dir() -> Path:
    path = (Path.cwd() / "artifacts" / "runtime_reports").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_download_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path).resolve()
    base = _pdf_output_dir()
    try:
        candidate.relative_to(base)
    except ValueError:
        current_app.logger.warning("Rejected download path outside runtime_reports: %s", candidate)
        return None
    return candidate


def generate_pdf(session: QuestionnaireSession, user_id: uuid.UUID) -> QuestionnaireSessionPdfExport:
    result_payload = get_results_payload(session)
    domains = result_payload["domains"]
    if not domains:
        raise ValueError("results_not_available")

    output_dir = _pdf_output_dir()
    file_name = f"questionnaire_{session.questionnaire_public_id}_{int(_utcnow().timestamp())}.pdf"
    file_path = (output_dir / file_name).resolve()

    probabilities = [float(item["probability"]) * 100.0 for item in domains]
    labels = [item["domain"].upper() for item in domains]
    plt, PdfPages = _pdf_plot_backend()

    with PdfPages(file_path) as pdf:
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.barh(labels, probabilities, color="#2E6F95")
        ax.set_xlim(0, 100)
        ax.set_xlabel("Probabilidad (%)")
        ax.set_title("Resultados por dominio (screening no diagnostico)")
        for idx, val in enumerate(probabilities):
            ax.text(val + 1, idx, f"{val:.1f}%", va="center", fontsize=9)
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(11, 8.5))
        ax2.axis("off")
        lines = [
            f"Questionnaire ID: {session.questionnaire_public_id}",
            f"Session ID: {session.id}",
            f"Generated at: {_utcnow().isoformat()}",
            f"Mode: {session.mode} ({session.mode_key})",
            f"Role: {_normalize_role(session.respondent_role)}",
            f"Questionnaire version: {session.questionnaire_version_label}",
            "",
            f"Executive summary: {result_payload['result'].get('summary') or 'N/A'}",
            f"Operational recommendation: {result_payload['result'].get('operational_recommendation') or 'N/A'}",
            "",
            "Important: this report is for screening/support in simulated setting, not automatic diagnosis.",
        ]
        for idx, line in enumerate(lines):
            ax2.text(0.02, 0.96 - idx * 0.05, line, fontsize=10, ha="left", va="top")
        plt.tight_layout()
        pdf.savefig(fig2)
        plt.close(fig2)

    export = QuestionnaireSessionPdfExport(
        session_id=session.id,
        file_path=str(file_path),
        file_name=file_name,
        status="generated",
        generated_by_user_id=user_id,
        metadata_json=_encrypt_json(
            {
                "questionnaire_version": session.questionnaire_version_label,
                "model_bundle": session.model_pipeline_version,
            },
            "questionnaire_session_pdf_export.metadata_json",
        ),
    )
    db.session.add(export)
    _audit(session.id, user_id, "pdf_generated", {"file_path": str(file_path)})
    db.session.commit()
    return export


def latest_pdf(session_id: uuid.UUID) -> QuestionnaireSessionPdfExport | None:
    return (
        QuestionnaireSessionPdfExport.query.filter_by(session_id=session_id)
        .order_by(QuestionnaireSessionPdfExport.created_at.desc())
        .first()
    )


def _monthly_series(query, date_column, months: int) -> list[dict[str, Any]]:
    start = _utcnow().date().replace(day=1)
    buckets = []
    for delta in range(months - 1, -1, -1):
        month_start = (pd.Timestamp(start) - pd.DateOffset(months=delta)).date().replace(day=1)
        month_end = (pd.Timestamp(month_start) + pd.DateOffset(months=1)).date()
        count = query.filter(date_column >= month_start).filter(date_column < month_end).count()
        buckets.append({"month": str(month_start), "count": count})
    return buckets


def dashboard_questionnaire_volume(months: int = 12) -> dict[str, Any]:
    query = QuestionnaireSession.query
    return {"series": _monthly_series(query, QuestionnaireSession.created_at, months)}


def dashboard_user_growth(months: int = 12) -> dict[str, Any]:
    query = AppUser.query
    return {"series": _monthly_series(query, AppUser.created_at, months)}


def dashboard_funnel(months: int = 12) -> dict[str, Any]:
    query = QuestionnaireSession.query
    start_month = (pd.Timestamp(_utcnow().date().replace(day=1)) - pd.DateOffset(months=max(0, months - 1))).to_pydatetime()
    created_query = query.filter(QuestionnaireSession.created_at >= start_month)
    created = created_query.count()
    submitted = created_query.filter(QuestionnaireSession.status.in_(["submitted", "processed"])).count()
    processed = created_query.filter(QuestionnaireSession.status == "processed").count()
    return {
        "created": created,
        "submitted": submitted,
        "processed": processed,
        "conversion_created_to_processed": round(processed / created, 4) if created else 0.0,
    }


def dashboard_adoption_history(months: int = 12) -> dict[str, Any]:
    volume = dashboard_questionnaire_volume(months)
    growth = dashboard_user_growth(months)
    funnel = dashboard_funnel(months)

    total_users = AppUser.query.count()
    processed_sessions = QuestionnaireSession.query.filter_by(status="processed").count()
    capacity = round(processed_sessions / max(total_users, 1), 4)

    return {
        "adoption_history": {
            "volume_and_growth": volume,
            "user_growth": growth,
            "conversion": funnel,
            "operational_capacity": {
                "processed_sessions": processed_sessions,
                "registered_users": total_users,
                "processed_per_user": capacity,
            },
        }
    }


def build_report(report_type: str, months: int, requested_by_user_id: uuid.UUID) -> dict[str, Any]:
    report_job = ReportJob(job_type=report_type, requested_by_user_id=requested_by_user_id, status="running", params_json={"months": months})
    db.session.add(report_job)
    db.session.flush()

    if report_type in {"executive_monthly", "adoption_history"}:
        dataset = dashboard_adoption_history(months)
    elif report_type in {"model_monitoring", "traceability_audit", "operational_productivity", "security_compliance"}:
        dataset = {
            "volume": dashboard_questionnaire_volume(months),
            "funnel": dashboard_funnel(months),
        }
    else:
        raise ValueError("unsupported_report_type")

    output_dir = _pdf_output_dir()
    file_name = f"report_{report_type}_{int(_utcnow().timestamp())}.pdf"
    file_path = (output_dir / file_name).resolve()
    plt, PdfPages = _pdf_plot_backend()

    with PdfPages(file_path) as pdf:
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        ax.text(0.02, 0.95, f"Report: {report_type}", fontsize=14, fontweight="bold")
        ax.text(0.02, 0.90, f"Generated: {_utcnow().isoformat()}", fontsize=10)
        ax.text(0.02, 0.84, json.dumps(dataset, ensure_ascii=True, indent=2)[:4500], fontsize=8, family="monospace")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    generated = GeneratedReport(
        report_job_id=report_job.id,
        report_type=report_type,
        file_path=str(file_path),
        file_format="pdf",
        metadata_json={"months": months},
    )
    db.session.add(generated)

    report_job.status = "completed"
    report_job.finished_at = _utcnow()
    db.session.add(report_job)
    db.session.commit()

    return {
        "report_job_id": str(report_job.id),
        "report_type": report_type,
        "file_path": str(file_path),
        "dataset": dataset,
    }
