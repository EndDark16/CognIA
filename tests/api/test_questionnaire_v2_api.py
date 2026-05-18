import os
import sys
import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from flask_jwt_extended import create_access_token
try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency in CI images
    PdfReader = None

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.cache import qv2_active_version_cache
from api.services import questionnaire_v2_loader_service as loader_service
from api.services import questionnaire_v2_service as runtime_service
from app.models import AppUser, QuestionnaireQuestion, QuestionnaireSession, db
from config.settings import TestingConfig


def _build_small_source_dir(tmp_path: Path) -> Path:
    source = tmp_path / "cuestionario_v16.4"
    source.mkdir(parents=True, exist_ok=True)

    scales = pd.DataFrame(
        [
            {
                "scale_id": "YES_NO",
                "scale_name": "Si/No",
                "response_type": "single_choice",
                "response_options_json": '[{"value": 0, "label": "No"}, {"value": 1, "label": "Si"}]',
                "min_value": 0,
                "max_value": 1,
                "unit": "",
                "scale_guidance": "Seleccione Si o No",
            },
            {
                "scale_id": "FREQ_0_3",
                "scale_name": "Frecuencia 0-3",
                "response_type": "single_choice",
                "response_options_json": '[{"value": 0, "label": "Nunca"}, {"value": 1, "label": "A veces"}, {"value": 2, "label": "Frecuente"}, {"value": 3, "label": "Muy frecuente"}]',
                "min_value": 0,
                "max_value": 3,
                "unit": "",
                "scale_guidance": "Seleccione frecuencia",
            },
        ]
    )
    scales.to_csv(source / "questionnaire_v16_4_scales_excel_utf8.csv", index=False)

    rows = [
        {
            "questionnaire_item_id": "Q001",
            "feature": "adhd_symptom_01",
            "question_text_primary": "Pregunta ADHD 1",
            "caregiver_question": "Pregunta ADHD 1",
            "psychologist_question": "Pregunta ADHD 1",
            "section_name": "Atencion",
            "subsection_name": "ADHD",
            "questionnaire_section_suggested": "Atencion",
            "questionnaire_subsection_suggested": "ADHD",
            "layer": "dsm5",
            "domain": "adhd",
            "domains_final": "adhd|conduct",
            "module": "core",
            "criterion_ref": "A1",
            "instrument_or_source": "dsm5",
            "feature_type": "symptom",
            "feature_role": "model_input",
            "respondent_expected": "caregiver_or_psychologist",
            "administered_by": "caregiver_or_psychologist",
            "response_type": "single_choice",
            "scale_id": "FREQ_0_3",
            "response_options_json": '[{"value": 0, "label": "Nunca"}, {"value": 1, "label": "A veces"}, {"value": 2, "label": "Frecuente"}, {"value": 3, "label": "Muy frecuente"}]',
            "min_value": 0,
            "max_value": 3,
            "unit": "",
            "visible_question_yes_no": "yes",
            "generated_input_yes_no": "no",
            "show_in_questionnaire_yes_no": "yes",
            "is_transparent_derived": "no",
            "requires_internal_scoring": "no",
            "requires_exact_item_wording": "no",
            "requires_clinician_administration": "no",
            "requires_child_self_report": "no",
            "include_caregiver_1_3": "yes",
            "include_caregiver_2_3": "yes",
            "include_caregiver_full": "yes",
            "include_psychologist_1_3": "yes",
            "include_psychologist_2_3": "yes",
            "include_psychologist_full": "yes",
            "caregiver_rank": 1,
            "psychologist_rank": 1,
            "caregiver_priority_bucket": "alta",
            "psychologist_priority_bucket": "alta",
            "derived_from_features": "",
            "internal_scoring_formula_summary": "",
            "help_text": "",
            "notes": "",
            "canonical_question_id": "",
            "reuse_answer_from_question_id": "",
            "question_audit_status": "audited_v16_4",
        },
        {
            "questionnaire_item_id": "Q002",
            "feature": "anxiety_context_01",
            "question_text_primary": "Pregunta Anxiety",
            "caregiver_question": "Pregunta Anxiety",
            "psychologist_question": "Pregunta Anxiety",
            "section_name": "Ansiedad",
            "subsection_name": "Contexto",
            "questionnaire_section_suggested": "Ansiedad",
            "questionnaire_subsection_suggested": "Contexto",
            "layer": "dsm5",
            "domain": "anxiety",
            "domains_final": "anxiety",
            "module": "core",
            "criterion_ref": "C1",
            "instrument_or_source": "dsm5",
            "feature_type": "symptom",
            "feature_role": "model_input",
            "respondent_expected": "caregiver_or_psychologist",
            "administered_by": "caregiver_or_psychologist",
            "response_type": "single_choice",
            "scale_id": "YES_NO",
            "response_options_json": '[{"value": 0, "label": "No"}, {"value": 1, "label": "Si"}]',
            "min_value": 0,
            "max_value": 1,
            "unit": "",
            "visible_question_yes_no": "yes",
            "generated_input_yes_no": "no",
            "show_in_questionnaire_yes_no": "yes",
            "is_transparent_derived": "no",
            "requires_internal_scoring": "no",
            "requires_exact_item_wording": "no",
            "requires_clinician_administration": "no",
            "requires_child_self_report": "no",
            "include_caregiver_1_3": "yes",
            "include_caregiver_2_3": "yes",
            "include_caregiver_full": "yes",
            "include_psychologist_1_3": "yes",
            "include_psychologist_2_3": "yes",
            "include_psychologist_full": "yes",
            "caregiver_rank": 2,
            "psychologist_rank": 2,
            "caregiver_priority_bucket": "media",
            "psychologist_priority_bucket": "media",
            "derived_from_features": "",
            "internal_scoring_formula_summary": "",
            "help_text": "",
            "notes": "",
            "canonical_question_id": "",
            "reuse_answer_from_question_id": "",
            "question_audit_status": "audited_v16_4",
        },
        {
            "questionnaire_item_id": "Q003",
            "feature": "conduct_symptom_01",
            "question_text_primary": "Pregunta repetida",
            "caregiver_question": "Pregunta repetida",
            "psychologist_question": "Pregunta repetida",
            "section_name": "Conducta",
            "subsection_name": "Contexto",
            "questionnaire_section_suggested": "Conducta",
            "questionnaire_subsection_suggested": "Contexto",
            "layer": "dsm5",
            "domain": "conduct",
            "domains_final": "conduct",
            "module": "core",
            "criterion_ref": "B1",
            "instrument_or_source": "dsm5",
            "feature_type": "symptom",
            "feature_role": "model_input",
            "respondent_expected": "caregiver_or_psychologist",
            "administered_by": "caregiver_or_psychologist",
            "response_type": "single_choice",
            "scale_id": "YES_NO",
            "response_options_json": '[{"value": 0, "label": "No"}, {"value": 1, "label": "Si"}]',
            "min_value": 0,
            "max_value": 1,
            "unit": "",
            "visible_question_yes_no": "yes",
            "generated_input_yes_no": "no",
            "show_in_questionnaire_yes_no": "yes",
            "is_transparent_derived": "no",
            "requires_internal_scoring": "no",
            "requires_exact_item_wording": "no",
            "requires_clinician_administration": "no",
            "requires_child_self_report": "no",
            "include_caregiver_1_3": "yes",
            "include_caregiver_2_3": "yes",
            "include_caregiver_full": "yes",
            "include_psychologist_1_3": "yes",
            "include_psychologist_2_3": "yes",
            "include_psychologist_full": "yes",
            "caregiver_rank": 3,
            "psychologist_rank": 3,
            "caregiver_priority_bucket": "baja",
            "psychologist_priority_bucket": "baja",
            "derived_from_features": "",
            "internal_scoring_formula_summary": "",
            "help_text": "",
            "notes": "",
            "canonical_question_id": "Q001",
            "reuse_answer_from_question_id": "Q001",
            "question_audit_status": "audited_v16_4",
        },
    ]

    frame = pd.DataFrame(rows)
    frame.to_csv(source / "questionnaire_v16_4_visible_questions_excel_utf8.csv", index=False)
    frame.to_csv(source / "questionnaire_v16_4_master_excel_utf8.csv", index=False)

    (source / "questionnaire_v16_4_preview.md").write_text("preview", encoding="utf-8")
    (source / "questionnaire_v16_4_audit_summary.md").write_text("audit", encoding="utf-8")
    (source / "cuestionario_v16_4.pdf").write_bytes(b"%PDF-1.4\n%EOF")
    return source


