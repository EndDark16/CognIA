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
from app.models import (
    AppUser,
    QuestionnaireQuestion,
    QuestionnaireSession,
    QuestionnaireSessionResultDomain,
    db,
)
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
            "question_text_primary": "Pregunta TDAH 1",
            "caregiver_question": "Pregunta TDAH 1",
            "psychologist_question": "Pregunta TDAH 1",
            "section_name": "Atencion",
            "subsection_name": "TDAH",
            "questionnaire_section_suggested": "Atencion",
            "questionnaire_subsection_suggested": "TDAH",
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
        {
            "questionnaire_item_id": "Q004",
            "feature": "depression_self_harm_ideas",
            "question_text_primary": "Ideas frecuentes sobre muerte, querer desaparecer o hacerse dano",
            "caregiver_question": "Ideas frecuentes sobre muerte, querer desaparecer o hacerse dano",
            "psychologist_question": "Ideas frecuentes sobre muerte, querer desaparecer o hacerse dano",
            "section_name": "Seguridad",
            "subsection_name": "Riesgo",
            "questionnaire_section_suggested": "Seguridad",
            "questionnaire_subsection_suggested": "Riesgo",
            "layer": "dsm5",
            "domain": "depression",
            "domains_final": "depression",
            "module": "safety",
            "criterion_ref": "SAFETY",
            "instrument_or_source": "dsm5",
            "feature_type": "safety_item",
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
            "caregiver_rank": 4,
            "psychologist_rank": 4,
            "caregiver_priority_bucket": "alta",
            "psychologist_priority_bucket": "alta",
            "derived_from_features": "",
            "internal_scoring_formula_summary": "",
            "help_text": "",
            "notes": "safety_critical",
            "canonical_question_id": "",
            "reuse_answer_from_question_id": "",
            "question_audit_status": "audited_v16_4",
        },
        {
            "questionnaire_item_id": "Q005",
            "feature": "elimination_never_established_continence",
            "question_text_primary": "Nunca establecio continencia",
            "caregiver_question": "Nunca establecio continencia",
            "psychologist_question": "Nunca establecio continencia",
            "section_name": "Eliminacion",
            "subsection_name": "Continencia",
            "questionnaire_section_suggested": "Eliminacion",
            "questionnaire_subsection_suggested": "Continencia",
            "layer": "dsm5",
            "domain": "elimination",
            "domains_final": "elimination",
            "module": "continence",
            "criterion_ref": "E1",
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
            "caregiver_rank": 5,
            "psychologist_rank": 5,
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
            "questionnaire_item_id": "Q006",
            "feature": "elimination_after_previous_continence_period",
            "question_text_primary": "El problema aparecio despues de un periodo previo de continencia",
            "caregiver_question": "El problema aparecio despues de un periodo previo de continencia",
            "psychologist_question": "El problema aparecio despues de un periodo previo de continencia",
            "section_name": "Eliminacion",
            "subsection_name": "Continencia",
            "questionnaire_section_suggested": "Eliminacion",
            "questionnaire_subsection_suggested": "Continencia",
            "layer": "dsm5",
            "domain": "elimination",
            "domains_final": "elimination",
            "module": "continence",
            "criterion_ref": "E2",
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
            "caregiver_rank": 6,
            "psychologist_rank": 6,
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
            "questionnaire_item_id": "Q007",
            "feature": "elimination_orina_escape_duracion_meses",
            "question_text_primary": "Duracion en meses de escapes de orina",
            "caregiver_question": "Duracion en meses de escapes de orina",
            "psychologist_question": "Duracion en meses de escapes de orina",
            "section_name": "Eliminacion",
            "subsection_name": "Frecuencia",
            "questionnaire_section_suggested": "Eliminacion",
            "questionnaire_subsection_suggested": "Frecuencia",
            "layer": "dsm5",
            "domain": "elimination",
            "domains_final": "elimination",
            "module": "frequency",
            "criterion_ref": "E3",
            "instrument_or_source": "dsm5",
            "feature_type": "duration",
            "feature_role": "model_input",
            "respondent_expected": "caregiver_or_psychologist",
            "administered_by": "caregiver_or_psychologist",
            "response_type": "number",
            "scale_id": "FREQ_0_3",
            "response_options_json": "[]",
            "min_value": 0,
            "max_value": 12,
            "unit": "meses",
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
            "caregiver_rank": 7,
            "psychologist_rank": 7,
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
            "questionnaire_item_id": "Q008",
            "feature": "elimination_orina_escape_frecuencia_semanal",
            "question_text_primary": "Frecuencia semanal de escapes de orina",
            "caregiver_question": "Frecuencia semanal de escapes de orina",
            "psychologist_question": "Frecuencia semanal de escapes de orina",
            "section_name": "Eliminacion",
            "subsection_name": "Frecuencia",
            "questionnaire_section_suggested": "Eliminacion",
            "questionnaire_subsection_suggested": "Frecuencia",
            "layer": "dsm5",
            "domain": "elimination",
            "domains_final": "elimination",
            "module": "frequency",
            "criterion_ref": "E4",
            "instrument_or_source": "dsm5",
            "feature_type": "frequency",
            "feature_role": "model_input",
            "respondent_expected": "caregiver_or_psychologist",
            "administered_by": "caregiver_or_psychologist",
            "response_type": "number",
            "scale_id": "FREQ_0_3",
            "response_options_json": "[]",
            "min_value": 0,
            "max_value": 7,
            "unit": "veces/semana",
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
            "caregiver_rank": 8,
            "psychologist_rank": 8,
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
    adhd = next(item for item in submitted.json["domains"] if item["domain"] == "adhd")
    assert adhd["domain_label"] == "TDAH"
    assert adhd["score_type"] == "symptom_load_index"
    assert "probabilidad diagnostica" in adhd["score_explanation"]
    assert submitted.json["session"]["completed_by_user_id"]
    assert submitted.json["session"]["applied_at"]


def test_questionnaire_v2_safety_item_sets_urgent_flag(client, app):
    _, token = _user_token(app, "safety_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={
            "mode": "short",
            "role": "guardian",
            "child_age_years": 9,
            "child_sex_assigned_at_birth": "male",
            "completed_by_role": "madre",
            "respondent_relationship": "madre",
            "source_channel": "web",
        },
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]
    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=50", headers=headers)
    questions = {q["question_code"]: q for section in page.json["pages"] for q in section["questions"]}

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": questions["Q004"]["question_id"], "answer": 3}]},
        headers=headers,
    )
    assert saved.status_code == 200
    submitted = client.post(f"/api/v2/questionnaires/sessions/{session_id}/submit", json={}, headers=headers)
    assert submitted.status_code == 200
    assert submitted.json["result"]["urgent_referral_recommended"] is True
    assert submitted.json["result"]["safety_signal_level"] == "urgent"
    assert submitted.json["result"]["safety_flags"][0]["code"] == "self_harm_or_death_item_positive"
    assert submitted.json["data_quality"]["safety_flags"]


