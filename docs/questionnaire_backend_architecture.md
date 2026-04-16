# Questionnaire Backend Architecture (v2)

## Scope
Backend operacional para cuestionarios con modos `short`, `medium`, `complete`, sesiones versionadas, inferencia por 30 pares dominio-modo y reporting.

## Capas
- `api/routes/questionnaire_v2.py`: endpoints v2.
- `api/schemas/questionnaire_v2_schema.py`: DTOs/validaciones Marshmallow.
- `api/services/questionnaire_v2_loader_service.py`: ingesta versionada de cuestionario/modelos.
- `api/services/questionnaire_v2_service.py`: sesiones, inferencia, historial, tags, share, PDF, dashboards/reportes.
- `app/models.py`: entidades ORM v2.
- `migrations/versions/20260414_01_add_questionnaire_backend_v2.py`: esquema Alembic.

## Flujo principal
1. Bootstrap catálogo (`questionnaire_definitions`, `questionnaire_versions`, secciones, preguntas, escalas).
2. Registro de modelos activos (`model_registry`, `model_versions`, `model_mode_domain_activation`, métricas/confianza/caveats).
3. Creación de sesión (`questionnaire_sessions` + `questionnaire_session_items`).
4. Guardado parcial y reanudación (`questionnaire_session_answers`, progreso).
5. Submit + inferencia (`questionnaire_session_internal_features`, `questionnaire_session_results`, dominios/comorbilidad).
6. Historial, tags, share code y accesos auditados.
7. Generación PDF y reportes operativos.

## Seguridad y acceso
- Owner siempre puede ver/etiquetar/descargar.
- Acceso delegado por `questionnaire_access_grants`.
- Acceso compartido por `questionnaire_share_codes` + `questionnaire_public_id`.
- Auditoría operacional en `questionnaire_audit_events` y `questionnaire_session_access_links`.

## Caveat metodológico
Las salidas son para `screening/apoyo profesional` en entorno simulado y no son diagnóstico automático.
