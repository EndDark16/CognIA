# api/services/questionnaire_service.py

from sqlalchemy import desc, case

from app.models import db, QuestionnaireTemplate, Question


def get_active_template():
    return (
        QuestionnaireTemplate.query.filter_by(is_active=True)
        .order_by(
            desc(QuestionnaireTemplate.updated_at).nullslast(),
            desc(QuestionnaireTemplate.created_at).nullslast(),
            desc(QuestionnaireTemplate.id),
        )
        .first()
    )


def get_template_questions(template_id):
    nulls_last = case((Question.position.is_(None), 1), else_=0)
    return (
        Question.query.filter_by(questionnaire_id=template_id)
        .order_by(nulls_last, Question.position.asc(), Question.created_at.asc())
        .all()
    )


def deactivate_all_templates():
    QuestionnaireTemplate.query.update(
        {QuestionnaireTemplate.is_active: False}, synchronize_session=False
    )


def activate_template(template):
    template.is_active = True
    db.session.add(template)


def clone_template(template, *, name, version, description=None):
    cloned = QuestionnaireTemplate(
        name=name,
        version=version,
        description=description,
        is_active=False,
    )
    db.session.add(cloned)
    db.session.flush()

    questions = Question.query.filter_by(questionnaire_id=template.id).all()
    for q in questions:
        db.session.add(
            Question(
                questionnaire_id=cloned.id,
                code=q.code,
                text=q.text,
                response_type=q.response_type,
                disorder_id=q.disorder_id,
                position=q.position,
            )
        )
    return cloned, len(questions)
