# 2026-05-10 A1 Postopt Micro-Baseline Summary

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
- Duracion: `3m`
- VUs: `5`
- SAFE_MODE: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_SUBMIT: `true`
- SKIP_PDF: `true`

## Resultados
- Requests totales: `1137`
- RPS: `6.0781`
- Error rate (`http_req_failed`): `0.1759%`
- p50: `710.24 ms`
- p90: `1024.18 ms`
- p95: `1218.51 ms`
- p99: `N/A`
- max latency: `3390.57 ms`

## Status / checks
- healthz status 200: `pass=283 fail=0`
- readyz status 200: `pass=283 fail=0`
- auth me status 200: `pass=283 fail=0`
- questionnaire active status 200: `pass=283 fail=0`
- 4xx/5xx observados en checks: `0`
- Requests fallidos de transporte/red: `2` (0.18%)

## Readiness y degradacion
- `/readyz` respondio 200 en todas las verificaciones de check.
- Punto de degradacion: sin degradacion severa; se observaron outliers de latencia bajo carga.
- Punto de quiebre: no alcanzado.

## Criterios de parada
- No se activo criterio de parada operativo (readyz consecutivo fallando, >5% error sostenido, p95 >10s sostenido, etc.).

## Observaciones por endpoint
- qv2_active p95: `2220.97 ms`
- readyz p95: `1106.15 ms`
- healthz p95: `622.10 ms`

## Conclusiones
- Escenario completado en produccion con checks funcionales en 200.
- Resultado util para comparacion antes/despues del baseline historico preopt.

## Recomendaciones
- Homelab actual: mantener progresion gradual y evitar cargas agresivas fuera de ventana controlada.
- Futuro servidor + fibra: repetir este escenario con observabilidad host-level completa.
