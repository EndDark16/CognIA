# CognIA - Backend
Backend de la tesis "Aplicativo web con Random Forest para la alerta temprana de cinco trastornos psicologicos en ninos de 6 a 11 anos". Expone una API REST que procesa datos clinicos/psicologicos estructurados, aplica un modelo de Random Forest y devuelve alertas de riesgo. Solo trabaja con datos simulados o anonimizados y funciona como apoyo temprano, no como diagnostico clinico definitivo.

## Contexto academico y objetivo del proyecto
Trabajo de grado de Ingenieria de Sistemas y Computacion en la Universidad de Cundinamarca, extension Facatativa, dentro del grupo de investigacion GISTFA. Atiende la necesidad de apoyar la deteccion temprana de trastornos frecuentes en la infancia (conducta, TDAH, eliminacion, ansiedad y depresion) donde la falta de herramientas objetivas y la deteccion tardia impactan el bienestar infantil. El backend recibe datos estructurados, ejecuta el modelo de Random Forest y expone resultados via API para integrarse con clientes web o moviles.

## Arquitectura general del backend
- Framework: Flask con Blueprints, CORS y configuraciones por entorno.
- Capas: rutas/controladores (api/routes), esquemas de validacion (api/schemas), servicios de dominio (api/services), utilidades y carga de modelos (core/models), configuracion (config).
- Modelo de ML: archivos .pkl en models/ cargados con core/models/predictor.py (ej. models/adhd_model.pkl).
- Configuracion: clases DevelopmentConfig, ProductionConfig y TestingConfig en config/settings.py; variables .env para MONGO_URI, MODEL_PATH, SECRET_KEY.
- Modelo de datos: ver `docs/database_schema.md` (incluye schemas Supabase y tablas public).

Flujo de peticion:
```
HTTP POST /api/predict
 -> Blueprint predict (api/routes/predict.py)
 -> Validacion con Marshmallow (api/schemas/predict_schema.py)
 -> Servicio predict_all_probabilities (api/services/model_service.py)
 -> Carga de modelo Random Forest desde models/ (core/models/predictor.py)
 -> Respuesta JSON con probabilidades
```

## Tecnologias y dependencias principales
- Lenguaje: Python 3.12+.
- Web: Flask 3.x, Flask-CORS, Flask-JWT-Extended, Flask-Limiter.
- ML y datos: scikit-learn, pandas, numpy, seaborn/matplotlib para analisis.
- Validacion: marshmallow.
- Base de datos: PostgreSQL 16 via SQLAlchemy/psycopg + Alembic para migraciones.
- Configuracion y despliegue: python-dotenv, gunicorn (Linux/macOS).
- Pruebas: pytest.

## Funcionalidades principales del backend
### Gestion de usuarios y seguridad
- Autenticacion JWT (Access/Refresh Tokens) y RBAC implementados.
- Base de usuarios y sesiones en PostgreSQL.
- Hash de contraseñas con bcrypt.
- Validaciones de registro (formato de email/username) y bloqueo temporal por intentos fallidos de login.

### Gestion de evaluaciones
- El endpoint disponible procesa una evaluacion simulada via POST /api/predict y retorna probabilidades de riesgo (actualmente TDAH). Campos requeridos: age, sex, conners_inattention_score, conners_hyperactivity, cbcl_attention_score, sleep_problems. No se almacenan datos; se espera uso anonimo/simulado.

### Motor de IA (Random Forest)
- Inferencia: api/services/model_service.py prepara el DataFrame y llama a predict_proba (en core/models/predictor.py), cargando el modelo desde models/adhd_model.pkl.
- Modelo: clasificador Random Forest entrenado con datos simulados (pipeline en scripts/train_model.py). La respuesta actual devuelve la probabilidad para TDAH; otras condiciones se planean.

### Registro, metricas y logging
- Logging basico activado en modo no debug (configuracion de logging en api/app.py).
- Logging por request configurable via `LOG_REQUESTS`, `LOG_LEVEL`, `LOG_FORMAT` y `LOG_EXCLUDE_PATHS`.
- Endpoints de observabilidad: `/healthz`, `/readyz`, `/metrics` (ver seccion de Observabilidad).
- Scripts de entrenamiento imprimen classification_report de scikit-learn para evaluar precision/recall/specificidad de forma local.

