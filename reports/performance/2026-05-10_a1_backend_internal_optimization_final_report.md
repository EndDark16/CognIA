# 2026-05-10 A1 Backend Internal Optimization Final Report

## 1. Resumen ejecutivo
Se completo una intervencion A1 de optimizacion interna del backend CognIA enfocada en observabilidad real, optimizacion de hot paths, reduccion de N+1, proteccion operativa del homelab y evidencia reproducible de pruebas reales post-deploy. Se mantuvo compatibilidad con frontend y contratos API existentes.

## 2. Contexto de infraestructura actual
- Servidor domestico limitado (homelab).
- Cliente de ejecucion de carga: Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb.
- Base de datos externa: Supabase.
- Este entorno NO representa la infraestructura final (servidor robusto + fibra).

## 3. Alcance de no regresion contractual
- Frontend no tocado.
- Endpoints existentes no cambiados (paths/metodos publicos).
- Inputs existentes no cambiados.
- Outputs JSON existentes no cambiados en endpoints publicos funcionales.
- Nombres de campos JSON existentes no cambiados.
- Codigos de respuesta esperados no cambiados salvo manejo interno de performance/observabilidad.
- Modelos/thresholds/caveats clinicos no tocados.

## 4. Cambios internos aplicados
- Observabilidad:
  - `X-Request-ID` propagado y log correlable.
  - Enriquecimiento de metricas internas por endpoint/status manteniendo compatibilidad de `/metrics`.
- Auth/JWT:
  - Optimizacion de `token_in_blocklist_loader` para evitar query de refresh en access tokens.
  - Cache TTL corta para estado de seguridad de usuario con invalidacion en eventos de auth.
- Questionnaire v2:
  - Cache TTL de payload activo con invalidacion explicita al sincronizar catalogo/modelos.
  - Optimizacion de carga por pagina en sesiones.
- DB y consultas:
  - Reduccion de N+1 en users/problem_reports.
  - Migracion aditiva de indices de hot path (`20260510_01_add_perf_hotpath_indexes.py`).
- Config/despliegue:
  - Tuning conservador para homelab en pool DB y gunicorn.
  - EntryPoint alineado a variables de worker class/graceful timeout.
- Suite k6:
  - `handleSummary()` y exportes JSON/MD versionables por escenario.

## 5. Riesgo por categoria
- Observabilidad: bajo.
- Auth/JWT hot path: medio-bajo.
- Cache questionnaire v2: medio.
- N+1 e indices: bajo-medio.
- Tuning homelab: medio-bajo.

## 6. Archivos/elementos protegidos
No se tocaron ni se incluyeron en commits estos archivos protegidos:
- `scripts/hardening_second_pass.py`
- `scripts/rebuild_dsm5_exact_datasets.py`
- `scripts/run_pipeline.py`
- `scripts/seed_users.py`
- `tests/test_health.py`

## 7. Validacion local final
- `ruff check --select F api tests` -> OK.
- `python -m compileall -q api app config core scripts run.py` -> OK.
- `python -c "from api.app import create_app; app = create_app(); print(app.name)"` -> OK (`api.app`).
- `pytest -q` -> `179 passed, 3 skipped`.
- `k6 inspect` de 7 scripts -> OK.

## 8. Flujo Git y despliegue
- PR #139: `perf/a1-backend-internal-optimization -> dev.enddark` (merged).
- PR #140: `dev.enddark -> development` (merged).
- PR #141: `development -> main` (merged con `squash` por politica del repo).
- SHA final desplegado en `main`: `bae532e0495aa62459a5278bf1a2a3858c11e595`.
- Workflows main:
  - `CI Backend` -> success.
  - `Deploy Backend (Best Effort)` -> success.

## 9. Salud post-deploy
- `https://www.cognia.lat/healthz` -> 200.
- `https://www.cognia.lat/readyz` -> 200.
- `https://www.cognia.lat/api/healthz` -> 404.
- `https://www.cognia.lat/api/readyz` -> 404.

Patron real confirmado: health/readiness en raiz y API funcional bajo `/api`.

## 10. Pruebas k6 reales post-optimizacion
### Smoke (5 VUs, 30s)
- Requests: 157
- RPS: 4.0606
- Error rate: 1.2739%
- p95: 2159.00 ms
- max: 29666.09 ms (outlier)
- checks funcionales: 100% pass

### Micro-baseline (5 VUs, 3m)
- Requests: 1137
- RPS: 6.0781
- Error rate: 0.1759%
- p95: 1218.51 ms
- checks funcionales: 100% pass

### Baseline (10 VUs, 5m)
- Requests: 2373
- RPS: 7.6512
- Error rate: 0.0843%
- p95 global: 2303.24 ms
- p95 por endpoint: `healthz=1515.04 ms`, `readyz=2121.08 ms`, `qv2_active=3086.19 ms`
- checks funcionales: 100% pass

Criterios de parada operativos: no activados en postopt.

## 11. Comparacion antes/despues
Referencia preopt (reporte previo 2026-05-10):
- Smoke preopt: error ~2.74%, p95 ~6377 ms.
- Baseline preopt 10 VUs/5m: error ~32.70%, p95 ~7615 ms.

Postopt:
- Smoke: error 1.27%, p95 2159 ms.
- Baseline 10 VUs/5m: error 0.08%, p95 2303 ms.

Resultado: mejora material y estable del baseline bajo la misma infraestructura limitada.

## 12. Cuellos de botella observados
- Persisten outliers de latencia en endpoints simples bajo carga.
- `qv2_active` sigue siendo endpoint sensible en p95.
- Sin telemetria host-level/DB-level durante esta corrida (no se uso SSH/metrics de host), por lo que la atribucion fina por CPU/red/pool/DB remota queda parcial.

## 13. Recomendaciones
- Homelab actual:
  - Mantener pruebas seguras en 5-10 VUs.
  - Evitar stress agresivo en ventanas con trafico real.
  - Mantener `SAFE_MODE` y payload sintetico.
- Servidor futuro + fibra:
  - Repetir baseline/load/stress/spike/soak con generador de carga separado.
  - Capturar observabilidad host-level (CPU/RAM/red/pool/latencia DB).
  - Evaluar cache/rate-limit distribuido (Redis/Valkey) para multi-worker.

## 14. Evidencia versionada
- `reports/performance/2026-05-10_a1_backend_internal_optimization_audit.md`
- `reports/load_tests/2026-05-10_a1_postopt_smoke_summary.md`
- `reports/load_tests/2026-05-10_a1_postopt_micro_baseline_summary.md`
- `reports/load_tests/2026-05-10_a1_postopt_baseline_summary.md`
- `reports/performance/2026-05-10_a1_backend_internal_optimization_final_report.md`

## 15. Confirmacion final
Intervencion A1 completada sin cambios destructivos y con evidencia real post-deploy. No se inventaron resultados y no se comprometieron frontend, contratos publicos ni componentes clinico-metodologicos.
