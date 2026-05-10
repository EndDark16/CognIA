# Manual Tecnico Backend CognIA

## 1) Proposito y alcance tecnico del backend
Este documento consolida el estado tecnico real del backend `EndDark16/CognIA` en rama `development`, con foco en:
- arquitectura implementada y rutas realmente montadas;
- contratos de API, validaciones, servicios y seguridad;
- logica de inferencia legacy y operacional;
- configuracion, operacion, despliegue y calidad.

Alcance metodologico obligatorio: los resultados del sistema son para **screening/apoyo profesional en entorno simulado** y no constituyen diagnostico automatico o definitivo.

## 2) Metodo de verificacion aplicado
La consolidacion se hizo con evidencia verificable del repositorio:
- runtime real desde `api.app:create_app(TestingConfig)` y `app.url_map`;
- rutas en `api/routes/*`, validaciones en `api/schemas/*`, logica en `api/services/*`;
- configuracion en `config/settings.py`, `run.py`, `.env.example`;
- contrato OpenAPI en `docs/openapi.yaml`;
- pruebas en `tests/`.
- `AGENTS_CONTEXT.md`: **por confirmar** (no presente en este worktree de `development` durante esta ventana).

Inventario runtime obtenido en esta ventana:
- `119` pares endpoint-metodo (`112` paths unicos), alineados con OpenAPI por comparacion canonica de rutas.

## 3) Arquitectura real del backend
### 3.1 Convivencia real de capas
El backend convive en dos lineas funcionales:

1. **Legacy de inferencia directa**
- Endpoint: `POST /api/predict`.
- Implementacion: `api/routes/predict.py` + `api/schemas/predict_schema.py` + `api/services/model_service.py` + `core/models/predictor.py`.
- Rol: inferencia puntual legacy (experimental/deprecated en OpenAPI).

2. **Plataforma operacional (v2)**
- Base: `/api/v2/*` (`api/routes/questionnaire_v2.py`).
- Rol: sesiones, historia, submit/inferencia por dominio-modo, share, PDF, dashboards, report jobs, bootstrap admin.
- Estado: linea operativa principal para backend de cuestionarios/plataforma.

Tambien coexisten rutas v1 y runtime v1 por compatibilidad:
- `/api/v1/questionnaires/*`
- `/api/v1/questionnaire-runtime/*`
- `/api/v1/evaluations`
- `/api/v1/users/*`

### 3.2 Registro de blueprints y limites de arquitectura
`api/app.py` registra blueprints base y opcionales:
- base: `predict`, `auth`, `mfa`, `docs`, `health`, `metrics`, `questionnaires`, `evaluations`, `users`, `email`, `admin`, `problem_reports`.
- opcionales controlados por politica: `questionnaire_runtime`, `questionnaire_v2`.

Politica opcional:
- `OPTIONAL_BLUEPRINTS_STRICT`.
- `OPTIONAL_BLUEPRINTS_REQUIRED` (default: `questionnaire_runtime,questionnaire_v2`).

Implicacion:
- en modo estricto, si un blueprint requerido no importa, el arranque falla (fail-fast).

## 4) Componentes y organizacion del codigo
Capas verificadas:
- `api/routes/`: contratos HTTP por dominio funcional.
- `api/schemas/`: validacion de payload/query con Marshmallow.
- `api/services/`: logica de negocio, inferencia, carga de catalogos/modelos.
- `app/models.py`: entidades ORM y tablas operativas.
- `config/settings.py`: configuracion por entorno y hardening.
- `migrations/versions/`: cadena Alembic.

## 5) Matriz tecnica de endpoints
Matriz tecnica completa y mantenible:
- `docs/backend_endpoint_matrix.csv`

Columnas incluidas (solicitadas):
- `endpoint`
- `method`
- `blueprint`
- `route_module`
- `schema_validacion`
- `servicio_asociado`
- `request_format`
- `response_format`
- `auth_autorizacion`
- `errores_verificables`
- `response_contract`
- `openapi_operation_id`
- `openapi_path_matched`

Notas de alcance:
- La matriz parte del runtime real (no de listado teorico).
- Se excluyen endpoints no montados.
- Para vinculo runtime/OpenAPI se uso comparacion canonica de path (`{id}` vs `{report_id}` no rompe match).

Resumen de cobertura por familias:
- `/api/v2/*`: 32 operaciones.
- `/api/v1/questionnaire-runtime/*`: 29 operaciones.
- `/api/admin/*`: 24 operaciones.
- `/api/auth/*`: 10 operaciones.
- `/api/predict`: 1 operacion.
- operativas transversales: `/healthz`, `/readyz`, `/metrics`, `/docs`, `/openapi.yaml`.

