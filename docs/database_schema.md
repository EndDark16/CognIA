# Database Schema Context (Supabase + public schema)

Este documento resume el esquema actual y la responsabilidad de cada schema.
La fuente es el JSON provisto (snapshot 2026-01-25). Esta referencia es para
entorno de tesis y auditoria tecnica.

## Alcance
- **public**: tablas propias del dominio CognIA (app, cuestionarios, evaluaciones, ML).
- **auth, storage, realtime, extensions, graphql, vault, pgbouncer**: schemas
  **gestionados por Supabase**. No se modifican desde esta app.

## Reglas de diseno (public)
- **Trazabilidad**: cada evaluacion guarda `questionnaire_template_id`.
- **Versionado**: las plantillas se versionan; solo una activa a la vez.
- **Privacidad**: datos sensibles limitados; no se guarda access key en claro.
- **Auditoria**: `audit_log` registra acciones del sistema.

## public: tablas principales por dominio

### Acceso y auditoria
- `app_user`: usuarios locales (no usa `auth.users`); incluye `user_type` (guardian/psychologist), `professional_card_number` (COLPSIC), `password_changed_at` y campos de bloqueo de login (`failed_login_attempts`, `login_locked_until`).
- `password_reset_token`: tokens de recuperación (hash, expiración, uso, metadata).
- `email_delivery_log`: log de envio de emails transaccionales (template, status, error, timestamps).
- `email_unsubscribe`: lista de bajas (email, reason, source, metadata).
- `role`, `user_role`: RBAC.
- `user_session`: sesiones de app.
- `audit_log`: eventos auditables.
- `refresh_token`, `user_mfa`, `recovery_code`, `mfa_login_challenge`: MFA/JWT.

### Cuestionarios
- `questionnaire_template`: plantilla (nombre, version, is_active).
- `question`: preguntas; incluye constraints opcionales:
  - `response_min`, `response_max`, `response_step`, `response_options`.
- `question_disorder`: **relacion N:M** para preguntas multi-trastorno.
- `disorder`: catalogo de trastornos.

### Sujetos y tutores
- `subject`: sujeto (nino).
- `subject_guardian`: relacion tutor/subject (activa/inactiva).

### Evaluaciones
- `evaluation`: evento clinico; incluye `registration_number`, `access_key_*`,
  `questionnaire_template_id`.
- `evaluation_response`: respuestas por pregunta.
- `evaluation_report`: reportes generados.
- `email_log`: auditoria de envio de reportes.

### ML y resultados (esquema listo, no implementa ML en app)
- `ml_model`, `ml_model_version`
- `training_dataset`, `training_run`
- `diagnostic_threshold`
- `evaluation_prediction`
- `evaluation_prediction_detail`
- `risk_alert`
- `psychologist_feedback`
- `synthetic_data_batch`

### Configuracion
- `system_setting`: parametros globales (key/value).

## Relaciones clave (resumen)
- `evaluation.questionnaire_template_id -> questionnaire_template.id`
- `question.questionnaire_id -> questionnaire_template.id`
- `question_disorder.question_id -> question.id`
- `question_disorder.disorder_id -> disorder.id`
- `evaluation_response.evaluation_id -> evaluation.id`
- `evaluation_response.question_id -> question.id`
- `subject_guardian.subject_id -> subject.id`
- `subject_guardian.user_id -> app_user.id`

## Buenas practicas operativas
- **No editar** plantillas activas: usar clon + nueva version.
- **Response types** cuantitativos; `text_context` solo contexto (no modelo).
- **Data-driven constraints**: si no existen, se aplican rangos por defecto
  segun `response_type`.
- **Separacion de schemas**: `auth` y `storage` son Supabase-managed.

## Notas sobre Supabase
Los schemas `auth`, `storage`, `realtime`, `extensions`, `graphql`, `vault` y
`pgbouncer` forman parte del sistema de Supabase. Solo se documentan para
contexto; no se versionan ni se migran desde Alembic en este repositorio.
