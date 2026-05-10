# 2026-05-10 A2 Capacity and Reliability Final Report

## 1) Resumen ejecutivo
- La intervencion A2 (optimizacion interna sin cambios de contrato API) quedo desplegada en `main` (`9d2a4f9f9898940af2a6b32d398b90832ea4efbc`).
- En pruebas post-deploy reales contra `https://www.cognia.lat/api`, el flujo principal `auth/me + qv2_active` mejoro de forma material frente a A1:
  - 10 VUs: `p95=1104.68 ms`, `error=0.0000%`.
  - 15 VUs: `p95=754.89 ms`, `error=0.0000%`.
  - 20 VUs: `p95=836.62 ms`, `error=0.0000%`.
- En `capacity_ladder` (10->30 VUs) se detecto punto de degradacion controlado en tramo alto, con corte automatico por criterio de parada (`http_req_failed=5.10%`).
- `healthz` y `readyz` continuaron en `200` despues del corte.

## 2) Cambios aplicados en A2
- Cache interna multi-capa para `qv2_active` (version snapshot, payload, activation/confidence, question bank).
- TTLs de cache ampliados y configurables para reducir round-trips y outliers.
- Cache TTL para `/api/auth/me` con invalidaciones en cambios de seguridad/roles/MFA.
- Backend de cache extensible con fallback seguro (`memory` default, `Redis/Valkey` opcional por `CACHE_BACKEND_URI`).
- Optimizacion de metricas internas para reducir lock contention y permitir exclusion configurable de detalles health/ready sin perder conteos globales.
- Warmup script (`scripts/warmup_backend.py`) y nuevos escenarios k6 A2:
  - `k6_infra_smoke.js`
  - `k6_auth_read.js`
  - `k6_qv2_active_read.js`
  - `k6_user_journey_read.js`
  - `k6_capacity_ladder.js`
  - `k6_constant_rps.js`
- Hardening interno adicional (cache key de cifrado, cache de feature contract, mejoras de carga runtime).

## 3) Confirmacion de no cambios de contrato API y alcance
- Frontend: no tocado.
- Endpoints existentes: sin cambio de paths/metodos publicos.
- Inputs existentes: sin cambios breaking.
- Outputs JSON existentes: sin cambios breaking.
- Nombres de campos JSON existentes: preservados.
- Codigos de respuesta esperados: preservados.
- Logica clinica/metodologica: no alterada.
- Modelos/thresholds/artefactos clinicos: no tocados.
- Archivos protegidos/sucios (`scripts/hardening_second_pass.py`, `scripts/rebuild_dsm5_exact_datasets.py`, `scripts/run_pipeline.py`, `scripts/seed_users.py`, `tests/test_health.py`): no tocados en esta intervencion A2.

## 4) Flujo git/PR/merge y despliegue
- PR `#150` `perf/a2-capacity-reliability-optimization -> dev.enddark` (MERGED)
  - merge commit: `a57566bdd70752d59cef954c9af0fd0960af55e5`
- PR `#151` `dev.enddark -> development` (MERGED)
  - merge commit: `1e76f47794e77591631c483d4dd76094af2cafe1`
- PR `#152` `development -> main` (MERGED, squash)
  - merge commit en `main`: `9d2a4f9f9898940af2a6b32d398b90832ea4efbc`
- Workflows en `main` para `#152`:
  - `CI Backend`: success
  - `Deploy Backend (Best Effort)`: success
- Verificacion de salud post-deploy:
  - `https://www.cognia.lat/healthz` -> `200`
  - `https://www.cognia.lat/readyz` -> `200`
  - `https://www.cognia.lat/api/healthz` -> `404` (esperado)
  - `https://www.cognia.lat/api/readyz` -> `404` (esperado)

## 5) Warmup post-deploy
- Intento directo con `scripts/warmup_backend.py` desde este cliente: bloqueado por CDN/WAF.
- Comando ejecutado:
  - `BASE_URL=https://www.cognia.lat API_PREFIX=/api USERNAME=<test> PASSWORD=<test> SAFE_MODE=true python scripts/warmup_backend.py`
- Error observado:
  - `RuntimeError: warmup failed at /healthz: status=403 payload=error code: 1010`
- Mitigacion operativa en la misma ventana:
  - warmup manual con `curl --ssl-no-revoke` para `login`, `auth/me`, `transport-key`, `qv2_active` (guardian/psychologist short+medium), y luego `healthz/readyz`; todos `200`.
- Evidencia:
  - `artifacts/load_tests/2026-05-10_a2_postopt/warmup_manual.log`
  - `reports/load_tests/2026-05-10_a2_postopt_warmup_summary.md`

## 6) Resultados k6 A2 post-deploy
Infraestructura de prueba:
- servidor domestico (Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb)
- DB remota Supabase
- objetivo: `https://www.cognia.lat/api`
- usuario sintetico `perf_loadtest_a2_*` (sin usuarios reales)

### 6.1 infra_smoke
- RPS: `5.2674`
- Error rate: `0.7407%`
- p95 global: `1738.53 ms`
- p95 `healthz`: `764.65 ms`
- p95 `readyz`: `1814.43 ms`
- Observacion: umbral estricto de `readyz` en este script se cruzo (sin caida de disponibilidad 200).

### 6.2 auth_read (10 VUs)
- RPS: `9.6496`
- Error rate: `0.0000%`
- p95 global: `1032.80 ms`
- p95 `auth_me`: `1031.49 ms`

