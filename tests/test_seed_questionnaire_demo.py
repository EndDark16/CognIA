import os
import sys

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db, Disorder, QuestionnaireTemplate, Question
from config.settings import TestingConfig
from scripts.seed_questionnaire_demo import seed_demo, DEFAULT_NAME, DEFAULT_VERSION


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed_disorders():
    disorders = [
        Disorder(code="CONDUCT", name="Trastorno de conducta", is_active=True),
        Disorder(code="ADHD", name="TDAH", is_active=True),
        Disorder(code="ELIM", name="Trastorno de eliminacion", is_active=True),
        Disorder(code="ANX", name="Trastorno de ansiedad", is_active=True),
        Disorder(code="DEP", name="Trastorno de depresion", is_active=True),
    ]
    db.session.add_all(disorders)
    db.session.commit()


def test_seed_questionnaire_demo_idempotent(app):
    with app.app_context():
        _seed_disorders()

    seed_demo(app, activate=False, name=DEFAULT_NAME, version=DEFAULT_VERSION)
    with app.app_context():
        template = QuestionnaireTemplate.query.filter_by(
            name=DEFAULT_NAME, version=DEFAULT_VERSION
        ).first()
        assert template is not None
        first_question_count = Question.query.filter_by(
            questionnaire_id=template.id
        ).count()
        multi_questions = (
            Question.query.filter_by(questionnaire_id=template.id)
            .join(Question.disorders)
            .filter(Question.code.in_(["BIO_AGE", "GENERAL_01", "GENERAL_02"]))
            .count()
        )

    seed_demo(app, activate=False, name=DEFAULT_NAME, version=DEFAULT_VERSION)
    with app.app_context():
        template_count = QuestionnaireTemplate.query.filter_by(
            name=DEFAULT_NAME, version=DEFAULT_VERSION
        ).count()
        second_question_count = Question.query.filter_by(
            questionnaire_id=template.id
        ).count()

    assert template_count == 1
    assert second_question_count == first_question_count
    assert multi_questions >= 1
