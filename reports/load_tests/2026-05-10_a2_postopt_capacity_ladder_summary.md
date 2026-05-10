# A2 postopt capacity_ladder

- Fecha UTC: 2026-05-10T23:18:39.591617+00:00
- Branch ejecutada localmente: `perf/a2-capacity-reliability-optimization`
- Entorno: servidor domestico (Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb, DB Supabase).
- Dominio objetivo: `https://www.cognia.lat`
- API publica: `https://www.cognia.lat/api`
- Commit runtime probado en main: `9d2a4f9f9898940af2a6b32d398b90832ea4efbc`
- Rama desplegada: `main`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`
- Usuario: sintetico `perf_loadtest_a2_*` (no usuario real).
- Escenario: `capacity_ladder`
- Duracion objetivo: staged 16m (abort at 15m46s)
- Carga objetivo: 10->15->20->25->30 VUs
- Requests totales: 20274
- RPS promedio: 21.4313
- Error rate (http_req_failed): 5.0952%
- Latencia p50 ms: 434.61
- Latencia p90 ms: 1011.57
- Latencia p95 ms: 1363.56
- Latencia p99 ms: N/A
- Latencia max ms: 28422.25

## Checks por endpoint
- `auth me status 200`: pass=8161 fail=514
- `healthz status 200`: pass=1462 fail=0
- `questionnaire active status 200`: pass=8154 fail=517
- `readyz status 200`: pass=1461 fail=0

## Status codes
- El `summary_export` de estos scripts no incluyo submetricas `http_reqs{status:*}`; se conserva evidencia via checks 200/fail por endpoint.

## Criterio de parada
- Se activo abort por threshold (`http_req_failed` > 5% sostenido).
- Resultado observado al corte: `http_req_failed=5.10%`, p95 global `1363.56 ms`.
- Ready/health siguieron respondiendo 200 despues del corte (ver validacion posterior).

## Conclusion operativa
- Escenario ejecutado contra produccion con modo seguro y usuario sintetico.