### 6.3 qv2_active_read (10 VUs)
- RPS: `9.3382`
- Error rate: `0.0000%`
- p95 global: `1212.13 ms`
- p95 `qv2_active`: `1211.69 ms`

### 6.4 user_journey_read (10 VUs)
- RPS: `11.8435`
- Error rate: `0.0000%`
- p95 global: `1104.68 ms`
- p95 `auth_me`: `981.43 ms`
- p95 `qv2_active`: `1201.99 ms`

### 6.5 user_journey_read (15 VUs)
- RPS: `22.5746`
- Error rate: `0.0000%`
- p95 global: `754.89 ms`
- p95 `auth_me`: `698.70 ms`
- p95 `qv2_active`: `804.92 ms`

### 6.6 user_journey_read (20 VUs)
- RPS: `29.0568`
- Error rate: `0.0000%`
- p95 global: `836.62 ms`
- p95 `auth_me`: `693.79 ms`
- p95 `qv2_active`: `959.62 ms`

### 6.7 capacity_ladder (10->30 VUs)
- RPS promedio global: `21.4313`
- Error rate: `5.0952%`
- p95 global: `1363.56 ms`
- p95 `auth_me`: `1060.32 ms`
- p95 `qv2_active`: `1408.72 ms`
- Punto de degradacion: tramo alto del ladder (cercano a 30 VUs), con fallos en checks 200 de `auth_me` y `qv2_active`.
- Criterio de parada activado: `http_req_failed > 5%` sostenido (abort automatico del script).

### 6.8 constant_rps
- No ejecutado en esta ventana por proteccion operacional tras activacion de criterio de parada en `capacity_ladder`.

## 7) Comparacion A1 vs A2
Referencia A1 reportada:
- baseline A1 10 VUs: `error=0.0843%`, `p95 global=2303.24 ms`, `qv2_active p95=3086.19 ms`.

A2 postopt:
- `user_journey_read` 10 VUs: `error=0.0000%`, `p95 global=1104.68 ms`.
- `qv2_active_read` 10 VUs: `error=0.0000%`, `qv2_active p95=1211.69 ms`.

Cambio observado:
- Reduccion marcada de p95 en ruta real de usuario y en hot path `qv2_active`.
- Capacidad estable observada al menos hasta 20 VUs en `user_journey_read` con error 0%.

## 8) Cuello de botella restante
- Degradacion aparece en la zona alta de concurrencia sostenida del ladder (aprox. banda 25-30 VUs en esta infraestructura actual), con errores en endpoints autenticados aunque `readyz` siga `200`.
- Probables factores combinados:
  - limite CPU/RAM del homelab
  - latencia y limites de Supabase remoto
  - naturaleza per-worker de caches/metricas/rate-limits sin backend compartido
  - picos de outliers en red/DB

## 9) Recomendacion para homelab actual
- Mantener operacion regular en banda de carga equivalente <= 20 VUs user_journey para estabilidad.
- Evitar pruebas agresivas continuas por encima de zona de degradacion.
- Conservar warmup antes de ventana de carga y validar `readyz` continuamente.
- Priorizar ejecucion de pruebas en horarios de baja actividad.

## 10) Recomendacion para servidor futuro (robusto + fibra)
- Activar `CACHE_BACKEND_URI` con Redis/Valkey para cache compartida real entre workers.
- Implementar cola durable para PDF/inferencia/email/reportes (RQ/Celery u opcion equivalente) para backpressure limpio.
- Recalibrar workers/threads/pool DB con benchmark sobre hardware objetivo y monitoreo host-level.
- Añadir trazas y metricas de DB wait/pool wait con export centralizado.

## 11) Que requiere Redis/Valkey
- Habilitar `CACHE_BACKEND_URI` y validar latencias/eviccion por namespace.
- Mantener fallback memory para no romper deploy sin Redis.
- Migrar gradualmente caches criticas (auth_me/qv2/security state) a backend compartido en entorno robusto.

## 12) Que requiere cola async
- Diseñar/activar ejecucion asincrona durable para tareas pesadas (PDF/reportes/email/inferencia opcional) sin romper endpoints actuales.
- Requiere componente worker dedicado + broker/queue + politicas de retry/timeout y observabilidad.

## 13) Evidencia local previa (A2)
- `ruff check --select F api tests` -> OK
- `python -m compileall -q api app config core scripts run.py` -> OK
- `python -c "from api.app import create_app; app = create_app(); print(app.name)"` -> OK
- `pytest -q` -> `188 passed, 3 skipped`
- `k6 inspect` de suite legacy + A2 -> OK

## 14) Archivos de evidencia versionados
- `reports/load_tests/2026-05-10_a2_postopt_warmup_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_infra_smoke_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_auth_read_10vu_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_qv2_active_read_10vu_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_user_journey_read_10vu_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_user_journey_read_15vu_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_user_journey_read_20vu_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_capacity_ladder_summary.md`
- `reports/load_tests/2026-05-10_a2_postopt_constant_rps_summary.md`

## 15) Estado final
- A2 implementada y desplegada en `main`.
- Salud post-deploy verificada.
- Pruebas k6 postopt ejecutadas hasta punto de degradacion controlado.
- No se inventaron resultados y no se oculto degradacion.
- No se realizaron cambios destructivos ni cambios contractuales breaking.
