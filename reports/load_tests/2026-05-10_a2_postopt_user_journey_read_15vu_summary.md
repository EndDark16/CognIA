# A2 postopt user_journey_15vu

- Fecha UTC: 2026-05-10T23:18:39.589317+00:00
- Branch ejecutada localmente: `perf/a2-capacity-reliability-optimization`
- Entorno: servidor domestico (Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb, DB Supabase).
- Dominio objetivo: `https://www.cognia.lat`
- API publica: `https://www.cognia.lat/api`
- Commit runtime probado en main: `9d2a4f9f9898940af2a6b32d398b90832ea4efbc`
- Rama desplegada: `main`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`
- Usuario: sintetico `perf_loadtest_a2_*` (no usuario real).
- Escenario: `user_journey_15vu`
- Duracion objetivo: 5m
- Carga objetivo: 15 VUs
- Requests totales: 6899
- RPS promedio: 22.5746
- Error rate (http_req_failed): 0.0000%
- Latencia p50 ms: 349.30
- Latencia p90 ms: 594.46
- Latencia p95 ms: 754.89
- Latencia p99 ms: N/A
- Latencia max ms: 7262.77

## Checks por endpoint
- `auth me status 200`: pass=3449 fail=0
- `questionnaire active status 200`: pass=3449 fail=0

## Status codes
- El `summary_export` de estos scripts no incluyo submetricas `http_reqs{status:*}`; se conserva evidencia via checks 200/fail por endpoint.

## Conclusion operativa
- Escenario ejecutado contra produccion con modo seguro y usuario sintetico.
