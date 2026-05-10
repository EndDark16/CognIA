# A2 postopt infra_smoke

- Fecha UTC: 2026-05-10T23:18:39.583876+00:00
- Branch ejecutada localmente: `perf/a2-capacity-reliability-optimization`
- Entorno: servidor domestico (Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb, DB Supabase).
- Dominio objetivo: `https://www.cognia.lat`
- API publica: `https://www.cognia.lat/api`
- Commit runtime probado en main: `9d2a4f9f9898940af2a6b32d398b90832ea4efbc`
- Rama desplegada: `main`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`
- Usuario: sintetico `perf_loadtest_a2_*` (no usuario real).
- Escenario: `infra_smoke`
- Duracion objetivo: 45s
- Carga objetivo: 5 VUs
- Requests totales: 270
- RPS promedio: 5.2674
- Error rate (http_req_failed): 0.7407%
- Latencia p50 ms: 414.78
- Latencia p90 ms: 1457.68
- Latencia p95 ms: 1738.53
- Latencia p99 ms: N/A
- Latencia max ms: 2365.73

## Checks por endpoint
- `healthz status 200`: pass=133 fail=0
- `readyz status 200`: pass=133 fail=0

## Status codes
- El `summary_export` de estos scripts no incluyo submetricas `http_reqs{status:*}`; se conserva evidencia via checks 200/fail por endpoint.

## Conclusion operativa
- Escenario ejecutado contra produccion con modo seguro y usuario sintetico.