## 6) Logica real de inferencia
### 6.1 Legacy `POST /api/predict`
Entrada validada por `PredictSchema`:
- `age` (rango 6-11)
- `sex` (0/1)
- `conners_inattention_score`
- `conners_hyperactivity`
- `cbcl_attention_score`
- `sleep_problems` (0/1)

Pipeline real:
1. `predict.py` valida JSON y schema.
2. `model_service.predict_all_probabilities` crea `DataFrame` con 6 features fijas.
3. Carga artefacto via `load_model("adhd")` (`models/adhd_model.pkl`).
4. Aplica `predict_proba(...)[0][1]`.

Salida real:
- `{"predictions": {"adhd": <float redondeado a 2 decimales>}}`

Limite verificable:
- aunque el sistema global contempla 5 dominios, este endpoint legacy solo materializa `adhd` en el codigo actual.

### 6.2 Runtime v1 (`/api/v1/questionnaire-runtime/*`)
Inferencia principal:
- `run_runtime_inference(feature_map)` en `api/services/questionnaire_runtime_service.py`.
- Evalua 5 dominios (`adhd`, `conduct`, `elimination`, `anxiety`, `depression`) con modelos en `models/champions/rf_<domain>_current`.
- Espera `metadata.json` + `calibrated.joblib` o `pipeline.joblib`.

Fallback verificable:
- en `TESTING=True`, ante ausencia de artefactos, usa `_testing_fallback_runtime`.
- fuera de testing, ausencia de metadata/artefacto dispara `FileNotFoundError`.
- para bootstrap/listado de preguntas se aplica fallback defensivo por contrato de features si faltan artefactos (evita caida de cuestionario activo).

### 6.3 Plataforma v2 (`/api/v2/*`)
Inferencia por sesion:
- `submit_session()` en `api/services/questionnaire_v2_service.py`.
- Resuelve activacion por `(domain, mode_key, role)` desde `model_mode_domain_activation` via `loader.get_active_activation`.
- Modelo activo cargado desde `ModelVersion.artifact_path` o `fallback_artifact_path`.
- Si no hay artefacto disponible o falla `predict_proba`, usa heuristica `_heuristic_domain_probability`.

Carga/registro de activaciones:
- `sync_active_models()` en `api/services/questionnaire_v2_loader_service.py` consume `data/hybrid_active_modes_freeze_v1/tables/hybrid_active_models_30_modes.csv`.
- Resuelve artefacto principal y fallback champion por dominio.
- Marca `metadata_json.por_confirmar = artifact_path is None`.
- Registra metricas, confianza y caveats operativos en tablas de registry.

Salida v2:
- resultado por dominio con `probability`, `alert_level`, `confidence_pct`, `confidence_band`, `operational_class`, `operational_caveat`, `needs_professional_review`.
- resumen operacional + comorbilidad.

### 6.4 Relacion entre legacy y mecanismos v2
- **No comparten el mismo contrato de entrada** ni la misma ruta de resolucion de modelos.
- `/api/predict` es flujo heredado y acotado.
- `/api/v2/*` es plataforma operativa basada en registry/activaciones de modo-dominio.

## 7) Resolucion de inconsistencias tecnicas visibles
### 7.1 Inconsistencia prioritaria de edad (corregida)
Problema detectado:
- alcance backend/documentacion: 6-11 anos.
- schema legacy de `/api/predict`: 3-21.

Decision y cambio aplicado:
- se corrigio localmente por coherencia metodologica y tecnica a 6-11.

Archivos actualizados:
- `api/schemas/predict_schema.py`
- `docs/openapi.yaml` (`PredictRequest` + ejemplo de borde)
- `tests/test_predict.py` (nuevo test de rango fuera de limite)

### 7.2 Discrepancias no corregidas por requerir rediseño o alcance mayor
- El guardrail `tests/contracts/test_openapi_documentation_quality.py` falla en este estado por formato de secciones en descripciones OpenAPI (deuda documental amplia, no limitada al cambio de edad).
- En `docs/HANDOFF.md` existen entradas historicas que afirman retiro de endpoints legacy v1, pero el runtime actual los mantiene montados por compatibilidad.

## 8) Seguridad implementada (backend)
Separacion: **implementado en codigo** vs **configurable**.

### 8.1 Implementado y verificable en repo
- JWT access + refresh:
  - refresh en cookie HttpOnly, ruta `/api/auth/refresh`.
- CSRF double-submit para refresh/logout:
  - header `X-CSRF-Token` debe coincidir con cookie CSRF.
