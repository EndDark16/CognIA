# infra_smoke summary

- Fecha: 2026-05-10
- Commit SHA probado: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat/api`
- BASE_URL/API_PREFIX: `https://www.cognia.lat` + `/api`
- Infraestructura: Servidor dom?stico (Mac 8 GB RAM, Intel Core i5-6360U x4, Internet ~16 Mb, DB Supabase remota)
- Objetivo: Smoke de infraestructura (healthz/readyz)
- Perfil: Bajo VU, tr?fico de control de salud
- Safe mode: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## M?tricas principales
- Requests totales: 328
- RPS promedio: 6.5616
- Error rate (`http_req_failed`): 0.6098%
- Latencia p50: 339.43 ms
- Latencia p90: 1003.91 ms
- Latencia p95: 1137.97 ms
- Latencia p99: N/A
- Latencia m?xima: 1560.29 ms
- p95 `auth_me`: N/A
- p95 `qv2_active`: N/A

## Checks
- `healthz status 200`: pass=162, fail=0
- `readyz status 200`: pass=162, fail=0

## Status codes
- Breakdown por status HTTP: N/A (la exportaci?n est?ndar de este escenario no incluy? subm?tricas `http_reqs{status:*}`).

## Readiness/Health observaciones
- Health p95=677.58 ms, Ready p95=1324.74 ms, checks de health/ready sin fallos funcionales.

## Degradaci?n y parada
- Punto de degradaci?n: Sin degradaci?n significativa observada en el escenario.
- Criterio de parada activado: No
- Motivo: No se activ? criterio de parada.

## Conclusi?n
- Resultado operativo: estable para este perfil.
- Nota de entorno: resultados limitados por homelab y no extrapolables al servidor futuro con fibra.
