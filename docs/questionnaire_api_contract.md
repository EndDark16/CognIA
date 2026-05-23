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
- Estos endpoints requieren rol `ADMIN`.
- `POST /reports/jobs` acepta filtros no-breaking (`months`, `date_from`, `date_to`, `granularity`, `format`, `filters`).
- `GET /reports/jobs/{report_job_id}` devuelve metadata + preview operativo (headline metrics y secciones).
- Ver contrato detallado en [docs/admin_reports_contract.md](/C:/Users/andre/Documents/cognia_clean_work/cognia_runtime_draft_fix_clean2/docs/admin_reports_contract.md).

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

## Nuevas capacidades de trazabilidad operativa (backend-only)

### 1) Casos del guardian

#### POST `/questionnaires/cases`
- Permiso: usuario autenticado (guardian/padre/tutor).
- Request:
```json
{
  "private_label": "Hijo mayor",
  "metadata": {
    "notes": "seguimiento escolar"
  }
}
```
- Response `201`:
```json
{
  "case": {
    "case_id": "4f695935-c87b-4286-af5f-ef74ea74fb75",
    "case_public_id": "CASO-8F2K7A",
    "private_label": "Hijo mayor",
    "display_label": "Hijo mayor",
    "status": "active",
    "sessions_count": 0,
    "created_at": "2026-05-22T23:00:00Z",
    "updated_at": "2026-05-22T23:00:00Z"
  }
}
```
- Errores: `case_validation_error` (400), `case_label_invalid` (400), `case_create_forbidden` (403), `case_public_id_conflict` (409), `case_create_failed` (500).

#### GET `/questionnaires/cases`
- Permiso: usuario autenticado propietario.
- Query: `status` opcional, `page`, `page_size`.
- Response `200`: lista paginada con `case_public_id`, `private_label` (solo owner), `sessions_count`, `latest_session_id`, `latest_alert_level`.
- Errores: `cases_list_forbidden` (403), `cases_list_failed` (500).

#### GET `/questionnaires/cases/{case_id}`
- Permiso: solo owner.
- Response `200`: `{ case, sessions, domain_summary, trend }`.
- Errores: `case_not_found` (404), `case_forbidden` (403), `case_detail_failed` (500).

#### PATCH `/questionnaires/cases/{case_id}`
- Permiso: solo owner.
- Request:
```json
{
  "private_label": "Hijo del medio",
  "status": "active"
}
```
- Errores: `case_not_found` (404), `case_forbidden` (403), `case_update_validation_error` (400), `case_update_failed` (500).

### 2) Extensión no-breaking de creación de sesión

#### POST `/questionnaires/sessions`
- Campos opcionales nuevos (aditivos): `case_id`, `case_public_id`, `case_label`.
- Reglas:
  - `case_id` / `case_public_id`: deben pertenecer al owner.
  - `case_label` sin `case_id/case_public_id`: crea caso y asocia sesión.
  - Sin campos de caso: mantiene comportamiento previo.
- Errores específicos: `session_case_not_found` (404), `session_case_forbidden` (403), `session_case_validation_error` (400).

### 3) Dashboard del guardian

#### GET `/questionnaires/guardian/dashboard`
- Permiso: owner autenticado.
- Query: `months` (default 3), `date_from`, `date_to`, `case_id`, `case_public_id`.
- Response `200`:
```json
{
  "period": { "months": 3, "date_from": "2026-03-01", "date_to": "2026-05-22" },
  "summary": {
    "total_cases": 2,
    "total_sessions": 5,
    "processed_sessions": 4,
    "cases_needing_professional_review": 1,
    "highest_alert_level": "elevated"
  },
  "cases": []
}
```
- Errores: `guardian_dashboard_forbidden` (403), `guardian_dashboard_invalid_period` (400), `guardian_dashboard_case_not_found` (404), `guardian_dashboard_failed` (500).

### 4) Dashboard del psicologo

#### GET `/questionnaires/psychologist/dashboard`
- Permiso: solo `user_type=psychologist`.
- Fuente: solo sesiones compartidas mediante grant vigente.
- Query: `q`, `case_public_id`, `date_from`, `date_to`, `domain`, `alert_level`, `review_status`, `page`, `page_size`.
- Response `200`: incluye `summary`, `aggregates`, `items`, `pagination`.
- Privacidad: nunca expone `private_label` del guardian.
- Errores: `psychologist_dashboard_requires_psychologist` (403), `psychologist_dashboard_invalid_period` (400), `psychologist_dashboard_invalid_filter` (400), `psychologist_dashboard_failed` (500).

