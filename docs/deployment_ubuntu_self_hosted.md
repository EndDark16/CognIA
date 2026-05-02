# Deployment Backend to Ubuntu Self-Hosted

## Objetivo
Documentar el flujo operativo real de despliegue del backend CognIA hacia Ubuntu self-hosted, sin bloquear el desarrollo cuando el runner self-hosted este offline.

## Alcance y supuestos operativos
- Rama de despliegue backend: `main`.
- Repo backend en servidor: `/opt/cognia/backend`.
- Compose global en servidor: `/opt/cognia`.
- Servicios compose involucrados en deploy: `backend` y `gateway`.
- Runner self-hosted esperado para deploy: `cognia-backend`.
- Health/readiness del backend:
  - `GET /healthz`
  - `GET /readyz`

## Workflows versionados

### 1) CI normal (GitHub-hosted)
- Archivo: `.github/workflows/ci-backend.yml`
- Runner: `ubuntu-latest`
- Trigger:
  - push a `development` y `main`
  - pull request hacia `development` y `main`
  - `workflow_dispatch`
- Validaciones ejecutadas:
  - instalacion reproducible desde `requirements.txt`
  - compile sanity (`python -m compileall`)
  - import sanity (`create_app()`)
  - `pytest -q`
  - docker build sanity (sin push)

### 2) Deploy backend Ubuntu (self-hosted, best effort)
- Archivo: `.github/workflows/deploy-backend.yml`
- Runner: `[self-hosted, linux, x64, cognia-backend]`
- Trigger:
  - push a `main`
  - `workflow_dispatch`
- Concurrency:
  - `group: deploy-backend-main`
  - `cancel-in-progress: false`

Regla de gobierno:
- Este workflow de deploy es `best effort deployment`.
- NO debe configurarse como required check en branch protection.
- El check requerido para integrar cambios debe ser CI (`ci-backend`).
- Si el runner self-hosted esta offline, CI continua funcionando y el equipo no queda bloqueado.

Checks recomendados para branch protection:
- Required check: `CI Backend / backend-ci`
- No requerido (best effort): `Deploy Backend (Best Effort) / backend-deploy-best-effort`

## Comportamiento exacto del deploy workflow

1. Valida paths esperados del servidor (`/opt/cognia/backend` y `/opt/cognia`).
2. Registra commit previo desplegado (`git rev-parse HEAD`).
3. Actualiza repo local del servidor con:

```bash
cd /opt/cognia/backend
git fetch origin main
git checkout -B main <github.sha>
git reset --hard <github.sha>
```

4. Reconstruye y levanta stack de servicios requeridos:

```bash
cd /opt/cognia
docker compose up -d --build backend
docker compose up -d --force-recreate gateway
```

5. Verifica readiness real contra:

```bash
curl -fsS http://localhost/readyz
```

6. Si el readyz falla, ejecuta rollback automatico basico:
- `git reset --hard <previous_sha>` en `/opt/cognia/backend`.
- vuelve a correr `docker compose up -d --build backend` y `docker compose up -d --force-recreate gateway`.
- reintenta `http://localhost/readyz`.

7. Siempre publica evidencia operativa al final:
- `docker compose ps`
- logs recientes de `backend`.
- logs recientes de `gateway`.

Nota:
- Si el rollback logra recuperar servicio, el job igual queda en fallo para dejar evidencia explicita de que el commit nuevo no quedo activo.

## Como verificar que el deploy quedo activo

En GitHub Actions:
- revisar la corrida de `Deploy Backend (Best Effort)`.
- confirmar en el summary:
  - `Previous SHA`
  - `Target SHA`
  - `Final status=deployed`

En Ubuntu:

```bash
cd /opt/cognia
docker compose ps
docker compose logs --tail=200 backend
curl -fsS http://localhost/healthz
curl -fsS http://localhost/readyz
cd /opt/cognia/backend
git rev-parse HEAD
```