def test_questionnaire_v2_blocks_mutually_exclusive_continence_answers(client, app):
    _, token = _user_token(app, "continence_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 8, "child_sex_assigned_at_birth": "female"},
        headers=headers,
    )
    session_id = created.json["session"]["session_id"]
    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=50", headers=headers)
    questions = {q["question_code"]: q for section in page.json["pages"] for q in section["questions"]}

    resp = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={
            "answers": [
                {"question_id": questions["Q005"]["question_id"], "answer": 1},
                {"question_id": questions["Q006"]["question_id"], "answer": 1},
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json["error"] == "clinical_consistency_error"


def test_questionnaire_v2_elimination_duration_frequency_warning(client, app):
    _, token = _user_token(app, "elimination_warning_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 7, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    session_id = created.json["session"]["session_id"]
    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=50", headers=headers)
    questions = {q["question_code"]: q for section in page.json["pages"] for q in section["questions"]}

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={
            "answers": [
                {"question_id": questions["Q007"]["question_id"], "answer": 5},
                {"question_id": questions["Q008"]["question_id"], "answer": 0},
            ]
        },
        headers=headers,
    )
    assert saved.status_code == 200
    submitted = client.post(f"/api/v2/questionnaires/sessions/{session_id}/submit", json={}, headers=headers)
    assert submitted.status_code == 200
    flags = submitted.json["result"]["inconsistency_flags"]
    assert any(item["code"] == "elimination_duration_without_frequency" for item in flags)
    assert submitted.json["result"]["developmental_context_notes"]


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
    assert len(saved.json["answers"]) == expected_count
    saved_codes = {item["question_code"] for item in saved.json["answers"]}
    assert saved_codes == {q["question_code"] for q in questions}
    assert "answers" not in saved.json["session"]

    session_resp = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=headers)
    assert session_resp.status_code == 200
    answered_codes = {item["question_code"] for item in session_resp.json.get("answers", [])}
    assert {q["question_code"] for q in questions}.issubset(answered_codes)


def test_questionnaire_v2_patch_answers_returns_only_saved_rows(client, app):
    _, token = _user_token(app, "save_perf_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "complete", "role": "guardian", "child_age_years": 8, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10", headers=headers)
    assert page.status_code == 200
    questions = [q for section in page.json.get("pages", []) for q in section.get("questions", [])][:2]
    assert len(questions) == 2

    q1 = questions[0]
    q2 = questions[1]

    save_1 = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": q1["question_id"], "answer": 1}]},
        headers=headers,
    )
    assert save_1.status_code == 200
    assert save_1.json["saved_count"] == 1
    assert len(save_1.json["answers"]) == 1
    assert save_1.json["answers"][0]["question_id"] == q1["question_id"]
    assert save_1.json["answered_count"] == 1
    assert "answers" not in save_1.json["session"]

    save_2 = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": q2["question_id"], "answer": 1}]},
        headers=headers,
    )
    assert save_2.status_code == 200
    assert save_2.json["saved_count"] == 1
    assert len(save_2.json["answers"]) == 1
    assert save_2.json["answers"][0]["question_id"] == q2["question_id"]
    assert save_2.json["answered_count"] == 2
    assert "answers" not in save_2.json["session"]

    detail = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=headers)
    assert detail.status_code == 200
    detail_ids = {row["question_id"] for row in detail.json.get("answers", [])}
    assert q1["question_id"] in detail_ids
    assert q2["question_id"] in detail_ids


