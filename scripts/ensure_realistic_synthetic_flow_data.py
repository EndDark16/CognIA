"""Create/repair a realistic synthetic end-to-end flow for backend QA.

This script is idempotent and restricted to synthetic users/data markers.
Dry-run is default. Use --apply to persist changes.
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
    QuestionnaireAccessGrant,
    QuestionnaireCase,
    QuestionnaireProfessionalReview,
    QuestionnaireSession,
    QuestionnaireSessionResult,
    QuestionnaireSessionResultDomain,
    Role,
    UserMFA,
    db,
)


FLOW_MARKER = "realistic_synjuan_psycam_v1"
PHASES = (
    "all",
    "users",
    "guardian-flow",
    "psychologist-flow",
    "admin-analytics",
    "validate",
    "credentials",
)

SYNJUAN_USERNAME = "synjuan"
PSYCAM_USERNAME = "psycam"
CASE_LABELS = ("hijo 1", "hijo 2", "hijo 3")
DOMAIN_FOCUS = {"hijo 1": "adhd", "hijo 2": "anxiety", "hijo 3": "conduct"}
CASE_SERIES = {
    "hijo 1": [0.90, 0.79, 0.83, 0.68, 0.57, 0.49, 0.41],
    "hijo 2": [0.34, 0.43, 0.40, 0.55, 0.63, 0.71, 0.82],
    "hijo 3": [0.20, 0.24, 0.18],
}
REVIEW_TEMPLATES = [
    (
        "Se observa disminucion progresiva de senales de inquietud.",
        "Mantener rutinas, coordinacion escolar y seguimiento mensual.",
    ),
    (
        "Se recomienda revisar cambios recientes en el contexto escolar.",
        "Fortalecer estrategias de regulacion emocional y monitoreo semanal.",
    ),
    (
        "No se identifican senales prioritarias en este corte.",
        "Continuar observacion preventiva y reevaluacion periodica.",
    ),
]


@dataclass
class Stats:
    users_created: int = 0
    users_repaired: int = 0
    credentials_written: int = 0
    cases_created: int = 0
    cases_archived: int = 0
    sessions_created: int = 0
    sessions_repaired: int = 0
    shares_created: int = 0
    shares_accepted: int = 0
    reviews_upserted: int = 0
    audit_events_created: int = 0
    warnings: list[str] = field(default_factory=list)
    by_alert: Counter = field(default_factory=Counter)
    by_domain: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        return {
            "users_created": self.users_created,
            "users_repaired": self.users_repaired,
            "credentials_written": self.credentials_written,
            "cases_created": self.cases_created,
            "cases_archived": self.cases_archived,
            "sessions_created": self.sessions_created,
            "sessions_repaired": self.sessions_repaired,
            "shares_created": self.shares_created,
            "shares_accepted": self.shares_accepted,
            "reviews_upserted": self.reviews_upserted,
            "audit_events_created": self.audit_events_created,
            "results_by_alert": dict(self.by_alert),
            "results_by_domain": dict(self.by_domain),
            "warnings": self.warnings,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _password() -> str:
    return f"CognIA-Flow-{secrets.token_urlsafe(18)}!8"


def _progress(message: str, *, apply: bool) -> None:
    if apply:
        print(f"[realistic-flow] {message}", flush=True)


def _role(name: str) -> Role:
    row = Role.query.filter_by(name=name).first()
    if row:
        return row
    row = Role(name=name, description=f"Synthetic realistic role {name}")
    db.session.add(row)
    db.session.flush()
    return row


def _safe_username_scope(username: str) -> bool:
    return username in {SYNJUAN_USERNAME, PSYCAM_USERNAME}


def _credentials_path(base_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"synjuan_psycam_credentials_{stamp}.txt"


def _user_specs() -> list[dict[str, Any]]:
    return [
        {
            "username": SYNJUAN_USERNAME,
            "email": "synjuan@cognia-synthetic.test",
            "full_name": "Juan Martinez",
            "user_type": "guardian",
            "role": "GUARDIAN",
            "department": "Bogota D.C.",
            "city": "Bogota",
            "needs_mfa": False,
            "professional_card_number": None,
            "colpsic_verified": False,
        },
        {
            "username": PSYCAM_USERNAME,
            "email": "psycam@cognia-synthetic.test",
            "full_name": "Camila Rodriguez",
            "user_type": "psychologist",
            "role": "PSYCHOLOGIST",
            "department": "Cundinamarca",
            "city": "Bogota",
            "needs_mfa": True,
            "professional_card_number": "COLPSIC-SYN-2026-001",
            "colpsic_verified": True,
        },
    ]


def _ensure_user(
    spec: dict[str, Any],
    *,
    apply: bool,
    rotate_credentials: bool,
    credential_rows: list[dict[str, Any]],
    stats: Stats,
) -> AppUser | None:
    user = AppUser.query.filter_by(username=spec["username"]).first()
    role = _role(spec["role"]) if apply else Role.query.filter_by(name=spec["role"]).first()
    if user and not _safe_username_scope(user.username):
        raise RuntimeError("unsafe_user_scope")

    if not user:
        stats.users_created += 1
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
            colpsic_verified=bool(spec["colpsic_verified"]),
            colpsic_verified_at=_now() if spec["colpsic_verified"] else None,
        )
        if role:
            user.roles.append(role)
        db.session.add(user)
        db.session.flush()
        credential_rows.append(
            {
                "role": spec["role"],
                "username": spec["username"],
                "email": spec["email"],
                "password": password,
                "mfa_required": bool(spec["needs_mfa"]),
                "totp_secret": None,
            }
        )
    else:
        repaired = False
        for field in ("email", "full_name", "user_type", "city", "department"):
            if getattr(user, field) != spec[field]:
                repaired = True
                if apply:
                    setattr(user, field, spec[field])
        if bool(user.is_active) is False:
            repaired = True
            if apply:
                user.is_active = True
        if spec["professional_card_number"] and user.professional_card_number != spec["professional_card_number"]:
            repaired = True
            if apply:
                user.professional_card_number = spec["professional_card_number"]
        if bool(spec["colpsic_verified"]) and not bool(user.colpsic_verified):
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
                credential_rows.append(
                    {
                        "role": spec["role"],
                        "username": spec["username"],
                        "email": spec["email"],
                        "password": password,
                        "mfa_required": bool(spec["needs_mfa"]),
                        "totp_secret": None,
                    }
                )
        if repaired:
            stats.users_repaired += 1

    if user and spec["needs_mfa"]:
        secret = None
        mfa_row = UserMFA.query.filter_by(user_id=user.id).first()
        if not mfa_row or rotate_credentials:
            if apply:
                secret = generate_totp_secret()
                if mfa_row:
                    mfa_row.secret_encrypted = encrypt_mfa_secret(secret)
                    mfa_row.updated_at = _now()
                else:
                    db.session.add(
                        UserMFA(
                            user_id=user.id,
                            method="totp",
                            secret_encrypted=encrypt_mfa_secret(secret),
                        )
                    )
        if apply:
            user.mfa_enabled = True
            user.mfa_method = "totp"
            user.mfa_confirmed_at = user.mfa_confirmed_at or _now()
            if secret:
                for row in reversed(credential_rows):
                    if row["username"] == user.username:
                        row["totp_secret"] = secret
                        break
    elif user and apply:
        user.mfa_enabled = False
        user.mfa_method = "none"
    return user


def _write_credentials(rows: list[dict[str, Any]], credentials_dir: Path, stats: Stats) -> None:
    if not rows:
        return
    path = _credentials_path(credentials_dir)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("CognIA realistic synthetic credentials (sensitive)\n\n")
        for row in rows:
            fh.write(f"role={row['role']}\n")
            fh.write(f"username={row['username']}\n")
            fh.write(f"email={row['email']}\n")
            fh.write(f"password={row['password']}\n")
            fh.write(f"mfa_required={row['mfa_required']}\n")
            fh.write(f"totp_secret={row.get('totp_secret') or '<existing-or-not-required>'}\n\n")
    stats.credentials_written = len(rows)
    stats.warnings.append(f"credentials_file={path}")


def _ensure_cases(guardian: AppUser, *, apply: bool, stats: Stats) -> dict[str, QuestionnaireCase]:
    out: dict[str, QuestionnaireCase] = {}
    for label in CASE_LABELS:
        label_hash = qv2._hash_case_label(label)
        row = (
            QuestionnaireCase.query.filter_by(owner_user_id=guardian.id, private_label_hash=label_hash)
            .order_by(QuestionnaireCase.created_at.asc())
            .first()
        )
        if not row and apply:
            result = qv2.create_case(
                owner_user_id=guardian.id,
                payload={
                    "label": label,
                    "private_label": label,
                    "description": f"Caso sintetico realista para {label}.",
                    "metadata": {"synthetic": True, "created_for": FLOW_MARKER},
                },
            )
            row = qv2.get_case_or_404(uuid.UUID(str(result["case_id"])))
            stats.cases_created += 1
        if row:
            out[label] = row
    return out


def _archive_non_presentable_cases(guardian: AppUser, *, apply: bool, stats: Stats) -> None:
    keep_hashes = {qv2._hash_case_label(label) for label in CASE_LABELS if qv2._hash_case_label(label)}
    rows = QuestionnaireCase.query.filter_by(owner_user_id=guardian.id, status="active").all()
    for row in rows:
        if row.private_label_hash in keep_hashes:
            continue
        # synjuan is a fully synthetic user for deterministic QA scenarios.
        # Keep only hijo 1/2/3 active to avoid dashboard contamination.
        stats.cases_archived += 1
        if apply:
            row.status = "archived"
            row.updated_at = _now()
            db.session.add(row)


def _existing_session_for_slot(case: QuestionnaireCase, slot_key: str) -> QuestionnaireSession | None:
    rows = (
        QuestionnaireSession.query.filter_by(case_id=case.id, owner_user_id=case.owner_user_id)
        .order_by(QuestionnaireSession.created_at.asc())
        .all()
    )
    for row in rows:
        meta = qv2._decrypt_json_safe(
            row.metadata_json,
            "questionnaire_session.metadata_json",
            default={},
        ) or {}
        marker = (meta.get("metadata") or {}).get("synthetic_flow_marker")
        slot = (meta.get("metadata") or {}).get("synthetic_flow_slot")
        if marker == FLOW_MARKER and slot == slot_key:
            return row
    return None


def _domain_probability_profile(focus_domain: str, focus_probability: float) -> dict[str, float]:
    base = {"adhd": 0.22, "anxiety": 0.24, "conduct": 0.21, "depression": 0.19, "elimination": 0.18}
    profile = {key: float(value) for key, value in base.items()}
    profile[focus_domain] = max(0.05, min(0.97, float(focus_probability)))
    for key in list(profile.keys()):
        if key == focus_domain:
            continue
        profile[key] = max(0.05, min(profile[key], profile[focus_domain] - 0.14))
    return profile


def _answer_value_for_question(question, focus_domain: str, focus_probability: float, index: int) -> Any:
    min_value = float(question.min_value if question.min_value is not None else 0.0)
    max_value = float(question.max_value if question.max_value is not None else 3.0)
    if max_value <= min_value:
        max_value = min_value + 3.0
    span = max_value - min_value
    raw = 0.22 + (0.62 if question.domain == focus_domain else 0.18)
    raw += (focus_probability - 0.5) * (0.70 if question.domain == focus_domain else 0.30)
    raw += ((index % 3) - 1) * 0.06
    raw = max(0.0, min(1.0, raw))
    numeric_value = round(min_value + (span * raw), 2)

    response_type = str(getattr(question, "response_type", "") or "").strip().lower()
    if response_type in {"single_choice", "likert_single", "boolean", "integer"}:
        options = qv2._json(getattr(question, "response_options_json", None))
        allowed: list[float] = []
        if isinstance(options, list):
            for option in options:
                candidate = option.get("value") if isinstance(option, dict) else option
                try:
                    allowed.append(float(candidate))
                except Exception:
                    continue
        if allowed:
            nearest = min(allowed, key=lambda value: abs(value - numeric_value))
            nearest_int = int(round(nearest))
            return nearest_int if abs(nearest - nearest_int) < 1e-6 else nearest
        rounded = int(round(numeric_value))
        bounded = int(max(min_value, min(max_value, rounded)))
        return bounded

    if response_type in {"decimal", "numeric_range"}:
        return numeric_value
    return str(int(round(numeric_value)))


def _create_or_repair_session(
    guardian: AppUser,
    case: QuestionnaireCase,
    *,
    child_label: str,
    slot_index: int,
    applied_at: datetime,
    focus_probability: float,
    apply: bool,
    stats: Stats,
) -> QuestionnaireSession | None:
    slot_key = f"{child_label}:{slot_index:02d}"
    existing = _existing_session_for_slot(case, slot_key)
    focus_domain = DOMAIN_FOCUS[child_label]
    if existing is None and not apply:
        stats.sessions_created += 1
        return None

    session = existing
    if session is None and apply:
        payload = {
            "mode": "short",
            "role": "guardian",
            "case_id": case.id,
            "case_label": child_label,
            "child_age_years": 9,
            "completed_by_role": "padre",
            "respondent_relationship": "padre",
            "applied_at": applied_at.isoformat(),
            "source_channel": "realistic_synthetic_flow",
            "metadata": {
                "synthetic": True,
                "created_for": FLOW_MARKER,
                "synthetic_flow_marker": FLOW_MARKER,
                "synthetic_flow_slot": slot_key,
                "synthetic_child_case": child_label,
            },
        }
        session = qv2.create_session(guardian.id, payload)
        stats.sessions_created += 1
    elif session is not None:
        stats.sessions_repaired += 1

    if session is None:
        return None

    if apply and session.status != "processed":
        rows = qv2._session_answer_rows(session)
        answers: list[dict[str, Any]] = []
        for idx, (_item, question, _answer, _section) in enumerate(rows, start=1):
            value = _answer_value_for_question(question, focus_domain, focus_probability, idx)
            answers.append({"question_id": question.id, "answer": value})
        if answers:
            qv2.save_answers(session, guardian.id, answers, mark_final=True)
        db.session.refresh(session)

    if apply:
        profile = _domain_probability_profile(focus_domain, focus_probability)
        session.status = "processed"
        session.applied_at = applied_at
        session.started_at = applied_at
        session.submitted_at = applied_at + timedelta(minutes=22)
        session.processed_at = applied_at + timedelta(minutes=27)
        session.created_at = applied_at
        session.updated_at = session.processed_at
        session.progress_pct = 100.0
        session.completed_by_user_id = guardian.id
        session.completed_by_display_name = guardian.full_name
        session.completed_by_role = "padre"
        session.respondent_relationship = "padre"
        session.source_channel = "realistic_synthetic_flow"
        meta = qv2._decrypt_json_safe(session.metadata_json, "questionnaire_session.metadata_json", default={}) or {}
        nested = dict(meta.get("metadata") or {})
        nested.update(
            {
                "synthetic": True,
                "created_for": FLOW_MARKER,
                "synthetic_flow_marker": FLOW_MARKER,
                "synthetic_flow_slot": slot_key,
                "synthetic_child_case": child_label,
            }
        )
        meta["metadata"] = nested
        session.metadata_json = qv2._encrypt_json(meta, "questionnaire_session.metadata_json")
        db.session.add(session)
        db.session.flush()

        result = QuestionnaireSessionResult.query.filter_by(session_id=session.id).first()
        if not result:
            result = QuestionnaireSessionResult(session_id=session.id)
        result.summary_text = (
            f"Patron orientativo sintetico para {child_label} con predominio en {qv2._domain_label(focus_domain)}."
        )
        result.operational_recommendation = "Seguimiento orientativo mensual. No constituye diagnostico."
        result.needs_professional_review = qv2._alert_level(focus_probability) in {"elevated", "high", "critical_review"}
        result.processed_at = session.processed_at
        result.runtime_ms = 25
        result.model_bundle_version = "synthetic-realistic-flow"
        result.questionnaire_version_label = session.questionnaire_version_label
        result.scales_version_label = session.scales_version_label
        result.metadata_json = qv2._encrypt_json(
            {
                "synthetic": True,
                "created_for": FLOW_MARKER,
                "score_type": qv2.SCORE_TYPE,
                "score_label": qv2.SCORE_LABEL,
                "score_explanation": qv2.SCORE_EXPLANATION,
            },
            "questionnaire_session_result.metadata_json",
        )
        db.session.add(result)
        db.session.flush()
        for domain, probability in profile.items():
            row = QuestionnaireSessionResultDomain.query.filter_by(result_id=result.id, domain=domain).first()
            alert_level = qv2._alert_level(probability)
            if not row:
                row = QuestionnaireSessionResultDomain(
                    result_id=result.id,
                    session_id=session.id,
                    domain=domain,
                    probability=probability,
                    alert_level=alert_level,
                    confidence_pct=round(probability * 100.0, 1),
                    confidence_band="orientativo",
                    model_id="realistic-synthetic-flow",
                    model_version="v1",
                    mode=session.mode_key,
                    operational_class="review" if alert_level in {"high", "critical_review"} else "monitor",
                    result_summary=f"{qv2._domain_label(domain)} sintetico",
                    needs_professional_review=alert_level in {"elevated", "high", "critical_review"},
                    metadata_json={"synthetic": True, "created_for": FLOW_MARKER},
                )
            else:
                row.probability = probability
                row.alert_level = alert_level
                row.confidence_pct = round(probability * 100.0, 1)
                row.needs_professional_review = alert_level in {"elevated", "high", "critical_review"}
                row.mode = session.mode_key
                row.result_summary = f"{qv2._domain_label(domain)} sintetico"
            stats.by_domain[domain] += 1
            stats.by_alert[alert_level] += 1
            db.session.add(row)
    return session


def _child_schedule(child_label: str) -> list[datetime]:
    scores = CASE_SERIES[child_label]
    start = _now() - timedelta(days=30 * (len(scores) + 1))
    return [start + timedelta(days=30 * idx + (idx % 3) * 2) for idx, _ in enumerate(scores)]


def _share_and_review_for_session(
    session: QuestionnaireSession,
    guardian: AppUser,
    psychologist: AppUser,
    *,
    review_idx: int,
    apply: bool,
    stats: Stats,
) -> None:
    grant = QuestionnaireAccessGrant.query.filter_by(session_id=session.id, grantee_user_id=psychologist.id).first()
    if grant is None and apply:
        response = qv2.create_share(
            session,
            guardian.id,
            {
                "grantee_user_id": psychologist.id,
                "share_scope": "session",
                "grant_can_download_pdf": True,
                "grant_can_tag": False,
            },
        )
        grant = QuestionnaireAccessGrant.query.filter_by(
            id=uuid.UUID(str(response.get("grant", {}).get("grant_id")))
        ).first() if response.get("grant", {}).get("grant_id") else None
        stats.shares_created += 1
    if grant and apply and str(grant.request_status or "").lower() == "pending":
        qv2.accept_share_request(grant.id, psychologist.id, "Acepto revision sintetica.")
        stats.shares_accepted += 1
    if grant and apply and str(grant.request_status or "").lower() == "accepted":
        concept, recommendation = REVIEW_TEMPLATES[review_idx % len(REVIEW_TEMPLATES)]
        qv2.upsert_professional_review(
            session,
            psychologist.id,
            {
                "review_status": "reviewed",
                "initial_concept": concept,
                "recommendation": recommendation,
                "visible_to_guardian": True,
            },
        )
        stats.reviews_upserted += 1


def _phase_users(*, apply: bool, rotate_credentials: bool, credentials_dir: Path, stats: Stats) -> None:
    credential_rows: list[dict[str, Any]] = []
    for spec in _user_specs():
        _progress(f"users username={spec['username']}", apply=apply)
        _ensure_user(
            spec,
            apply=apply,
            rotate_credentials=rotate_credentials,
            credential_rows=credential_rows,
            stats=stats,
        )
    if apply:
        if rotate_credentials:
            _write_credentials(credential_rows, credentials_dir, stats)
        db.session.commit()


def _phase_guardian_flow(*, apply: bool, stats: Stats) -> None:
    guardian = AppUser.query.filter_by(username=SYNJUAN_USERNAME).first()
    if not guardian:
        stats.warnings.append("guardian_missing_run_users_phase_first")
        return
    cases = _ensure_cases(guardian, apply=apply, stats=stats)
    _archive_non_presentable_cases(guardian, apply=apply, stats=stats)
    for label in CASE_LABELS:
        case = cases.get(label)
        if not case:
            continue
        schedule = _child_schedule(label)
        for idx, (slot_date, score) in enumerate(zip(schedule, CASE_SERIES[label], strict=False), start=1):
            _progress(f"guardian-flow {label} slot={idx}", apply=apply)
            _create_or_repair_session(
                guardian,
                case,
                child_label=label,
                slot_index=idx,
                applied_at=slot_date,
                focus_probability=score,
                apply=apply,
                stats=stats,
            )
    if apply:
        db.session.commit()


def _phase_psychologist_flow(*, apply: bool, stats: Stats) -> None:
    guardian = AppUser.query.filter_by(username=SYNJUAN_USERNAME).first()
    psychologist = AppUser.query.filter_by(username=PSYCAM_USERNAME).first()
    if not guardian or not psychologist:
        stats.warnings.append("psychologist_flow_missing_users")
        return
    sessions = (
        QuestionnaireSession.query.filter_by(owner_user_id=guardian.id, status="processed")
        .order_by(QuestionnaireSession.processed_at.asc())
        .all()
    )
    review_idx = 0
    for row in sessions:
        domain_rows = QuestionnaireSessionResultDomain.query.filter_by(session_id=row.id).all()
        top = max(domain_rows, key=lambda item: float(item.probability or 0.0), default=None)
        if not top:
            continue
        if qv2._alert_rank(top.alert_level) < qv2._alert_rank("elevated"):
            continue
        _progress(f"psychologist-flow share session={row.questionnaire_public_id}", apply=apply)
        _share_and_review_for_session(
            row,
            guardian,
            psychologist,
            review_idx=review_idx,
            apply=apply,
            stats=stats,
        )
        review_idx += 1
    if apply:
        db.session.commit()


def _phase_admin_analytics(*, apply: bool, stats: Stats) -> None:
    guardian = AppUser.query.filter_by(username=SYNJUAN_USERNAME).first()
    psychologist = AppUser.query.filter_by(username=PSYCAM_USERNAME).first()
    if not guardian or not psychologist:
        stats.warnings.append("admin_analytics_missing_users")
        return
    actions = [
        ("QA_REALISTIC_CASE_CREATED", guardian.id),
        ("QA_REALISTIC_SHARE_REQUESTED", guardian.id),
        ("QA_REALISTIC_SHARE_ACCEPTED", psychologist.id),
        ("QA_REALISTIC_REVIEW_CREATED", psychologist.id),
    ]
    for action, user_id in actions:
        exists = AuditLog.query.filter_by(user_id=user_id, action=action, section="questionnaire_v2").first()
        if exists:
            continue
        stats.audit_events_created += 1
        if apply:
            db.session.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    section="questionnaire_v2",
                    details={"synthetic": True, "created_for": FLOW_MARKER},
                )
            )
    if apply:
        db.session.commit()


def _phase_validate(stats: Stats) -> dict[str, Any]:
    guardian = AppUser.query.filter_by(username=SYNJUAN_USERNAME).first()
    psychologist = AppUser.query.filter_by(username=PSYCAM_USERNAME).first()
    if not guardian or not psychologist:
        return {"ok": False, "reason": "users_missing"}

    case_rows = (
        QuestionnaireCase.query.filter_by(owner_user_id=guardian.id)
        .order_by(QuestionnaireCase.created_at.asc())
        .all()
    )
    cases_by_label: dict[str, QuestionnaireCase] = {}
    for row in case_rows:
        label = qv2._case_display_label(row, guardian.id)
        if label in CASE_LABELS:
            cases_by_label[label] = row

    evolution_checks: dict[str, str] = {}
    for label, case in cases_by_label.items():
        rows = (
            QuestionnaireSession.query.filter_by(owner_user_id=guardian.id, case_id=case.id, status="processed")
            .order_by(QuestionnaireSession.processed_at.asc())
            .all()
        )
        focus_domain = DOMAIN_FOCUS[label]
        values: list[float] = []
        for row in rows:
            top = QuestionnaireSessionResultDomain.query.filter_by(session_id=row.id, domain=focus_domain).first()
            if top:
                values.append(float(top.probability or 0.0))
        if len(values) >= 2:
            delta = values[-1] - values[0]
            if label == "hijo 1":
                evolution_checks[label] = "improving" if delta < -0.10 else "flat_or_invalid"
            elif label == "hijo 2":
                evolution_checks[label] = "worsening" if delta > 0.10 else "flat_or_invalid"
            else:
                evolution_checks[label] = "low_or_sparse" if max(values) < 0.45 else "unexpected_high"
        else:
            evolution_checks[label] = "insufficient_points"

    guardian_dashboard = qv2.guardian_dashboard(owner_user_id=guardian.id, months=8)
    psych_dashboard = qv2.psychologist_dashboard(psychologist_user_id=psychologist.id, page=1, page_size=20)
    share_summary = qv2.list_psychologist_share_requests(psychologist.id, status="all", page=1, page_size=20)

    return {
        "ok": True,
        "users": {"guardian": guardian.username, "psychologist": psychologist.username},
        "cases_expected": list(CASE_LABELS),
        "cases_found": sorted(cases_by_label.keys()),
        "evolution_checks": evolution_checks,
        "guardian_dashboard_summary": guardian_dashboard.get("summary", {}),
        "psychologist_dashboard_summary": psych_dashboard.get("summary", {}),
        "psychologist_share_requests_summary": share_summary.get("summary", {}),
        "psychologist_share_requests_charts_non_empty": {
            "by_status": bool(share_summary.get("charts", {}).get("by_status")),
            "by_domain": bool(share_summary.get("charts", {}).get("by_domain")),
            "over_time": bool(share_summary.get("charts", {}).get("over_time")),
        },
    }


def ensure_realistic_data(
    *,
    apply: bool,
    rotate_credentials: bool,
    credentials_dir: Path,
    phase: str = "all",
) -> dict[str, Any]:
    if phase not in PHASES:
        raise ValueError("invalid_phase")
    stats = Stats()
    validation: dict[str, Any] | None = None
    phases = ["users", "guardian-flow", "psychologist-flow", "admin-analytics", "validate"] if phase == "all" else [phase]
    try:
        for current in phases:
            if current == "users":
                _phase_users(
                    apply=apply,
                    rotate_credentials=False,
                    credentials_dir=credentials_dir,
                    stats=stats,
                )
            elif current == "guardian-flow":
                _phase_guardian_flow(apply=apply, stats=stats)
            elif current == "psychologist-flow":
                _phase_psychologist_flow(apply=apply, stats=stats)
            elif current == "admin-analytics":
                _phase_admin_analytics(apply=apply, stats=stats)
            elif current == "validate":
                validation = _phase_validate(stats)
            elif current == "credentials":
                if rotate_credentials:
                    _phase_users(
                        apply=apply,
                        rotate_credentials=True,
                        credentials_dir=credentials_dir,
                        stats=stats,
                    )
                else:
                    stats.warnings.append("credentials_phase_requires_rotate_credentials")
                    stats.warnings.append(f"credentials_output_plan={credentials_dir}")
        if not apply:
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise
    summary = stats.as_dict()
    summary["mode"] = "apply" if apply else "dry-run"
    summary["phase"] = phase
    summary["phases_available"] = list(PHASES)
    summary["users_scope"] = [SYNJUAN_USERNAME, PSYCAM_USERNAME]
    summary["safety_scope"] = {
        "touches_real_users": False,
        "allowed_email_domain": "@cognia-synthetic.test",
        "allowed_usernames": [SYNJUAN_USERNAME, PSYCAM_USERNAME],
        "prints_passwords_or_totp": False,
    }
    if validation is not None:
        summary["validation"] = validation
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure realistic synthetic backend flow data.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only (default).")
    mode.add_argument("--apply", action="store_true", help="Persist changes.")
    parser.add_argument("--env", default=os.getenv("APP_ENV", "local"), choices=["local", "staging", "production"])
    parser.add_argument("--phase", default="all", choices=PHASES)
    parser.add_argument("--all", action="store_true", help="Alias for --phase all.")
    parser.add_argument("--rotate-credentials", action="store_true")
    parser.add_argument(
        "--credentials-dir",
        default=str(Path.home() / "Documents" / "cognia_synthetic_credentials"),
        help="External directory (never inside repo).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = "all" if args.all else args.phase
    credentials_dir = Path(args.credentials_dir).resolve()
    if PROJECT_ROOT in credentials_dir.parents or credentials_dir == PROJECT_ROOT:
        raise SystemExit("credentials_dir_must_be_outside_repo")
    os.environ["APP_ENV"] = args.env
    app = create_app()
    with app.app_context():
        summary = ensure_realistic_data(
            apply=bool(args.apply),
            rotate_credentials=bool(args.rotate_credentials),
            credentials_dir=credentials_dir,
            phase=phase,
        )
    summary["env"] = args.env
    _safe_print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
