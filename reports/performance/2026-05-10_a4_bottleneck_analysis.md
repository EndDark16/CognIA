# 2026-05-10 A4 Bottleneck Analysis

## Ventana ejecutada
- Fecha real de ejecucion: 2026-05-12 (UTC).
- Base URL: `https://www.cognia.lat`.
- Usuario sintetico: `diag01` (rol `GUARDIAN`, activo, sin MFA, no admin).
- Corridas A4 completadas:
  - `20260512T230500Z_diagnostic_health_vs_api_a4_health_10vu_final`
  - `20260512T231118Z_diagnostic_auth_vs_qv2_a4_authqv2_10vu_final`
  - `20260512T231726Z_diagnostic_auth_vs_qv2_a4_authqv2_20vu_final`
  - `20260512T232345Z_diagnostic_ladder_short_a4_ladder_10_30_final`
  - `20260512T233005Z_diagnostic_soak_light_a4_soak_20vu_10m_final`

## 1) Timeline correlada
- Primer error no-2xx en artefactos k6: `health_prefixed=404` y `ready_prefixed=404` en setup (esperado por probe de resolucion, no error funcional de negocio).
- Primer error funcional en endpoints objetivo (`healthz`, `readyz`, `auth_me`, `qv2_active`): no observado.
- Primera senal de degradacion >1200 ms (excluyendo `auth_login`):
  - `auth_me` en `auth_vs_qv2_20vu`: `t+4.50s` (`diag_degradation_ms_auth_me min=4502.3971`).
  - `readyz` en `soak_20vu_10m`: `t+6.91s` (`diag_degradation_ms_readyz min=6905.0943`).
  - `qv2_active` en `soak_20vu_10m`: `t+8.48s` (`diag_degradation_ms_qv2_active min=8481.6304`).

## 2) Breakdown por endpoint (evidencia principal)

| Escenario | Error rate global | p95 global (ms) | p95 healthz (ms) | p95 readyz (ms) | p95 auth_me (ms) | p95 qv2_active (ms) |
|---|---:|---:|---:|---:|---:|---:|
| health_vs_api 10 VUs 5m | 0.04% | 1060.53 | 632.35 | 1225.10 | 684.78 | 926.00 |
| auth_vs_qv2 10 VUs | 0.00% | 839.43 | N/A | N/A | 637.96 | 939.81 |
| auth_vs_qv2 20 VUs | 0.00% | 807.01 | N/A | N/A | 671.64 | 862.98 |
| ladder_short 10->30 | 0.05%* | 1031.76 | 697.55** | 1358.04 | 633.09 | 876.47 |
| soak_light 20 VUs 10m | 0.01%* | 1468.68 | 827.28** | 1541.55 | 843.43 | 1708.44 |

- `*`: el porcentaje global incluye probes `health_prefixed/ready_prefixed` con `404` esperado durante auto-resolucion de rutas en setup.
- `**`: `healthz` en ladder/soak calculado desde `k6_raw_output.json` (no submetrica en summary export de ese script).

Conclusiones directas del breakdown:
- `qv2_active` es consistentemente mas lento que `auth_me` en escenarios autenticados.
- `readyz` (que ejecuta `SELECT 1` real a DB) domina sobre `healthz` en todas las corridas donde se midio junto.
- No hubo 5xx ni 429 en endpoints objetivo.

## 3) Red vs procesamiento (curl timing before/during/after)
Patron repetido en todas las corridas:
- `time_connect` y `time_appconnect` se mantienen relativamente bajos/estables (tipicamente `0.10s`-`0.45s`).
- El salto fuerte aparece en `time_starttransfer` para `readyz` y `qv2_active`.

Ejemplo representativo (soak, snapshot `during`):
- healthz: `connect=0.114s`, `starttransfer=0.710s`, `total=0.710s`.
- readyz: `connect=0.124s`, `starttransfer=1.319s`, `total=1.320s`.
- qv2_active: `connect=0.131s`, `starttransfer=1.336s`, `total=1.347s`.

Interpretacion:
- La red/handshake aporta un piso importante.
- La diferencia adicional de `readyz`/`qv2_active` se explica por tiempo de backend/dependencias (DB/cache/path de endpoint), no por connect/TLS.

## 4) Evidencia DB y cache
### 4.1 `readyz` confirma dependencia DB
Codigo runtime (`api/routes/health.py`):
- `readyz` ejecuta `SELECT 1` real con timeout y devuelve `latency_ms`.

Probe de 20 llamadas post-run (`artifacts/diagnostics/a4_readyz_cache_probe.txt`):
- `status=ready` en 20/20.
- `latency_ms_avg=897.73`.
- `latency_ms_max=1132.17`.
- `cached_true=8`, `cached_false=12` con TTL default de 3s.