## Estructura del proyecto
```
cognia_app/
|-- api/
|   |-- app.py              # Fabrica Flask y registro de blueprints/extensiones
|   |-- routes/             # Endpoints (auth, predict)
|   |-- schemas/            # Validacion de entrada (Marshmallow)
|   |-- services/           # Logica de negocio (p.ej. model_service)
|   |-- decorators.py       # Decoradores de RBAC/JWT
|   |-- extensions.py       # Instancias compartidas (limiter)
|   |-- security.py         # Utilidades de hash de password y auditoria
|-- app/
|   |-- models.py           # Modelos SQLAlchemy (PostgreSQL)
|-- config/
|   |-- settings.py         # Config por entorno (.env)
|-- migrations/             # Migraciones Alembic
|-- core/
|   |-- models/predictor.py # Carga de modelos ML y helpers
|-- models/                 # Artefactos entrenados (.pkl)
|-- data/                   # Datasets simulados (CSV)
|-- scripts/                # Entrenamiento/analisis (train_model.py)
|-- tests/                  # Pruebas (p.ej. test_auth.py)
|-- run.py                  # Punto de entrada en desarrollo
|-- requirements.txt        # Dependencias
```

## Migraciones (Alembic)
- Config por defecto toma `config.settings.DevelopmentConfig`. Cambia con `APP_CONFIG_CLASS=config.settings.ProductionConfig` al correr comandos.
- Crear nueva revision: `alembic revision --autogenerate -m "mensaje"`
- Aplicar migraciones: `alembic upgrade head`
- Baseline incluida: crea la tabla `refresh_token` si falta (segura en entornos donde ya existe).

## Auth con cookies (refresh) y MFA
- El refresh token nunca viaja en el body. Se devuelve como cookie HttpOnly `refresh_token` (Path=/api/auth/refresh) protegida con CSRF doble submit (`csrf_refresh_token` cookie y header `X-CSRF-Token`).
- Access token sigue en JSON (`access_token`). Para usar refresh/logout: enviar cookies y el header CSRF.
- En cliente (fetch/axios): `credentials: "include"` + header `X-CSRF-Token` con el valor de `csrf_refresh_token`.
- CORS: al usar credenciales no se permite `origins="*"`. Define `CORS_ORIGINS` (coma-separado) en .env.
- MFA obligatorio para roles `ADMIN` y `PSYCHOLOGIST/PSICOLOGO`. Si no esta habilitado, el login devuelve `mfa_enrollment_required` y un `enrollment_token` de vida corta para activar MFA. Usuarios con MFA activo deben completar login en 2 pasos (`/auth/login` -> `/auth/login/mfa`).
- MFA usa TOTP (pyotp) con secreto cifrado (Fernet). Debes definir `MFA_ENCRYPTION_KEY` (base64 urlsafe de 32 bytes) en entorno.
- Onboarding MFA (roles privilegiados): usa el `enrollment_token` solo en `/api/mfa/setup` y `/api/mfa/confirm`. Hasta completar el MFA no se emiten access/refresh tokens normales.
- CSRF en refresh/logout: si falta o no coincide el header `X-CSRF-Token`, responde 403 con `error: "csrf_failed"`. El valor de `csrf_refresh_token` rota en cada `/api/auth/refresh`, así que el cliente debe leer la nueva cookie después de refrescar.
- Logout revoca todos los refresh tokens del usuario (logout all) para evitar reuso.
- Errores estandarizados: todas las respuestas de error incluyen `{"msg": "...", "error": "<codigo>"}`. Ejemplos: `invalid_credentials`, `mfa_required`, `mfa_enrollment_required`, `csrf_failed`, `token_revoked`, `user_exists`.
- Roles/RBAC: el access token incluye `roles` y las rutas sensibles deben protegerse con `roles_required(...)`. El frontend puede redirigir segun roles, pero la validacion real debe ocurrir en el backend.

