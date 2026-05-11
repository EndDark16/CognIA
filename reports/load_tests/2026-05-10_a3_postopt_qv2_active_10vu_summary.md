# qv2_active_read_10vu summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Lectura /api/v2/questionnaires/active
- Perfil: 10 VUs, flujo lectura cuestionario activo
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 2843
- RPS promedio: 11.6169
- Error rate (`http_req_failed`): 0.0000%
- Latencia p50: 306.25 ms
- Latencia p90: 432.62 ms
- Latencia p95: 510.30 ms
- Latencia p99: N/A
- Latencia m?xima: 5337.28 ms
- p95 `auth_me`: N/A
- p95 `qv2_active`: 509.83 ms

## Checks
- `questionnaire active status 200`: pass=2842, fail=0

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