def test_questionnaire_v2_patch_answers_include_answers_true_returns_full_session_answers(client, app):
    _, token = _user_token(app, "save_include_answers_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 8, "child_sex_assigned_at_birth": "female"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10", headers=headers)
    assert page.status_code == 200
    first_question = page.json["pages"][0]["questions"][0]

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={
            "answers": [{"question_id": first_question["question_id"], "answer": 1}],
            "include_answers": True,
        },
        headers=headers,
    )
    assert saved.status_code == 200
    assert "answers" in saved.json["session"]
    assert len(saved.json["session"]["answers"]) >= 1


def test_questionnaire_v2_bulk_answers_returns_only_saved_rows_from_request(client, app):
    _, token = _user_token(app, "bulk_scope_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "complete", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=10", headers=headers)
    assert page.status_code == 200
    questions = [q for section in page.json.get("pages", []) for q in section.get("questions", [])][:2]
    assert len(questions) == 2

    first = questions[0]
    second = questions[1]
    first_saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": first["question_id"], "answer": 1}]},
        headers=headers,
    )
    assert first_saved.status_code == 200
    assert first_saved.json["saved_count"] == 1

    bulk_saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers/bulk",
        json={"answers": [{"question_id": second["question_id"], "answer": 1}]},
        headers=headers,
    )
    assert bulk_saved.status_code == 200
    assert bulk_saved.json["saved_count"] == 1
    assert len(bulk_saved.json["answers"]) == 1
    assert bulk_saved.json["answers"][0]["question_id"] == second["question_id"]


def test_questionnaire_v2_submit_maps_low_coverage_to_validation_error(client, app, monkeypatch):
    _, token = _user_token(app, "coverage_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    def _raise_low_coverage(*_args, **_kwargs):
        raise runtime_service.RuntimeArtifactResolutionError("feature_coverage_below_minimum:adhd:0.1200:3/25")

    monkeypatch.setattr(runtime_service, "submit_session", _raise_low_coverage)
    submitted = client.post(
        f"/api/v2/questionnaires/sessions/{session_id}/submit",
        json={"force_reprocess": False},
        headers=headers,
    )
    assert submitted.status_code == 400
    assert submitted.json["error"] == "validation_error"
    assert submitted.json["details"]["runtime"].startswith("feature_coverage_below_minimum:")


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
    _, admin_token = _user_token(app, "admin_reports_qv2", roles=["ADMIN"])

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psychologist_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

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
        if q.get("question_code") in {"Q005", "Q008"}:
            val = 0
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
    assert shared.json["grant"]["request_status"] == "pending"
    grant_id = shared.json["grant"]["grant_id"]

    shared_payload = client.get(
        f"/api/v2/questionnaires/shared/{shared.json['questionnaire_id']}/{shared.json['share_code']}"
    )
    assert shared_payload.status_code == 200

    psych_history = client.get("/api/v2/questionnaires/history", headers=psych_headers)
    assert psych_history.status_code == 200
    assert not any(item["session_id"] == session_id for item in psych_history.json["items"])

    inbox = client.get("/api/v2/questionnaires/psychologist/share-requests?status=pending", headers=psych_headers)
    assert inbox.status_code == 200
    assert any(item["grant_id"] == grant_id for item in inbox.json["items"])

    accepted = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
        json={"message": "Acepto revisar"},
        headers=psych_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json["grant"]["request_status"] == "accepted"

    psych_history_after_accept = client.get("/api/v2/questionnaires/history", headers=psych_headers)
    assert psych_history_after_accept.status_code == 200
    assert any(item["session_id"] == session_id for item in psych_history_after_accept.json["items"])

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
        assert "Limitaciones y uso responsable" in pdf_text
        assert "Indice de carga sintomatica" in pdf_text
        assert "Anexo tecnico" in pdf_text

    adoption = client.get("/api/v2/dashboard/adoption-history?months=6", headers=owner_headers)
    assert adoption.status_code == 200
    assert "adoption_history" in adoption.json

    report = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "adoption_history", "months": 6},
        headers=admin_headers,
    )
    assert report.status_code == 201
    assert report.json["download_url"].startswith("/api/v2/reports/jobs/")
    assert "file_path" not in report.json
    assert report.json["summary"]["headline_metrics"]


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
    _, admin2_token = _user_token(app, "report_admin2_qv2", roles=["ADMIN"])

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin2_headers = {"Authorization": f"Bearer {admin2_token}"}

    created = client.post(
        "/api/v2/reports/jobs",
        json={
            "report_type": "executive_summary",
            "months": 6,
            "granularity": "month",
            "format": "pdf",
            "filters": {"status": "processed", "include_sections": ["Crecimiento de usuarios"]},
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    report_job_id = created.json["report_job_id"]
    assert created.json["download_url"].endswith(f"/api/v2/reports/jobs/{report_job_id}/download")
    assert created.json["summary"]["headline_metrics"]

    owner_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=owner_headers)
    assert owner_meta.status_code == 403

    outsider_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=outsider_headers)
    assert outsider_meta.status_code == 403

    admin_meta = client.get(f"/api/v2/reports/jobs/{report_job_id}", headers=admin2_headers)
    assert admin_meta.status_code == 200
    assert admin_meta.json["report_job_id"] == report_job_id
    assert admin_meta.json["summary"]["headline_metrics"]
    assert admin_meta.json["period"]["months"] == 6
    assert "file_path" not in admin_meta.json

    admin_download = client.get(f"/api/v2/reports/jobs/{report_job_id}/download", headers=admin_headers)
    assert admin_download.status_code == 200
    assert admin_download.headers.get("Content-Type", "").startswith("application/pdf")

    non_admin_download = client.get(f"/api/v2/reports/jobs/{report_job_id}/download", headers=owner_headers)
    assert non_admin_download.status_code == 403