### Flujo de login y MFA (resumen)
- Login normal (usuario sin MFA requerido): `/api/auth/login` devuelve `access_token` y cookies `refresh_token` + `csrf_refresh_token`.
- Login con MFA activo: `/api/auth/login` devuelve `mfa_required` + `challenge_id` (sin cookies); luego `/api/auth/login/mfa` emite tokens normales.
- Login con MFA requerido pero no habilitado: `/api/auth/login` devuelve `mfa_enrollment_required` + `enrollment_token` (sin cookies). Ese token solo sirve para `/api/mfa/setup` y `/api/mfa/confirm`.
- Tras confirmar MFA, el usuario debe volver a hacer login para obtener access/refresh tokens normales.

### MFA onboarding (detallado)
- Credenciales validas: `/api/auth/login` responde 200. El cliente decide el flujo segun el payload.
- `access_token`: login completo + cookies refresh/csrf.
- `mfa_required`: `challenge_id` + `expires_in` (sin cookies); continuar con `/api/auth/login/mfa`.
- `mfa_enrollment_required`: `enrollment_token` + `expires_in` (sin cookies); solo sirve para `/api/mfa/setup` y `/api/mfa/confirm`.
- El enrollment token incluye `mfa_enrollment=true` y `roles=[]`; no permite refresh/logout ni `/api/mfa/disable`.
- `MFA_ENROLL_TOKEN_TTL` define la vida del enrollment token (default 600s).
- `/api/mfa/confirm` devuelve `recovery_codes` una sola vez; guardalos offline.
- Tras confirmar MFA, se debe hacer login de nuevo para obtener access/refresh tokens normales.

## Requisitos previos
- Python 3.12 o superior.
- Sistemas: Linux, macOS o Windows.
- Herramientas: git, pip, entorno virtual (venv o similar).
- PostgreSQL 16 local (para Auth).

## Configuracion e instalacion
1) Clonar el repositorio:
   ```
   git clone <URL_DEL_REPO>
   cd cognia_app
   ```
2) Crear y activar entorno virtual:
   - Windows:
     ```
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - Linux/macOS:
     ```
     python -m venv venv
     source venv/bin/activate
     ```
3) Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```
4) Crear archivo .env en la raiz:
   ```
   SECRET_KEY=dev-secret-key
   MODEL_PATH=models/adhd_model.pkl
   DB_USER=postgres
   DB_PASSWORD=your_db_password
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=cognia_db
   # Si usas Supabase u otro servicio que exige TLS:
   # DB_SSL_MODE=require
   MFA_ENCRYPTION_KEY=base64-urlsafe-32bytes-key
   MFA_ENROLL_TOKEN_TTL=600
  # Migraciones (rol db_migrator)
  # MIGRATION_DB_USER=db_migrator
  # MIGRATION_DB_PASSWORD=your_migrator_password
  # RUN_MIGRATIONS=false   # opcional: deshabilita migraciones en arranque (Render)
  # Logging/Metrics
  # LOG_LEVEL=INFO
  # LOG_REQUESTS=true
  # LOG_EXCLUDE_PATHS=/healthz,/readyz,/metrics
  # METRICS_ENABLED=true
  # METRICS_TOKEN=un_token_opcional
  # METRICS_TOKEN_REQUIRED=false
  # Email (SMTP)
  # EMAIL_ENABLED=false
  # EMAIL_SEND_ASYNC=true
  # EMAIL_FROM="CognIA <no-reply@tu-dominio.com>"
  # EMAIL_REPLY_TO="soporte@tu-dominio.com"
  # EMAIL_LIST_UNSUBSCRIBE="<mailto:unsubscribe@tu-dominio.com>"
  # SMTP_HOST=smtp.tu-proveedor.com
  # SMTP_PORT=587
  # SMTP_USER=tu_usuario
  # SMTP_PASSWORD=tu_password
  # SMTP_USE_TLS=true
  # SMTP_USE_SSL=false
  # SMTP_TIMEOUT=10
  # Auth hardening
  # MAX_LOGIN_ATTEMPTS=5
  # LOGIN_LOCKOUT_MINUTES=15
  # RECOVERY_CODE_MAX_AGE_DAYS=90
  # Rate limits
  # REGISTER_RATE_LIMIT=5 per 10 minutes
  # LOGIN_RATE_LIMIT=5 per 15 minutes
  # LOGIN_MFA_RATE_LIMIT=5 per 10 minutes
  # MFA_SETUP_RATE_LIMIT=3 per 10 minutes
  # MFA_CONFIRM_RATE_LIMIT=5 per 10 minutes
  # MFA_DISABLE_RATE_LIMIT=3 per 10 minutes
  # Evaluations
  # EVALUATION_MIN_AGE=6
  # EVALUATION_MAX_AGE=11
  # EVALUATION_ALLOWED_STATUSES=draft,submitted,completed
   # RATE_LIMIT_STORAGE_URI=redis://localhost:6379/0   # opcional, para rate limiting profesional
   # Startup
   # AUTO_CREATE_REFRESH_TOKEN_TABLE=false
   # APP_HOST=0.0.0.0
   # PORT=5000
   # DUALSTACK=true
   ```