@pytest.fixture
def app(tmp_path):
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()

        source = _build_small_source_dir(tmp_path)
        loader_service.sync_questionnaire_catalog(source_dir=source)
        loader_service.sync_active_models()
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _user_token(app, username: str, user_type: str = "guardian", roles: list[str] | None = None):
    with app.app_context():
        user = AppUser(
            username=username,
            email=f"{username}@example.com",
            password="hashed",
            user_type=user_type,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": roles or []})
        return user.id, token


def test_transport_key_endpoint_public(client):
    resp = client.get("/api/v2/security/transport-key")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["version"] == "transport_envelope_v1"
    assert payload["algorithm"] == "RSA-OAEP-256+AES-256-GCM"
    assert "public_key_jwk" in payload


def test_questionnaire_v2_session_flow(client, app):
    _, token = _user_token(app, "owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    active = client.get("/api/v2/questionnaires/active?mode=short&role=guardian", headers=headers)
    assert active.status_code == 200
    codes = [row["question_code"] for row in active.json["questions"]]
    assert "Q003" not in codes

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10", headers=headers)
    assert page.status_code == 200
    questions = page.json["pages"][0]["questions"]
    answer_payload = []
    for q in questions:
        options = q.get("response_options") or []
        if options and isinstance(options, list):
            if isinstance(options[0], dict):
                value = options[0]["value"]
            else:
                value = options[0]
        else:
            value = 1
        answer_payload.append({"question_id": q["question_id"], "answer": value})

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": answer_payload, "mark_final": True},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json["session"]["progress_pct"] > 0

    submitted = client.post(
        f"/api/v2/questionnaires/sessions/{session_id}/submit",
        json={"force_reprocess": False},
        headers=headers,
    )
    assert submitted.status_code == 200
    assert len(submitted.json["domains"]) == 5

    domain_keys = {item["domain"] for item in submitted.json["domains"]}
    assert domain_keys == {"adhd", "conduct", "elimination", "anxiety", "depression"}


def test_questionnaire_v2_bulk_answers_alias_accepts_question_code(client, app):
    _, token = _user_token(app, "bulk_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10", headers=headers)
    assert page.status_code == 200
    questions = page.json["pages"][0]["questions"][:2]
    assert len(questions) >= 1
    payload = [{"question_code": q["question_code"], "answer": 1} for q in questions]

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers/bulk",
        json={"answers": payload, "mark_final": False},
        headers=headers,
    )
    assert saved.status_code == 200
    expected_count = len(questions)
    assert saved.json["saved_answers"] == expected_count
    assert saved.json["saved_count"] == expected_count
    assert saved.json["answered_count"] >= expected_count
    assert isinstance(saved.json.get("answers"), list)

    session_resp = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=headers)
    assert session_resp.status_code == 200
    answered_codes = {item["question_code"] for item in session_resp.json.get("answers", [])}
    assert {q["question_code"] for q in questions}.issubset(answered_codes)