def test_questionnaire_v2_report_job_multiple_types_and_invalid_filters(client, app):
    _, admin_token = _user_token(app, "report_admin_types_qv2", roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    for report_type in ["executive_summary", "user_growth", "questionnaire_volume", "funnel", "model_monitoring"]:
        created = client.post(
            "/api/v2/reports/jobs",
            json={"report_type": report_type, "months": 3, "granularity": "week", "filters": {"mode": "complete"}},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json["report_type"] == report_type
        assert created.json["summary"]["sections"]

    bad_period = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "executive_summary", "date_from": "2026-05-10", "date_to": "2026-05-01"},
        headers=headers,
    )
    assert bad_period.status_code == 400

    bad_format = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "executive_summary", "format": "csv"},
        headers=headers,
    )
    assert bad_format.status_code == 400


def test_questionnaire_v2_report_download_rejects_outside_runtime_reports(client, app, monkeypatch):
    _, admin_token = _user_token(app, "report_admin_guard_qv2", roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/v2/reports/jobs",
        json={"report_type": "executive_summary", "months": 1},
        headers=headers,
    )
    assert created.status_code == 201
    report_job_id = created.json["report_job_id"]

    from api.routes import questionnaire_v2 as route_module

    class _Generated:
        file_path = str((Path.cwd() / "README.md").resolve())

    monkeypatch.setattr(route_module.service, "latest_generated_report_for_job", lambda _rid: _Generated())

    resp = client.get(f"/api/v2/reports/jobs/{report_job_id}/download", headers=headers)
    assert resp.status_code == 404
    assert resp.json["error"] == "report_file_missing"


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


def test_questionnaire_v2_cases_create_list_update_and_session_association(client, app):
    _, token = _user_token(app, "case_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created_case = client.post(
        "/api/v2/questionnaires/cases",
        json={"private_label": "Hijo mayor"},
        headers=headers,
    )
    assert created_case.status_code == 201
    case = created_case.json["case"]
    assert case["case_public_id"].startswith("CASO-")
    assert case["private_label"] == "Hijo mayor"

    listed = client.get("/api/v2/questionnaires/cases", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json["items"]) >= 1

    patched = client.patch(
        f"/api/v2/questionnaires/cases/{case['case_id']}",
        json={"private_label": "Hijo del medio", "status": "active"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json["case"]["private_label"] == "Hijo del medio"

    session_created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_id": case["case_id"], "child_age_years": 9},
        headers=headers,
    )
    assert session_created.status_code == 201
    assert session_created.json["session"]["case"]["case_id"] == case["case_id"]


def test_questionnaire_v2_create_session_with_case_label_creates_case(client, app):
    _, token = _user_token(app, "case_label_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={
            "mode": "short",
            "role": "guardian",
            "case_label": "Hijo menor",
            "child_age_years": 8,
            "child_sex_assigned_at_birth": "female",
        },
        headers=headers,
    )
    assert created.status_code == 201
    case_payload = created.json["session"].get("case")
    assert case_payload is not None
    assert case_payload["private_label"] == "Hijo menor"


def test_questionnaire_v2_psychologist_search_filters_active_psychologists(client, app):
    _, requester_token = _user_token(app, "search_requester_qv2")
    headers = {"Authorization": f"Bearer {requester_token}"}

    with app.app_context():
        psych = AppUser.query.filter_by(username="search_psych_qv2").first()
        if psych is None:
            psych = AppUser(
                username="search_psych_qv2",
                email="search_psych_qv2@example.com",
                password="hashed",
                user_type="psychologist",
                is_active=True,
                full_name="Psicologo Uno",
                city="Facatativa",
                department="Cundinamarca",
            )
            db.session.add(psych)
        guardian = AppUser(
            username="search_guardian_qv2",
            email="search_guardian_qv2@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
            full_name="Guardian Uno",
            city="Bogota",
            department="Bogota D.C.",
        )
        db.session.add(guardian)
        db.session.commit()

    resp = client.get("/api/v2/psychologists/search?q=psicologo&department=Cundinamarca&city=Facatativa", headers=headers)
    assert resp.status_code == 200
    usernames = {item["username"] for item in resp.json["items"]}
    assert "search_psych_qv2" in usernames
    assert "search_guardian_qv2" not in usernames
    assert resp.json["items"][0]["department"] == "Cundinamarca"
    assert resp.json["items"][0]["city"] == "Facatativa"
    assert "professional_location" not in resp.json["items"][0]


