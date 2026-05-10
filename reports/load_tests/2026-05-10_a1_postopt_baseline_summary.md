# 2026-05-10 A1 Postopt Baseline Summary

- Fecha: 2026-05-10 16:00:57 -05:00
- Commit SHA probado (main): `bae532e0495aa62459a5278bf1a2a3858c11e595`
- Rama desplegada: `main`
- URL objetivo: `https://www.cognia.lat`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`

## Infraestructura
- Servidor domestico limitado (homelab)
- Cliente de ejecucion de carga: Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb
- Base de datos externa: Supabase
- Este entorno NO representa la infraestructura final (servidor robusto + fibra)

## Escenario
- Script: `scripts/load/k6_baseline.js`
- Duracion: `5m`
- VUs: `10`
- SAFE_MODE: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_SUBMIT: `true`
- SKIP_PDF: `true`

## Resultados
- Requests totales: `2373`
- RPS: `7.6512`
- Error rate (`http_req_failed`): `0.0843%`
- p50: `1055.42 ms`
- p90: `1886.57 ms`
- p95: `2303.24 ms`
- p99: `N/A`
- max latency: `5552.04 ms`

## Status / checks
- healthz status 200: `pass=592 fail=0`
- readyz status 200: `pass=592 fail=0`
- auth me status 200: `pass=592 fail=0`
- questionnaire active status 200: `pass=592 fail=0`
- 4xx/5xx observados en checks: `0`
- Requests fallidos de transporte/red: `2` (0.08%)

## Readiness y degradacion
- `/readyz` respondio 200 en todas las verificaciones de check.
- Punto de degradacion: aumento de p95 por endpoint (`readyz`, `healthz`, `qv2_active`) por encima de thresholds estrictos del script.
- Punto de quiebre: no alcanzado.

## Criterios de parada
- No se activo criterio de parada operativo (readyz consecutivo fallando, >5% error sostenido, p95 >10s sostenido, etc.).

## Observaciones por endpoint
- qv2_active p95: `3086.19 ms`
- readyz p95: `2121.08 ms`
- healthz p95: `1515.04 ms`

## Conclusiones
- Escenario completado en produccion con checks funcionales en 200.
- Resultado util para comparacion antes/despues del baseline historico preopt.

## Recomendaciones
- Homelab actual: mantener progresion gradual y evitar cargas agresivas fuera de ventana controlada.
- Futuro servidor + fibra: repetir este escenario con observabilidad host-level completa.
