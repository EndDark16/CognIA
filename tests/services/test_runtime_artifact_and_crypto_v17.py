import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import crypto_service, questionnaire_v2_loader_service as loader, questionnaire_v2_service as qv2
from app.models import AppUser, ModelModeDomainActivation, ModelVersion, QuestionnaireQuestion, QuestionnaireSessionAnswer, db
from config.settings import TestingConfig


def _mini_source(tmp_path: Path) -> Path:
    source = tmp_path / "cuestionario_v16.4"
    source.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
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
    ).to_csv(source / "questionnaire_v16_4_scales_excel_utf8.csv", index=False)

    rows = []
    for idx, domain in enumerate(["adhd", "conduct", "elimination", "anxiety", "depression"], start=1):
        rows.append(
            {
                "questionnaire_item_id": f"Q{idx:03d}",
                "feature": f"{domain}_symptom_01",
                "question_text_primary": f"Pregunta {domain}",
                "caregiver_question": f"Pregunta {domain}",
                "psychologist_question": f"Pregunta {domain}",
                "section_name": "General",
                "subsection_name": "Base",
                "questionnaire_section_suggested": "General",
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

    frame = pd.DataFrame(rows)
    frame.to_csv(source / "questionnaire_v16_4_master_excel_utf8.csv", index=False)
    frame.to_csv(source / "questionnaire_v16_4_visible_questions_excel_utf8.csv", index=False)

    (source / "questionnaire_v16_4_preview.md").write_text("preview", encoding="utf-8")
    (source / "questionnaire_v16_4_audit_summary.md").write_text("audit", encoding="utf-8")
    (source / "cuestionario_v16_4.pdf").write_bytes(b"%PDF-1.4\n%EOF")
    return source


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIA_ENABLE_FIELD_ENCRYPTION", "true")
    app = create_app(TestingConfig)
    app.config["COGNIA_ENABLE_FIELD_ENCRYPTION"] = True
    with app.app_context():
        db.create_all()
        source = _mini_source(tmp_path)
        loader.sync_questionnaire_catalog(source_dir=source)
        loader.sync_active_models()
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_runtime_artifact_resolution_30_30(app):
    with app.app_context():
        active = ModelModeDomainActivation.query.filter_by(active_flag=True).all()
        assert len(active) == 30
        model_versions = {
            row.model_version_id: db.session.get(ModelVersion, row.model_version_id)
            for row in active
        }
        assert all(model_versions.values())


def test_no_heuristic_fallback_for_active_champions(monkeypatch):
    class StrictConfig(TestingConfig):
        TESTING = False

    app = create_app(StrictConfig)
    with app.app_context():
        model_version = ModelVersion(
            model_registry_id=uuid.uuid4(),
            model_version_tag="test-v1",
            artifact_path=None,
            fallback_artifact_path=None,
            metadata_json={"feature_columns": ["adhd_symptom_01"]},
        )
        with pytest.raises(qv2.RuntimeArtifactResolutionError):
            qv2._model_probability(model_version, {"adhd_symptom_01": 1}, "adhd")


def test_field_encryption_roundtrip(app):
    with app.app_context():
        value = {"clinical": "sensitive", "score": 3}
        encrypted = crypto_service.encrypt_json(value, "test.value")
        assert crypto_service.is_encrypted(encrypted)
        assert "sensitive" not in str(encrypted)
        decrypted = crypto_service.decrypt_json(encrypted, "test.value")
        assert decrypted == value


def test_sensitive_field_not_stored_plaintext(app):
    with app.app_context():
        owner = AppUser(
            username=f"owner_{uuid.uuid4().hex[:6]}",
            email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
            password="hashed",
            user_type="guardian",
            is_active=True,
        )
        db.session.add(owner)
        db.session.commit()

        session = qv2.create_session(
            owner_user_id=owner.id,
            payload={"mode": "short", "role": "guardian", "child_age_years": 9, "child_sex_assigned_at_birth": "male"},
        )
        question_ids = [
            str(item.id)
            for item in db.session.query(QuestionnaireQuestion)
            .order_by(QuestionnaireQuestion.display_order.asc())
            .all()
        ]
        answers = [{"question_id": qid, "answer": 3} for qid in question_ids]
        qv2.save_answers(session=session, user_id=owner.id, answers=answers, mark_final=True)

        row = QuestionnaireSessionAnswer.query.filter_by(session_id=session.id).first()
        assert row is not None
        assert crypto_service.is_encrypted(row.answer_raw)
        assert crypto_service.is_encrypted(row.answer_normalized)
        assert crypto_service.decrypt_json(row.answer_raw, "questionnaire_session_answer.answer_raw") == 3
