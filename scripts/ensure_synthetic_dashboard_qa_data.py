"""Ensure synthetic QA users and dashboard data.

Dry-run is the default. The script only creates or repairs users whose usernames
are listed in this file or start with the QA synthetic prefixes.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app
from api.security import encrypt_mfa_secret, generate_totp_secret, hash_password
from api.services import questionnaire_v2_service as qv2
from app.models import (
    AppUser,
    AuditLog,
    DashboardAggregate,
    GeneratedReport,
    QuestionnaireAccessGrant,
    QuestionnaireAuditEvent,
    QuestionnaireCase,
    QuestionnaireDefinition,
    QuestionnaireNotification,
    QuestionnaireProfessionalReview,
    QuestionnaireSession,
    QuestionnaireSessionPdfExport,
    QuestionnaireSessionResult,
    QuestionnaireSessionResultDomain,
    QuestionnaireSessionTag,
    QuestionnaireTag,
    QuestionnaireVersion,
    ReportJob,
    Role,
    UserMFA,
    db,
)


PRIMARY_USERS = {
    "guardian": [
        "synthetic_guardian_dashboard_01",
        "synthetic_guardian_dashboard_02",
        "synthetic_guardian_dashboard_03",
    ],
    "psychologist": [
        "syn_psych_dashboard_01",
        "syn_psych_dashboard_02",
        "syn_psych_dashboard_03",
    ],
    "admin": [
        "synthetic_admin_dashboard_01",
        "synthetic_admin_dashboard_02",
        "synthetic_admin_dashboard_03",
    ],
}

EXTRA_GUARDIANS = [f"qa_dashboard_guardian_{idx:02d}" for idx in range(1, 9)]
EXTRA_PSYCHOLOGISTS = [f"qa_dashboard_psychologist_{idx:02d}" for idx in range(1, 6)]

ROLE_BY_TYPE = {"guardian": "GUARDIAN", "psychologist": "PSYCHOLOGIST", "admin": "ADMIN"}
DOMAIN_LABELS = {
    "adhd": "TDAH",
    "anxiety": "Ansiedad",
    "conduct": "Conducta",
    "depression": "Depresion",
    "elimination": "Eliminacion",
}
CASE_BLUEPRINTS = [
    ("Atencion escolar", "adhd", "elevated"),
    ("Rutina familiar", "anxiety", "moderate"),
    ("Bienestar emocional", "depression", "high"),
    ("Conducta en casa", "conduct", "elevated"),
    ("Seguimiento trimestral", "elimination", "low"),
]
TAG_BLUEPRINTS = [
    ("QA - Alta prioridad", "#D9534F"),
    ("QA - Seguimiento escolar", "#2F80ED"),
    ("QA - Revision profesional", "#6C757D"),
    ("QA - Monitoreo reciente", "#198754"),
]


@dataclass
class Stats:
    users_created: int = 0
    users_repaired: int = 0
    credentials_written: int = 0
    cases_created: int = 0
    cases_repaired: int = 0
    sessions_created: int = 0
    sessions_repaired: int = 0
    results_created: int = 0
    tags_created: int = 0
    tag_links_created: int = 0
    grants_created: int = 0
    grants_repaired: int = 0
    reviews_created: int = 0
    notifications_created: int = 0
    report_jobs_created: int = 0
    pdf_exports_created: int = 0
    audit_events_created: int = 0
    by_role: Counter = field(default_factory=Counter)
    by_domain: Counter = field(default_factory=Counter)
    by_alert: Counter = field(default_factory=Counter)
    share_status: Counter = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "users_created": self.users_created,
            "users_repaired": self.users_repaired,
            "credentials_written": self.credentials_written,
            "cases_created": self.cases_created,
            "cases_repaired": self.cases_repaired,
            "sessions_created": self.sessions_created,
            "sessions_repaired": self.sessions_repaired,
            "results_created": self.results_created,
            "tags_created": self.tags_created,
            "tag_links_created": self.tag_links_created,
            "grants_created": self.grants_created,
            "grants_repaired": self.grants_repaired,
            "reviews_created": self.reviews_created,
            "notifications_created": self.notifications_created,
            "report_jobs_created": self.report_jobs_created,
            "pdf_exports_created": self.pdf_exports_created,
            "audit_events_created": self.audit_events_created,
            "users_by_role": dict(self.by_role),
            "results_by_domain": dict(self.by_domain),
            "results_by_alert": dict(self.by_alert),
            "shares_by_status": dict(self.share_status),
            "warnings": self.warnings,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _password() -> str:
    return f"CognIA-QA-{secrets.token_urlsafe(18)}!7"


def _safe_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _progress(message: str, *, apply: bool) -> None:
    if apply:
        print(f"[synthetic-qa] {message}", flush=True)


def _role(name: str) -> Role:
    row = Role.query.filter_by(name=name).first()
    if row:
        return row
    row = Role(name=name, description=f"Synthetic QA role {name}")
    db.session.add(row)
    db.session.flush()
    return row


def _ensure_version() -> QuestionnaireVersion:
    version = QuestionnaireVersion.query.filter_by(is_active=True).order_by(QuestionnaireVersion.created_at.desc()).first()
    if version:
        return version
    definition = QuestionnaireDefinition.query.filter_by(slug="qa-dashboard-synthetic").first()
    if not definition:
        definition = QuestionnaireDefinition(
            slug="qa-dashboard-synthetic",
            name="QA Dashboard Synthetic Questionnaire",
            description="Synthetic questionnaire definition for dashboard QA only.",
            is_active=True,
        )
        db.session.add(definition)
        db.session.flush()
    version = QuestionnaireVersion(
        definition_id=definition.id,
        version_label="qa-dashboard-v1",
        questionnaire_version_final="qa-dashboard-v1",
        scales_version_label="qa-dashboard-scales-v1",
        metadata_json={"synthetic": True, "created_for": "dashboard_qa"},
        is_active=True,
        published_at=_now(),
    )
    db.session.add(version)
    db.session.flush()
    return version


def _user_spec(username: str, user_type: str, idx: int) -> dict[str, Any]:
    role_label = {"guardian": "Padre/Tutor", "psychologist": "Psicologo QA", "admin": "Administrador QA"}[user_type]
    city = ["Bogota", "Facatativa", "Madrid", "Mosquera", "Funza"][idx % 5]
    department = "Bogota D.C." if city == "Bogota" else "Cundinamarca"
    return {
        "username": username,
        "email": f"{username}@cognia-synthetic.test",
        "full_name": f"QA Dashboard {role_label} {idx:02d}",
        "user_type": "psychologist" if user_type == "psychologist" else "guardian",
        "role": ROLE_BY_TYPE[user_type],
        "city": city,
        "department": department,
        "professional_card_number": f"COLPSIC-QA-{idx:04d}" if user_type == "psychologist" else None,
        "needs_mfa": user_type in {"psychologist", "admin"},
        "is_admin": user_type == "admin",
    }


def _all_user_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    idx = 1
    for user_type, names in PRIMARY_USERS.items():
        for username in names:
            specs.append(_user_spec(username, user_type, idx))
            idx += 1
    for username in EXTRA_GUARDIANS:
        specs.append(_user_spec(username, "guardian", idx))
        idx += 1
    for username in EXTRA_PSYCHOLOGISTS:
        specs.append(_user_spec(username, "psychologist", idx))
        idx += 1
    return specs


def _credential_path(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return base_dir / f"dashboard_qa_credentials_{stamp}.txt"


def _ensure_user(spec: dict[str, Any], *, apply: bool, rotate_credentials: bool, credential_rows: list[dict[str, Any]], stats: Stats) -> AppUser | None:
    user = AppUser.query.filter_by(username=spec["username"]).first()
    role = _role(spec["role"]) if apply else Role.query.filter_by(name=spec["role"]).first()
    if not user:
        stats.users_created += 1
        stats.by_role[spec["role"]] += 1
        if not apply:
            return None
        password = _password()
        user = AppUser(
            username=spec["username"],
            email=spec["email"],
            password=hash_password(password),
            full_name=spec["full_name"],
            user_type=spec["user_type"],
            professional_card_number=spec["professional_card_number"],
            city=spec["city"],
            department=spec["department"],
            is_active=True,
            colpsic_verified=bool(spec["professional_card_number"]),
            colpsic_verified_at=_now() if spec["professional_card_number"] else None,
        )
        if role:
            user.roles.append(role)
        db.session.add(user)
        db.session.flush()
        credential_rows.append({"spec": spec, "password": password, "totp_secret": None})
    else:
        repaired = False
        for field in ("email", "full_name", "user_type", "city", "department"):
            expected = spec[field]
            if getattr(user, field) != expected:
                repaired = True
                if apply:
                    setattr(user, field, expected)
        if spec["professional_card_number"] and user.professional_card_number != spec["professional_card_number"]:
            repaired = True
            if apply:
                user.professional_card_number = spec["professional_card_number"]
        if not user.is_active:
            repaired = True
            if apply:
                user.is_active = True
        if spec["professional_card_number"] and not user.colpsic_verified:
            repaired = True
            if apply:
                user.colpsic_verified = True
                user.colpsic_verified_at = _now()
        if role and role not in user.roles:
            repaired = True
            if apply:
                user.roles.append(role)
        if rotate_credentials:
            repaired = True
            if apply:
                password = _password()
                user.password = hash_password(password)
                user.password_changed_at = _now()
                credential_rows.append({"spec": spec, "password": password, "totp_secret": None})
        if repaired:
            stats.users_repaired += 1
            stats.by_role[spec["role"]] += 1
    if user and spec["needs_mfa"]:
        secret = None
        mfa = UserMFA.query.filter_by(user_id=user.id).first()
        if not mfa or rotate_credentials:
            stats.users_repaired += 1
            if apply:
                secret = generate_totp_secret()
                if mfa:
                    mfa.secret_encrypted = encrypt_mfa_secret(secret)
                    mfa.method = "totp"
                    mfa.updated_at = _now()
                else:
                    mfa = UserMFA(user_id=user.id, method="totp", secret_encrypted=encrypt_mfa_secret(secret))
                    db.session.add(mfa)
        if apply:
            user.mfa_enabled = True
            user.mfa_confirmed_at = user.mfa_confirmed_at or _now()
            user.mfa_method = "totp"
            if secret:
                for row in reversed(credential_rows):
                    if row["spec"]["username"] == spec["username"]:
                        row["totp_secret"] = secret
                        break
                else:
                    credential_rows.append({"spec": spec, "password": "<existing-not-rotated>", "totp_secret": secret})
    return user


def _ensure_case(owner: AppUser, label: str, status: str, *, apply: bool, stats: Stats) -> QuestionnaireCase | None:
    label_hash = qv2._hash_case_label(label)
    row = (
        QuestionnaireCase.query.filter_by(owner_user_id=owner.id, private_label_hash=label_hash, status=status)
        .order_by(QuestionnaireCase.created_at.asc())
        .first()
    )
    if row:
        stats.cases_repaired += 1
        if apply:
            row.updated_at = row.updated_at or row.created_at or _now()
            row.metadata_json = {**(row.metadata_json or {}), "synthetic": True, "created_for": "dashboard_qa"}
        return row
    stats.cases_created += 1
    if not apply:
        return None
    row = QuestionnaireCase(
        case_public_id=qv2._generate_case_public_id(),
        owner_user_id=owner.id,
        private_label=qv2._encrypt_text(label, "questionnaire_case.private_label") or label,
        private_label_hash=label_hash,
        status=status,
        metadata_json={"synthetic": True, "created_for": "dashboard_qa", "display_label": label},
        created_at=_now() - timedelta(days=150),
        updated_at=_now() - timedelta(days=7),
    )
    db.session.add(row)
    db.session.flush()
    return row


def _ensure_tag(owner: AppUser, name: str, color: str, *, apply: bool, stats: Stats) -> QuestionnaireTag | None:
    tag = QuestionnaireTag.query.filter_by(owner_user_id=owner.id, name=name).first()
    if tag:
        return tag
    stats.tags_created += 1
    if not apply:
        return None
    tag = QuestionnaireTag(owner_user_id=owner.id, name=name, color=color, visibility="private")
    db.session.add(tag)
    db.session.flush()
    return tag


def _ensure_session(owner: AppUser, case: QuestionnaireCase, version: QuestionnaireVersion, public_id: str, domain: str, alert: str, idx: int, *, apply: bool, stats: Stats) -> QuestionnaireSession | None:
    session = QuestionnaireSession.query.filter_by(questionnaire_public_id=public_id).first()
    processed_at = _now() - timedelta(days=idx * 11 + 3)
    created_at = processed_at - timedelta(hours=4)
    submitted_at = processed_at - timedelta(hours=2)
    safety = domain == "depression" and alert in {"high", "critical_review"} and idx % 2 == 0
    inconsistency = domain == "elimination" and idx % 2 == 1
    if not session:
        stats.sessions_created += 1
        if not apply:
            return None
        session = QuestionnaireSession(
            questionnaire_public_id=public_id,
            version_id=version.id,
            case_id=case.id,
            owner_user_id=owner.id,
            completed_by_user_id=owner.id,
            completed_by_display_name=owner.full_name,
            completed_by_role="padre",
            respondent_relationship="padre",
            applied_at=created_at,
            source_channel="dashboard_qa",
            respondent_role="guardian",
            mode="complete",
            mode_key="complete_guardian",
            status="processed",
            progress_pct=100,
            completion_quality_score=0.92,
            missingness_score=0.02,
            inconsistency_flags_json=["elimination_duration_frequency_mismatch"] if inconsistency else [],
            metadata_json={
                "synthetic": True,
                "created_for": "dashboard_qa",
                "case_label": qv2._case_display_label(case, owner.id),
                "safety_flags": ["self_harm_response_max"] if safety else [],
                "urgent_referral_recommended": safety,
            },
            started_at=created_at,
            submitted_at=submitted_at,
            processed_at=processed_at,
            created_at=created_at,
            updated_at=processed_at,
        )
        db.session.add(session)
        db.session.flush()
    else:
        stats.sessions_repaired += 1
        if apply:
            session.case_id = case.id
            session.status = "processed"
            session.completed_by_user_id = owner.id
            session.completed_by_display_name = owner.full_name
            session.completed_by_role = session.completed_by_role or "padre"
            session.respondent_relationship = session.respondent_relationship or "padre"
            session.applied_at = session.applied_at or created_at
            session.submitted_at = session.submitted_at or submitted_at
            session.processed_at = session.processed_at or processed_at
            session.created_at = session.created_at or created_at
            session.updated_at = processed_at
            session.metadata_json = {
                **(session.metadata_json or {}),
                "synthetic": True,
                "created_for": "dashboard_qa",
                "safety_flags": ["self_harm_response_max"] if safety else [],
                "urgent_referral_recommended": safety,
            }
    result = QuestionnaireSessionResult.query.filter_by(session_id=session.id).first() if session else None
    if not result:
        stats.results_created += 1
        if apply and session:
            result = QuestionnaireSessionResult(
                session_id=session.id,
                summary_text=f"Resultado sintetico QA con dominio principal {DOMAIN_LABELS[domain]}.",
                operational_recommendation="Concepto orientativo no diagnostico para validacion de dashboard.",
                completion_quality_score=0.92,
                missingness_score=0.02,
                inconsistency_flags_json=["elimination_duration_frequency_mismatch"] if inconsistency else [],
                needs_professional_review=alert in {"elevated", "high", "critical_review"} or safety,
                runtime_ms=120,
                model_bundle_version="qa-dashboard-synthetic",
                questionnaire_version_label=version.version_label,
                scales_version_label=version.scales_version_label,
                metadata_json={
                    "synthetic": True,
                    "created_for": "dashboard_qa",
                    "safety_flags": ["self_harm_response_max"] if safety else [],
                    "urgent_referral_recommended": safety,
                    "score_type": "symptom_load_index",
                    "score_label": "Indice de carga sintomatica",
                    "score_explanation": "Este valor no representa probabilidad diagnostica.",
                },
                processed_at=processed_at,
            )
            db.session.add(result)
            db.session.flush()
    if apply and session and result:
        probability = {"low": 0.28, "moderate": 0.48, "elevated": 0.67, "high": 0.82, "critical_review": 0.9}[alert]
        domain_row = QuestionnaireSessionResultDomain.query.filter_by(result_id=result.id, domain=domain).first()
        if not domain_row:
            domain_row = QuestionnaireSessionResultDomain(
                result_id=result.id,
                session_id=session.id,
                domain=domain,
                probability=probability,
                alert_level=alert,
                confidence_pct=round(probability * 100, 1),
                confidence_band="orientativo",
                model_id="qa-dashboard-synthetic",
                model_version="qa-dashboard-v1",
                mode="complete",
                operational_class="review" if alert in {"high", "critical_review"} else "monitor",
                result_summary=f"{DOMAIN_LABELS[domain]} sintetico para QA.",
                needs_professional_review=alert in {"elevated", "high", "critical_review"} or safety,
                metadata_json={
                    "synthetic": True,
                    "domain_code": domain,
                    "domain_label": DOMAIN_LABELS[domain],
                    "score_type": "symptom_load_index",
                    "score_explanation": "Indice orientativo, no diagnostico.",
                },
            )
            db.session.add(domain_row)
        stats.by_domain[domain] += 1
        stats.by_alert[alert] += 1
    return session


def _link_tag(session: QuestionnaireSession | None, tag: QuestionnaireTag | None, owner: AppUser, *, apply: bool, stats: Stats) -> None:
    if not session or not tag:
        return
    exists = QuestionnaireSessionTag.query.filter_by(session_id=session.id, tag_id=tag.id, assigned_by_user_id=owner.id).first()
    if exists:
        return
    stats.tag_links_created += 1
    if apply:
        db.session.add(QuestionnaireSessionTag(session_id=session.id, tag_id=tag.id, assigned_by_user_id=owner.id))


def _ensure_share(session: QuestionnaireSession | None, psychologist: AppUser | None, status: str, *, apply: bool, stats: Stats) -> QuestionnaireAccessGrant | None:
    if not session or not psychologist:
        return None
    grant = QuestionnaireAccessGrant.query.filter_by(session_id=session.id, grantee_user_id=psychologist.id).first()
    can_view = status == "accepted"
    if not grant:
        stats.grants_created += 1
        stats.share_status[status] += 1
        if not apply:
            return None
        grant = QuestionnaireAccessGrant(
            session_id=session.id,
            owner_user_id=session.owner_user_id,
            grantee_user_id=psychologist.id,
            grant_type="dashboard_qa",
            request_status=status,
            requested_at=(session.processed_at or _now()) + timedelta(hours=1),
            responded_at=(session.processed_at or _now()) + timedelta(hours=4) if status != "pending" else None,
            decision_by_user_id=psychologist.id if status != "pending" else None,
            requested_can_tag=True,
            requested_can_download_pdf=True,
            can_view=can_view,
            can_tag=can_view,
            can_download_pdf=can_view,
        )
        db.session.add(grant)
        db.session.flush()
    else:
        stats.grants_repaired += 1
        stats.share_status[status] += 1
        if apply:
            grant.request_status = status
            grant.can_view = can_view
            grant.can_tag = can_view
            grant.can_download_pdf = can_view
            grant.revoked_at = None
            if status != "pending":
                grant.responded_at = grant.responded_at or _now()
                grant.decision_by_user_id = psychologist.id
    return grant


def _ensure_review(session: QuestionnaireSession | None, psychologist: AppUser | None, status: str, *, apply: bool, stats: Stats) -> None:
    if not session or not psychologist or status == "pending":
        return
    review = QuestionnaireProfessionalReview.query.filter_by(session_id=session.id, psychologist_user_id=psychologist.id).first()
    if review:
        return
    stats.reviews_created += 1
    if apply:
        db.session.add(
            QuestionnaireProfessionalReview(
                session_id=session.id,
                case_id=session.case_id,
                owner_user_id=session.owner_user_id,
                psychologist_user_id=psychologist.id,
                review_status="closed" if status == "reviewed" else "in_review",
                initial_concept="Concepto inicial sintetico no diagnostico para QA.",
                recommendation="Orientacion sintetica para validar el flujo de revision.",
                visible_to_guardian=True,
                is_diagnostic=False,
                metadata_json={"synthetic": True, "created_for": "dashboard_qa"},
            )
        )


def _ensure_notification(user_id: uuid.UUID, actor_id: uuid.UUID, session: QuestionnaireSession | None, grant: QuestionnaireAccessGrant | None, notification_type: str, *, apply: bool, stats: Stats) -> None:
    if not session or not grant:
        return
    exists = QuestionnaireNotification.query.filter_by(user_id=user_id, grant_id=grant.id, notification_type=notification_type).first()
    if exists:
        return
    stats.notifications_created += 1
    if apply:
        db.session.add(
            QuestionnaireNotification(
                user_id=user_id,
                actor_user_id=actor_id,
                session_id=session.id,
                case_id=session.case_id,
                grant_id=grant.id,
                notification_type=notification_type,
                title="Solicitud QA de cuestionario",
                message="Solicitud sintetica para validacion de dashboard QA.",
                payload_json={"synthetic": True, "created_for": "dashboard_qa"},
            )
        )


def _ensure_reports_and_audit(user: AppUser, session: QuestionnaireSession | None, *, apply: bool, stats: Stats) -> None:
    if not session:
        return
    if not ReportJob.query.filter_by(requested_by_user_id=user.id, job_type="dashboard_qa_summary").first():
        stats.report_jobs_created += 1
        if apply:
            job = ReportJob(
                job_type="dashboard_qa_summary",
                requested_by_user_id=user.id,
                status="completed",
                params_json={"synthetic": True, "created_for": "dashboard_qa"},
                started_at=_now() - timedelta(minutes=5),
                finished_at=_now() - timedelta(minutes=3),
            )
            db.session.add(job)
            db.session.flush()
            db.session.add(
                GeneratedReport(
                    report_job_id=job.id,
                    report_type="executive_summary",
                    file_path="/tmp/cognia-dashboard-qa-report.pdf",
                    file_format="pdf",
                    metadata_json={"synthetic": True, "created_for": "dashboard_qa"},
                )
            )
    if not QuestionnaireSessionPdfExport.query.filter_by(session_id=session.id).first():
        stats.pdf_exports_created += 1
        if apply:
            db.session.add(
                QuestionnaireSessionPdfExport(
                    session_id=session.id,
                    file_path="/tmp/cognia-dashboard-qa-session.pdf",
                    file_name=f"{session.questionnaire_public_id}.pdf",
                    status="generated",
                    generated_by_user_id=user.id,
                    metadata_json={"synthetic": True, "created_for": "dashboard_qa"},
                )
            )
    for action in ("case_created", "tag_assigned", "share_requested", "pdf_generated"):
        if not QuestionnaireAuditEvent.query.filter_by(session_id=session.id, actor_user_id=user.id, event_type=f"qa_{action}").first():
            stats.audit_events_created += 1
            if apply:
                db.session.add(
                    QuestionnaireAuditEvent(
                        session_id=session.id,
                        actor_user_id=user.id,
                        event_type=f"qa_{action}",
                        payload_json={"synthetic": True, "created_for": "dashboard_qa"},
                    )
                )
        if not AuditLog.query.filter_by(user_id=user.id, action=f"QA_{action.upper()}").first():
            if apply:
                db.session.add(
                    AuditLog(
                        user_id=user.id,
                        action=f"QA_{action.upper()}",
                        section="dashboard_qa",
                        details={"synthetic": True, "created_for": "dashboard_qa"},
                    )
                )


def _ensure_aggregate(*, apply: bool) -> None:
    key = "qa_dashboard.synthetic_summary"
    today = _now().date()
    row = DashboardAggregate.query.filter_by(aggregate_key=key, period_start=today, period_end=today).first()
    if row or not apply:
        return
    db.session.add(
        DashboardAggregate(
            aggregate_key=key,
            period_start=today,
            period_end=today,
            value_json={"synthetic": True, "created_for": "dashboard_qa"},
            value_numeric=1.0,
        )
    )


def ensure_dashboard_data(*, apply: bool, rotate_credentials: bool, credentials_dir: Path) -> dict[str, Any]:
    stats = Stats()
    credential_rows: list[dict[str, Any]] = []
    specs = _all_user_specs()
    users: dict[str, AppUser] = {}
    for spec in specs:
        user = _ensure_user(spec, apply=apply, rotate_credentials=rotate_credentials, credential_rows=credential_rows, stats=stats)
        if user:
            users[spec["username"]] = user
    if apply:
        db.session.commit()
        _progress("users phase committed", apply=apply)

    version = _ensure_version() if apply else QuestionnaireVersion.query.filter_by(is_active=True).first()
    if apply:
        db.session.commit()
        _progress("questionnaire version phase committed", apply=apply)
    guardians = [users.get(username) for username in PRIMARY_USERS["guardian"] + EXTRA_GUARDIANS]
    psychologists = [users.get(username) for username in PRIMARY_USERS["psychologist"] + EXTRA_PSYCHOLOGISTS]
    psychologists = [row for row in psychologists if row is not None]
    share_cycle = ["pending", "accepted", "accepted", "rejected", "accepted"]

    for guardian_idx, guardian in enumerate([row for row in guardians if row is not None], start=1):
        tags = [_ensure_tag(guardian, name, color, apply=apply, stats=stats) for name, color in TAG_BLUEPRINTS]
        sessions: list[QuestionnaireSession | None] = []
        for case_idx, (label, domain, alert) in enumerate(CASE_BLUEPRINTS, start=1):
            status = "archived" if case_idx == len(CASE_BLUEPRINTS) else "active"
            case = _ensure_case(guardian, f"QA Dashboard · {label}", status, apply=apply, stats=stats)
            for q_idx in range(1, 5 if status == "active" else 2):
                public_id = f"QV2-QA-G{guardian_idx:02d}-C{case_idx:02d}-Q{q_idx:02d}"
                session = _ensure_session(
                    guardian,
                    case,
                    version,
                    public_id,
                    domain,
                    "critical_review" if domain == "depression" and q_idx == 2 else alert,
                    guardian_idx + case_idx + q_idx,
                    apply=apply,
                    stats=stats,
                )
                sessions.append(session)
                _link_tag(session, tags[(case_idx + q_idx) % len(tags)] if tags else None, guardian, apply=apply, stats=stats)
                if psychologists:
                    psych = psychologists[(guardian_idx + case_idx + q_idx) % len(psychologists)]
                    share_status = share_cycle[(guardian_idx + case_idx + q_idx) % len(share_cycle)]
                    grant = _ensure_share(session, psych, share_status, apply=apply, stats=stats)
                    _ensure_review(session, psych, "reviewed" if share_status == "accepted" and q_idx % 2 == 0 else share_status, apply=apply, stats=stats)
                    _ensure_notification(psych.id, guardian.id, session, grant, "questionnaire_share_requested", apply=apply, stats=stats)
                    if share_status in {"accepted", "rejected"}:
                        _ensure_notification(guardian.id, psych.id, session, grant, f"questionnaire_share_{share_status}", apply=apply, stats=stats)
                _ensure_reports_and_audit(guardian, session, apply=apply, stats=stats)
        if apply:
            db.session.commit()
            _progress(f"guardian phase committed username={guardian.username}", apply=apply)

    _ensure_aggregate(apply=apply)
    if credential_rows and apply:
        path = _credential_path(credentials_dir)
        with path.open("w", encoding="utf-8") as fh:
            fh.write("CognIA synthetic dashboard QA credentials\n")
            fh.write("Sensitive. Do not commit. Do not upload to CI artifacts.\n\n")
            for row in credential_rows:
                spec = row["spec"]
                fh.write(f"role={spec['role']}\n")
                fh.write(f"display_name={spec['full_name']}\n")
                fh.write(f"username={spec['username']}\n")
                fh.write(f"email={spec['email']}\n")
                fh.write(f"password={row['password']}\n")
                fh.write(f"mfa_required={spec['needs_mfa']}\n")
                fh.write(f"totp_secret={row.get('totp_secret') or '<existing-or-not-required>'}\n")
                fh.write("status=active\n\n")
        stats.credentials_written = len(credential_rows)
        stats.warnings.append(f"credentials_file={path}")
    if apply:
        db.session.commit()
        _progress("final phase committed", apply=apply)
    else:
        db.session.rollback()
    summary = stats.as_dict()
    summary["mode"] = "apply" if apply else "dry-run"
    summary["primary_users"] = {key: list(value) for key, value in PRIMARY_USERS.items()}
    summary["planned_minimums"] = {
        "synthetic_users_total": len(_all_user_specs()),
        "primary_users_total": sum(len(value) for value in PRIMARY_USERS.values()),
        "active_cases_per_primary_guardian": 4,
        "archived_cases_per_primary_guardian": 1,
        "questionnaires_per_primary_guardian": 17,
        "global_share_requests_minimum": 15,
        "professional_reviews_minimum": 6,
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure synthetic dashboard QA data.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes without writing. Default.")
    mode.add_argument("--apply", action="store_true", help="Write synthetic QA data.")
    parser.add_argument("--env", default=os.getenv("APP_ENV", "local"), choices=["local", "staging", "production"])
    parser.add_argument("--rotate-credentials", action="store_true", help="Rotate synthetic user passwords and write them externally.")
    parser.add_argument(
        "--credentials-dir",
        default=str(Path.home() / "Documents" / "cognia_synthetic_credentials"),
        help="External directory for generated credentials. Never use a repo path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    credentials_dir = Path(args.credentials_dir).resolve()
    if PROJECT_ROOT in credentials_dir.parents or credentials_dir == PROJECT_ROOT:
        raise SystemExit("credentials_dir_must_be_outside_repo")
    app = create_app()
    with app.app_context():
        summary = ensure_dashboard_data(
            apply=bool(args.apply),
            rotate_credentials=bool(args.rotate_credentials),
            credentials_dir=credentials_dir,
        )
    summary["env"] = args.env
    _safe_print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
