# Current Placeholder Questionnaire Summary
Fecha: 2026-03-30

## Que existe hoy
- Infraestructura backend para plantillas y preguntas (`questionnaire_template`, `question`) y para respuestas (`evaluation`, `evaluation_response`).
- Endpoints operativos:
  - `GET /api/v1/questionnaires/active`
  - ciclo de vida de templates (create/add_questions/activate/clone + admin publish/archive/clone)
  - `POST /api/v1/evaluations`
- Endpoint legacy `POST /api/predict` marcado experimental/deprecated.
- Artefactos de specs (581 features) y capa `data/questionnaire_dsm5_v1` no integrados al runtime user-facing.

## Hallazgo principal
El cuestionario actual es **placeholder funcional de integracion**, no diseno final:
- frontend carga template activa,
- responde localmente,
- termina localmente,
- no hay submit real conectado desde UI,
- no hay salida de resultados integrada en ese flujo.

## Reutilizable vs provisional
- Reutilizable (plumbing):
  - versionado base de templates,
  - validacion server-side por `response_type`,
  - persistencia por `question_id`,
  - trazabilidad por `questionnaire_template_id`.
- Provisional:
  - UI local sin submit,
  - tipos frontend simplificados y desalineados,
  - `/api/predict` legacy adhd-only.
- Parcial y con refactor:
  - `artifacts/specs/*` y `data/questionnaire_dsm5_v1/*` como base metodologica, no contrato runtime final.

## Impacto separado
- Backend/BD: falta completar submit real, resultados por evaluacion, draft/section validation y contrato versionado.
- Frontend (repo externo): requiere handoff para submit real, payloads definitivos, validaciones sincronizadas y pantalla de resultados.

## Evidencia clave
- `api/routes/questionnaires.py`, `api/routes/evaluations.py`, `api/schemas/questionnaire_schema.py`, `api/schemas/evaluation_schema.py`.
- `app/models.py`, `docs/openapi.yaml`.
- `artifacts/specs/*`, `data/questionnaire_dsm5_v1/*`, `artifacts/inference_v4/*`.
- Frontend referencia (read-only): `JeiTy29/cognIA-frontend`.
