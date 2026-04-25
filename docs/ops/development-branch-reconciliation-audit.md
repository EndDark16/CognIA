# Development Branch Reconciliation Audit

Fecha: 2026-04-25

Repositorio: `EndDark16/CognIA`

Rama objetivo: `development`

Base auditada antes de cambios: `origin/development` en `136a683`

## Metodologia

1. Se ejecuto `git fetch --all --prune`.
2. Se auditaron todas las ramas remotas visibles excepto `origin/HEAD`.
3. Para cada rama se calculo `ahead/behind` contra `origin/development` con `git rev-list --left-right --count origin/development...<rama>`.
4. Se compararon archivos criticos:
   - `.github/workflows/`
   - `scripts/`
   - `.deploy/`
   - `Dockerfile`
   - `.dockerignore`
   - `docker-compose.yml`
   - `docker/`
   - `requirements.txt`
   - `.env.example`
   - `README.md`
   - `alembic.ini`
   - `run.py`
   - `api/`
   - `app/`
   - `config/`
5. Se reviso historial de workflows con `git log --all -- .github/workflows/...`.
6. Se inspeccionaron versiones de workflow en ramas con deriva operativa.

Nota de ejecucion: los workflows estaban desactivados temporalmente fuera del repo. Esta auditoria no depende de ejecuciones remotas y deja los YAML listos para reactivacion controlada.

## Inventario de ramas remotas

| Rama | Ahead vs development | Behind vs development | Archivos criticos distintos | Decision |
|---|---:|---:|---:|---|
| `chore/deploy-gateway-recreate-separate` | 1 | 26 | 1 | Aplicar idea util manualmente: separa rebuild de backend y recreacion de gateway. |
| `chore/repo-standards` | 0 | 129 | 0 | Ignorar; totalmente superada por `development`. |
| `chore/workflow-ci-deploy-sync` | 1 | 27 | 2 | Ignorar como version intermedia; introdujo workflow duplicado/legado. |
| `dev.enddark` | 0 | 30 | 0 | Ignorar para esta reconciliacion; no tiene delta critico contra `development`. |
| `development` | 0 | 0 | 0 | Rama base. |
| `docs/readme-overhaul-2026-04-22` | 1 | 30 | 1 | Ignorar; cambio documental viejo y parcialmente absorbido. |
| `feat/api-docs` | 0 | 129 | 0 | Ignorar; superada. |
| `feat/backend-ubuntu-selfhosted-deploy-v1` | 2 | 29 | 7 | Tomar criterio, no cherry-pick: contiene separacion CI/deploy pero es vieja y carece de MFA deterministica en CI. |
| `feat/backend-ubuntu-selfhosted-deploy-v1-dev` | 0 | 3 | 0 | Ya absorbida o superada. |
| `feat/docs-metrics-render` | 1 | 119 | 5 | Ignorar; rama antigua de startup/docs, alto riesgo de retroceso. |
| `feat/docs-metrics-startup` | 0 | 115 | 0 | Ignorar; superada. |
| `feat/final-aggressive-honest-rescue-v7` | 2 | 26 | 4 | Tomar solo fix de gateway si aplica; no promover cambios de modelado v7 en auditoria ops. |
| `feat/final-aggressive-honest-rescue-v7-only` | 1 | 26 | 3 | Ignorar; modelado v7 no solicitado para consolidacion operativa. |
| `feat/final-aggressive-rescue-v6` | 1 | 28 | 3 | Ignorar; modelado v6 no solicitado para consolidacion operativa. |
| `feat/final-decisive-rescue-v5` | 3 | 26 | 8 | No aplicar; contiene limpieza F401 repetida y cambios de modelado/API no necesarios tras validar Ruff en `development`. |
| `feat/final-repo-deploy-closure` | 0 | 87 | 0 | Ignorar; superada. |
| `feat/openapi-docs` | 0 | 123 | 0 | Ignorar; superada. |
| `feat/openapi-runtime-contract-v6` | 0 | 48 | 0 | Ignorar; superada. |
| `feat/openapi-runtime-hardening-v2` | 0 | 54 | 0 | Ignorar; superada. |
| `feat/openapi-spanish-endpoint-descriptions` | 0 | 5 | 0 | Ya absorbida por `development`. |
| `feat/questionnaire-v1` | 0 | 105 | 0 | Ignorar; superada. |
| `feat/test-hardening` | 0 | 129 | 0 | Ignorar; superada. |
| `feature/admin-colpsic-governance` | 0 | 92 | 0 | Ignorar; superada. |
| `feature/api-platform-hardening-openapi-v1` | 0 | 79 | 0 | Ignorar; superada. |
| `feature/email-smtp-welcome` | 0 | 93 | 0 | Ignorar; superada. |
| `feature/observability-ci` | 0 | 131 | 0 | Ignorar; superada. |
| `feature/validation-user-crud` | 0 | 103 | 0 | Ignorar; superada. |
| `fix/entrypoint-lf` | 0 | 97 | 0 | Ignorar; superada. |
| `fix/final-active-line-audit` | 2 | 0 | 3 | No aplicar; rama de auditoria/modelado, no fix de CI/CD runtime. |
| `fix/openapi-endpoint-smoke-v1` | 0 | 37 | 0 | Ya absorbida o superada. |
| `fix/openapi-requestbody-examples` | 0 | 35 | 0 | Ya absorbida o superada. |
| `fix/openapi-response-examples-pro` | 0 | 33 | 0 | Ya absorbida o superada. |
| `fix/v6-champion-gate-clean` | 1 | 0 | 1 | No aplicar; validacion de modelado v6, no operacion backend. |
| `fix/v6-quick-champion-guard-hotfix` | 0 | 10 | 0 | Ya absorbida o superada. |
| `main` | 0 | 133 | 0 | No usar como fuente; atrasada respecto de `development`. |
| `sync/development-pending-20260424` | 0 | 23 | 0 | Ya absorbida o superada. |
| `sync/local-v7-pending-20260424` | 0 | 23 | 0 | Ya absorbida o superada. |