## Rollback manual (operativo)
Si necesitas rollback manual inmediato:

```bash
cd /opt/cognia/backend
git log --oneline -n 20
git reset --hard <commit_anterior_estable>
cd /opt/cognia
docker compose up -d --build backend
docker compose up -d --force-recreate gateway
curl -fsS http://localhost/readyz
```

## Bootstrap desde cero en Ubuntu (resumen)

1. Preparar host con Docker Engine + Compose plugin.
2. Crear/arreglar estructura esperada:
- `/opt/cognia` con `docker compose` funcional.
- `/opt/cognia/backend` con este repo y branch `development`.
3. Garantizar que `docker compose` tenga servicios llamados `backend` y `gateway`.
4. Instalar y registrar GitHub Actions self-hosted runner en ese host.
5. Asignar labels al runner: `self-hosted`, `linux`, `x64`, `cognia-backend`.
6. Levantar runner como servicio del sistema.
7. En branch protection, dejar `CI Backend / backend-ci` como required y `Deploy Backend (Best Effort) / backend-deploy-best-effort` como no requerido.

### Comandos base sugeridos (Ubuntu)
```bash
sudo mkdir -p /opt/cognia
sudo chown -R $USER:$USER /opt/cognia

cd /opt/cognia
git clone <URL_DEL_REPO_BACKEND> backend
cd backend
git checkout development
git pull origin development
```

### Registro de runner self-hosted (ejemplo)
En GitHub (repo settings -> Actions -> Runners) genera el comando con token temporal y luego ejecuta en Ubuntu algo como:

```bash
mkdir -p /opt/cognia/actions-runner
cd /opt/cognia/actions-runner
curl -o actions-runner-linux-x64.tar.gz -L https://github.com/actions/runner/releases/download/v2.327.1/actions-runner-linux-x64-2.327.1.tar.gz
tar xzf actions-runner-linux-x64.tar.gz
./config.sh --url https://github.com/<ORG_O_USER>/<REPO> --token <TOKEN_TEMPORAL> --labels cognia-backend --unattended
sudo ./svc.sh install
sudo ./svc.sh start
```

Verifica labels esperados en GitHub:
- `self-hosted`
- `linux`
- `x64`
- `cognia-backend`

## Seguridad y secretos
- No versionar secretos en el repo.
- Variables sensibles (tokens, credenciales, cloud secrets) deben residir en secretos del entorno/servidor y/o GitHub Secrets segun corresponda.
- Mantener el claim metodologico del proyecto: screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Compatibilidad Render + Vercel y dominio propio
Este repo opera con deploy productivo principal en `main` (self-hosted), pero mantiene compatibilidad con escenarios cloud de continuidad (frontend en Vercel y backend en Render).

Variables clave para ambos escenarios:
- `CORS_ORIGINS`: incluir exactamente el origin del frontend publico.
- `FRONTEND_URL`: URL canónica del frontend para enlaces operativos (password reset/email flows).
- `AUTH_CROSS_SITE_COOKIES=true` cuando frontend y backend estan en dominios distintos.
- `JWT_COOKIE_SAMESITE=None` y `JWT_COOKIE_SECURE=true` para cookies cross-site en HTTPS.
- `JWT_COOKIE_DOMAIN`: opcional; usar solo si se necesita compartir cookie entre subdominios del mismo dominio raiz.

Ejemplo con dominio propio:
- Frontend: `https://app.cognia.lat`
- Backend API: `https://api.cognia.lat`
- Config minima:
  - `CORS_ORIGINS=https://app.cognia.lat`
  - `FRONTEND_URL=https://app.cognia.lat`
  - `AUTH_CROSS_SITE_COOKIES=true`
  - `JWT_COOKIE_SAMESITE=None`
  - `JWT_COOKIE_SECURE=true`
  - `JWT_COOKIE_DOMAIN=.cognia.lat` (solo si aplica sharing cross-subdomain)
