# constant_rps_5_10 summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Ramping arrival rate 5?10 RPS
- Perfil: Variante controlada A3 para evitar 20 RPS
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 3299
- RPS promedio: 12.1027
- Error rate (`http_req_failed`): 0.0000%
- Latencia p50: 293.53 ms
- Latencia p90: 358.18 ms
- Latencia p95: 387.56 ms
- Latencia p99: N/A
- Latencia m?xima: 3038.34 ms
- p95 `auth_me`: 385.67 ms
- p95 `qv2_active`: 388.28 ms

## Checks
- `auth me status 200`: pass=1649, fail=0
- `questionnaire active status 200`: pass=1649, fail=0

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