def test_questionnaire_v2_share_with_psychologist_hides_private_label_for_grantee(client, app):
    _, owner_token = _user_token(app, "case_share_owner_qv2")
    psych_id, psych_token = _user_token(app, "case_share_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={
            "mode": "short",
            "role": "guardian",
            "case_label": "Etiqueta privada guardian",
            "child_age_years": 9,
            "child_sex_assigned_at_birth": "male",
        },
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id), "grant_can_tag": False, "grant_can_download_pdf": True},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    assert shared.json["case"]["case_public_id"].startswith("CASO-")
    assert shared.json["grantee"]["username"] == "case_share_psych_qv2"
    assert "department" in shared.json["grantee"]
    assert "city" in shared.json["grantee"]
    assert "professional_location" not in shared.json["grantee"]
    grant_id = shared.json["grant"]["grant_id"]
    assert shared.json["grant"]["request_status"] == "pending"

    psych_session_before_accept = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=psych_headers)
    assert psych_session_before_accept.status_code == 403

    accepted = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
        json={"message": "Acepto"},
        headers=psych_headers,
    )
    assert accepted.status_code == 200

    psych_session = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=psych_headers)
    assert psych_session.status_code == 200
    case_payload = psych_session.json.get("case") or {}
    assert case_payload.get("case_public_id", "").startswith("CASO-")
    assert "private_label" not in case_payload


def test_questionnaire_v2_locations_catalog(client):
    resp = client.get("/api/v2/locations/colombia")
    assert resp.status_code == 200
    assert resp.json["country"] == "Colombia"
    assert any(item["department"] == "Cundinamarca" for item in resp.json["departments"])

    cities = client.get("/api/v2/locations/colombia/cities?department=Cundinamarca")
    assert cities.status_code == 200
    assert "Facatativa" in cities.json["cities"]

    missing = client.get("/api/v2/locations/colombia/cities?department=Invalido")
    assert missing.status_code == 404
    assert missing.json.get("error") == "location_department_not_found"


def test_questionnaire_v2_psychologist_search_same_location_recommendation(client, app):
    _, requester_token = _user_token(app, "search_same_location_requester_qv2")
    headers = {"Authorization": f"Bearer {requester_token}"}

    with app.app_context():
        requester = AppUser.query.filter_by(username="search_same_location_requester_qv2").first()
        requester.department = "Cundinamarca"
        requester.city = "Facatativa"
        db.session.add(requester)

        psych_same = AppUser(
            username="search_same_loc_psych_qv2",
            email="search_same_loc_psych_qv2@example.com",
            password="hashed",
            user_type="psychologist",
            is_active=True,
            full_name="Psicologo Mismo Lugar",
            city="Facatativa",
            department="Cundinamarca",
        )
        psych_other = AppUser(
            username="search_other_loc_psych_qv2",
            email="search_other_loc_psych_qv2@example.com",
            password="hashed",
            user_type="psychologist",
            is_active=True,
            full_name="Psicologo Otra Ciudad",
            city="Bogota",
            department="Bogota D.C.",
        )
        db.session.add(psych_same)
        db.session.add(psych_other)
        db.session.commit()

    resp = client.get("/api/v2/psychologists/search?same_location=true&page=1&page_size=20", headers=headers)
    assert resp.status_code == 200
    assert resp.json["recommendation"]["basis"] == "same_location"
    assert resp.json["recommendation"]["department"] == "Cundinamarca"
    assert resp.json["recommendation"]["city"] == "Facatativa"
    assert resp.json["items"][0]["same_city"] is True
    assert resp.json["items"][0]["username"] == "search_same_loc_psych_qv2"


def test_questionnaire_v2_psychologist_search_same_location_without_user_location_warns(client, app):
    _, requester_token = _user_token(app, "search_missing_location_requester_qv2")
    headers = {"Authorization": f"Bearer {requester_token}"}
    resp = client.get("/api/v2/psychologists/search?same_location=true&page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    assert "user_location_missing" in resp.json.get("warnings", [])


def test_questionnaire_v2_professional_review_visibility_rules(client, app):
    _, owner_token = _user_token(app, "review_owner_qv2")
    psych_id, psych_token = _user_token(app, "review_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Caso review", "child_age_years": 10},
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    grant_id = shared.json["grant"]["grant_id"]

    accepted = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
        json={"message": "Acepto"},
        headers=psych_headers,
    )
    assert accepted.status_code == 200

    review_created = client.post(
        f"/api/v2/questionnaires/history/{session_id}/professional-reviews",
        json={
            "review_status": "reviewed",
            "initial_concept": "Concepto orientativo inicial",
            "recommendation": "Recomendacion de seguimiento",
            "visible_to_guardian": False,
        },
        headers=psych_headers,
    )
    assert review_created.status_code == 201
    review_id = review_created.json["review"]["review_id"]

    owner_list = client.get(
        f"/api/v2/questionnaires/history/{session_id}/professional-reviews",
        headers=owner_headers,
    )
    assert owner_list.status_code == 200
    assert owner_list.json["items"] == []

    review_updated = client.patch(
        f"/api/v2/questionnaires/history/{session_id}/professional-reviews/{review_id}",
        json={"visible_to_guardian": True},
        headers=psych_headers,
    )
    assert review_updated.status_code == 200

    owner_list_visible = client.get(
        f"/api/v2/questionnaires/history/{session_id}/professional-reviews",
        headers=owner_headers,
    )
    assert owner_list_visible.status_code == 200
    assert len(owner_list_visible.json["items"]) == 1
    assert owner_list_visible.json["items"][0]["is_diagnostic"] is False