def test_questionnaire_v2_session_resume_payload_includes_saved_answers(client, app):
    _, token = _user_token(app, "resume_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=50", headers=headers)
    assert page.status_code == 200
    questions = page.json["pages"][0]["questions"][:3]
    answer_payload = []
    for q in questions:
        options = q.get("response_options") or []
        value = options[-1]["value"] if options and isinstance(options[0], dict) else 1
        answer_payload.append({"question_id": q["question_id"], "answer": value})

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": answer_payload, "mark_final": False},
        headers=headers,
    )
    assert saved.status_code == 200

    detail = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.get_json()
    assert payload["status"] in {"draft", "in_progress"}
    assert payload["answered_count"] == len(answer_payload)
    assert payload["total_questions"] >= len(answer_payload)
    assert isinstance(payload["answers"], list)

    answers_by_question = {row["question_id"]: row for row in payload["answers"]}
    for item in answer_payload:
        row = answers_by_question[item["question_id"]]
        assert str(row["answer_value"]) == str(item["answer"])
        assert row["answer"] == item["answer"]
        assert row["updated_at"] is not None


def test_questionnaire_v2_session_page_includes_answer_values_for_resume(client, app):
    _, token = _user_token(app, "resume_page_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 10, "child_sex_assigned_at_birth": "female"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page_before = client.get(
        f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10",
        headers=headers,
    )
    assert page_before.status_code == 200
    first_question = page_before.json["pages"][0]["questions"][0]
    options = first_question.get("response_options") or []
    value = options[-1]["value"] if options and isinstance(options[0], dict) else 1

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": first_question["question_id"], "answer": value}], "mark_final": False},
        headers=headers,
    )
    assert saved.status_code == 200

    page_after = client.get(
        f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10",
        headers=headers,
    )
    assert page_after.status_code == 200
    questions_after = page_after.json["pages"][0]["questions"]
    row = next(q for q in questions_after if q["question_id"] == first_question["question_id"])
    assert row["answered"] is True
    assert row["answer"] == value
    assert str(row["answer_value"]) == str(value)
    assert row["answer_updated_at"] is not None


