# Questionnaire Runtime v1 - Dise?o final de API

## Usuario/cuidador
- `GET /api/v1/questionnaire-runtime/questionnaire/active`
- `POST /api/v1/questionnaire-runtime/evaluations/draft`
- `PATCH /api/v1/questionnaire-runtime/evaluations/{id}/draft`
- `POST /api/v1/questionnaire-runtime/evaluations/{id}/validate-section`
- `POST /api/v1/questionnaire-runtime/evaluations/{id}/submit`
- `POST /api/v1/questionnaire-runtime/evaluations/{id}/heartbeat`
- `GET /api/v1/questionnaire-runtime/evaluations/{id}/status`
- `GET /api/v1/questionnaire-runtime/evaluations/{id}/responses`
- `GET /api/v1/questionnaire-runtime/evaluations/{id}/results`
- `GET /api/v1/questionnaire-runtime/evaluations/history`
- `DELETE /api/v1/questionnaire-runtime/evaluations/{id}`
- `GET /api/v1/questionnaire-runtime/evaluations/{id}/export?mode=...`

## Psic?logo/profesional
- `POST /api/v1/questionnaire-runtime/professional/access`
- `GET /api/v1/questionnaire-runtime/professional/evaluations/{id}/responses`
- `GET /api/v1/questionnaire-runtime/professional/evaluations/{id}/results`
- `PATCH /api/v1/questionnaire-runtime/professional/evaluations/{id}/tag`
- `DELETE /api/v1/questionnaire-runtime/professional/evaluations/{id}/access`

## Notificaciones
- `GET /api/v1/questionnaire-runtime/notifications`
- `PATCH /api/v1/questionnaire-runtime/notifications/{id}/read`

## Admin
- `POST /api/v1/questionnaire-runtime/admin/bootstrap`
- `POST /api/v1/questionnaire-runtime/admin/templates`
- `POST /api/v1/questionnaire-runtime/admin/templates/{id}/versions`
- `POST /api/v1/questionnaire-runtime/admin/templates/{id}/active`
- `GET /api/v1/questionnaire-runtime/admin/templates/{id}/versions`
- `POST /api/v1/questionnaire-runtime/admin/versions/{id}/publish`
- `POST /api/v1/questionnaire-runtime/admin/versions/{id}/disclosures`
- `POST /api/v1/questionnaire-runtime/admin/versions/{id}/sections`
- `POST /api/v1/questionnaire-runtime/admin/sections/{id}/questions`
- `GET /api/v1/questionnaire-runtime/admin/versions/{id}`

## Contratos legacy
- `POST /api/predict` sigue disponible por compatibilidad, pero queda marcado como **deprecated** en headers HTTP (`Deprecation`, `Sunset`, `Link`).
- Nuevo flujo recomendado: `/api/v1/questionnaire-runtime/*`.