def test_questionnaire_v2_report_preview_for_granted_psychologist_hides_private_label(client, app):
    _, owner_token = _user_token(app, "preview_owner_qv2")
    psych_id, psych_token = _user_token(app, "preview_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Etiqueta privada preview", "child_age_years": 9},
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]
    question_id = client.get(
        f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=1",
        headers=owner_headers,
    ).json["pages"][0]["questions"][0]["question_id"]
    client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": question_id, "answer": 1}]},
        headers=owner_headers,
    )

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    grant_id = shared.json["grant"]["grant_id"]

    preview_pending = client.get(f"/api/v2/questionnaires/history/{session_id}/report-preview", headers=psych_headers)
    assert preview_pending.status_code == 403

    accepted = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
        json={"message": "Acepto revisar"},
        headers=psych_headers,
    )
    assert accepted.status_code == 200

    preview = client.get(f"/api/v2/questionnaires/history/{session_id}/report-preview", headers=psych_headers)
    assert preview.status_code == 200
    case_payload = preview.json["session"].get("case") or {}
    assert case_payload.get("case_public_id", "").startswith("CASO-")
    assert "private_label" not in case_payload


def test_questionnaire_v2_guardian_and_psychologist_dashboards(client, app):
    _, owner_token = _user_token(app, "dash_owner_qv2")
    psych_id, psych_token = _user_token(app, "dash_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "complete", "role": "guardian", "case_label": "Caso dashboard", "child_age_years": 9},
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]
    case_public_id = created.json["session"]["case"]["case_public_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    grant_id = shared.json["grant"]["grant_id"]

    psych_dashboard_pending = client.get(
        f"/api/v2/questionnaires/psychologist/dashboard?case_public_id={case_public_id}",
        headers=psych_headers,
    )
    assert psych_dashboard_pending.status_code == 200
    assert psych_dashboard_pending.json["summary"]["total_shared_sessions"] == 0

    accepted = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
        json={"message": "Acepto"},
        headers=psych_headers,
    )
    assert accepted.status_code == 200

    guardian_dashboard = client.get("/api/v2/questionnaires/guardian/dashboard?months=3", headers=owner_headers)
    assert guardian_dashboard.status_code == 200
    assert guardian_dashboard.json["summary"]["total_cases"] >= 1

    psych_dashboard = client.get(
        f"/api/v2/questionnaires/psychologist/dashboard?case_public_id={case_public_id}",
        headers=psych_headers,
    )
    assert psych_dashboard.status_code == 200
    assert psych_dashboard.json["summary"]["total_shared_sessions"] >= 1


def test_questionnaire_v2_case_label_reuse_same_owner(client, app):
    _, token = _user_token(app, "case_reuse_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Hijo mayor", "child_age_years": 8},
        headers=headers,
    )
    assert first.status_code == 201
    first_case = first.json["session"]["case"]["case_id"]

    second = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "  hijo   mayor  ", "child_age_years": 9},
        headers=headers,
    )
    assert second.status_code == 201
    second_case = second.json["session"]["case"]["case_id"]
    assert second_case == first_case


