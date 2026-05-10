from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict

from flask import current_app
from sqlalchemy import or_
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from api.repositories.admin_repository import apply_pagination, apply_sort
from api.services import crypto_service
from api.security import log_audit
from app.models import (
    AppUser,
    ProblemReport,
    ProblemReportAttachment,
    ProblemReportAuditEvent,
    db,
)


DEFAULT_ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/webp",
}


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


def _upload_root() -> Path:
    root = Path(current_app.config.get("PROBLEM_REPORT_UPLOAD_DIR", "artifacts/problem_reports/uploads")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _max_attachment_size() -> int:
    try:
        return int(current_app.config.get("PROBLEM_REPORT_MAX_ATTACHMENT_BYTES", 5 * 1024 * 1024))
    except Exception:
        return 5 * 1024 * 1024


def _allowed_mime_types() -> set[str]:
    configured = current_app.config.get("PROBLEM_REPORT_ALLOWED_MIME_TYPES")
    if not configured:
        return set(DEFAULT_ALLOWED_MIME)
    if isinstance(configured, (list, tuple, set)):
        return {str(x).strip().lower() for x in configured if str(x).strip()}
    return {x.strip().lower() for x in str(configured).split(",") if x.strip()}


def _content_signature_matches(content_type: str, payload: bytes) -> bool:
    if not payload:
        return False
    if content_type == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return payload.startswith(b"\xff\xd8")
    if content_type == "image/webp":
        return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    return False


def _primary_reporter_role(user: AppUser, roles: list[str]) -> str:
    roles_set = {str(role).upper() for role in (roles or [])}
    if "ADMIN" in roles_set:
        return "ADMIN"
    if "PSYCHOLOGIST" in roles_set:
        return "PSYCHOLOGIST"
    if "GUARDIAN" in roles_set:
        return "GUARDIAN"
    if roles_set:
        return min(roles_set)
    return (user.user_type or "UNKNOWN").upper()


def _generate_report_code() -> str:
    prefix = _utcnow().strftime("%Y%m%d")
    for _ in range(10):
        candidate = f"PRB-{prefix}-{uuid.uuid4().hex[:6].upper()}"
        if not ProblemReport.query.filter_by(report_code=candidate).first():
            return candidate
    raise RuntimeError("problem_report_code_generation_failed")


def _audit(report_id: uuid.UUID, actor_user_id: uuid.UUID | None, event_type: str, payload: dict[str, Any] | None = None) -> None:
    db.session.add(
        ProblemReportAuditEvent(
            report_id=report_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            payload_json=payload or {},
        )
    )


def _save_attachment(report: ProblemReport, attachment: FileStorage, actor_user_id: uuid.UUID | None) -> ProblemReportAttachment:
    if not attachment:
        raise ValueError("attachment_missing")
    if not attachment.filename:
        raise ValueError("attachment_filename_missing")

    content_type = (attachment.mimetype or "").lower().strip()
    allowed_mimes = _allowed_mime_types()
    if content_type not in allowed_mimes:
        raise ValueError("attachment_mime_not_allowed")

    payload = attachment.read()
    attachment.seek(0)
    size = len(payload or b"")
    if size <= 0:
        raise ValueError("attachment_empty")
    if size > _max_attachment_size():
        raise ValueError("attachment_too_large")
    if not _content_signature_matches(content_type, payload):
        raise ValueError("attachment_content_mismatch")

    original_filename = secure_filename(attachment.filename)
    suffix = Path(original_filename).suffix.lower()
    if not suffix:
        suffix = (mimetypes.guess_extension(content_type) or "").lower()
    if not suffix:
        suffix = ".bin"

    safe_name = f"{report.id}_{uuid.uuid4().hex}{suffix}"
    target_path = _upload_root() / safe_name
    target_path.write_bytes(payload)

    row = ProblemReportAttachment(
        report_id=report.id,
        storage_kind="local",
        file_path=str(target_path),
        original_filename=original_filename or safe_name,
        mime_type=content_type or None,
        size_bytes=size,
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
        metadata_json=_encrypt_json(
            {"uploaded_at": _utcnow().isoformat()},
            "problem_report_attachment.metadata_json",
        ),
    )
    db.session.add(row)
    report.attachment_count = int(report.attachment_count or 0) + 1
    report.updated_at = _utcnow()
    db.session.add(report)
    _audit(report.id, actor_user_id, "attachment_uploaded", {"attachment_id": str(row.id), "size_bytes": size})
    return row


def preload_attachments_by_report_ids(
    report_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[ProblemReportAttachment]]:
    if not report_ids:
        return {}
    rows = (
        ProblemReportAttachment.query.filter(
            ProblemReportAttachment.report_id.in_(report_ids)
        )
        .order_by(
            ProblemReportAttachment.report_id.asc(),
            ProblemReportAttachment.created_at.asc(),
        )
        .all()
    )
    grouped: dict[uuid.UUID, list[ProblemReportAttachment]] = defaultdict(list)
    for row in rows:
        grouped[row.report_id].append(row)
    return grouped


def serialize_problem_report(
    report: ProblemReport,
    include_private: bool = True,
    attachments: list[ProblemReportAttachment] | None = None,
) -> dict[str, Any]:
    if attachments is None:
        attachments = (
            ProblemReportAttachment.query.filter_by(report_id=report.id)
            .order_by(ProblemReportAttachment.created_at.asc())
            .all()
        )
    payload = {
        "id": str(report.id),
        "report_code": report.report_code,
        "reporter_user_id": str(report.reporter_user_id),
        "reporter_role": report.reporter_role,
        "issue_type": report.issue_type,
        "description": _decrypt_text(report.description, "problem_report.description"),
        "status": report.status,
        "source_module": report.source_module,
        "source_path": report.source_path,
        "related_questionnaire_session_id": (
            str(report.related_questionnaire_session_id) if report.related_questionnaire_session_id else None
        ),
        "related_questionnaire_history_id": report.related_questionnaire_history_id,
        "admin_notes": (
            _decrypt_text(report.admin_notes, "problem_report.admin_notes")
            if include_private
            else None
        ),
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
        "attachment_count": int(report.attachment_count or 0),
        "attachments": [
            {
                "attachment_id": str(item.id),
                "storage_kind": item.storage_kind,
                "original_filename": item.original_filename,
                "mime_type": item.mime_type,
                "size_bytes": int(item.size_bytes or 0),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in attachments
        ],
        "metadata": _decrypt_json(report.metadata_json, "problem_report.metadata_json") or {},
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }
    return payload


def create_problem_report(
    *,
    reporter: AppUser,
    roles: list[str],
    payload: dict[str, Any],
    attachment: FileStorage | None = None,
) -> ProblemReport:
    report = ProblemReport(
        report_code=_generate_report_code(),
        reporter_user_id=reporter.id,
        reporter_role=_primary_reporter_role(reporter, roles),
        issue_type=str(payload.get("issue_type", "")).strip().lower(),
        description=_encrypt_text(
            str(payload.get("description", "")).strip(),
            "problem_report.description",
        )
        or "",
        source_module=(payload.get("source_module") or "").strip() or None,
        source_path=(payload.get("source_path") or "").strip() or None,
        related_questionnaire_session_id=payload.get("related_questionnaire_session_id"),
        related_questionnaire_history_id=(payload.get("related_questionnaire_history_id") or "").strip() or None,
        status="open",
        metadata_json=_encrypt_json(
            payload.get("metadata") or {},
            "problem_report.metadata_json",
        ),
    )
    db.session.add(report)
    db.session.flush()
    _audit(report.id, reporter.id, "created", {"issue_type": report.issue_type, "status": report.status})

    if attachment:
        _save_attachment(report, attachment, reporter.id)

    db.session.add(report)
    db.session.commit()
    log_audit(
        reporter.id,
        "PROBLEM_REPORT_CREATED",
        "problem_reports",
        {"problem_report_id": str(report.id), "report_code": report.report_code},
    )
    return report


def list_problem_reports(params: dict[str, Any]) -> tuple[list[ProblemReport], dict[str, Any]]:
    query = ProblemReport.query

    if params.get("status"):
        query = query.filter(ProblemReport.status == params["status"])
    if params.get("issue_type"):
        query = query.filter(ProblemReport.issue_type == params["issue_type"])
    if params.get("reporter_role"):
        query = query.filter(ProblemReport.reporter_role == params["reporter_role"].upper())
    if params.get("from_date"):
        query = query.filter(ProblemReport.created_at >= params["from_date"])
    if params.get("to_date"):
        query = query.filter(ProblemReport.created_at <= params["to_date"])

    q = (params.get("q") or "").strip()
    if q:
        predicates = [
            ProblemReport.report_code.ilike(f"%{q}%"),
            ProblemReport.source_module.ilike(f"%{q}%"),
            ProblemReport.source_path.ilike(f"%{q}%"),
        ]
        if not crypto_service.is_field_encryption_enabled():
            predicates.append(ProblemReport.description.ilike(f"%{q}%"))
        query = query.filter(or_(*predicates))

    sort = params.get("sort") or "created_at"
    order = params.get("order") or "desc"
    query = apply_sort(
        query,
        model=ProblemReport,
        sort=sort,
        order=order,
        allowed={"created_at", "updated_at", "resolved_at", "status", "issue_type"},
    )
    if not sort:
        query = query.order_by(ProblemReport.created_at.desc())

    return apply_pagination(query, page=params["page"], page_size=params["page_size"])


def list_my_problem_reports(user_id: uuid.UUID, page: int, page_size: int) -> tuple[list[ProblemReport], dict[str, Any]]:
    query = ProblemReport.query.filter_by(reporter_user_id=user_id).order_by(ProblemReport.created_at.desc())
    return apply_pagination(query, page=page, page_size=page_size)


def get_problem_report_or_404(report_id: uuid.UUID) -> ProblemReport:
    row = db.session.get(ProblemReport, report_id)
    if not row:
        raise LookupError("problem_report_not_found")
    return row


def admin_update_problem_report(
    *,
    report: ProblemReport,
    actor_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> ProblemReport:
    status = payload.get("status")
    notes = payload.get("admin_notes")

    changed = False
    if status and status != report.status:
        report.status = status
        changed = True
        if status in {"resolved", "rejected"}:
            report.resolved_at = _utcnow()
        elif status in {"open", "triaged", "in_progress"}:
            report.resolved_at = None
    if notes is not None:
        report.admin_notes = _encrypt_text(
            str(notes).strip(),
            "problem_report.admin_notes",
        ) or ""
        changed = True

    if not changed:
        return report

    report.updated_at = _utcnow()
    db.session.add(report)
    _audit(
        report.id,
        actor_user_id,
        "admin_updated",
        {"status": report.status, "has_admin_notes": bool(report.admin_notes)},
    )
    db.session.commit()
    log_audit(
        actor_user_id,
        "PROBLEM_REPORT_UPDATED",
        "problem_reports",
        {"problem_report_id": str(report.id), "status": report.status},
    )
    return report
