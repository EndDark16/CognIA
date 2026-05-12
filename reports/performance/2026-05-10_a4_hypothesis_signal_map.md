# 2026-05-10 A4 Hypothesis Signal Map

## Objetivo
Definir hipotesis y senales esperadas para atribuir cuello de botella real por evidencia, no por suposicion.

## Mapa de hipotesis
| Hipotesis | Senales esperadas | Fuentes de evidencia A4 |
|---|---|---|
| CPU bound | CPU 90-100%, load average alto, p95 sube con DB estable, docker CPU alto | `host_before/during/after`, `docker stats`, `k6_summary_export.json`, `k6_raw_output.json` |
| RAM/swap/memory pressure | memoria libre baja, swap usado, memory pressure alto, outliers crecientes en pruebas largas | `host_before/during/after`, `vm_stat/free`, `memory_pressure`, `k6_raw_output.json` |
| Red domestica | jitter/ping inestable, connect/starttransfer altos, healthz lento tambien | `network_before/during/after`, `k6_diagnostic_health_vs_api` |
| Supabase/DB remoto | readyz lento, db_unavailable, waits/locks, conexiones en cola | `backend_logs_*`, `capture_supabase_snapshot.sql` (si acceso), `k6 endpoint breakdown` |
| SQLAlchemy pool | pool timeout/queuepool waits, errores intermitentes bajo concurrencia | `backend_logs_*`, `error_counts` en `/metrics` (si capturado), k6 ladder |
| Gunicorn workers/threads | worker timeout, cola de requests, latencia sube antes de error | `backend_logs_*`, `k6_raw_output.json`, host snapshots |
| Cache miss/warmup/per-worker cache | primeras requests lentas, 2da corrida mejora, qv2/auth mejora tras warmup | `warmup.log`, `k6 diffs`, `/metrics cache_metrics` si capturado |
| WAF/CDN | 403/1010/rate behavior selectivo por UA/IP | `k6 status breakdown`, logs backend, logs CDN/WAF (si acceso) |
| Endpoint especifico | auth_me o qv2_active concentra p95 y/o errores | `k6 endpoint latency + status`, `diagnostic_digest.json` |
| Lock interno / metrics overhead | latencia sube tambien en endpoints simples, sin causa DB/red clara | k6 health vs api + logs + CPU Python + comparacion con/ sin carga de metricas (solo si seguro) |

## Criterios de cierre de hipotesis
- primario: evidencia consistente en >=2 fuentes independientes y correlacion temporal.
- secundario: evidencia parcial consistente pero no dominante.
- descartado: evidencia en contra en la misma ventana.
- no concluyente: faltan accesos o evidencia contradictoria.