## Ejecucion en desarrollo
1) Activar el entorno virtual.
2) Iniciar la API:
   ```
   python run.py
   ```
   - Host: 0.0.0.0
   - Puerto por defecto: 5000
3) Verificar enviando una peticion a POST http://localhost:5000/api/predict (ver ejemplos abajo).

### Nota sobre inicio y base de datos
- Por defecto la app no fuerza conexion a la BD al arrancar. La disponibilidad real se verifica en `/readyz`.
- Si necesitas auto-crear la tabla `refresh_token` al inicio (solo dev), activa `AUTO_CREATE_REFRESH_TOKEN_TABLE=true`.

## Ejecucion en produccion
- Ejemplo con gunicorn (Linux/macOS):
  ```
  gunicorn -w 4 -b 0.0.0.0:8000 run:app
  ```
- Recomendaciones: usar reverse proxy (Nginx), gestionar variables de entorno y certificados TLS, y agregar autenticacion/autorizacion antes de exponer publicamente. En Windows usar un servidor WSGI alternativo o contenedor Docker.
- En Render (free tier), el entrypoint ajusta workers/threads segun memoria disponible. Si necesitas forzar, usa `GUNICORN_WORKERS=1` y `GUNICORN_THREADS=2-4` como punto de partida y ajusta con pruebas de carga.

## Entrenamiento y actualizacion del modelo de IA
- Script principal: scripts/train_model.py
  - Dataset esperado: data/adhd_dataset_simulated.csv (simulado/anonimizado).
  - Ejecucion:
    ```
    python scripts/train_model.py
    ```
  - Salida: models/adhd_model.pkl (cargado por el backend para inferencia).
- Para usar un modelo nuevo, coloque el .pkl en models/ y asegure que MODEL_PATH apunte a esa ruta si se modifica el nombre.
- Entrenamiento solo con datos simulados o anonimizados; nunca use informacion identificable de menores.

## Uso de la API
### POST /api/predict
- Descripcion: calcula probabilidades de riesgo (actualmente TDAH) a partir de una evaluacion estructurada.
- Cuerpo JSON requerido:
```json
{
  "age": 10,
  "sex": 1,
  "conners_inattention_score": 12.5,
  "conners_hyperactivity": 8.1,
  "cbcl_attention_score": 14.0,
  "sleep_problems": 0
}
```
- Respuesta exitosa (200):
```json
{
  "predictions": {
    "adhd": 0.42
  }
}
```
- Errores de validacion (400):
```json
{
  "errors": {
    "age": ["Must be greater than or equal to 3."]
  }
}
```
- Otros codigos: 500 en caso de error interno del servidor.

### Questionnaires y evaluaciones (v1)
Flujo recomendado (admin):
1) Crear plantilla (inactiva): `POST /api/v1/questionnaires`
2) Agregar preguntas: `POST /api/v1/questionnaires/{template_id}/questions`
3) Activar plantilla: `POST /api/v1/questionnaires/{template_id}/activate`
4) Para nueva version: `POST /api/v1/questionnaires/active/clone` y luego activar.

