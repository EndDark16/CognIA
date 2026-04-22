# CognIA Backend

Backend del proyecto CognIA para tamizaje/apoyo profesional en salud mental infantil (6-11 anos) en entorno simulado.

## Proposito del proyecto
CognIA expone una API para:
- autenticacion/autorizacion,
- entrega y procesamiento de cuestionarios,
- inferencia de modelos activos por dominio/modo,
- historial y reportes operativos,
- gobierno admin y trazabilidad.

Importante: los resultados son de **screening/apoyo profesional**, no diagnostico automatico ni definitivo.

## Contexto y alcance
- Base empirica y metodologica: HBN + DSM-5 (segun artefactos internos).
- Dominios operativos: `adhd`, `conduct`, `elimination`, `anxiety`, `depression`.
- Backend incluye flujos legacy v1, runtime v1 y flujo operacional v2.

## Arquitectura general
- Framework: Flask (Blueprints).
- Persistencia: SQLAlchemy + PostgreSQL.
- Migraciones: Alembic.
- Seguridad: JWT, RBAC, MFA, rate limiting.
- Contratos: Marshmallow + OpenAPI.
- Testing: pytest.

Capas:
- `api/routes`: endpoints.
- `api/schemas`: validacion de payloads/query.
- `api/services`: logica de dominio.
- `app/models.py`: entidades ORM.
- `migrations/versions`: evolucion de esquema.

## Stack tecnologico
- Python 3.12+
- Flask, Flask-JWT-Extended, Flask-Limiter, Flask-CORS
- SQLAlchemy, Alembic, psycopg
- Marshmallow
- pandas, scikit-learn (runtime/model integration)
- pytest

## Estructura del proyecto
```text
cognia_app/
|- api/
|  |- app.py
|  |- decorators.py
|  |- extensions.py
|  |- security.py
|  |- routes/
|  |  |- auth.py
|  |  |- admin.py
|  |  |- predict.py
|  |  |- questionnaires.py
|  |  |- evaluations.py
|  |  |- questionnaire_runtime.py
|  |  |- questionnaire_v2.py
|  |  |- problem_reports.py
|  |  |- users.py
|  |  |- health.py
|  |  |- docs.py
|  |  |- email.py
|  |- schemas/
|  |  |- *.py
|  |- services/
|     |- *.py
|- app/
|  |- models.py
|- config/
|  |- settings.py
|- migrations/
|  |- versions/
|- docs/
|  |- openapi.yaml
|  |- archive/
|  |  |- openapi/
|  |     |- *.yaml
|  |- OPENAPI_GUIDE.md
|  |- endpoint_lifecycle_matrix.md
|  |- api_full_reference.md
|  |- questionnaire_backend_architecture.md
|  |- questionnaire_api_contract.md
|  |- model_registry_and_inference.md
|  |- reporting_and_dashboards.md
|  |- problem_reporting_backend.md
|  |- security_hardening_20260416.md
|  |- repository_artifact_policy.md
|  |- traceability_map.md
|  |- continuidad.md
|- scripts/
|  |- openapi_professionalize.py
|  |- *.py
|- tests/
|  |- *.py
|  |- api/
|  |- contracts/
|  |- services/
|- data/
|- artifacts/
|- reports/
|- models/
|- static/
|- templates/
|- README.md
|- docs/traceability_map.md
|- CONTRIBUTING.md
|- REPO_CONTENT_POLICY.md
|- requirements.txt
|- run.py
```

## Configuracion local
1. Crear entorno virtual.
2. Instalar dependencias: `pip install -r requirements.txt`.
3. Configurar variables en `.env` (no versionar secretos).
4. Ejecutar migraciones: `alembic upgrade head`.
5. Iniciar app: `python run.py`.

## Variables de entorno clave
Ver `.env.example` para plantilla completa.

