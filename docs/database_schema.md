# Database Schema (live introspection)

Fecha de corte: 2026-05-02.
Fuente: introspeccion SQL estructural contra DB configurada por `.env` (sin extraer PII ni filas de negocio).

## Metodo
- Conexion usando `config.settings.Config.SQLALCHEMY_DATABASE_URI`.
- Solo metadatos estructurales:
  - tablas
  - columnas/tipos/nullability/default
  - PK/FK
  - indices
  - conteos agregados por tabla
- Evidencia generada en `data/database_schema_audit/`.

## Resultado de conexion
- `connection_attempted=true`
- `connected=true`
- `schema=public`
- `table_count=84`

Resumen estructural:
- columnas inspeccionadas: `869`
- foreign keys: `128`
- indices: `155`

## Artefactos auditables
- `data/database_schema_audit/db_introspection_summary.json`
- `data/database_schema_audit/tables.csv`
- `data/database_schema_audit/columns.csv`
- `data/database_schema_audit/primary_keys.csv`
- `data/database_schema_audit/foreign_keys.csv`
- `data/database_schema_audit/indexes.csv`
- `data/database_schema_audit/table_row_counts.csv`

## Grupos funcionales detectados (schema `public`)

### Auth, seguridad y auditoria
- `app_user`, `role`, `user_role`, `user_session`, `refresh_token`, `user_mfa`, `recovery_code`, `mfa_login_challenge`, `password_reset_token`, `audit_log`, `email_unsubscribe`, `email_delivery_log`.

### Cuestionarios v2 y runtime
- `questionnaire_*` (definiciones, preguntas, escalas, sesiones, respuestas, resultados, tags, share, grants, auditoria).
- `qr_*` (runtime v1 y su capa administrativa/operativa).

### Evaluaciones y reportes
- `evaluation*`, `generated_reports`, `report_jobs`, `dashboard_aggregates`, `service_health_snapshots`.

### Registry de modelos e inferencia
- `model_registry`, `model_versions`, `model_mode_domain_activation`, `model_metrics_snapshot`, `model_confidence_registry`, `model_operational_caveats`, `model_artifact_registry`, `model_monitoring_snapshots`.

### Linea historica ML/dataset
- `ml_model`, `ml_model_version`, `training_dataset`, `training_run`, `diagnostic_threshold`, `evaluation_prediction*`, `risk_alert`, `psychologist_feedback`, `synthetic_data_batch`.

## Caveats
- Este documento no publica credenciales, payloads clinicos ni PII.
- Los conteos por tabla son agregados tecnicos y pueden cambiar entre corridas.
- Para contratos API, la fuente activa sigue siendo `docs/openapi.yaml`.