### 5) Búsqueda de psicólogos registrados

#### GET `/psychologists/search`
- Permiso: JWT requerido.
- Query: `q` (username/email/full_name), `location`, `page`, `page_size`.
- Response `200`: usuarios activos `user_type=psychologist` con `professional_location` y `colpsic_verified`.
- Errores: `psychologist_search_forbidden` (403), `psychologist_search_invalid_query` (400), `psychologist_search_failed` (500).

### 6) Compartir sesión con psicólogo registrado

#### POST `/questionnaires/history/{session_id}/share`
- Request (aditivo):
```json
{
  "grantee_user_id": "f6de67c4-7975-4f57-9f47-087f22ead89f",
  "expires_in_hours": 720,
  "max_uses": 100,
  "grant_can_tag": false,
  "grant_can_download_pdf": true,
  "share_scope": "session"
}
```
- Response `201`: mantiene `share_code` y agrega `case.case_public_id`, `grantee` y `grant`.
- Errores: `share_session_not_found` (404), `share_owner_required` (403), `share_grantee_not_found` (404), `share_target_not_psychologist` (400), `share_grantee_inactive` (400), `share_validation_error` (400), `share_failed` (500).

### 7) Concepto inicial no diagnóstico

#### GET `/questionnaires/history/{session_id}/professional-reviews`
- Permiso: owner, psicólogo con grant o admin.
- Response `200`: lista de revisiones visibles.

#### POST `/questionnaires/history/{session_id}/professional-reviews`
- Permiso: solo psicólogo con grant vigente.
- Request:
```json
{
  "review_status": "reviewed",
  "initial_concept": "Concepto inicial orientativo, no diagnóstico.",
  "recommendation": "Se sugiere revisión profesional presencial.",
  "visible_to_guardian": true
}
```
- Errores: `professional_review_requires_psychologist` (403), `professional_review_session_not_found` (404), `professional_review_forbidden` (403), `professional_review_status_invalid` (400), `professional_review_text_too_long` (400), `professional_review_validation_error` (400), `professional_review_failed` (500).

#### PATCH `/questionnaires/history/{session_id}/professional-reviews/{review_id}`
- Permiso: psicólogo autorizado.
- Errores: `professional_review_not_found` (404), `professional_review_forbidden` (403), `professional_review_update_validation_error` (400), `professional_review_update_failed` (500).

### 8) Vista previa backend del reporte

#### GET `/questionnaires/history/{session_id}/report-preview`
#### POST `/questionnaires/history/{session_id}/report-preview/secure`
- Permiso: owner o psicólogo con grant.
- Retorna view-model (no PDF), con resultados y respuestas visibles.
- En psicólogo: usa `case_public_id`; no expone `private_label`.
- Errores: `report_preview_session_not_found` (404), `report_preview_forbidden` (403), `report_preview_failed` (500).

## Privacidad y etiquetas
- `private_label` es visible solo para el owner.
- Para psicólogos se expone `case_public_id` y etiqueta de presentación basada en id público.
- Los endpoints de dashboard/reporte/reviews aplican esta regla.

## Texto visible de rol administrativo
- Se mantiene rol interno `admin`/`ADMIN` para autorización.
- Payload visible agrega `display_role: "Administrador del sistema"` para UX/documentación.

## Guía de integración frontend (sin cambios breaking)
- Crear caso: `POST /api/v2/questionnaires/cases`.
- Crear sesión asociada: `POST /api/v2/questionnaires/sessions` con `case_id` o `case_public_id` o `case_label`.
- Reanudar borrador completo: `GET /api/v2/questionnaires/sessions/{id}`.
- Guardado por página: `PATCH /api/v2/questionnaires/sessions/{id}/answers` o `/answers/bulk`.
- Dashboard guardian: `GET /api/v2/questionnaires/guardian/dashboard`.
- Buscar psicólogos: `GET /api/v2/psychologists/search?q=...`.
- Compartir a psicólogo: `POST /api/v2/questionnaires/history/{id}/share`.
- Dashboard psicólogo: `GET /api/v2/questionnaires/psychologist/dashboard`.
- Registrar concepto no diagnóstico: `POST /api/v2/questionnaires/history/{id}/professional-reviews`.
- Vista previa in-app: `GET /api/v2/questionnaires/history/{id}/report-preview`.
- Descarga PDF: mantener endpoints actuales `/pdf/generate`, `/pdf`, `/pdf/download`.
