import os
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import questionnaire_v2_loader_service as loader
from app.models import ModelModeDomainActivation, QuestionnaireQuestion, QuestionnaireVersion, db
from config.settings import TestingConfig


def _mini_source(tmp_path: Path) -> Path:
    source = tmp_path / "cuestionario_v16.4"
    source.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "scale_id": "YES_NO",
                "scale_name": "Si/No",
                "response_type": "single_choice",
                "response_options_json": '[{"value": 0, "label": "No"}, {"value": 1, "label": "Si"}]',
                "min_value": 0,
                "max_value": 1,
                "unit": "",
                "scale_guidance": "",
            }
        ]
    ).to_csv(source / "questionnaire_v16_4_scales_excel_utf8.csv", index=False)

    master = pd.DataFrame(
        [
            {
                "questionnaire_item_id": "Q100",
                "feature": "feature_100",
                "question_text_primary": "Pregunta 100",
                "caregiver_question": "Pregunta 100",
                "psychologist_question": "Pregunta 100",
                "section_name": "General",
                "subsection_name": "Base",
                "questionnaire_section_suggested": "General",
                "questionnaire_subsection_suggested": "Base",
                "layer": "clean_base",
                "domain": "adhd",
                "domains_final": "adhd",
                "module": "core",
                "criterion_ref": "A1",
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
            }
        ]
    )
    master.to_csv(source / "questionnaire_v16_4_master_excel_utf8.csv", index=False)
    master.to_csv(source / "questionnaire_v16_4_visible_questions_excel_utf8.csv", index=False)

    (source / "questionnaire_v16_4_preview.md").write_text("preview", encoding="utf-8")
    (source / "questionnaire_v16_4_audit_summary.md").write_text("audit", encoding="utf-8")
    (source / "cuestionario_v16_4.pdf").write_bytes(b"%PDF-1.4\n%EOF")
    return source


@pytest.fixture
def app(tmp_path):
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_loader_questionnaire_idempotent(app, tmp_path):
    source = _mini_source(tmp_path)
    with app.app_context():
        first = loader.sync_questionnaire_catalog(source_dir=source)
        db.session.commit()

        second = loader.sync_questionnaire_catalog(source_dir=source)
        db.session.commit()

        assert first["questions"] == second["questions"] == 1
        version = QuestionnaireVersion.query.filter_by(version_label="v16.4").first()
        assert version is not None
        assert QuestionnaireQuestion.query.filter_by(version_id=version.id).count() == 1


def test_loader_models_registers_30_active_pairs(app, tmp_path):
    source = _mini_source(tmp_path)
    with app.app_context():
        loader.sync_questionnaire_catalog(source_dir=source)
        stats = loader.sync_active_models()
        db.session.commit()

        assert stats["models_synced"] == 30

        active_pairs = ModelModeDomainActivation.query.filter_by(active_flag=True).count()
        assert active_pairs == 30

        tuples = {
            (row.domain, row.mode_key, row.role)
            for row in ModelModeDomainActivation.query.filter_by(active_flag=True).all()
        }
        assert len(tuples) == 30


def test_migration_file_declares_required_tables():
    migration_path = Path(PROJECT_ROOT) / "migrations" / "versions" / "20260414_01_add_questionnaire_backend_v2.py"
    text = migration_path.read_text(encoding="utf-8")

    assert "questionnaire_definitions" in text
    assert "model_registry" in text
    assert "questionnaire_sessions" in text
    assert "questionnaire_share_codes" in text
    assert "report_jobs" in text