Variables criticas:
- `SECRET_KEY`
- `MFA_ENCRYPTION_KEY`
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSL_MODE`
- `CORS_ORIGINS`
- `RATELIMIT_ENABLED`
- `OPTIONAL_BLUEPRINTS_STRICT`
- `OPTIONAL_BLUEPRINTS_REQUIRED`
- `QV2_SHARED_ACCESS_RATE_LIMIT`
- `PREDICT_RATE_LIMIT`
- `PROBLEM_REPORT_UPLOAD_DIR`
- `PROBLEM_REPORT_MAX_ATTACHMENT_BYTES`
- `PROBLEM_REPORT_ALLOWED_MIME_TYPES`

## Migraciones y bootstrap
- Revisiones en `migrations/versions/`.
- Flujo recomendado:
  - `alembic upgrade head`
- Para backend v2 de cuestionarios:
  - `python scripts/bootstrap_questionnaire_backend_v2.py load-all`

## API y contratos
- Swagger UI: `GET /docs`
- OpenAPI: `GET /openapi.yaml`
- Fuente activa de contrato: `docs/openapi.yaml` (snapshots historicos en `docs/archive/openapi/`)
- Matriz de ciclo de vida de endpoints: `docs/endpoint_lifecycle_matrix.md`
- Referencia mantenedor: `docs/api_full_reference.md`

## Endpoints principales
- Auth/MFA: `/api/auth/*`, `/api/mfa/*`
- Admin: `/api/admin/*`
- Questionnaires legacy: `/api/v1/questionnaires/*`
- Questionnaire runtime v1: `/api/v1/questionnaire-runtime/*`
- Questionnaire v2: `/api/v2/*`
- Nota de migracion:
  - `POST /api/v1/questionnaires/{template_id}/activate` se mantiene por compatibilidad, pero el reemplazo operativo recomendado es `POST /api/admin/questionnaires/{template_id}/publish`.
  - `POST /api/v1/questionnaires/active/clone` se mantiene por compatibilidad, pero el reemplazo operativo recomendado es `POST /api/admin/questionnaires/{template_id}/clone`.
- Problem reports:
  - `POST /api/problem-reports`
  - `GET /api/problem-reports/mine`
  - `GET /api/admin/problem-reports`
  - `GET /api/admin/problem-reports/{id}`
  - `PATCH /api/admin/problem-reports/{id}`

## Reporte de problemas (nuevo)
Soporta captura de incidentes desde frontend (tipo, descripcion, captura opcional) con:
- persistencia en DB,
- control de acceso (ADMIN para gestion global),
- filtros/paginacion,
- auditoria de cambios.

Detalles: `docs/problem_reporting_backend.md`.

## Modelos activos e inferencia
- Activacion vigente por modo/dominio en artefactos de freeze operativa.
- El backend mantiene claim metodologico: screening/apoyo profesional.
- Evitar lenguaje diagnostico.

## Autenticacion y permisos
- JWT Bearer para rutas protegidas.
- RBAC por claims `roles` (`ADMIN`, `PSYCHOLOGIST`, etc.).
- MFA requerido para roles sensibles.
- Hardening y decisiones de seguridad: `docs/security_hardening_20260416.md`.

## Testing
- Ejecutar suite completa: `pytest -q`
- Pruebas especificas de problem reports: `pytest tests/test_problem_reports.py -q`
- Guardrail OpenAPI vs runtime: `pytest tests/contracts/test_openapi_runtime_alignment.py -q`
- Guardrail de calidad documental OpenAPI: `pytest tests/contracts/test_openapi_documentation_quality.py -q`
- Hardening de predict experimental: `pytest tests/test_predict.py -q`

## SonarCloud (analisis local desde .env)
- Variables requeridas en `.env`:
  - `SONAR_HOST_URL`
  - `SONAR_TOKEN`
  - `SONAR_PROJECT_KEY`
  - `SONAR_ORGANIZATION`
- Ejecutar analisis:
  - `.\scripts\run_sonar.ps1`
- El script genera `coverage.xml` automaticamente con pruebas backend focalizadas antes del scan.
- Esperar Quality Gate (opcional):
  - `.\scripts\run_sonar.ps1 -WaitQualityGate -QualityGateTimeoutSec 300`
- Omitir cobertura (si solo quieres validar scanner):
  - `.\scripts\run_sonar.ps1 -SkipCoverage`
- Scope actual versionado para Sonar:
  - `api`, `app`, `config` (ver `sonar-project.properties`).

## Reporting y dashboards
- Endpoints v2 en `/api/v2/dashboard/*` y `/api/v2/reports/jobs`.
- Ver `docs/reporting_and_dashboards.md`.

## Trazabilidad
- Estado y decisiones: `docs/traceability_map.md`, `docs/traceability_map.md`.
- Mapa de trazabilidad: `docs/traceability_map.md`.
- Matriz de brechas backend 9-25: `docs/backend_gap_matrix_20260422.md`.
- Ingesta de playbook de despliegue externo: `docs/deployment_playbook_ingest_20260422.md`.
- Versionado backend:
  - `VERSION`
  - `CHANGELOG.md`
  - `docs/backend_versioning_policy.md`
  - `docs/backend_release_workflow.md`
  - `docs/backend_release_registry.csv`
  - `docs/releases/backend_release_2026-04-22_r1.md`
  - `artifacts/backend_release_registry/backend_release_2026-04-22_r1_manifest.json`
- Cierre final: `reports/final_closure/`.

## Politica de artefactos del repositorio
- Politica detallada: `docs/repository_artifact_policy.md`.
- Regla: versionar fuente de verdad y codigo; excluir runtime/generated/secrets.

## Convenciones de ramas y PR
- Flujo recomendado: feature branch -> `dev.enddark` -> `development`.
- Usar plantilla de PR en `.github/pull_request_template.md`.

## Rama canonica y politica de worktrees
- Rama canonica operativa: `development` (sin sobrescribirla desde ramas atrasadas o experimentales).
- Antes de limpiar/remover worktrees:
  - exportar estado (`git status`, `git diff`, `git ls-files --others`) y crear snapshot de seguridad.
  - clasificar cambios contra `origin/development` (`KEEP`, `CHERRY_PICK_SAFE`, `MANUAL_PORT_REQUIRED`, `REJECT_*`).
- No usar worktrees como fuente paralela de contrato API.
- Si un worktree queda obsoleto:
  - preservar respaldo no destructivo,
  - remover worktree,
  - mantener la rama para trazabilidad si aplica.
- Evitar crear worktrees dentro del repo que puedan contaminar el arbol principal; si se usan, quedan ignorados por `.gitignore`.

## Troubleshooting rapido
- `401/403` en endpoints protegidos: validar JWT, roles y MFA.
- `503` en readiness: revisar conectividad DB y variables.
- Errores de migracion: verificar `alembic.ini`, `APP_CONFIG_CLASS` y credenciales.
- Upload de captura rechazado: validar MIME permitido y tamano maximo.

## Limitaciones
- Entorno simulado para apoyo operativo.
- No sustituye juicio clinico profesional.
