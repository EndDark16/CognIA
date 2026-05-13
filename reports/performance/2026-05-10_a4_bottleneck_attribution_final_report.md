# 2026-05-10 A4 Bottleneck Attribution Final Report

## Respuestas directas
1. **Cual es el cuello principal?**  
   `Supabase/DB path latency` (incluye roundtrip DB y costo de lectura de rutas DB-backed), evidenciado por `readyz` y `qv2_active`.

2. **Cual es el cuello secundario?**  
   `piso de latencia edge/red` (Cloudflare + red de origen), que agrega base alta a todos los endpoints.

3. **El problema esta en CPU?**  
   `descartado como cuello primario` en esta ventana (no hubo sintomas de saturacion tipo 5xx/timeouts/colapso al subir carga).

4. **RAM/swap?**  
   `descartado como cuello primario` en esta ventana (sin sintomas de degradacion tipo OOM/restarts/errores progresivos).

5. **Red domestica?**  
   `secundario` (hay piso de latencia alto en `healthz`, pero no explica la brecha extra de `readyz/qv2`).

6. **Supabase/DB?**  
   `primario`.

7. **SQLAlchemy pool?**  
   `secundario` (potencial parte del costo DB-backed; no evidencia de `pool_timeout`/errores de pool como trigger principal).

8. **Gunicorn workers/threads?**  
   `secundario` (indicio por cache in-memory no compartida entre workers/procesos).

9. **WAF/CDN?**  
   `descartado` como trigger de degradacion (sin 403/1010 en corridas objetivo).

10. **auth_me esta implicado?**  
    `descartado como endpoint culpable principal` (siempre por debajo de qv2/readyz).

11. **qv2_active esta implicado?**  
    `secundario alto` (endpoint sintomatico principal de la degradacion DB-backed).

12. **readyz esta implicado?**  
    `primario` como endpoint sentinela (ejecuta `SELECT 1` real y concentra latencia alta).

13. **cache miss/per-worker cache esta implicado?**  
    `secundario` (patron de cache por worker observado en `readyz`: muchos `cached=false` aun bajo TTL corto).

14. **Donde aparece el primer error?**  
    En probes de setup: `health_prefixed=404` y `ready_prefixed=404` (esperado por auto-resolucion).  
    En endpoints objetivo (`healthz`, `readyz`, `auth_me`, `qv2_active`): no aparecio error funcional.

15. **Donde aparece el primer aumento p95?**  
    Primer cruce >1200 ms (excluyendo `auth_login`) en `auth_me` a `t+4.50s` durante `auth_vs_qv2_20vu`; luego `readyz` `t+6.91s` y `qv2_active` `t+8.48s` en soak.

16. **Que evidencia respalda cada conclusion?**  
    Correlacion de 5 corridas k6 + snapshots de red + probes de `readyz` (`latency_ms/cached`) + probes de `auth_me/qv2` + headers Cloudflare + intentos de acceso host/DB documentados con error exacto.

17. **Que tan confiable es la conclusion?**  
    `media-alta` para cuello primario/secundario (por consistencia multi-escenario).  
    `media-baja` para descarte fino de CPU/RAM/pool/Gunicorn por falta de acceso SSH/DB directo.

18. **Que accion concreta se recomienda?**  
    Mantener A4 cerrado con cuello primario DB-backed + secundario edge/red, y priorizar en siguiente ventana operativa: cache compartida (Redis/Valkey) y observabilidad DB/pool con acceso SQL/host.

