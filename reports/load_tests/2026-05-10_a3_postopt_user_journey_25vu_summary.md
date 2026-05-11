# user_journey_read_25vu summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Journey lectura (auth/me + qv2_active)
- Perfil: 25 VUs, modo seguro sin writes pesados
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 10317
- RPS promedio: 42.3147
- Error rate (`http_req_failed`): 0.0000%
- Latencia p50: 313.44 ms
- Latencia p90: 443.55 ms
- Latencia p95: 547.24 ms
- Latencia p99: N/A
- Latencia m?xima: 3106.12 ms
- p95 `auth_me`: 461.65 ms
- p95 `qv2_active`: 609.82 ms

## Checks
- `auth me status 200`: pass=5158, fail=0
- `questionnaire active status 200`: pass=5158, fail=0

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