- Revocacion de tokens/sesiones:
  - blocklist por `jti` revocado;
  - invalida tokens emitidos antes de `password_changed_at` o `sessions_revoked_at`.
- RBAC:
  - `roles_required(...)` para rutas admin/protegidas.
- MFA:
  - setup/confirm/disable + challenge en login MFA.
- Rate limiting:
  - Flask-Limiter global + limites por endpoint sensible.
- Security headers:
  - `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, opcional `CSP`, `Permissions-Policy`, `HSTS` (si request segura).
- CORS:
  - `Flask-CORS` con `supports_credentials=True`.
- Health/readiness:
  - `/healthz` (liveness basico);
  - `/readyz` (SELECT 1 real a DB, con cache corta configurable para evitar tormenta de checks concurrentes).
- Hardening de archivos:
  - descarga PDF v2 restringida a `artifacts/runtime_reports`;
  - adjuntos problem report con validacion de firma binaria PNG/JPEG/WEBP.

### 8.2 Configurable (no siempre activo)
- `RATELIMIT_ENABLED`, storage backend y limites por variable.
- `METRICS_TOKEN` / `METRICS_TOKEN_REQUIRED`.
- `SWAGGER_ENABLED` para exponer `/docs` y `/openapi.yaml`.
- `SECURITY_HEADERS_ENABLED` y politicas de cabeceras.
- `TRUST_PROXY_HEADERS` + `PROXY_FIX_*`.
- `AUTH_CROSS_SITE_COOKIES`, `JWT_COOKIE_SAMESITE`, `JWT_COOKIE_SECURE`, `JWT_COOKIE_DOMAIN`.
- `OPTIONAL_BLUEPRINTS_STRICT` / `OPTIONAL_BLUEPRINTS_REQUIRED`.

## 9) Configuracion, operacion y despliegue

### 9.1 Verificado en repositorio
- Objetivo operativo de la seccion (verificado por codigo): backend Flask por blueprints, ORM SQLAlchemy, migraciones Alembic, autenticacion JWT, validacion Marshmallow, rate limiting Flask-Limiter, CORS con Flask-CORS y persistencia principal PostgreSQL.
- La documentacion del repositorio declara Python `3.12+` como base objetivo del proyecto.
- Dependencias declaradas en `requirements.txt` (evidencia directa):
  - `Flask==3.0.3`
  - `flask-cors==4.0.1`
  - `flask-jwt-extended==4.6.0`
  - `Flask-SQLAlchemy==3.1.1`
  - `psycopg[binary]==3.1.19`
  - `Flask-Limiter==3.7.0`
  - `marshmallow==3.21.1`
  - `pandas==2.2.3`
  - `scikit-learn==1.7.1`
  - `alembic==1.14.0`
  - `gunicorn==23.0.0`
- Config classes reales:
  - `DevelopmentConfig`
  - `ProductionConfig`
  - `TestingConfig`
- `run.py` usa `create_app()` sin pasar clase explicita; por defecto se usa `DevelopmentConfig` salvo override via entorno/entrypoint alterno.
- Efectos observables de configuracion:
  - `ProductionConfig` desactiva debug, endurece cookies y activa confianza en proxy por defecto.
  - `TestingConfig` usa SQLite en memoria, desactiva varios controles no deseados en pruebas (`RATELIMIT_ENABLED=False`, `SECURITY_HEADERS_ENABLED=False`, etc.).
- Variables de entorno con evidencia directa en `.env.example` + `config/settings.py`:
  - Base: `APP_CONFIG_CLASS`, `PORT`, `SECRET_KEY`, `MFA_ENCRYPTION_KEY`.
  - BD: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSL_MODE`, `SQLALCHEMY_DATABASE_URI`.
  - Frontend/cookies/CORS: `FRONTEND_URL`, `CORS_ORIGINS`, `AUTH_CROSS_SITE_COOKIES`, `JWT_COOKIE_SAMESITE`, `JWT_COOKIE_SECURE`, `JWT_COOKIE_DOMAIN`.
  - Migraciones/startup: `RUN_MIGRATIONS`, `SKIP_MIGRATIONS`, `DB_RETRIES`, `DB_RETRY_SLEEP`, `AUTO_CREATE_REFRESH_TOKEN_TABLE`.
  - Seguridad/proxy/headers: `TRUST_PROXY_HEADERS`, `PROXY_FIX_*`, `SECURITY_HEADERS_ENABLED`, `SECURITY_HSTS_*`, `SECURITY_FRAME_OPTIONS`, `SECURITY_CONTENT_TYPE_OPTIONS`, `SECURITY_REFERRER_POLICY`, `SECURITY_CSP`, `SECURITY_PERMISSIONS_POLICY`.
  - Runtime/blueprints/rate limits: `QR_*`, `QV2_SHARED_ACCESS_RATE_LIMIT`, `QV2_TRANSPORT_KEY_RATE_LIMIT`, `QV2_TRANSPORT_KEY_CACHE_TTL_SECONDS`, `PREDICT_RATE_LIMIT`, `OPTIONAL_BLUEPRINTS_STRICT`, `OPTIONAL_BLUEPRINTS_REQUIRED`.
  - Capacidad/conexion: `GUNICORN_*`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `DB_POOL_PRE_PING`, `READINESS_CACHE_TTL_SECONDS`, `READINESS_DB_TIMEOUT_MS`.
  - Documentacion: `SWAGGER_ENABLED`.
