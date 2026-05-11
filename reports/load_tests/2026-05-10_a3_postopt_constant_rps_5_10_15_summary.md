# constant_rps_5_10_15 summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Ramping arrival rate 5?10?15 RPS
- Perfil: Ejecutado solo tras estabilidad en 10 RPS
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 6429
- RPS promedio: 16.3734
- Error rate (`http_req_failed`): 0.0000%
- Latencia p50: 290.52 ms
- Latencia p90: 369.04 ms
- Latencia p95: 395.96 ms
- Latencia p99: N/A
- Latencia m?xima: 3292.90 ms
- p95 `auth_me`: 391.05 ms
- p95 `qv2_active`: 399.11 ms

## Checks
- `auth me status 200`: pass=3214, fail=0
- `questionnaire active status 200`: pass=3214, fail=0

## Status codes
- Breakdown por status HTTP: N/A (la exportaci?n est?ndar de este escenario no incluy? subm?tricas `http_reqs{status:*}`).

## Readiness/Health observaciones
- N/A en este escenario.

## Degradaci?n y parada
- Punto de degradaci?n: Sin degradaci?n significativa observada en el escenario.
- Criterio de parada activado: No
- Motivo: No se activ? criterio de parada.

## Conclusi?n
- Resultado operativo: estable para este perfil.
- Nota de entorno: resultados limitados por homelab y no extrapolables al servidor futuro con fibra.