Consumo UI (padre/tutor):
- Obtener plantilla activa: `GET /api/v1/questionnaires/active`

Registro de evaluacion:
- Crear evaluacion: `POST /api/v1/evaluations` (siempre enlaza la plantilla activa).

Tipos de respuesta permitidos:
- `likert_0_4`: escala 0-4
- `likert_1_5`: escala 1-5
- `boolean`: 0/1
- `frequency_0_3`: 0=never, 1=sometimes, 2=often, 3=always
- `intensity_0_10`: escala 0-10
- `count`: conteos (n veces)
- `ordinal`: escala ordinal codificada
- `text_context`: texto libre solo para contexto (no entra al modelo)

Validacion data-driven (opcional por pregunta):
- `response_min` / `response_max`: rangos numericos permitidos.
- `response_options`: lista de valores permitidos (ordinal/codificada).
- `response_step`: paso permitido (por ejemplo 1).
- Si no se define constraint, se valida el rango por defecto segun `response_type`.

Trastornos por pregunta:
- `disorder_id`: legado (un solo trastorno).
- `disorder_ids`: recomendado para asociar uno o mas trastornos a la misma pregunta.

### Seed de cuestionario demo
- Script: `scripts/seed_questionnaire_demo.py` (idempotente).
- Por defecto crea la plantilla inactiva; para activarla:
  - `SEED_TEMPLATE_ACTIVE=true`
- Ejemplo:
  ```bash
  APP_CONFIG_CLASS=config.settings.DevelopmentConfig \
  SEED_TEMPLATE_ACTIVE=true \
  python scripts/seed_questionnaire_demo.py
  ```

## Auth Testing
Instrucciones rapidas para probar la autenticacion (ajusta la URL si es necesario):

### Register
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"t@t.com","password":"P4ssw0rd!","full_name":"Test User","user_type":"guardian"}'
```
-> Nota: si `user_type` es `psychologist`, debes enviar `professional_card_number` (Tarjeta Profesional COLPSIC).

### Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"P4ssw0rd!"}'
```
-> Respuesta: `access_token` en JSON y cookies `refresh_token` (HttpOnly, Path=/api/auth/refresh) y `csrf_refresh_token` (para header CSRF). Si el usuario tiene MFA activo devuelve `{ "mfa_required": true, "challenge_id": "...", "expires_in": 300 }` (sin cookies). Si el rol requiere MFA y no está habilitado devuelve `{ "mfa_enrollment_required": true }` (sin tokens).
-> Nota: cuando las credenciales son validas, `/api/auth/login` devuelve 200 con uno de los payloads (`access_token`, `mfa_required` o `mfa_enrollment_required`). El frontend debe ramificar por campo, no por status.

### Login MFA (cuando `mfa_required: true`)
```bash
curl -X POST http://localhost:5000/api/auth/login/mfa \
  -H "Content-Type: application/json" \
  -d '{"challenge_id":"<challenge_id>","code":"123456"}'
```
-> Respuesta: `access_token` en JSON y set-cookie de `refresh_token` + `csrf_refresh_token`.

### Refresh
```bash
curl -X POST http://localhost:5000/api/auth/refresh \
  -H "X-CSRF-Token: <csrf_refresh_token_from_cookie>" \
  --cookie "refresh_token=<refresh_token_cookie>; csrf_refresh_token=<csrf_refresh_token_from_cookie>"
```

### Logout
```bash
curl -X POST http://localhost:5000/api/auth/logout \
  -H "Authorization: Bearer <access_token>" \
  -H "X-CSRF-Token: <csrf_refresh_token_from_cookie>" \
  --cookie "refresh_token=<refresh_token_cookie>; csrf_refresh_token=<csrf_refresh_token_from_cookie>"
```

### MFA setup / confirm
Nota: si el login devolvio `enrollment_token`, usa `Authorization: Bearer <enrollment_token>` en estos endpoints.