- Dependencia formal de base de datos:
  - `SQLALCHEMY_DATABASE_URI` se construye en formato `postgresql+psycopg://...` salvo override.
  - readiness (`/readyz`) ejecuta `SELECT 1`; por tanto, PostgreSQL disponible es condicion de preparacion operativa.
- Dependencia de DB operativa:
  - readiness (`/readyz`) depende de `SELECT 1` contra DB y aplica TTL corto para control de costo bajo concurrencia.
- Migraciones:
  - flujo recomendado `alembic upgrade head`.
  - existe migracion `20251210_01_fix_user_session_defaults.py` que asume tabla `user_session` preexistente.
- Arranque local recomendado (verificado en repo):
  - crear entorno virtual;
  - `pip install -r requirements.txt`;
  - configurar `.env`;
  - `alembic upgrade head`;
  - `python run.py`.
- Politica de blueprints opcionales en `api/app.py` con fail-fast configurable.
- Scripts operativos visibles:
  - `run.py`
  - `scripts/bootstrap_questionnaire_backend_v2.py`
- Documentacion operativa versionada relevante:
  - `docs/openapi.yaml`
  - `docs/api_full_reference.md`
  - `docs/questionnaire_backend_architecture.md`
  - `docs/model_registry_and_inference.md`
  - `docs/reporting_and_dashboards.md`
  - `docs/problem_reporting_backend.md`
  - `docs/security_hardening_20260416.md`
- Fuente OpenAPI activa:
  - `docs/openapi.yaml`.

### 9.2 Contexto operativo proporcionado por el proyecto (externo al repo)
Esta subseccion integra contexto operativo oficial entregado por el proyecto y **no debe interpretarse como evidencia directa de codigo versionado**.

#### 9.2.1 Evolucion de despliegue
- Etapa cloud previa:
  - frontend en Vercel
  - backend en Render
  - auto deploy por Git en ambas plataformas.
- Etapa objetivo:
  - entorno self-hosted en Ubuntu para reemplazo gradual de cloud.

#### 9.2.2 Arquitectura operativa Ubuntu objetivo
- Ubuntu base.
- Docker Engine + Docker Compose.
- PostgreSQL contenedorizado local.
- Backend contenedor independiente.
- Frontend contenedor independiente (Vite + Nginx).
- Gateway Nginx interno como reverse proxy.
- Cloudflare Tunnel (cloudflared) para publicacion publica sin exponer IP/puertos inbound publicos.
- UFW + OpenSSH Server.

#### 9.2.3 Dominio y red
- Dominio `cognia.lat` publicado via Cloudflare Tunnel.
- Puertos `80/443` limitados a LAN por UFW.
- Backend no expuesto directamente a Internet.
- Flujo operativo de trafico declarado:
  - Internet entra por Cloudflare Tunnel.
  - LAN puede acceder por IP local segun politica.
  - backend sin exposicion directa publica.
- Operacion SSH declarada:
  - OpenSSH Server activo para administracion remota;
  - validacion con `sshd -t`;
  - endurecimiento progresivo hacia llaves publicas.

#### 9.2.4 Automatizacion
- Cloud previo: auto deploy nativo Render/Vercel.
- Self-hosted objetivo: GitHub Actions + self-hosted runners por repo (backend/frontend) con rebuild Docker Compose.
- El proyecto considera ya resueltos:
  - runners self-hosted estables/validados,
  - backups + restore test DB,
  - publicacion estable por Cloudflare Tunnel.
- Implicacion practica declarada:
  - con servidor encendido, deploy casi inmediato tras push;
  - con servidor apagado, jobs pueden quedar en cola temporal;
  - por dependencia fisica del hardware local, no se asume operacion unica definitiva mientras persista riesgo electrico.

