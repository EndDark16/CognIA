# 2026-05-10 A3 Professional Reliability Final Report

## 1) Resumen ejecutivo
- A3 se ejecutó con foco en confiabilidad operativa y rendimiento interno sin cambios contractuales de API.
<<<<<<< HEAD
- El backend desplegado para batería k6 fue `main` en SHA `f69252321cd26d8c5f8657223a0a027183bd52e5`; luego se promovió el paquete final A3 de evidencia/hardening a `main` en SHA `73a3c2cd88c357af473cb29073fba003e91e9f09`.
=======
- El backend desplegado en `main` (`f69252321cd26d8c5f8657223a0a027183bd52e5`) se validó con health checks y batería k6 post-deploy en modo seguro.
>>>>>>> origin/dev.enddark
- Se confirmó estabilidad en `user_journey_read` hasta `30 VUs` en corrida dedicada (error `0.00%`, p95 global `585.41 ms`).
- En `capacity_ladder` 10→30 VUs se volvió a activar corte por criterio de parada en tramo alto (`http_req_failed=5.04%`), sin caída de `healthz/readyz`.
- Se añadió hardening operativo para warmup shell en Windows (`WARMUP_CURL_SSL_NO_REVOKE` + fix parse login token), sin impacto funcional en API.

## 2) Qué se implementó en A3
Cambios internos ya integrados en A3 (previos a esta medición):
- cache backend profesional memory + Redis/Valkey opcional (`fail-open`, `required/optional`, timeouts, JSON serialization)
- fallback seguro de rate limiter a memory
- métricas A3 de backend/cache/rate-limit compatibles hacia atrás
- backpressure configurable para endpoints costosos de qv2/problem reports
- `job_queue_service` opcional para preparación de colas futuras (sin cambiar comportamiento público)
- warmup Python robusto y scripts operativos de captura/snapshot

Ajuste adicional ejecutado en esta ventana A3:
- `scripts/warmup_backend.sh`:
  - flag opcional `WARMUP_CURL_SSL_NO_REVOKE=true`
  - fix de parseo de `access_token` de login en shell warmup
- documentación actualizada:
  - `docs/deployment_performance.md`
  - `docs/load_testing.md`

## 3) Qué se dejó documentado por riesgo
- No se migró submit/PDF/email a cola asíncrona obligatoria.
- No se activó Redis como dependencia requerida en deploy actual.
- No se ejecutó stress destructivo ni pruebas para “romper” el homelab.

## 4) Confirmación de no cambios contractuales
- Frontend no tocado.
- Endpoints existentes no cambiados (paths/métodos).
- Inputs existentes no cambiados.
- Outputs JSON existentes no cambiados.
- Nombres de campos JSON no cambiados.
- Códigos de respuesta esperados no cambiados.
- Modelos clínicos/thresholds/dominios/caveats no tocados.

Evidencia archivos protegidos intactos (repo original con su suciedad preservada):
- comando: `git status --short -- scripts/hardening_second_pass.py scripts/rebuild_dsm5_exact_datasets.py scripts/run_pipeline.py scripts/seed_users.py tests/test_health.py`
- resultado: los 5 archivos siguen `M` y no fueron intervenidos en A3.

## 5) Redis/Valkey (estado A3)
- Implementación: opcional (`CACHE_BACKEND_URI`), con fallback memory.
- Seguridad: sin logging de secretos; serialización JSON; no cache de passwords/tokens.
- Operación: `CACHE_BACKEND_REQUIRED=false`, `CACHE_FAIL_OPEN=true` por defecto.

## 6) Rate limit distribuido
- Estado actual: compatible con `memory://` y `redis://`.
- `RATE_LIMIT_FAIL_OPEN=true` evita caída total por storage compartido no disponible.
- Formato de 429 existente preservado.

## 7) Backpressure interno
- Límites configurables ya activos para rutas costosas (`submit`, `pdf`, `dashboards`, `save_answers`, `session_create`, problem reports create).
- No cambia respuestas de éxito ni contratos públicos.

## 8) Warmup A3
- Python warmup: exitoso (`200` en todas las rutas objetivo).
- Shell warmup:
  - fallo inicial por Schannel revocation en Windows
  - corregido con flag opcional y fix de parse login token
  - reintento exitoso (`200` en todas las rutas)
- Evidencia:
  - `artifacts/load_tests/2026-05-10_a3_postopt_warmup/warmup.log`
  - `artifacts/load_tests/2026-05-10_a3_postopt_warmup/warmup_shell.log`
  - `reports/load_tests/2026-05-10_a3_postopt_warmup_summary.md`

## 9) Validación funcional ejecutada
- `ruff check --select F api tests` -> OK
- `python -m compileall -q api app config core scripts run.py` -> OK
- `python -c "from api.app import create_app; app = create_app(); print(app.name)"` -> `api.app`
- `pytest -q` -> `197 passed, 3 skipped`
- `alembic heads` -> `20260510_01 (head)`
- `k6 inspect` suite legacy + A2/A3 -> OK