```bash
# 1) Obtener secreto / otpauth_uri (requiere access token)
curl -X POST http://localhost:5000/api/mfa/setup \
  -H "Authorization: Bearer <access_token>"

# 2) Confirmar TOTP generado con tu app (Google Authenticator, Authy, etc.)
curl -X POST http://localhost:5000/api/mfa/confirm \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"code":"123456"}'
```
-> Devuelve recovery codes (guárdalos en un lugar seguro, se entregan una sola vez).

### Administracion de usuarios (RBAC)
Requiere rol `ADMIN` (Bearer access token).

- Listar usuarios: `GET /api/v1/users?page=1&page_size=20`
- Obtener usuario: `GET /api/v1/users/{user_id}`
- Crear usuario: `POST /api/v1/users`
- Actualizar usuario: `PATCH /api/v1/users/{user_id}`
- Desactivar usuario (soft delete): `DELETE /api/v1/users/{user_id}`

Notas:
- `user_type` es obligatorio en alta. Si es `psychologist`, debes enviar `professional_card_number`.
- `roles` es opcional; si se envia, se reemplaza el set de roles del usuario.

### Emails transaccionales
- Actualmente se envia un **correo de bienvenida** al registrar usuarios (via SMTP).
- Recomendado en produccion: configurar SPF/DKIM/DMARC en tu dominio para evitar spam.
- En entornos de pruebas puedes dejar `EMAIL_ENABLED=false`.

## Despliegue en Docker

### Build local
```bash
docker build -t cognia-app .
```

### Ejecutar solo la app (DB externa ya creada)
```bash
docker run -p 5000:5000 \
  -e APP_CONFIG_CLASS=config.settings.ProductionConfig \
  -e DB_HOST=<host_db> -e DB_PORT=5432 -e DB_USER=postgres -e DB_PASSWORD=<pass> -e DB_NAME=cognia_db \
  -e SECRET_KEY=<secret_key> \
  -e MFA_ENCRYPTION_KEY=<base64_fernet_key> \
  -e CORS_ORIGINS="http://tu-frontend.com" \
  cognia-app
```

### docker-compose (app + Postgres)
1) Define variables sensibles (SECRET_KEY, DB_PASSWORD, MFA_ENCRYPTION_KEY) en tu shell o en un `.env` (no se sube a git).
2) Levanta todo:
```bash
docker compose up --build
```
- Servicio `db`: Postgres 16 con credenciales de `DB_USER/DB_PASSWORD/DB_NAME`.
- Servicio `app`: expone puerto 5000, aplica migraciones Alembic al arrancar y lanza Gunicorn. Por defecto usa `DB_HOST=host.docker.internal` para conectar a tu Postgres del host. Si quieres usar el Postgres del compose, exporta `DB_HOST=db` antes de levantar.
  - Para evitar migraciones automáticas (p. ej. en Render), define `RUN_MIGRATIONS=false` o `SKIP_MIGRATIONS=true`.

### Notas de seguridad en contenedores
- No incluyas `.env` en la imagen (está en `.dockerignore`).
- Pasa secretos solo via variables de entorno o secret manager del orquestador.
- En producción, usa `APP_CONFIG_CLASS=config.settings.ProductionConfig`, `JWT_COOKIE_SECURE=True` ya se aplica automáticamente si no está en debug/testing.

### Baseline completa del esquema (opcional)
- Se agregó una migración baseline condicional `20251215_01_baseline_full_schema.py` con DDL incrustado del esquema completo. Solo se ejecuta si defines `APPLY_FULL_SCHEMA_SQL=1` en el entorno al correr Alembic.
- Uso típico en una BD vacía:
  ```bash
  $env:APPLY_FULL_SCHEMA_SQL="1"
  alembic upgrade head
  ```
  Luego retira la variable para evitar reejecuciones.
- En una BD ya poblada, no habilites `APPLY_FULL_SCHEMA_SQL`; si necesitas marcar estado, usa `alembic stamp head`.