#### 9.2.5 Estado de transicion
Segun contexto operativo del proyecto, el cierre total de migracion cloud->self-hosted aun depende de:
- estabilidad electrica/hardware del servidor local,
- consolidacion productiva final del backend,
- endurecimiento suficiente de acceso/administracion.

Mientras eso no cierre, Render/Vercel permanecen como soporte temporal de continuidad.

#### 9.2.6 Infraestructura externa relevante (contexto declarado)
- GitHub como origen de codigo/eventos de despliegue.
- Cloudflare como DNS/publicacion por Tunnel.
- PostgreSQL como persistencia.
- SMTP si se activa modulo de correo.
- `unpkg.com` para assets de Swagger UI.
- Render y Vercel como continuidad temporal durante la transicion.

#### 9.2.7 Notas operativas complementarias declaradas
- Render/Vercel deben documentarse como infraestructura cloud de desarrollo/continuidad, no destino final.
- El contexto operativo indica que no hay manifiesto Render formal versionado como contrato principal del backend.
- El mismo contexto reporta evidencia historica de backend publico en Render consumido por frontend (`https://cognia-api.onrender.com`) durante fase cloud.
- La estrategia de reemplazo definitivo cloud->self-hosted se considera abierta hasta cumplir conjuntamente:
  - estabilidad electrica/hardware;
  - consolidacion productiva backend;
  - endurecimiento suficiente de acceso/administracion.
- Sintesis operativa declarada por el proyecto:
  - desarrollo/continuidad temporal: backend Render + frontend Vercel;
  - entorno objetivo: Ubuntu self-hosted con Docker Compose, PostgreSQL local, gateway Nginx y Cloudflare Tunnel;
  - automatizacion objetivo: GitHub Actions con self-hosted runners ya estabilizados segun contexto del proyecto.

## 10) Calidad y pruebas
Evidencia verificable en repo:
- framework de pruebas: `pytest`.
- pruebas de `/api/predict`: `tests/test_predict.py`.
- guardrail runtime/OpenAPI: `tests/contracts/test_openapi_runtime_alignment.py`.
- guardrails de docs/swagger/metrics: `tests/test_docs_metrics.py`.
- seguridad/hardening: `tests/test_security_hardening.py`, `tests/test_auth.py`, `tests/test_problem_reports.py`, `tests/api/test_app_blueprint_policy.py`.
- pruebas de runtime/v2: `tests/api/test_questionnaire_runtime_api.py`, `tests/api/test_questionnaire_v2_api.py`, `tests/services/test_questionnaire_v2_loader.py`, `tests/smoke/test_questionnaire_runtime_smoke.py`.

Ejecucion en esta ventana:
- `pytest tests/test_predict.py tests/contracts/test_openapi_runtime_alignment.py tests/test_docs_metrics.py tests/test_security_hardening.py -q` -> **13 passed**.
- `pytest tests/contracts/test_openapi_documentation_quality.py -q` -> **falla** (deuda documental de formato en descripciones OpenAPI).

Vacios observables:
- no se ejecuta aqui `pytest -q` completo de todo el repositorio;
- guardrail de calidad documental OpenAPI no esta verde en este estado local.

## 11) Limitaciones verificadas del backend
- `/api/predict` no representa toda la plataforma actual; es flujo legacy acotado.
- v2 puede usar fallback heuristico cuando artefacto de modelo no esta disponible o falla carga/ejecucion.
- runtime v1 fuera de testing depende de artefactos de champions en filesystem.
- coexisten contratos v1 legacy + v2; el consumidor debe distinguirlos para evitar interpretaciones incorrectas.
- hay brechas documentales historicas (ej. narrativa de retiro de endpoints v1 vs runtime montado).
- el sistema no debe presentarse como diagnostico automatico.

## 12) Notas metodologicas y advertencias
- Evidencia de backend util para screening/apoyo profesional en entorno simulado.
- No hay base para afirmar validacion clinica definitiva ni sustitucion del juicio profesional.
- Donde no hay confirmacion estricta en artefactos/rutas de modelo, se debe mantener etiqueta `por confirmar`.

## 13) Fuentes internas consultadas
- `README.md`
- `AGENTS.md`
- `docs/openapi.yaml`
- `docs/OPENAPI_GUIDE.md`
- `docs/model_registry_and_inference.md`
- `docs/questionnaire_backend_architecture.md`
- `docs/security_hardening_20260416.md`
- `api/app.py`
- `api/routes/*.py`
- `api/schemas/*.py`
- `api/services/*.py`
- `core/models/predictor.py`
- `config/settings.py`
- `run.py`
- `tests/*`
- `docs/backend_endpoint_matrix.csv` (anexo tecnico generado en esta ventana)