## Matriz obligatoria
| Factor | Estado | Evidencia | Confianza | Accion |
|---|---|---|---|---|
| CPU | descartado | Sin 5xx, sin timeout de negocio, ladder 10->30 y soak 20VU estables; no patron de colapso por concurrencia | media-baja | Verificar con host metrics reales cuando SSH este habilitado |
| RAM/swap | descartado | No hubo reinicios/errores progresivos/caida de checks en 10m de soak | baja | Confirmar con memoria de host real (SSH) |
| Red domestica | secundario | `healthz` mantiene piso alto (p95 632-827ms); curl `connect/TLS` estable pero no despreciable | media | Mantener medicion desde otra red para comparar piso |
| Supabase/DB | primario | `readyz` (SELECT 1 real) p95 1225-1541ms; `latency_ms` avg ~897ms, p95 ~1436ms; `qv2_active` y `readyz` se elevan juntos | alta | Tratar ruta DB como cuello principal operativo |
| SQLAlchemy pool | secundario | No `pool_timeout`/errores de pool observables; posible costo de checkout dentro del path DB-backed | media-baja | Instrumentar pool checkout/wait cuando haya admin/metrics SQL |
| Gunicorn | secundario | Patron de cache por worker: `readyz` alterna `cached=false/true` bajo TTL 3s (cache no compartida global) | media | Mantener worker tuning y cache compartida |
| WAF/CDN | descartado | Sin 403/1010 en k6 objetivo; headers Cloudflare normales (`cf-cache-status: DYNAMIC`) | alta | Sin cambio WAF en A4 |
| auth_me | descartado | p95 auth_me < p95 qv2/readyz en todos los escenarios autenticados | alta | No priorizar auth_me como cuello principal |
| qv2_active | secundario | p95 qv2 863-1708ms; mayor cola que auth_me; outliers >2s en probe dedicado | alta | Priorizar path qv2 en acciones sobre DB/cache |
| readyz | primario | Endpoint DB-check directo con p95 alto y latencia interna reportada por backend | alta | Usar readyz como sentinela continuo de salud DB |
| cache | secundario | Evidencia de cache por worker/proceso (no compartida), outliers por misses/rotacion de worker | media | Migrar cache compartida para reducir outliers |

## Distribucion estimada del cuello (p95, soak 20VU)
- Referencia: `healthz p95=827.28 ms`, `qv2_active p95=1708.44 ms`, `readyz p95=1541.55 ms`.
- Descomposicion aproximada de `qv2_active p95`:
  - piso compartido edge/red + app base: **48.4%**
  - sobrecosto DB/cache/logica qv2: **51.6%**
- Descomposicion aproximada de `readyz p95`:
  - piso compartido edge/red + app base: **53.7%**
  - sobrecosto DB readiness: **46.3%**

## Evidencia clave (paths)
- Corridas diagnosticas:
  - `artifacts/diagnostics/20260512T230500Z_diagnostic_health_vs_api_a4_health_10vu_final/`
  - `artifacts/diagnostics/20260512T231118Z_diagnostic_auth_vs_qv2_a4_authqv2_10vu_final/`
  - `artifacts/diagnostics/20260512T231726Z_diagnostic_auth_vs_qv2_a4_authqv2_20vu_final/`
  - `artifacts/diagnostics/20260512T232345Z_diagnostic_ladder_short_a4_ladder_10_30_final/`
  - `artifacts/diagnostics/20260512T233005Z_diagnostic_soak_light_a4_soak_20vu_10m_final/`
- Probes adicionales:
  - `artifacts/diagnostics/a4_readyz_cache_probe.txt`
  - `artifacts/diagnostics/a4_readyz_sampling_post_runs.txt`
  - `artifacts/diagnostics/a4_qv2_60probe.txt`
  - `artifacts/diagnostics/a4_authme_60probe.txt`
- Acceso e imposibilidades reales:
  - `artifacts/diagnostics/a4_remote_access_attempts.txt` (SSH port 22 timeout)
  - `artifacts/diagnostics/a4_db_access_attempts.txt` (`psql` no disponible)
  - `artifacts/diagnostics/a4_waf_cdn_headers.txt`
  - `artifacts/diagnostics/a4_metrics_access_attempts.txt` (`/api/admin/metrics`=403 con usuario sintetico no admin)
