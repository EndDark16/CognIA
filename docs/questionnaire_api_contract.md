# Questionnaire API Contract (v2)

Base path: `/api/v2`

## Alcance metodologico obligatorio
- Backend orientado a entorno simulado para screening/apoyo profesional.
- No usar este contrato para afirmar diagnostico clinico automatico.

## Cuestionario y sesiones
- `GET /questionnaires/active?mode=short|medium|complete&role=guardian|psychologist`
- `POST /questionnaires/sessions`
- `GET /questionnaires/sessions/{id}`
- `GET /questionnaires/sessions/{id}/page?page=1&page_size=20`
- `PATCH /questionnaires/sessions/{id}/answers`
- `PATCH /questionnaires/sessions/{id}/answers/bulk`
- `POST /questionnaires/sessions/{id}/submit`

### Continuacion de borrador (resume)
- `GET /questionnaires/sessions/{id}` devuelve estado reanudable para el duenio autorizado:
  - `session_id`, `status`, `mode`, `role`, `progress_pct`
  - `answered_count`, `total_questions`
  - `answers[]` con `question_id`, `question_code`, `section`, `answer`, `answer_value`, `updated_at`
- `GET /questionnaires/sessions/{id}/page` devuelve por pregunta:
  - `answered`, `answer`, `answer_value`, `answer_updated_at`

## Historial y resultados
- `GET /questionnaires/history`
- `GET /questionnaires/history/{id}`
- `GET /questionnaires/history/{id}/results`

## Tags
- `POST /questionnaires/history/{id}/tags`
- `DELETE /questionnaires/history/{id}/tags/{tag_id}`

## Share y acceso compartido
- `POST /questionnaires/history/{id}/share`
- `GET /questionnaires/shared/{questionnaire_id}/{share_code}`

## PDF de resultados
- `POST /questionnaires/history/{id}/pdf/generate`
- `GET /questionnaires/history/{id}/pdf`
- `GET /questionnaires/history/{id}/pdf/download`

## Dashboards
- `GET /dashboard/adoption-history`
- `GET /dashboard/questionnaire-volume`
- `GET /dashboard/user-growth`
- `GET /dashboard/funnel`
- `GET /dashboard/retention`
- `GET /dashboard/productivity`
- `GET /dashboard/questionnaire-quality`
- `GET /dashboard/data-quality`
- `GET /dashboard/api-health`
- `GET /dashboard/model-monitoring`
- `GET /dashboard/drift`
- `GET /dashboard/equity`
- `GET /dashboard/human-review`
- `GET /dashboard/executive-summary`

## Reportes
- `POST /reports/jobs`
- `GET /reports/jobs/{report_job_id}`
- `GET /reports/jobs/{report_job_id}/download`

## Admin bootstrap
- `POST /questionnaires/admin/bootstrap` (requiere `ADMIN`)

## Compatibilidad y migracion v1 -> v2/admin
- El flujo recomendado para integraciones nuevas es v2 (`/api/v2/questionnaires/*`).
- Los endpoints legacy de `api/v1/questionnaires` se mantienen por compatibilidad, pero deben considerarse deprecados para desarrollo nuevo.
- Mapeo de reemplazo operativo:
  - `POST /api/v1/questionnaires/{template_id}/activate` -> `POST /api/admin/questionnaires/{template_id}/publish`
  - `POST /api/v1/questionnaires/active/clone` -> `POST /api/admin/questionnaires/{template_id}/clone`

## Respuesta de resultados por dominio
Cada dominio retorna minimo:
- `probability`
- `alert_level`
- `confidence_pct`
- `confidence_band`
- `model_id`
- `model_version`
- `mode`
- `domain`
- `operational_caveat`
- `result_summary`
- `needs_professional_review`

Nota: contrato de apoyo de screening; no diagnostico automatico.
