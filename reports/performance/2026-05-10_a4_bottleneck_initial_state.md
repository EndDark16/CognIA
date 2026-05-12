# 2026-05-10 A4 Bottleneck Attribution - Initial State

## 1) Base de trabajo
- fecha_utc: `2026-05-12T21:04:58Z`
- rama_a4: `perf/a4-bottleneck-attribution`
- sha_base: `c36cd5ba0669697a04a38f53fefd3dc38454d2c3`
- repo: `EndDark16/CognIA`
- objetivo_a4: atribucion forense de cuello primario/secundario/descartado con correlacion real entre k6, logs, host/docker/red y DB cuando haya acceso.

## 2) Alcance operativo A4
- diagnostico e instrumentacion segura (sin cambios breaking).
- medicion controlada con scripts versionados.
- correlacion automatizada en artefactos reproducibles.
- no cambio de contratos publicos API.

## 3) Confirmacion de no cambios API (regla maxima)
- no se cambian endpoints existentes.
- no se cambian paths/metodos/inputs/query params/outputs JSON/campos/codigos esperados.
- no se toca frontend.
- no se tocan modelos clinicos, thresholds ni artefactos ML.
- cualquier ajuste de codigo es interno/opcional/backward-compatible.

## 4) Estado de archivos protegidos (workspace original)
Comando ejecutado:
- `git status --short -- scripts/hardening_second_pass.py scripts/rebuild_dsm5_exact_datasets.py scripts/run_pipeline.py scripts/seed_users.py tests/test_health.py`

Resultado:
- `M scripts/hardening_second_pass.py`
- `M scripts/rebuild_dsm5_exact_datasets.py`
- `M scripts/run_pipeline.py`
- `M scripts/seed_users.py`
- `M tests/test_health.py`

Nota:
- para no intervenir esos archivos se trabajo en worktree limpio `../cognia_app_a4` desde `origin/main`.

## 5) Accesos disponibles / no disponibles (estado actual de esta ventana)
- SSH al servidor: `por confirmar` (cliente `ssh` disponible localmente, credenciales/host remoto no configurados en esta ventana).
- Docker: `disponible` local (`docker` detectado).
- logs backend: `parcial` (capturables via docker local; acceso a logs de produccion remoto `por confirmar`).
- Supabase dashboard/SQL: `por confirmar` (cliente `psql` no detectado; acceso por consola/dashboard no provisto en esta ventana).
- Cloudflare/CDN/WAF logs: `no disponible` en esta ventana.
- metricas host: `disponible` local (snapshot scripts macOS/Linux).
- acceso consola local: `disponible`.
- `docs/traceability_map.md`: `por confirmar` (archivo no encontrado en esta rama base).

## 6) Hipotesis A4 a evaluar (resumen)
- CPU bound
- RAM/swap/memory pressure
- red domestica
- Supabase/DB remoto
- SQLAlchemy pool
- Gunicorn workers/threads
- cache miss/warmup/per-worker cache
- WAF/CDN
- endpoint especifico
- lock/overhead interno de metricas

## 7) Evidencia inicial generada
- este reporte: `reports/performance/2026-05-10_a4_bottleneck_initial_state.md`
- rama tecnica A4 creada desde `main` actualizado con SHA base registrado.