## Hallazgos principales

### Workflows

- `development` tenia tres workflows backend:
  - `.github/workflows/ci.yml` (`name: CI`)
  - `.github/workflows/ci-backend.yml` (`name: CI Backend`)
  - `.github/workflows/deploy-backend.yml`
- `ci.yml` era legado y redundante:
  - duplicaba pytest y docker build frente a `ci-backend.yml`,
  - no tenia `permissions`,
  - no tenia `concurrency`,
  - no tenia `workflow_dispatch`,
  - no tenia `MFA_ENCRYPTION_KEY` deterministica para CI,
  - no ejecutaba compile/import sanity.
- `ci-backend.yml` era la base correcta, pero perderia el lint de Ruff si se borraba `ci.yml` sin transferir ese gate.
- `deploy-backend.yml` tenia rollback y readyz, pero mantenia el patron fragil:
  - `docker compose up -d --build backend gateway`
- Ninguna version remota de `deploy-backend.yml` revisada incluia verificacion estricta de `github.sha`.
- `chore/deploy-gateway-recreate-separate` y `feat/final-aggressive-honest-rescue-v7` contenian el fix util de gateway:
  - `docker compose up -d --build backend`
  - `docker compose up -d --force-recreate gateway`

### Scripts y runtime

- Las ramas de modelado v6/v7 modifican loaders/scripts de campanas, pero no aportan un fix de CI/CD o runtime seguro para consolidar en esta ventana.
- `feat/final-decisive-rescue-v5`, `sync/development-pending-20260424` y `sync/local-v7-pending-20260424` contienen el mismo commit de limpieza F401. Se valido localmente que `origin/development` ya pasa `ruff check --select F api tests`, por lo que no se trajo ese commit.
- No se encontraron artefactos `.deploy/` versionados en ninguna rama remota.
- La corrida completa de tests revelo una falla documental preexistente en `docs/openapi.yaml` para tres operaciones admin. Se corrigio porque el guardrail contractual es parte del estado operativo limpio de `development`; tambien se normalizaron estados `ACTIVE` residuales a `KEEP_ACTIVE` en health/readiness/metrics.

## Evaluacion antes de actuar

### Cambio 1: eliminar `.github/workflows/ci.yml`

- Por que es correcto: es un workflow backend duplicado y menos completo que `ci-backend.yml`.
- Fuente de verdad usada: comparacion de los YAML en `development` y ramas `feat/backend-ubuntu-selfhosted-deploy-v1` / `chore/workflow-ci-deploy-sync`.
- Riesgo: bajo; reduce checks duplicados y evita ambiguedad de branch protection.
- Metodo elegido: eliminacion directa por parche manual.
- Por que no cherry-pick: los commits que lo borraban venian mezclados con deploy/modelado mas antiguo.

### Cambio 2: conservar `ci-backend.yml` y agregar lint Ruff

- Por que es correcto: `ci-backend.yml` es el CI autoritativo; se preserva el gate de Ruff que antes vivia en `ci.yml`.
- Fuente de verdad usada: `ci.yml` existente y validacion local `python -m ruff check --select F api tests`.
- Riesgo: bajo; Ruff se instala en CI igual que hacia el workflow legado.
- Metodo elegido: parche manual minimo.
- Por que no merge: no hace falta traer ramas completas para un step.

### Cambio 3: robustecer `deploy-backend.yml`