def test_questionnaire_v2_share_request_reject_notifies_owner_and_blocks_access(client, app):
    _, owner_token = _user_token(app, "share_reject_owner_qv2")
    psych_id, psych_token = _user_token(app, "share_reject_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Caso rechazo", "child_age_years": 9},
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    grant_id = shared.json["grant"]["grant_id"]

    rejected = client.post(
        f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/reject",
        json={"message": "No puedo revisar este caso por ahora."},
        headers=psych_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json["grant"]["request_status"] == "rejected"

    psych_session = client.get(f"/api/v2/questionnaires/sessions/{session_id}", headers=psych_headers)
    assert psych_session.status_code == 403

    owner_notifications = client.get("/api/v2/notifications?unread_only=true", headers=owner_headers)
    assert owner_notifications.status_code == 200
    assert any(item["type"] == "questionnaire_share_rejected" for item in owner_notifications.json["items"])

    rejected_inbox = client.get(
        "/api/v2/questionnaires/psychologist/share-requests?status=rejected",
        headers=psych_headers,
    )
    assert rejected_inbox.status_code == 200
    assert any(item["grant_id"] == grant_id for item in rejected_inbox.json["items"])


def test_questionnaire_v2_share_requests_and_notifications_endpoints(client, app):
    _, guardian_token = _user_token(app, "share_requests_guardian_qv2")
    psych_id, psych_token = _user_token(app, "share_requests_psych_qv2", user_type="psychologist")
    guardian_headers = {"Authorization": f"Bearer {guardian_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Caso inbox", "child_age_years": 9},
        headers=guardian_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id), "grant_can_download_pdf": True, "grant_can_tag": False},
        headers=guardian_headers,
    )
    assert shared.status_code == 201
    grant_id = shared.json["grant"]["grant_id"]

    guardian_forbidden = client.get("/api/v2/questionnaires/psychologist/share-requests", headers=guardian_headers)
    assert guardian_forbidden.status_code == 403

    psych_inbox = client.get("/api/v2/questionnaires/psychologist/share-requests?status=pending", headers=psych_headers)
    assert psych_inbox.status_code == 200
    grant_item = next(item for item in psych_inbox.json["items"] if item["grant_id"] == grant_id)
    assert grant_item["request_status"] == "pending"
    assert grant_item["case"]["case_public_id"].startswith("CASO-")
    assert "private_label" not in grant_item["case"]

    psych_notifications = client.get("/api/v2/notifications?unread_only=true", headers=psych_headers)
    assert psych_notifications.status_code == 200
    assert any(item["type"] == "questionnaire_share_requested" for item in psych_notifications.json["items"])
    first_notification_id = psych_notifications.json["items"][0]["notification_id"]

    mark_read = client.patch(f"/api/v2/notifications/{first_notification_id}/read", headers=psych_headers)
    assert mark_read.status_code == 200
    assert mark_read.json["notification"]["read_at"] is not None


def test_questionnaire_v2_share_legacy_without_grantee_keeps_compatibility(client, app):
    _, owner_token = _user_token(app, "share_legacy_owner_qv2")
    headers = {"Authorization": f"Bearer {owner_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"expires_in_hours": 24, "max_uses": 5},
        headers=headers,
    )
    assert shared.status_code == 201
    assert shared.json["share_code"]
    assert "grant" not in shared.json


def test_questionnaire_v2_pending_grant_blocks_pdf_and_professional_review(client, app):
    _, owner_token = _user_token(app, "pending_block_owner_qv2")
    psych_id, psych_token = _user_token(app, "pending_block_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Caso pending block", "child_age_years": 9},
        headers=owner_headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=1", headers=owner_headers)
    assert page.status_code == 200
    question_id = page.json["pages"][0]["questions"][0]["question_id"]
    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": question_id, "answer": 1}]},
        headers=owner_headers,
    )
    assert saved.status_code == 200

    submitted = client.post(
        f"/api/v2/questionnaires/sessions/{session_id}/submit",
        json={},
        headers=owner_headers,
    )
    assert submitted.status_code == 200

    shared = client.post(
        f"/api/v2/questionnaires/history/{session_id}/share",
        json={"grantee_user_id": str(psych_id)},
        headers=owner_headers,
    )
    assert shared.status_code == 201
    assert shared.json["grant"]["request_status"] == "pending"

    preview = client.get(f"/api/v2/questionnaires/history/{session_id}/report-preview", headers=psych_headers)
    assert preview.status_code == 403

    pdf_meta = client.get(f"/api/v2/questionnaires/history/{session_id}/pdf", headers=psych_headers)
    assert pdf_meta.status_code == 403

    review_try = client.post(
        f"/api/v2/questionnaires/history/{session_id}/professional-reviews",
        json={
            "review_status": "reviewed",
            "initial_concept": "No debe permitir en pending",
            "recommendation": "N/A",
            "visible_to_guardian": True,
        },
        headers=psych_headers,
    )
    assert review_try.status_code == 403


def test_questionnaire_v2_case_label_reuse_with_accents_and_separators(client, app):
    _, token = _user_token(app, "case_reuse_accent_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Híjo-1", "child_age_years": 8},
        headers=headers,
    )
    assert first.status_code == 201
    first_case = first.json["session"]["case"]["case_id"]

    second = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "hijo 1", "child_age_years": 9},
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json["session"]["case"]["case_id"] == first_case


def test_questionnaire_v2_cases_filters_and_metrics(client, app):
    _, token = _user_token(app, "cases_filters_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    c1 = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Hijo 1", "child_age_years": 8},
        headers=headers,
    )
    assert c1.status_code == 201
    case_public_id = c1.json["session"]["case"]["case_public_id"]

    c2 = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Seguimiento escolar", "child_age_years": 10},
        headers=headers,
    )
    assert c2.status_code == 201

    all_cases = client.get("/api/v2/questionnaires/cases?page=1&page_size=20", headers=headers)
    assert all_cases.status_code == 200
    assert all_cases.json["pagination"]["total"] >= 2
    first_item = all_cases.json["items"][0]
    assert "processed_sessions_count" in first_item
    assert "draft_sessions_count" in first_item
    assert "in_progress_sessions_count" in first_item

    by_public = client.get(f"/api/v2/questionnaires/cases?case_public_id={case_public_id}", headers=headers)
    assert by_public.status_code == 200
    assert by_public.json["pagination"]["total"] == 1

    by_label = client.get("/api/v2/questionnaires/cases?label=hijo 1", headers=headers)
    assert by_label.status_code == 200
    assert by_label.json["pagination"]["total"] == 1

    by_q = client.get("/api/v2/questionnaires/cases?q=seguimiento", headers=headers)
    assert by_q.status_code == 200
    assert by_q.json["pagination"]["total"] >= 1


