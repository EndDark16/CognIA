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
from app.models import db, QuestionnaireTemplate, Question, Disorder


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
MULTI_DISORDER_KEYS = ["conduct", "adhd", "elimination", "anxiety", "depression"]
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
            "code": "BIO_AGE",
            "text": "Edad del nino (en anos).",
            "response_type": "count",
            "response_min": 6,
            "response_max": 11,
            "response_step": 1,
            "disorder_key": "multi",
        },
        {
            "code": "GENERAL_01",
            "text": "En general, el estado emocional del nino afecta su rendimiento escolar.",
            "response_type": "likert_0_4",
            "disorder_key": "multi",
        },
        {
            "code": "GENERAL_02",
            "text": "Nivel de preocupacion general del tutor (0=bajo, 1=medio, 2=alto).",
            "response_type": "ordinal",
            "response_options": [0, 1, 2],
            "disorder_key": "multi",
        },
        {
            "code": "CONDUCT_01",
            "text": "En las ultimas 4 semanas, el nino ha tenido rabietas intensas.",
            "response_type": "likert_0_4",
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
            "response_type": "likert_0_4",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_04",
            "text": "Numero de incidentes disciplinarios en el ultimo mes.",
            "response_type": "count",
            "disorder_key": "conduct",
        },
        {
            "code": "CONDUCT_05",
            "text": "Observaciones del tutor sobre conducta (no se usa en el modelo).",
            "response_type": "text_context",
            "disorder_key": "conduct",
        },
        {
            "code": "ADHD_01",
            "text": "Dificultad para mantener la atencion en tareas.",
            "response_type": "likert_0_4",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_02",
            "text": "Se mueve en exceso o le cuesta estar sentado.",
            "response_type": "likert_0_4",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_03",
            "text": "Interrumpe conversaciones o responde impulsivamente.",
            "response_type": "likert_0_4",
            "disorder_key": "adhd",
        },
        {
            "code": "ADHD_04",
            "text": "Horas promedio de concentracion en tareas escolares por dia.",
            "response_type": "count",
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
            "response_type": "frequency_0_3",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_04",
            "text": "Evita usar el bano fuera de casa.",
            "response_type": "likert_0_4",
            "disorder_key": "elimination",
        },
        {
            "code": "ELIM_05",
            "text": "Observaciones del tutor sobre eliminacion (no se usa en el modelo).",
            "response_type": "text_context",
            "disorder_key": "elimination",
        },
        {
            "code": "ANX_01",
            "text": "Se muestra excesivamente preocupado o nervioso.",
            "response_type": "likert_0_4",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_02",
            "text": "Evita situaciones sociales o escolares.",
            "response_type": "frequency_0_3",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_03",
            "text": "Presenta sintomas fisicos ante estres (dolor de estomago, etc.).",
            "response_type": "intensity_0_10",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_04",
            "text": "Dificultad para dormir por preocupaciones.",
            "response_type": "likert_0_4",
            "disorder_key": "anxiety",
        },
        {
            "code": "ANX_05",
            "text": "Observaciones del tutor sobre ansiedad (no se usa en el modelo).",
            "response_type": "text_context",
            "disorder_key": "anxiety",
        },
        {
            "code": "DEP_01",
            "text": "Ha perdido interes en actividades que antes disfrutaba.",
            "response_type": "likert_0_4",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_02",
            "text": "Se muestra triste la mayor parte del tiempo.",
            "response_type": "likert_0_4",
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
            "response_type": "intensity_0_10",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_05",
            "text": "Pensamientos negativos frecuentes.",
            "response_type": "frequency_0_3",
            "disorder_key": "depression",
        },
        {
            "code": "DEP_06",
            "text": "Observaciones del tutor sobre estado de animo (no se usa en el modelo).",
            "response_type": "text_context",
            "disorder_key": "depression",
        },
    ]

    def _constraints_for_type(response_type):
        if response_type == "likert_0_4":
            return {"response_min": 0, "response_max": 4}
        if response_type == "likert_1_5":
            return {"response_min": 1, "response_max": 5}
        if response_type == "frequency_0_3":
            return {"response_min": 0, "response_max": 3}
        if response_type == "intensity_0_10":
            return {"response_min": 0, "response_max": 10}
        if response_type == "boolean":
            return {"response_options": [0, 1]}
        if response_type == "count":
            return {"response_min": 0}
        return {}

    for idx, question in enumerate(questions, start=1):
        disorder_ids = []
        if question["disorder_key"] == "multi":
            for key in MULTI_DISORDER_KEYS:
                disorder_id = _resolve_disorder_id(
                    disorder_entries, DISORDER_KEYWORDS.get(key, [])
                )
                if disorder_id:
                    disorder_ids.append(disorder_id)
        else:
            disorder_id = _resolve_disorder_id(
                disorder_entries, DISORDER_KEYWORDS.get(question["disorder_key"], [])
            )
            if disorder_id:
                disorder_ids.append(disorder_id)
        question["disorder_id"] = disorder_ids[0] if disorder_ids else None
        question["disorder_ids"] = disorder_ids
        question["position"] = idx
        defaults = _constraints_for_type(question["response_type"])
        for key, value in defaults.items():
            question.setdefault(key, value)
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
            question = Question(
                questionnaire_id=template.id,
                code=item["code"],
                text=item["text"],
                response_type=item["response_type"],
                disorder_id=item["disorder_id"],
                position=item["position"],
                response_min=item.get("response_min"),
                response_max=item.get("response_max"),
                response_step=item.get("response_step"),
                response_options=item.get("response_options"),
            )
            disorder_ids = item.get("disorder_ids") or []
            if disorder_ids:
                disorders = Disorder.query.filter(Disorder.id.in_(disorder_ids)).all()
                question.disorders = disorders
            db.session.add(question)
            created_questions += 1

        # Update disorder_id for existing questions when disorders are now available.
        updated_questions = 0
        if disorder_entries:
            existing_questions = Question.query.filter_by(
                questionnaire_id=template.id
            ).all()
            for question in existing_questions:
                if question.disorders:
                    continue
                matched_keys = []
                if question.code.startswith("GENERAL_") or question.code.startswith("BIO_"):
                    matched_keys = MULTI_DISORDER_KEYS
                else:
                    for prefix, disorder_key in PREFIX_TO_DISORDER_KEY.items():
                        if question.code.startswith(prefix):
                            matched_keys = [disorder_key]
                            break
                if not matched_keys:
                    continue
                resolved_ids = []
                for key in matched_keys:
                    disorder_id = _resolve_disorder_id(
                        disorder_entries, DISORDER_KEYWORDS.get(key, [])
                    )
                    if disorder_id:
                        resolved_ids.append(disorder_id)
                if not resolved_ids:
                    continue
                disorders = Disorder.query.filter(Disorder.id.in_(resolved_ids)).all()
                question.disorders = disorders
                if question.disorder_id is None:
                    question.disorder_id = resolved_ids[0]
                updated_questions += 1

        # Fill missing response constraints for existing questions when absent.
        constraint_updates = 0
        existing_questions = Question.query.filter_by(questionnaire_id=template.id).all()
        for question in existing_questions:
            if any(
                value is not None
                for value in (
                    question.response_min,
                    question.response_max,
                    question.response_step,
                    question.response_options,
                )
            ):
                continue
            defaults = {}
            if question.response_type == "likert_0_4":
                defaults = {"response_min": 0, "response_max": 4}
            elif question.response_type == "likert_1_5":
                defaults = {"response_min": 1, "response_max": 5}
            elif question.response_type == "frequency_0_3":
                defaults = {"response_min": 0, "response_max": 3}
            elif question.response_type == "intensity_0_10":
                defaults = {"response_min": 0, "response_max": 10}
            elif question.response_type == "boolean":
                defaults = {"response_options": [0, 1]}
            elif question.response_type == "count":
                defaults = {"response_min": 0}
            if defaults:
                question.response_min = defaults.get("response_min")
                question.response_max = defaults.get("response_max")
                question.response_step = defaults.get("response_step")
                question.response_options = defaults.get("response_options")
                constraint_updates += 1

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
        if constraint_updates:
            print(f"Preguntas actualizadas con constraints: {constraint_updates}")


def main():
    activate = os.getenv("SEED_TEMPLATE_ACTIVE", "false").lower() == "true"
    name = os.getenv("SEED_TEMPLATE_NAME", DEFAULT_NAME)
    version = os.getenv("SEED_TEMPLATE_VERSION", DEFAULT_VERSION)
    app = create_app(get_config_class())
    seed_demo(app, activate=activate, name=name, version=version)


if __name__ == "__main__":
    main()
