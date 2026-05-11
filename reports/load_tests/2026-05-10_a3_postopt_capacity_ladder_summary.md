# capacity_ladder summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Escalado 10?15?20?25?30 VUs
- Perfil: Con abortOnFail activo (rate/latency thresholds)
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 29335
- RPS promedio: 30.8140
- Error rate (`http_req_failed`): 5.0384%
- Latencia p50: 296.68 ms
- Latencia p90: 455.07 ms
- Latencia p95: 757.33 ms
- Latencia p99: N/A
- Latencia m?xima: 3078.01 ms
- p95 `auth_me`: 602.69 ms
- p95 `qv2_active`: 577.41 ms

## Checks
- `healthz status 200`: pass=2109, fail=0
- `readyz status 200`: pass=2108, fail=0
- `auth me status 200`: pass=11823, fail=734
- `questionnaire active status 200`: pass=11814, fail=742

## Status codes
- Breakdown por status HTTP: N/A (la exportaci?n est?ndar de este escenario no incluy? subm?tricas `http_reqs{status:*}`).

## Readiness/Health observaciones
- Checks `healthz`/`readyz` sin fallos durante ladder; fallas se concentraron en endpoints autenticados al final.

## Degradaci?n y parada
- Punto de degradaci?n: Degradaci?n observada en tramo alto (25-30 VUs), con errores de checks auth/qv2 y corte por threshold.
- Criterio de parada activado: S?
- Motivo: Se super? threshold de `http_req_failed` con `abortOnFail` durante etapa alta.

## Conclusi?n
- Resultado operativo: estable con degradaci?n controlada en tramo alto.
- Nota de entorno: resultados limitados por homelab y no extrapolables al servidor futuro con fibra.
