# 2026-05-10 A4 Bottleneck Attribution Final Report

## Respuestas directas (A4)
1. **Cual es el cuello principal?**  
   `no concluyente` con evidencia disponible en esta ventana.

2. **Cual es el cuello secundario?**  
   En la corrida parcial ejecutada (`healthz/readyz`), `readyz` mostro mayor p95 que `healthz` y fue el primer endpoint con senal de degradacion relativa.

3. **El problema esta en CPU?**  
   `no concluyente` (sin snapshot host before/during/after en esta ventana).

4. **RAM/swap?**  
   `no concluyente` (sin evidencia de memory pressure/swap de la misma ventana).

5. **Red domestica?**  
   `no concluyente` (sin snapshot de red curl timing/ping/traceroute de la misma ventana).

6. **Supabase/DB?**  
   `no concluyente` (sin snapshot SQL ni logs DB correlados de la misma ventana).

7. **SQLAlchemy pool?**  
   `no concluyente` (sin pool timeout/waits observables en evidencia capturada de esta ventana).

8. **Gunicorn workers/threads?**  
   `no concluyente` (sin logs de workers/timeout correlados en la misma ventana).

9. **WAF/CDN?**  
   `no concluyente` (sin logs WAF/CDN; no evidencia directa nueva en esta corrida parcial).

10. **Endpoint especifico?**  
   `secundario`: `readyz` dentro del subconjunto medido (`healthz/readyz`) por p95 superior.

11. **Cache miss?**  
   `no concluyente` (sin snapshot `/metrics` before/during/after para hit/miss por namespace).

12. **Se ve degradacion acumulativa?**  
   `no concluyente` (solo corrida corta de 20s sin soak/ladder autenticado en esta ventana).

13. **Donde aparece el primer error?**  
   No se observaron errores en el flujo default medido (`healthz/readyz`).  
   En setup hubo `404` esperados al probar `/api/healthz` y `/api/readyz` durante auto-resolucion de rutas.

14. **Donde aparece el primer aumento p95?**  
   En el subconjunto medido, la primera senal relativa registrada por helper fue en `readyz` (`relative_timestamp_ms=11045`).

15. **Que evidencia respalda cada conclusion?**  
   Artifact principal: `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/`:
   - `k6_summary_export.json`
   - `k6_raw_output.json`
   - `k6_handle_summary/*_summary.md`
   - `diagnostic_analysis.md`
   - `diagnostic_analysis.json`

16. **Que tan confiable es la conclusion?**  
   `baja`, por cobertura incompleta de fuentes (host/db/red/waf/auth endpoints).

17. **Que falta medir?**  
   - corridas autenticadas (`auth_me`, `qv2_active`) con usuario sintetico real.
   - snapshots host/docker/logs before-during-after en misma ventana.
   - snapshot SQL Supabase (`pg_stat_activity`, waits, locks, conexiones).
   - telemetria WAF/CDN si aplica.
   - ladder corto y soak light autenticados.
   - bloqueo tecnico local documentado:
     - comando: `bash -n scripts/diagnostics/capture_host_snapshot.sh ...`
     - error: `<3>WSL (9 - Relay) ERROR: CreateProcessCommon:798: execvpe(/bin/bash) failed: No such file or directory`
     - comando: `where.exe psql`
     - resultado: `missing`

18. **Que accion concreta se recomienda?**  
   Ejecutar `scripts/diagnostics/run_diagnostic_window.sh` en host con bash operativo y credenciales sinteticas, en este orden:
   - `diagnostic_health_vs_api` 10 VUs
   - `diagnostic_auth_vs_qv2` (10->20->30)
   - `diagnostic_ladder_short` (abort criteria activos)
   - `diagnostic_soak_light` solo si los anteriores son estables
   y luego consolidar con `scripts/diagnostics/analyze_diagnostic_run.py`.

## Matriz de factores (obligatoria)
| Factor | Estado | Evidencia | Confianza | Accion |
|---|---|---|---|---|
| CPU | no concluyente | no hay `host_before/during/after` en esta ventana | baja | ejecutar `capture_host_snapshot.sh` en misma ventana de k6 |
| RAM | no concluyente | no hay `vm_stat/free/swap/memory_pressure` correlado | baja | capturar memoria/swap during load |
| Red domestica | no concluyente | no hay `capture_network_snapshot.sh` during load | baja | correr snapshot red before/during/after |
| Supabase/DB | no concluyente | sin snapshot SQL ni waits/locks de la ventana | baja | ejecutar `capture_supabase_snapshot.sql` durante ladder |
| SQLAlchemy pool | no concluyente | sin evidencia de pool timeout en logs capturados en esta ventana | baja | capturar backend logs during ladder y buscar `queuepool/pool_timeout` |
| Gunicorn | no concluyente | sin logs correlados de worker timeout | baja | correlar logs gunicorn con first p95 rise |
| WAF/CDN | no concluyente | sin logs Cloudflare/WAF de esta ventana | baja | obtener logs por ventana temporal exacta |
| qv2_active | no concluyente | no medido (sin credenciales sinteticas) | baja | ejecutar `k6_diagnostic_auth_vs_qv2.js` autenticado |
| auth_me | no concluyente | no medido (sin credenciales sinteticas) | baja | ejecutar `k6_diagnostic_auth_vs_qv2.js` autenticado |
| cache | no concluyente | sin snapshot `/metrics` hit/miss before-during-after | baja | capturar `/metrics` en tres cortes y correlar con p95 |

## Resultado operativo de esta ventana
- corrida real ejecutada: `k6_diagnostic_health_vs_api` (safe, no auth), `K6_VUS=10`, `K6_DURATION=20s`.
- metricas observadas:
  - `http_req_failed`: `0.64%`
  - `global p95`: `944.71 ms`
  - `healthz p95`: `481.86 ms`
  - `readyz p95`: `1025.67 ms`
- interpretacion permitida: evidencia parcial de comportamiento de infraestructura base (`health/ready`) sin atribucion causal completa.