### Roles y credenciales (Supabase / producción)
- Se recomienda usar dos roles:
  - `api_backend`: runtime con privilegios mínimos (DB_USER/DB_PASSWORD).
  - `db_migrator`: solo para migraciones (MIGRATION_DB_USER/MIGRATION_DB_PASSWORD) o `MIGRATION_DATABASE_URI`.
- Ejemplo de URI con SSL para Supabase:
  `postgresql+psycopg://<user>:<password>@db.eiqmbxydrpzotwrppsss.supabase.co:5432/postgres?sslmode=require`
- Alembic usará `MIGRATION_DATABASE_URI` si está presente; si no, puede armarse con `MIGRATION_DB_USER/MIGRATION_DB_PASSWORD` y el resto de variables (`DB_HOST/DB_PORT/DB_NAME/DB_SSL_MODE`).

## Observabilidad (health / ready / metrics)
- `GET /healthz`: liveness básico. Siempre devuelve 200 si la app está viva.
- `GET /readyz`: readiness con chequeo de DB (`SELECT 1`). Devuelve 503 si falla.
- `GET /metrics`: métricas básicas en memoria (por worker): `requests_total`, latencia promedio/max y conteo por status.
  - Puedes protegerlo con `METRICS_TOKEN` (header `Authorization: Bearer <token>`).
  - En Gunicorn multiproceso, cada worker mantiene sus propias métricas (no agregadas).
  - En Swagger UI, usa el candado (Authorize) para enviar el header `Authorization`.

## Documentación API (Swagger/OpenAPI)
- Documentación interactiva: `GET /docs`
- Especificación OpenAPI: `GET /openapi.yaml`
- Postman: importa `http://localhost:5000/openapi.yaml` y tendrás todos los endpoints con ejemplos base.
- Auth:
  - Access: `Authorization: Bearer <access_token>`
  - Refresh: cookie `refresh_token` + header `X-CSRF-Token` (valor de la cookie `csrf_refresh_token`)
  - Si `localhost` falla en tu equipo (IPv6), prueba `http://127.0.0.1:5000/docs` o activa `DUALSTACK=true`.

## Pruebas de carga (k6)
1) Crea un usuario de prueba y anota credenciales.
2) Ejecuta:
```bash
k6 run -e BASE_URL=http://localhost:5000 -e USERNAME=testuser -e PASSWORD=P4ssw0rd! scripts/k6_smoke.js
```
3) Ajusta `GUNICORN_WORKERS/GUNICORN_THREADS` segun latencia, CPU y memoria disponible (el entrypoint usa valores seguros si no se definen).

## CI/CD (GitHub Actions)
- Pipeline básico:
  - Lint rápido con Ruff (errores lógicos/sintaxis).
  - Tests con pytest.
  - Build Docker (sin push).
- Archivo: `.github/workflows/ci.yml`.

## Contribucion
- Lee `CONTRIBUTING.md` para flujo de ramas y checklist de PR.
- Flujo recomendado: `dev.enddark` -> `development` -> `main`.

## Pruebas
- Ejecutar:
  ```
  pytest
  ```
- Los tests actuales son plantillas; se recomienda ampliarlos para cubrir endpoints, validacion y logica de modelo.

## Consideraciones eticas y limitaciones
- Prototipo academico en entorno simulado; no sustituye evaluacion clinica profesional.
- Genera alertas de riesgo, no diagnosticos definitivos.
- No debe usarse con pacientes reales sin aprobacion etica, validacion clinica y cumplimiento legal.
- Los trastornos abordados (conducta, TDAH, eliminacion, ansiedad, depresion) son sensibles; el proyecto busca alinearse con los ODS 3 (salud) y 4 (educacion) promoviendo uso responsable y proteccion de datos.

## Creditos
- Andres Felipe Melo Chaguala - Estudiante investigador
- Johan Thomas Cristancho Silva - Estudiante investigador
- Oscar Jobany Gomez Ochoa - Director
- Universidad de Cundinamarca, grupo de investigacion GISTFA
- Uso academico restringido salvo indicacion contraria (sin licencia explicita en el repositorio).