Patron de cache:
- Con intervalos de ~0.4s (< TTL), deberia haber mas cache hits continuos si todo cae en el mismo worker.
- La alternancia `cached=false/true` frecuente sugiere cache in-memory distribuida por worker/proceso (no cache global compartida).

### 4.2 Probe dedicado qv2/auth
- `a4_qv2_60probe.txt`: `qv2_active p95=1.88s`, picos >2s (3/60).
- `a4_authme_60probe.txt`: `auth_me p95=1.52s`, menos severo que `qv2_active`.

Interpretacion:
- Hay jitter/outliers incluso en secuencia controlada.
- `qv2_active` tiene cola de latencia mas pesada que `auth_me`.

## 5) Host / Docker / logs backend / Supabase / WAF
### Host y Docker de produccion
No accesible en esta ventana:
- SSH intentado a `root@cognia.lat`, `ubuntu@cognia.lat`, `root@www.cognia.lat`, `ubuntu@www.cognia.lat`.
- Error exacto en todos: `ssh: connect to host ... port 22: Connection timed out`.
- Evidencia: `artifacts/diagnostics/a4_remote_access_attempts.txt`.

### Docker stats / compose logs
No accesible del host de produccion (sin SSH).
En runner local:
- Docker daemon no operativo durante captura (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`).

### Logs backend de produccion
Sin acceso directo (sin SSH/admin endpoint autorizado).
`capture_backend_logs.sh` en esta ventana solo pudo confirmar ausencia de fuente local de logs.

### Supabase SQL snapshot
No ejecutable desde esta ventana:
- `psql` no instalado (`where.exe psql` sin resultado).
- Evidencia: `artifacts/diagnostics/a4_db_access_attempts.txt`.

### WAF/CDN
- Headers confirman Cloudflare (`Server: cloudflare`, `CF-RAY`, `cf-cache-status: DYNAMIC`).
- No hubo `403/1010` en corridas k6 objetivo.
- Evidencia: `artifacts/diagnostics/a4_waf_cdn_headers.txt`.

## 6) Atribucion cuantitativa (distribucion del cuello)
Usando soak 20 VUs (p95 raw):
- healthz p95: `827.28 ms` (piso compartido edge/red + app minima).
- qv2_active p95: `1708.44 ms`.
- Diferencia qv2 sobre piso: `881.16 ms`.

Descomposicion aproximada en p95 para `qv2_active`:
- Piso compartido (edge/red + app base): ~`48.4%` (`827.28 / 1708.44`).
- Sobrecosto path qv2 (DB/cache/logica endpoint): ~`51.6%` (`881.16 / 1708.44`).

Para `readyz` (DB check) en p95:
- Piso compartido: ~`53.7%` (`827.28 / 1541.55`).
- Sobrecosto DB readiness: ~`46.3%`.

## 7) Diagnostico final (tecnico)
- Cuello primario: latencia del path dependiente de DB (Supabase/PostgreSQL + lectura del endpoint), visible en `readyz` y amplificado en `qv2_active`.
- Cuello secundario: piso de latencia de transporte/edge (Cloudflare + red de origen), que eleva la base de todos los endpoints pero no explica por si solo la brecha `healthz` vs `readyz/qv2`.
- Factor adicional secundario: cache in-memory por worker (no compartida) que reduce consistencia de hits y deja outliers al rotar worker/proceso.

## 8) Evidencia referenciada
- Corridas k6 (JSON/MD/raw):
  - `artifacts/diagnostics/20260512T230500Z_diagnostic_health_vs_api_a4_health_10vu_final/`
  - `artifacts/diagnostics/20260512T231118Z_diagnostic_auth_vs_qv2_a4_authqv2_10vu_final/`
  - `artifacts/diagnostics/20260512T231726Z_diagnostic_auth_vs_qv2_a4_authqv2_20vu_final/`
  - `artifacts/diagnostics/20260512T232345Z_diagnostic_ladder_short_a4_ladder_10_30_final/`
  - `artifacts/diagnostics/20260512T233005Z_diagnostic_soak_light_a4_soak_20vu_10m_final/`
- Probes adicionales:
  - `artifacts/diagnostics/a4_readyz_sampling_post_runs.txt`
  - `artifacts/diagnostics/a4_readyz_cache_probe.txt`
  - `artifacts/diagnostics/a4_auth_qv2_sampling_post_runs.txt`
  - `artifacts/diagnostics/a4_qv2_60probe.txt`
  - `artifacts/diagnostics/a4_authme_60probe.txt`
- Acceso/limitaciones:
  - `artifacts/diagnostics/a4_remote_access_attempts.txt`
  - `artifacts/diagnostics/a4_db_access_attempts.txt`
  - `artifacts/diagnostics/a4_waf_cdn_headers.txt`
  - `artifacts/diagnostics/a4_metrics_access_attempts.txt`
