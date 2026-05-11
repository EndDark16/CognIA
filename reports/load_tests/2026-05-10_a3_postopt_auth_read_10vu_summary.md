# auth_read_10vu summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Lectura autenticada /auth/me con login en setup
- Perfil: 10 VUs, lectura auth
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 2994
- RPS promedio: 12.2346
- Error rate (`http_req_failed`): 0.0000%
- Latencia p50: 285.92 ms
- Latencia p90: 421.29 ms
- Latencia p95: 487.08 ms
- Latencia p99: N/A
- Latencia m?xima: 3359.06 ms
- p95 `auth_me`: 485.70 ms
- p95 `qv2_active`: N/A

## Checks
- `auth me status 200`: pass=2993, fail=0

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
