import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest
from flask_jwt_extended import create_access_token

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import questionnaire_v2_loader_service as loader_service
from app.models import AppUser, db
from config.settings import TestingConfig


FORBIDDEN_CONFIRMED_LANGUAGE = [
    "diagnostico confirmado",
    "se diagnostica",
    "padece",
    "sufre de",
    "presenta oficialmente",
]


def _build_source_dir(tmp_path: Path) -> Path:
    source = tmp_path / "cuestionario_v16.4"
    source.mkdir(parents=True, exist_ok=True)

    scales = pd.DataFrame(
        [
            {
                "scale_id": "FREQ_0_3",
                "scale_name": "Frecuencia 0-3",
                "response_type": "single_choice",
                "response_options_json": '[{"value": 0, "label": "Nunca"}, {"value": 1, "label": "A veces"}, {"value": 2, "label": "Frecuente"}, {"value": 3, "label": "Muy frecuente"}]',
                "min_value": 0,
                "max_value": 3,
                "unit": "",
                "scale_guidance": "Seleccione frecuencia",
            }
        ]
    )
    scales.to_csv(source / "questionnaire_v16_4_scales_excel_utf8.csv", index=False)

    domains = ["adhd", "conduct", "elimination", "anxiety", "depression"]
    rows = []
    for idx, domain in enumerate(domains, start=1):
        rows.append(
            {
                "questionnaire_item_id": f"Q{idx:03d}",
                "feature": f"{domain}_symptom_01",
                "question_text_primary": f"Pregunta {domain}",
                "caregiver_question": f"Pregunta {domain}",
                "psychologist_question": f"Pregunta {domain}",
                "section_name": domain.upper(),
                "subsection_name": "Base",
                "questionnaire_section_suggested": domain.upper(),
                "questionnaire_subsection_suggested": "Base",
                "layer": "dsm5",
                "domain": domain,
                "domains_final": domain,
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
                "caregiver_rank": idx,
                "psychologist_rank": idx,
                "caregiver_priority_bucket": "alta",
                "psychologist_priority_bucket": "alta",
                "derived_from_features": "",
                "internal_scoring_formula_summary": "",
                "help_text": "",
                "notes": "",
                "canonical_question_id": "",
                "reuse_answer_from_question_id": "",
                "question_audit_status": "audited_v16_4",
            }
        )

    master = pd.DataFrame(rows)
    master.to_csv(source / "questionnaire_v16_4_master_excel_utf8.csv", index=False)
    master.to_csv(source / "questionnaire_v16_4_visible_questions_excel_utf8.csv", index=False)

    (source / "questionnaire_v16_4_preview.md").write_text("preview", encoding="utf-8")
    (source / "questionnaire_v16_4_audit_summary.md").write_text("audit", encoding="utf-8")
    (source / "cuestionario_v16_4.pdf").write_bytes(b"%PDF-1.4\n%EOF")
    return source


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIA_ENABLE_FIELD_ENCRYPTION", "true")
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        source = _build_source_dir(tmp_path)
        loader_service.sync_questionnaire_catalog(source_dir=source)
        loader_service.sync_active_models()
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _user_token(app):
    with app.app_context():
        user = AppUser(
            username=f"user_{uuid.uuid4().hex[:8]}",
            email=f"user_{uuid.uuid4().hex[:8]}@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id), additional_claims={"roles": []})
        return token


def _prepare_processed_session(client, app) -> str:
    token = _user_token(app)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v2/questionnaires/sessions",
        json={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json["session"]["session_id"]

    page = client.get(f"/api/v2/questionnaires/sessions/{session_id}/page?page=1&page_size=100", headers=headers)
    assert page.status_code == 200

    answers = []
    for block in page.json["pages"]:
        for q in block["questions"]:
            answers.append({"question_id": q["question_id"], "answer": 3})

    saved = client.patch(
        f"/api/v2/questionnaires/sessions/{session_id}/answers",
        json={"answers": answers, "mark_final": True},
        headers=headers,
    )
    assert saved.status_code == 200

    submitted = client.post(
        f"/api/v2/questionnaires/sessions/{session_id}/submit",
        json={"force_reprocess": False},
        headers=headers,
    )
    assert submitted.status_code == 200

    return session_id, headers


def test_clinical_summary_endpoint_structure(client, app):
    session_id, headers = _prepare_processed_session(client, app)

    resp = client.post(f"/api/v2/questionnaires/history/{session_id}/clinical-summary", json={}, headers=headers)
    assert resp.status_code == 200

    payload = resp.get_json()
    assert payload["report_version"] == "clinical_summary_v1"
    assert payload["overall_risk_level"] in {"baja", "intermedia", "relevante", "alta"}
    assert isinstance(payload["domains"], list) and len(payload["domains"]) == 5

    text = payload["simulated_diagnostic_text"]
    required_sections = [
        "sintesis_general",
        "niveles_de_compatibilidad",
        "indicadores_principales_observados",
        "impacto_funcional",
        "recomendacion_profesional",
        "aclaracion_importante",
    ]
    for section in required_sections:
        assert section in text
        assert isinstance(text[section], str)
        assert text[section].strip()


def test_clinical_summary_disclaimer_always_present(client, app):
    session_id, headers = _prepare_processed_session(client, app)

    resp = client.post(f"/api/v2/questionnaires/history/{session_id}/clinical-summary", json={}, headers=headers)
    assert resp.status_code == 200
    payload = resp.get_json()

    disclaimer = payload.get("disclaimer") or ""
    assert "no constituye un diagnostico clinico" in disclaimer.lower()
    assert "tamizaje" in disclaimer.lower()


def test_clinical_summary_mentions_comorbidity_when_relevant(client, app):
    session_id, headers = _prepare_processed_session(client, app)

    resp = client.post(f"/api/v2/questionnaires/history/{session_id}/clinical-summary", json={}, headers=headers)
    assert resp.status_code == 200
    payload = resp.get_json()

    assert payload["comorbidity"]["has_comorbidity_signal"] is True
    assert len(payload["comorbidity"]["domains"]) >= 2
    assert "comorbilidad" in payload["comorbidity"]["summary"].lower()


def test_clinical_summary_no_confirmed_diagnosis_language(client, app):
    session_id, headers = _prepare_processed_session(client, app)

    resp = client.post(f"/api/v2/questionnaires/history/{session_id}/clinical-summary", json={}, headers=headers)
    assert resp.status_code == 200
    payload = resp.get_json()

    text_blocks = [payload.get("disclaimer", "")]
    text_blocks.extend(payload["simulated_diagnostic_text"].values())
    combined = " ".join(str(x).lower() for x in text_blocks)

    for forbidden in FORBIDDEN_CONFIRMED_LANGUAGE:
        assert forbidden not in combined
