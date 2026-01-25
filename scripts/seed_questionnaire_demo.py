"""
Seed a demo questionnaire template and questions.

Usage (desde la raiz del repo):
  APP_CONFIG_CLASS=config.settings.DevelopmentConfig python scripts/seed_questionnaire_demo.py

Opcional:
  SEED_TEMPLATE_ACTIVE=true para activar el template (desactiva los demas).
  SEED_TEMPLATE_NAME y SEED_TEMPLATE_VERSION para personalizar.
"""

import importlib
import os
import sys
import unicodedata
import uuid

from sqlalchemy import text

# Asegura que el proyecto este en el path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from app.models import db, QuestionnaireTemplate, Question


DEFAULT_NAME = "Cuestionario Demo Salud Mental Infantil"
DEFAULT_VERSION = "v1"
DEFAULT_DESCRIPTION = (
    "Instrumento demostrativo con secciones para conducta, TDAH, eliminacion, "
    "ansiedad y depresion."
)

DISORDER_KEYWORDS = {
    "conduct": ["conducta", "conduct", "behavior", "oposicion", "disruptive"],
    "adhd": ["adhd", "tdah", "attention", "hiperactividad", "hyperactivity"],
    "elimination": ["eliminacion", "enuresis", "encopresis"],
    "anxiety": ["ansiedad", "anxiety"],
    "depression": ["depresion", "depression"],
}
PREFIX_TO_DISORDER_KEY = {
    "CONDUCT_": "conduct",
    "ADHD_": "adhd",
    "ELIM_": "elimination",
    "ANX_": "anxiety",
    "DEP_": "depression",
}


def get_config_class():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _normalize(text_value: str) -> str:
    if text_value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text_value))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _load_disorders():
    try:
        rows = db.session.execute(
            text("SELECT id, code, name FROM disorder WHERE is_active = true")
        ).fetchall()
    except Exception:
        return []
    entries = []
    for row in rows:
        try:
            disorder_id = uuid.UUID(str(row[0]))
        except (TypeError, ValueError):
            disorder_id = None
        entries.append((disorder_id, _normalize(row[1]), _normalize(row[2])))
    return entries


def _resolve_disorder_id(entries, keys):
    if not entries:
        return None
    for key in keys:
        for disorder_id, code_norm, name_norm in entries:
            if disorder_id is None:
                continue
            if key in code_norm or key in name_norm:
                return disorder_id
    return None


def _build_questions(disorder_entries):
    questions = [
        {
            "code": "CONDUCT_01",
            "text": "En las ultimas 4 semanas, el nino ha tenido rabietas intensas.",
            "response_type": "likert",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_02",
            "text": "Ha habido agresion fisica hacia otros?",
            "response_type": "boolean",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_03",
            "text": "Se niega a seguir reglas en casa o escuela.",
            "response_type": "likert",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_04",
            "text": "Numero de incidentes disciplinarios en el ultimo mes.",
            "response_type": "integer",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_05",
            "text": "Describe un ejemplo reciente de conducta desafiante.",
            "response_type": "text",
            "disorder_key": "conduct",
        },
        {
            "code": "ADHD_01",
            "text": "Dificultad para mantener la atencion en tareas.",
            "response_type": "likert",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_02",
            "text": "Se mueve en exceso o le cuesta estar sentado.",
            "response_type": "likert",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_03",
            "text": "Interrumpe conversaciones o responde impulsivamente.",
            "response_type": "likert",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_04",
            "text": "Horas promedio de concentracion en tareas escolares por dia.",
            "response_type": "integer",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_05",
            "text": "El docente ha reportado dificultades de atencion?",
            "response_type": "boolean",
            "disorder_key": "adhd",
        },
        {
            "code": "ELIM_01",
            "text": "Ha presentado enuresis nocturna?",
            "response_type": "boolean",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_02",
            "text": "Ha presentado encopresis?",
            "response_type": "boolean",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_03",
            "text": "Frecuencia de accidentes en las ultimas 4 semanas.",
            "response_type": "integer",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_04",
            "text": "Evita usar el bano fuera de casa.",
            "response_type": "likert",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_05",
            "text": "Observaciones relevantes sobre eliminacion.",
            "response_type": "text",
            "disorder_key": "elimination",
        },
        {
            "code": "ANX_01",
            "text": "Se muestra excesivamente preocupado o nervioso.",
            "response_type": "likert",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_02",
            "text": "Evita situaciones sociales o escolares.",
            "response_type": "likert",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_03",
            "text": "Presenta sintomas fisicos ante estres (dolor de estomago, etc.).",
            "response_type": "likert",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_04",
            "text": "Dificultad para dormir por preocupaciones.",
            "response_type": "likert",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_05",
            "text": "Describe el principal miedo o preocupacion.",
            "response_type": "text",
            "disorder_key": "anxiety",
        },
        {
            "code": "DEP_01",
            "text": "Ha perdido interes en actividades que antes disfrutaba.",
            "response_type": "likert",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_02",
            "text": "Se muestra triste la mayor parte del tiempo.",
            "response_type": "likert",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_03",
            "text": "Ha habido cambios significativos de apetito.",
            "response_type": "boolean",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_04",
            "text": "Cambios en energia o fatiga frecuente.",
            "response_type": "likert",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_05",
            "text": "Pensamientos negativos frecuentes.",
            "response_type": "likert",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_06",
            "text": "Observaciones adicionales sobre estado de animo.",
            "response_type": "text",
            "disorder_key": "depression",
        },
    ]

    for idx, question in enumerate(questions, start=1):
        disorder_id = _resolve_disorder_id(
            disorder_entries, DISORDER_KEYWORDS.get(question["disorder_key"], [])
        )
        question["disorder_id"] = disorder_id
        question["position"] = idx
    return questions