def test_questionnaire_v2_history_filters_by_case_label_tag_domain_and_alert(client, app):
    _, token = _user_token(app, "history_filters_owner_qv2")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "case_label": "Hijo 2", "child_age_years": 9},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]
    case_public_id = created.json["session"]["case"]["case_public_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=5", headers=headers)
    question_id = page.json["pages"][0]["questions"][0]["question_id"]
    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": [{"question_id": question_id, "answer": 1}]},
        headers=headers,
    )
    assert saved.status_code == 200
    submitted = client.post(f"/api/v2/questionnaires/sessions/{session_id}/submit", json={}, headers=headers)
    assert submitted.status_code == 200

    tagged = client.post(
        f"/api/v2/questionnaires/history/{session_id}/tags",
        json={"tag": "seguimiento escolar", "color": "#114499", "visibility": "private"},
        headers=headers,
    )
    assert tagged.status_code == 200

    base = client.get("/api/v2/questionnaires/history?page=1&page_size=20", headers=headers)
    assert base.status_code == 200
    assert any(item["session_id"] == session_id for item in base.json["items"])

    by_case_label = client.get("/api/v2/questionnaires/history?case_label=hijo 2", headers=headers)
    assert by_case_label.status_code == 200
    assert any(item["session_id"] == session_id for item in by_case_label.json["items"])

    by_case_public = client.get(f"/api/v2/questionnaires/history?case_public_id={case_public_id}", headers=headers)
    assert by_case_public.status_code == 200
    assert any(item["session_id"] == session_id for item in by_case_public.json["items"])

    by_tag = client.get("/api/v2/questionnaires/history?tag=seguimiento escolar", headers=headers)
    assert by_tag.status_code == 200
    assert any(item["session_id"] == session_id for item in by_tag.json["items"])

    by_domain = client.get("/api/v2/questionnaires/history?domain=anxiety", headers=headers)
    assert by_domain.status_code == 200
    assert any(item["session_id"] == session_id for item in by_domain.json["items"])

    by_alert = client.get("/api/v2/questionnaires/history?alert_level=low", headers=headers)
    assert by_alert.status_code == 200
    assert any(item["session_id"] == session_id for item in by_alert.json["items"])


def test_questionnaire_v2_psychologist_dashboard_aggregates_use_full_filtered_set(client, app):
    _, owner_token = _user_token(app, "psych_agg_owner_qv2")
    psych_id, psych_token = _user_token(app, "psych_agg_psych_qv2", user_type="psychologist")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    psych_headers = {"Authorization": f"Bearer {psych_token}"}

    created_ids = []
    for idx in range(2):
        created = client.post(
            "/api/v2/questionnaires/sessions",
            json={"mode": "short", "role": "guardian", "case_label": f"Caso agg {idx}", "child_age_years": 9},
            headers=owner_headers,
        )
        assert created.status_code == 201
        session_id = created.json["session"]["session_id"]
        created_ids.append(session_id)
        page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=1", headers=owner_headers)
        qid = page.json["pages"][0]["questions"][0]["question_id"]
        assert client.patch(
            f"/api/v2/questionnaires/sessions/{session_id}/answers",
            json={"answers": [{"question_id": qid, "answer": 1}]},
            headers=owner_headers,
        ).status_code == 200
        assert client.post(
            f"/api/v2/questionnaires/sessions/{session_id}/submit",
            json={},
            headers=owner_headers,
        ).status_code == 200
        shared = client.post(
            f"/api/v2/questionnaires/history/{session_id}/share",
            json={"grantee_user_id": str(psych_id)},
            headers=owner_headers,
        )
        assert shared.status_code == 201
        grant_id = shared.json["grant"]["grant_id"]
        assert client.post(
            f"/api/v2/questionnaires/psychologist/share-requests/{grant_id}/accept",
            json={},
            headers=psych_headers,
        ).status_code == 200

    with app.app_context():
        target = QuestionnaireSession.query.filter_by(id=uuid.UUID(created_ids[0])).first()
        assert target is not None
        rows = QuestionnaireSessionResultDomain.query.filter_by(session_id=target.id).all()
        assert rows
        for row in rows:
            if row.domain == "anxiety":
                row.alert_level = "high"
            else:
                row.alert_level = "low"
        db.session.commit()

    dashboard = client.get(
        "/api/v2/questionnaires/psychologist/dashboard?domain=anxiety&page=1&page_size=1",
        headers=psych_headers,
    )
    assert dashboard.status_code == 200
    assert dashboard.json["pagination"]["total"] == 2
    assert len(dashboard.json["items"]) == 1
    assert dashboard.json["summary"]["total_shared_sessions"] == 2
    assert any(item["domain"] == "anxiety" for item in dashboard.json["aggregates"]["by_domain"])
