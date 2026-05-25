from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app
from api.services import crypto_service
from app.models import (
    AppUser,
    GeneratedReport,
    QuestionnaireAccessGrant,
    QuestionnaireCase,
    QuestionnaireProfessionalReview,
    QuestionnaireSession,
    QuestionnaireSessionAnswer,
    QuestionnaireSessionPdfExport,
    QuestionnaireSessionResult,
    db,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_case_label(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[_/|.,;:\\-]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _hash_case_label(value: str | None, secret: str) -> str:
    normalized = _normalize_case_label(value)
    if not normalized:
        return ""
    return hashlib.sha256(f"{secret}:{normalized}".encode("utf-8")).hexdigest()


def _is_synthetic_user(user: AppUser) -> bool:
    blob = " ".join(
        [
            str(user.username or ""),
            str(user.email or ""),
            str(user.full_name or ""),
        ]
    ).lower()
    synthetic_tokens = ("synthetic", "demo", "test", "fixture", "qa_")
    return any(token in blob for token in synthetic_tokens)


def _spread_offset_days(seed: str, days_spread: int) -> int:
    if days_spread <= 0:
        return 0
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % days_spread


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _decrypt_case_label(row: QuestionnaireCase) -> str | None:
    if not row.private_label:
        return None
    try:
        return crypto_service.decrypt_text(row.private_label, purpose="questionnaire_case.private_label")
    except Exception:
        return None


@dataclass
class RepairStats:
    sessions_relinked: int = 0
    cases_archived: int = 0
    drafts_archived: int = 0
    timestamps_redistributed: int = 0


def _owner_duplicate_cases(owner_id: uuid.UUID, case_rows: list[QuestionnaireCase], secret: str) -> dict[str, list[QuestionnaireCase]]:
    groups: dict[str, list[QuestionnaireCase]] = defaultdict(list)
    for row in case_rows:
        if row.owner_user_id != owner_id or str(row.status or "").lower() != "active":
            continue
        label_hash = str(row.private_label_hash or "").strip().lower()
        if not label_hash:
            label_hash = _hash_case_label(_decrypt_case_label(row), secret)
        if not label_hash:
            continue
        groups[label_hash].append(row)
    return {key: sorted(val, key=lambda item: (item.created_at or _utcnow(), str(item.id))) for key, val in groups.items() if len(val) > 1}


def _pick_keeper_case(case_rows: list[QuestionnaireCase], sessions_by_case: dict[uuid.UUID, list[QuestionnaireSession]]) -> QuestionnaireCase:
    return sorted(
        case_rows,
        key=lambda row: (
            -len(sessions_by_case.get(row.id, [])),
            row.created_at or _utcnow(),
            str(row.id),
        ),
    )[0]


def _safe_to_archive_draft(session: QuestionnaireSession) -> bool:
    if str(session.status or "").lower() not in {"draft", "in_progress"}:
        return False
    if QuestionnaireSessionResult.query.filter_by(session_id=session.id).first():
        return False
    if QuestionnaireSessionPdfExport.query.filter_by(session_id=session.id).first():
        return False
    if QuestionnaireProfessionalReview.query.filter_by(session_id=session.id).first():
        return False
    active_grant = QuestionnaireAccessGrant.query.filter(
        QuestionnaireAccessGrant.session_id == session.id,
        QuestionnaireAccessGrant.revoked_at.is_(None),
        QuestionnaireAccessGrant.can_view.is_(True),
    ).first()
    if active_grant:
        return False
    has_answers = QuestionnaireSessionAnswer.query.filter_by(session_id=session.id).first()
    return has_answers is None


def audit_and_repair(
    *,
    execute: bool,
    limit: int,
    only_synthetic: bool,
    user_email: str | None,
    guardian_email: str | None,
    psychologist_email: str | None,
    days_spread: int,
    archive_excess_drafts: bool,
    group_sessions_by_case_label: bool,
    repair_case_labels: bool,
    ensure_realistic_dashboard_data: bool,
) -> int:
    app = create_app(_config_class_from_env())
    with app.app_context():
        users = AppUser.query.order_by(AppUser.created_at.asc().nullslast(), AppUser.id.asc()).all()
        if user_email:
            users = [user for user in users if str(user.email or "").lower() == user_email.lower()]
        if guardian_email:
            users = [user for user in users if str(user.email or "").lower() == guardian_email.lower()]
        if psychologist_email:
            users = [user for user in users if str(user.email or "").lower() == psychologist_email.lower()]
        if only_synthetic:
            users = [user for user in users if _is_synthetic_user(user)]
        if limit > 0:
            users = users[:limit]

        user_ids = [user.id for user in users]
        sessions = QuestionnaireSession.query.filter(QuestionnaireSession.owner_user_id.in_(user_ids)).all() if user_ids else []
        session_ids = [row.id for row in sessions]
        cases = QuestionnaireCase.query.filter(QuestionnaireCase.owner_user_id.in_(user_ids)).all() if user_ids else []
        results = QuestionnaireSessionResult.query.filter(QuestionnaireSessionResult.session_id.in_(session_ids)).all() if session_ids else []
        grants = QuestionnaireAccessGrant.query.filter(QuestionnaireAccessGrant.session_id.in_(session_ids)).all() if session_ids else []
        reviews = QuestionnaireProfessionalReview.query.filter(QuestionnaireProfessionalReview.session_id.in_(session_ids)).all() if session_ids else []

        sessions_by_owner: dict[uuid.UUID, list[QuestionnaireSession]] = defaultdict(list)
        for row in sessions:
            sessions_by_owner[row.owner_user_id].append(row)
        sessions_by_case: dict[uuid.UUID, list[QuestionnaireSession]] = defaultdict(list)
        for row in sessions:
            if row.case_id:
                sessions_by_case[row.case_id].append(row)

        print(f"[audit-dashboard-data] execute={execute}")
        print(f"[audit-dashboard-data] users_analyzed={len(users)}")
        print(f"[audit-dashboard-data] guardians={sum(1 for u in users if str(u.user_type).lower() == 'guardian')}")
        print(f"[audit-dashboard-data] psychologists={sum(1 for u in users if str(u.user_type).lower() == 'psychologist')}")
        print(f"[audit-dashboard-data] sessions_total={len(sessions)}")
        status_counter = Counter(str(row.status or "unknown") for row in sessions)
        for key, value in sorted(status_counter.items()):
            print(f"  sessions_status[{key}]={value}")
        sessions_without_case = [row for row in sessions if row.case_id is None]
        print(f"[audit-dashboard-data] sessions_without_case={len(sessions_without_case)}")
        cases_without_sessions = [row for row in cases if not sessions_by_case.get(row.id)]
        print(f"[audit-dashboard-data] cases_without_sessions={len(cases_without_sessions)}")
        duplicate_hash_groups = 0
        secret = str(app.config.get("CASE_LABEL_HASH_SECRET") or app.config.get("SECRET_KEY") or "")
        for owner_id in sessions_by_owner:
            dup = _owner_duplicate_cases(owner_id, cases, secret)
            duplicate_hash_groups += len(dup)
        print(f"[audit-dashboard-data] duplicate_active_case_groups={duplicate_hash_groups}")
        print(f"[audit-dashboard-data] processed_without_results={sum(1 for row in sessions if row.status == 'processed' and row.id not in {r.session_id for r in results})}")
        print(f"[audit-dashboard-data] shares_pending={sum(1 for row in grants if str(row.request_status or '').lower() == 'pending')}")
        print(f"[audit-dashboard-data] shares_accepted={sum(1 for row in grants if str(row.request_status or '').lower() in {'', 'accepted'})}")
        print(f"[audit-dashboard-data] shares_rejected={sum(1 for row in grants if str(row.request_status or '').lower() == 'rejected')}")
        print(f"[audit-dashboard-data] professional_reviews={len(reviews)}")

        stats = RepairStats()
        if not execute:
            return 0

        for owner_id, owner_sessions in sessions_by_owner.items():
            owner_user = next((u for u in users if u.id == owner_id), None)
            owner_cases = [row for row in cases if row.owner_user_id == owner_id]
            active_cases_by_hash: dict[str, QuestionnaireCase] = {}
            for row in owner_cases:
                if str(row.status or "").lower() != "active":
                    continue
                key = str(row.private_label_hash or "").strip().lower()
                if key:
                    active_cases_by_hash.setdefault(key, row)

            if repair_case_labels and group_sessions_by_case_label:
                duplicates = _owner_duplicate_cases(owner_id, owner_cases, secret)
                for label_hash, group_rows in duplicates.items():
                    keeper = _pick_keeper_case(group_rows, sessions_by_case)
                    for duplicate in group_rows:
                        if duplicate.id == keeper.id:
                            continue
                        for session in sessions_by_case.get(duplicate.id, []):
                            session.case_id = keeper.id
                            session.updated_at = _utcnow()
                            stats.sessions_relinked += 1
                        if not sessions_by_case.get(duplicate.id):
                            duplicate.status = "archived"
                            duplicate.updated_at = _utcnow()
                            stats.cases_archived += 1

            if group_sessions_by_case_label:
                for session in owner_sessions:
                    metadata = session.metadata_json or {}
                    label = (
                        metadata.get("case_label")
                        or metadata.get("case_private_label")
                        or metadata.get("label")
                    )
                    label_hash = _hash_case_label(label, secret)
                    if not label_hash:
                        continue
                    target_case = active_cases_by_hash.get(label_hash)
                    if not target_case:
                        new_case = QuestionnaireCase(
                            case_public_id=f"CASO-{uuid.uuid4().hex[:6].upper()}",
                            owner_user_id=owner_id,
                            private_label=crypto_service.encrypt_text(str(label), purpose="questionnaire_case.private_label"),
                            private_label_hash=label_hash,
                            status="active",
                            metadata_json={"source": "audit_and_repair"},
                        )
                        db.session.add(new_case)
                        db.session.flush()
                        active_cases_by_hash[label_hash] = new_case
                        target_case = new_case
                    if session.case_id != target_case.id:
                        session.case_id = target_case.id
                        session.updated_at = _utcnow()
                        stats.sessions_relinked += 1

            if archive_excess_drafts:
                draft_like = [
                    row for row in sorted(owner_sessions, key=lambda item: item.created_at or _utcnow(), reverse=True)
                    if str(row.status or "").lower() in {"draft", "in_progress"}
                ]
                keep = 2
                for row in draft_like[keep:]:
                    if _safe_to_archive_draft(row):
                        row.status = "archived"
                        row.archived_at = row.archived_at or _utcnow()
                        row.updated_at = _utcnow()
                        stats.drafts_archived += 1

            if ensure_realistic_dashboard_data and days_spread > 0:
                for row in owner_sessions:
                    if not owner_user or not _is_synthetic_user(owner_user):
                        continue
                    offset_days = _spread_offset_days(str(row.id), days_spread)
                    base = (row.created_at or _utcnow()) - timedelta(days=offset_days)
                    new_created = base
                    new_updated = max(new_created, row.updated_at or new_created)
                    new_submitted = row.submitted_at
                    new_processed = row.processed_at
                    if new_submitted and new_submitted < new_updated:
                        new_submitted = new_updated + timedelta(minutes=5)
                    if new_processed:
                        floor = new_submitted or new_updated
                        if new_processed < floor:
                            new_processed = floor + timedelta(minutes=5)
                    changed = (
                        row.created_at != new_created
                        or row.updated_at != new_updated
                        or row.submitted_at != new_submitted
                        or row.processed_at != new_processed
                    )
                    if changed:
                        row.created_at = new_created
                        row.updated_at = new_updated
                        row.submitted_at = new_submitted
                        row.processed_at = new_processed
                        stats.timestamps_redistributed += 1

        db.session.commit()
        print(f"[audit-dashboard-data] sessions_relinked={stats.sessions_relinked}")
        print(f"[audit-dashboard-data] cases_archived={stats.cases_archived}")
        print(f"[audit-dashboard-data] drafts_archived={stats.drafts_archived}")
        print(f"[audit-dashboard-data] timestamps_redistributed={stats.timestamps_redistributed}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and repair questionnaire dashboard synthetic data quality.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only (default).")
    parser.add_argument("--execute", action="store_true", help="Apply changes.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-synthetic", action="store_true", help="Restrict to synthetic users.")
    parser.add_argument("--user-email", type=str, default=None)
    parser.add_argument("--guardian-email", type=str, default=None)
    parser.add_argument("--psychologist-email", type=str, default=None)
    parser.add_argument("--days-spread", type=int, default=120)
    parser.add_argument("--archive-excess-drafts", action="store_true")
    parser.add_argument("--group-sessions-by-case-label", action="store_true")
    parser.add_argument("--repair-case-labels", action="store_true")
    parser.add_argument("--ensure-realistic-dashboard-data", action="store_true")
    args = parser.parse_args()

    execute = bool(args.execute)
    if not execute:
        args.dry_run = True

    return audit_and_repair(
        execute=execute,
        limit=int(args.limit or 0),
        only_synthetic=bool(args.only_synthetic),
        user_email=args.user_email,
        guardian_email=args.guardian_email,
        psychologist_email=args.psychologist_email,
        days_spread=int(args.days_spread or 0),
        archive_excess_drafts=bool(args.archive_excess_drafts),
        group_sessions_by_case_label=bool(args.group_sessions_by_case_label),
        repair_case_labels=bool(args.repair_case_labels),
        ensure_realistic_dashboard_data=bool(args.ensure_realistic_dashboard_data),
    )


if __name__ == "__main__":
    raise SystemExit(main())