def seed_demo(app, *, activate=False, name=DEFAULT_NAME, version=DEFAULT_VERSION):
    description = os.getenv("SEED_TEMPLATE_DESCRIPTION", DEFAULT_DESCRIPTION)
    with app.app_context():
        template = QuestionnaireTemplate.query.filter_by(name=name, version=version).first()
        created_template = False
        if not template:
            template = QuestionnaireTemplate(
                name=name,
                version=version,
                description=description,
                is_active=False,
            )
            db.session.add(template)
            db.session.flush()
            created_template = True
        elif template.description != description and description:
            template.description = description

        disorder_entries = _load_disorders()
        if not disorder_entries:
            print("No disorders found or disorder table missing. disorder_id will be NULL.")

        questions = _build_questions(disorder_entries)
        existing_codes = {
            q.code
            for q in Question.query.filter_by(questionnaire_id=template.id).all()
        }

        created_questions = 0
        for item in questions:
            if item["code"] in existing_codes:
                continue
            db.session.add(
                Question(
                    questionnaire_id=template.id,
                    code=item["code"],
                    text=item["text"],
                    response_type=item["response_type"],
                    disorder_id=item["disorder_id"],
                    position=item["position"],
                )
            )
            created_questions += 1

        # Update disorder_id for existing questions when disorders are now available.
        updated_questions = 0
        if disorder_entries:
            existing_questions = Question.query.filter_by(
                questionnaire_id=template.id
            ).all()
            for question in existing_questions:
                if question.disorder_id is not None:
                    continue
                matched_key = None
                for prefix, disorder_key in PREFIX_TO_DISORDER_KEY.items():
                    if question.code.startswith(prefix):
                        matched_key = disorder_key
                        break
                if not matched_key:
                    continue
                disorder_id = _resolve_disorder_id(
                    disorder_entries, DISORDER_KEYWORDS.get(matched_key, [])
                )
                if disorder_id is None:
                    continue
                question.disorder_id = disorder_id
                updated_questions += 1

        if activate:
            QuestionnaireTemplate.query.update(
                {QuestionnaireTemplate.is_active: False}, synchronize_session=False
            )
            template.is_active = True

        db.session.commit()
        print(
            f"Template {'creado' if created_template else 'existente'}: {template.name} {template.version}"
        )
        print(f"Preguntas creadas: {created_questions}")
        if updated_questions:
            print(f"Preguntas actualizadas con disorder_id: {updated_questions}")


def main():
    activate = os.getenv("SEED_TEMPLATE_ACTIVE", "false").lower() == "true"
    name = os.getenv("SEED_TEMPLATE_NAME", DEFAULT_NAME)
    version = os.getenv("SEED_TEMPLATE_VERSION", DEFAULT_VERSION)
    app = create_app(get_config_class())
    seed_demo(app, activate=activate, name=name, version=version)


if __name__ == "__main__":
    main()