def test_questionnaire_v2_active_payload_cache_and_invalidation(client, app, monkeypatch):
    _, token = _user_token(app, "cache_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    runtime_service.invalidate_active_questionnaire_cache()
    original = runtime_service.loader.get_active_activation
    call_counter = {"count": 0}

    def wrapped_get_active_activation(*args, **kwargs):
        call_counter["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        runtime_service.loader,
        "get_active_activation",
        wrapped_get_active_activation,
    )

    first = client.get(
        "/api/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5",
        headers=headers,
    )
    assert first.status_code == 200

    second = client.get(
        "/api/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5",
        headers=headers,
    )
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    assert call_counter["count"] == 5

    runtime_service.invalidate_active_questionnaire_cache()
    third = client.get(
        "/api/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5",
        headers=headers,
    )
    assert third.status_code == 200
    assert call_counter["count"] == 10


def test_questionnaire_v2_active_payload_cache_hit_skips_catalog_lookup(client, app, monkeypatch):
    _, token = _user_token(app, "cache_lookup_skip_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    runtime_service.invalidate_active_questionnaire_cache()
    qv2_active_version_cache.clear()

    first = client.get(
        "/api/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5",
        headers=headers,
    )
    assert first.status_code == 200

    def _fail_catalog_lookup():
        raise AssertionError("cache hit should not call ensure_catalog_loaded")

    monkeypatch.setattr(runtime_service.loader, "ensure_catalog_loaded", _fail_catalog_lookup)
    second = client.get(
        "/api/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5",
        headers=headers,
    )
    assert second.status_code == 200
    assert first.get_json() == second.get_json()


def test_questionnaire_v2_feature_contract_cache_hits(app):
    with app.app_context():
        runtime_service._load_feature_contract_cached.cache_clear()
        info_before = runtime_service._load_feature_contract_cached.cache_info()
        version = runtime_service.ModelVersion.query.order_by(runtime_service.ModelVersion.created_at.desc()).first()
        assert version is not None
        runtime_service._load_feature_contract(version)
        runtime_service._load_feature_contract(version)
        info_after = runtime_service._load_feature_contract_cached.cache_info()
        assert info_after.hits >= info_before.hits + 1


def test_questionnaire_v2_share_tags_pdf_and_dashboards(client, app):
    owner_id, owner_token = _user_token(app, "owner2_qv2")
    psychologist_id, psychologist_token = _user_token(app, "psych_qv2", user_type="psychologist")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psychologist_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "medium", "role": "guardian", "child_age_years": 10, "child_sex_assigned_at_birth": "female"},
        headers=owner_headers,
    )
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=50", headers=owner_headers)
    questions = []
    for block in page.json["pages"]:
        questions.extend(block["questions"])

    answers = []
    for q in questions:
        options = q.get("response_options") or []
        val = options[-1]["value"] if options and isinstance(options[0], dict) else 1
        answers.append({"question_id": q["question_id"], "answer": val})

    client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": answers, "mark_final": True},
        headers=owner_headers,
    )
    client.post(f"/api/v2/questionnaires/sessions/{session_id}/submit", json={}, headers=owner_headers)

    tagged = client.post(
        f"/api/v2/questionnaires/history/{session_id}/tags",
        json={"tag": "urgente", "color": "#AA0000", "visibility": "private"},
        headers=owner_headers,
    )
    assert tagged.status_code == 200
    assert tagged.json["tags"][0]["name"] == "urgente"

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"expires_in_hours": 24, "grantee_user_id": str(psychologist_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201

    shared_payload = client.get(
        f"/api/v2/questionnaires/shared/{shared.json['questionnaire_id']}/{shared.json['share_code']}"
    )
    assert shared_payload.status_code == 200

    psych_history = client.get("/api/v2/questionnaires/history", headers=psych_headers)
    assert psych_history.status_code == 200
    assert any(item["session_id"] == session_id for item in psych_history.json["items"])

    generated = client.post(f"/api/v2/questionnaires/history/{session_id}/pdf/generate", headers=owner_headers)
    assert generated.status_code == 201

    pdf_meta = client.get(f"/api/v2/questionnaires/history/{session_id}/pdf", headers=owner_headers)
    assert pdf_meta.status_code == 200
    assert "file_path" not in pdf_meta.json
    assert pdf_meta.json["download_url"].endswith(f"/api/v2/questionnaires/history/{session_id}/pdf/download")

    pdf_download = client.get(f"/api/v2/questionnaires/history/{session_id}/pdf/download", headers=owner_headers)
    assert pdf_download.status_code == 200
    if PdfReader is not None and runtime_service._pdf_reportlab_backend() is not None:
        reader = PdfReader(BytesIO(pdf_download.data))
        pdf_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        assert "Reporte de screening / apoyo profesional" in pdf_text
        assert "Resultados por dominio" in pdf_text
        assert "Preguntas y respuestas respondidas" in pdf_text
        assert "Resumen por secciones" in pdf_text
        assert "Anexo tecnico" in pdf_text

    adoption = client.get("/api/v2/dashboard/adoption-history?months=6", headers=owner_headers)
    assert adoption.status_code == 200
    assert "adoption_history" in adoption.json

    report = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "adoption_history", "months": 6},
        headers=owner_headers,
    )
    assert report.status_code == 201
    assert Path(report.json["file_path"]).exists()