- Por que es correcto: el deploy actual podia dejar el gateway desfasado al reconstruir backend y gateway en un solo comando. El fix disperso en ramas separa backend y recrea gateway forzadamente.
- Fuente de verdad usada: workflow actual de `development` + fix de `origin/chore/deploy-gateway-recreate-separate`.
- Riesgo: medio-bajo; toca deploy self-hosted, pero mantiene rollback y readyz.
- Metodo elegido: parche manual.
- Por que no cherry-pick: el branch fuente no tenia verificacion de `github.sha`, resumen equivalente ni logs de gateway; cherry-pick habria retrocedido partes utiles.

### Cambio 4: documentar auditoria y continuidad

- Por que es correcto: `AGENTS.md` exige reflejar decisiones relevantes tambien en `docs/HANDOFF.md`.
- Fuente de verdad usada: regla de continuidad del repo.
- Riesgo: bajo.
- Metodo elegido: documentacion versionada.

### Cambio 5: corregir guardrail documental OpenAPI

- Por que es correcto: `pytest -q` fallaba por secciones obligatorias y `x-contract-status` invalido; se alinearon tres operaciones admin y estados residuales health/readiness/metrics con el set contractual permitido.
- Fuente de verdad usada: `tests/contracts/test_openapi_documentation_quality.py`.
- Riesgo: bajo; cambio documental sin modificar rutas ni runtime.
- Metodo elegido: parche manual localizado en `docs/openapi.yaml`.
- Por que no merge: no existia una rama remota con este arreglo aislado.

## Cambios aplicados

- Eliminado:
  - `.github/workflows/ci.yml`
- Modificado:
  - `.github/workflows/ci-backend.yml`
    - conserva un unico CI backend autoritativo,
    - instala Ruff,
    - ejecuta `ruff check --select F api tests`,
    - conserva compile/import sanity, `pytest -q` y docker build sanity.
  - `.github/workflows/deploy-backend.yml`
    - agrega `DEPLOY_BRANCH`,
    - valida que `origin/development` coincida con `github.sha`,
    - reconstruye `backend` separado,
    - recrea `gateway` con `--force-recreate`,
    - mantiene readyz y rollback,
    - agrega logs de `gateway`.
  - `README.md`
  - `docs/backend_release_workflow.md`
  - `docs/deployment_ubuntu_self_hosted.md`
  - `docs/openapi.yaml`
  - `AGENTS.md`
  - `docs/HANDOFF.md`
- Agregado:
  - `docs/ops/development-branch-reconciliation-audit.md`

## Cambios no aplicados y motivo

- No se aplicaron ramas v6/v7 de modelado (`feat/final-aggressive-*`, `fix/final-active-line-audit`, `fix/v6-*`) porque no son fixes operativos de CI/CD y tienen impacto metodologico/modelado que requiere auditoria propia.
- No se aplico `feat/docs-metrics-render` porque esta 119 commits detras y toca startup/config de forma amplia; `development` ya contiene hardenings posteriores.
- No se aplico el commit F401 disperso porque el estado actual de `development` ya pasa la validacion Ruff objetivo.
- No se agrego `.deploy/` porque no existe version auditada en ramas remotas.

## Validacion local

- Sintaxis YAML workflows: OK (`ci-backend.yml`, `deploy-backend.yml`).
- Inventario de workflows: OK, solo quedan `ci-backend.yml` y `deploy-backend.yml`.
- Referencias operativas a `docker compose up -d --build backend gateway`: eliminadas de workflows y guias operativas; solo quedan menciones historicas en esta auditoria/continuidad.
- `python -m ruff check --select F api tests`: OK.
- `python -m compileall -q api app config core scripts run.py`: OK.
- Import sanity `from api.app import create_app; app = create_app()`: OK.
- `pytest tests/contracts/test_openapi_documentation_quality.py tests/contracts/test_openapi_runtime_alignment.py -q`: OK, `3 passed`.
- `pytest -q`: OK, `149 passed, 3 skipped`.

## Estado final esperado de workflows

- Deben existir:
  - `.github/workflows/ci-backend.yml`
  - `.github/workflows/deploy-backend.yml`
- Debe desaparecer:
  - `.github/workflows/ci.yml`

Checks recomendados:

- Required: `CI Backend / backend-ci`
- No required: `Deploy Backend (Best Effort) / backend-deploy-best-effort`

## Riesgos residuales

- Los workflows estaban desactivados externamente; falta una ejecucion real controlada al reactivarlos.
- El deploy self-hosted depende de `/opt/cognia/backend`, `/opt/cognia`, Docker Compose y runner `cognia-backend`; eso no se puede validar completamente desde esta maquina.
- La verificacion `github.sha` evita despliegues de un commit distinto al evento. Si se dispara un workflow viejo despues de que `development` avance, fallara de forma intencional antes de mutar el checkout.
- Hay deriva de modelado en ramas v6/v7 que no debe mezclarse con esta correccion operativa sin una decision metodologica separada.