## 10) Resultados k6 A3 post-deploy
### 10.1 infra_smoke
- error: `0.6098%`
- p95 global: `1137.97 ms`
- p95 `healthz`: `677.58 ms`
- p95 `readyz`: `1324.74 ms`

### 10.2 auth_read 10 VUs
- error: `0.0000%`
- p95 global: `487.08 ms`
- p95 `auth_me`: `485.70 ms`

### 10.3 qv2_active_read 10 VUs
- error: `0.0000%`
- p95 global: `510.30 ms`
- p95 `qv2_active`: `509.83 ms`

### 10.4 user_journey_read
- 10 VUs: error `0.0000%`, p95 global `460.52 ms`, p95 auth `434.49 ms`, p95 qv2 `482.24 ms`
- 20 VUs: error `0.0000%`, p95 global `464.52 ms`, p95 auth `405.49 ms`, p95 qv2 `497.59 ms`
- 25 VUs: error `0.0000%`, p95 global `547.24 ms`, p95 auth `461.65 ms`, p95 qv2 `609.82 ms`
- 30 VUs: error `0.0000%`, p95 global `585.41 ms`, p95 auth `497.23 ms`, p95 qv2 `642.57 ms`

### 10.5 capacity_ladder (10→30 VUs)
- error global: `5.0384%`
- p95 global: `757.33 ms`
- p95 auth: `602.69 ms`
- p95 qv2: `577.41 ms`
- criterio de parada activado por `http_req_failed` (abortOnFail) en tramo alto
- `healthz/readyz` se mantuvieron funcionales en checks

### 10.6 constant_rps (seguro)
- 5→10 RPS (corrida controlada): error `0.0000%`, p95 global `387.56 ms`
- 5→10→15 RPS (corrida controlada): error `0.0000%`, p95 global `395.96 ms`
- No se ejecutó 20 RPS en esta fase por protección operacional.

## 11) Comparación A2 vs A3
Referencia A2:
- user_journey 10 VUs: p95 `1104.68 ms`, error `0.0000%`
- user_journey 20 VUs: p95 `836.62 ms`, error `0.0000%`
- qv2_active 10 VUs: p95 `1211.69 ms`
- auth_read 10 VUs: p95 `1031.49 ms`
- capacity_ladder error `5.10%`

A3 observado:
- user_journey 10 VUs: p95 `460.52 ms` (mejora material)
- user_journey 20 VUs: p95 `464.52 ms` (mejora material)
- qv2_active 10 VUs: p95 `509.83 ms` (mejora material)
- auth_read 10 VUs: p95 `485.70 ms` (mejora material)
- capacity_ladder error `5.04%` (misma zona de quiebre alta, leve mejora)

## 12) Límite actual del homelab
- Capacidad estable observada en corridas dedicadas de `user_journey` hasta 30 VUs.
- En carga escalonada prolongada aparece degradación en tramo alto (25-30 VUs) con corte por error rate >5%.
- Interpretación: límite operativo sigue condicionado por CPU/RAM local + red doméstica + latencia/limitaciones Supabase.

## 13) Recomendación homelab actual
- Operar normal en banda <=20 VUs equivalentes para margen conservador.
- Usar warmup previo y monitoreo continuo de `readyz` durante pruebas.
- Mantener pruebas de capacidad con criterio de parada y ventanas de baja actividad.

## 14) Recomendación servidor robusto + fibra
- Activar Redis/Valkey compartido para cache/rate-limit global real.
- Migrar tareas pesadas a cola durable (PDF/email/reportes/inferencia opcional).
- Recalibrar workers/threads/pool DB con benchmark externo sobre nuevo hardware.
- Agregar observabilidad host-level + DB pool wait + trazas centralizadas.

## 15) SHA, PRs y merges
- SHA runtime probado en producción: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- SHA final en `main` (cierre documental/hardening A3): `73a3c2cd88c357af473cb29073fba003e91e9f09`
- Flujo A3 aplicado previamente:
  - PR `#157`: `perf/a3-professional-reliability-cache-queue -> dev.enddark` (merged)
  - PR `#158`: `dev.enddark -> development` (merged)
  - PR `#159`: `development -> main` (merged/squash)
- Flujo de cierre A3 (evidencia/hardening final):
  - PR `#160`: `perf/a3-postdeploy-report-hardening -> dev.enddark` (merged)
  - PR `#161`: `dev.enddark -> development` (merged)
  - PR `#162`: `development -> main` (merged/squash)

## 16) Bloqueos y resolución
- Bloqueo operativo detectado: warmup shell en Windows con Schannel revocation + parse token login.
- Resolución aplicada: flag `WARMUP_CURL_SSL_NO_REVOKE` + fix parser login en script shell.
- Validación posterior: warmup shell exitoso en todas las rutas objetivo con `200`.

## 17) Estado final
- A3 completada con mejoras internas y evidencia reproducible.
- Funcionalidad preservada y contratos API públicos intactos.
- Resultados de rendimiento reportados sin maquillaje y con degradación alta documentada en ladder.