def test_questionnaire_v2_permissions_block_ungranted_user(client, app):
    _, owner_token = _user_token(app, "owner3_qv2")
    _, stranger_token = _user_token(app, "stranger_qv2")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 8, "child_sex_assigned_at_birth": "male"},
        headers=owner_headers,
    )
    session_id = created.json["session"]["session_id"]

    forbidden = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=stranger_headers)
    assert forbidden.status_code == 403


def test_questionnaire_v2_report_job_metadata_and_download(client, app):
    _, owner_token = _user_token(app, "report_owner_qv2")
    _, outsider_token = _user_token(app, "report_outsider_qv2")
    _, admin_token = _user_token(app, "report_admin_qv2", roles=["ADMIN"])

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "adoption_history", "months": 6},
        headers=owner_headers,
    )
    assert created.status_code == 201
    report_job_id = created.json["report_job_id"]
    assert created.json["download_url"].endswith(f"/api/v2/reports/jobs/{report_job_id}/download")

    owner_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=owner_headers)
    assert owner_meta.status_code == 200
    assert owner_meta.json["report_job_id"] == report_job_id
    assert owner_meta.json["download_url"].endswith(f"/api/v2/reports/jobs/{report_job_id}/download")
    assert "file_path" not in owner_meta.json

    owner_download = client.get(f"/api/v2/reports/jobs/{report_job_id}/download", headers=owner_headers)
    assert owner_download.status_code == 200
    assert owner_download.headers.get("Content-Type", "").startswith("application/pdf")

    outsider_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=outsider_headers)
    assert outsider_meta.status_code == 403

    admin_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=admin_headers)
    assert admin_meta.status_code == 200
    assert admin_meta.json["report_job_id"] == report_job_id


def test_questionnaire_v2_tables_created_in_metadata(app):
    with app.app_context():
        tables = set(db.metadata.tables.keys())
        required = {
            "questionnaire_definitions",
            "questionnaire_versions",
            "questionnaire_questions",
            "model_registry",
            "questionnaire_sessions",
            "questionnaire_session_results",
            "questionnaire_share_codes",
            "report_jobs",
        }
        assert required.issubset(tables)

        repeat_count = QuestionnaireQuestion.query.filter_by(question_code="Q003").count()
        assert repeat_count == 1
        session_count = QuestionnaireSession.query.count()
        assert session_count >= 0


def test_questionnaire_v2_internal_error_hides_exception_details(client, app, monkeypatch):
    _, token = _user_token(app, "owner_err_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    from api.routes import questionnaire_v2 as route_module

    def _boom(*args, **kwargs):
        raise RuntimeError("sensitive stack trace detail")

    monkeypatch.setattr(route_module.service, "create_session", _boom)

    resp = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "server_error"
    assert "details" not in body


def test_questionnaire_v2_shared_access_validates_path_params(client, app):
    resp = client.get("/api/v2/questionnaires/shared/x/$$$")
    assert resp.status_code == 400
    assert resp.json["error"] == "validation_error"


def test_questionnaire_v2_pdf_download_rejects_outside_runtime_reports(client, app, monkeypatch):
    _, token = _user_token(app, "owner_pdf_guard_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    from api.routes import questionnaire_v2 as route_module

    class _Export:
        id = uuid.uuid4()
        file_name = "fake.pdf"
        file_path = str((Path.cwd() / "README.md").resolve())

    monkeypatch.setattr(route_module.service, "latest_pdf", lambda _sid: _Export())

    resp = client.get(f"/api/v2/questionnaires/history/{session_id}/pdf/download", headers=headers)
    assert resp.status_code == 404
    assert resp.json["error"] == "pdf_file_missing"
