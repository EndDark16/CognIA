from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from app.models import ReportJob, db


TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(
    *,
    job_type: str,
    requested_by_user_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> ReportJob:
    job = ReportJob(
        job_type=str(job_type).strip(),
        requested_by_user_id=requested_by_user_id,
        status="queued",
        params_json=payload or {},
    )
    db.session.add(job)
    db.session.commit()
    return job


def claim_next_job(
    *,
    worker_id: str,
    allowed_job_types: list[str] | None = None,
) -> ReportJob | None:
    query = ReportJob.query.filter_by(status="queued")
    if allowed_job_types:
        normalized = [str(item).strip() for item in allowed_job_types if str(item).strip()]
        if normalized:
            query = query.filter(ReportJob.job_type.in_(normalized))

    query = query.order_by(ReportJob.created_at.asc())

    # best effort skip-locked on engines that support it
    try:
        row = query.with_for_update(skip_locked=True).first()
    except Exception:
        row = query.first()

    if not row:
        return None

    params = dict(row.params_json or {})
    params["locked_by"] = str(worker_id)
    params["locked_at"] = _utcnow().isoformat()
    row.params_json = params
    row.status = "running"
    row.started_at = _utcnow()
    db.session.add(row)
    db.session.commit()
    return row


def mark_job_succeeded(
    *,
    job: ReportJob,
    result_meta: dict[str, Any] | None = None,
) -> ReportJob:
    params = dict(job.params_json or {})
    if result_meta:
        params["result_meta"] = result_meta
    job.params_json = params
    job.status = "completed"
    job.finished_at = _utcnow()
    job.error_message = None
    db.session.add(job)
    db.session.commit()
    return job


def mark_job_failed(
    *,
    job: ReportJob,
    error_message: str,
    retryable: bool = False,
) -> ReportJob:
    params = dict(job.params_json or {})
    attempts = int(params.get("attempts") or 0) + 1
    params["attempts"] = attempts
    params["last_error_at"] = _utcnow().isoformat()
    job.params_json = params
    job.error_message = str(error_message or "job_failed")
    job.finished_at = _utcnow()
    job.status = "queued" if retryable else "failed"
    if job.status == "queued":
        job.started_at = None
        job.finished_at = None
    db.session.add(job)
    db.session.commit()
    return job


def queue_snapshot() -> dict[str, Any]:
    rows = (
        db.session.query(ReportJob.status, func.count(ReportJob.id))
        .group_by(ReportJob.status)
        .all()
    )
    counts = {str(status): int(count or 0) for status, count in rows}
    return {
        "counts": counts,
        "queued": int(counts.get("queued", 0)),
        "running": int(counts.get("running", 0)),
        "terminal": int(sum(count for status, count in counts.items() if status in TERMINAL_JOB_STATUSES)),
    }
