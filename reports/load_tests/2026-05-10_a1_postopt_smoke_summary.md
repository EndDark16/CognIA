# 2026-05-10 A1 Postopt Smoke Summary

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
- Script: `scripts/load/k6_smoke.js`
- Duracion: `30s`
- VUs: `5`
- SAFE_MODE: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_SUBMIT: `true`
- SKIP_PDF: `true`

## Resultados
- Requests totales: `157`
- RPS: `4.0606`
- Error rate (`http_req_failed`): `1.2739%`
- p50: `711.37 ms`
- p90: `1102.50 ms`
- p95: `2159.00 ms`
- p99: `N/A`
- max latency: `29666.09 ms`

## Status / checks
- healthz status 200: `pass=38 fail=0`
- readyz status 200: `pass=38 fail=0`
- auth me status 200: `pass=38 fail=0`
- questionnaire active status 200: `pass=38 fail=0`
- 4xx/5xx observados en checks: `0`
- Requests fallidos de transporte/red: `2` (1.27%)

## Readiness y degradacion
- `/readyz` respondio 200 en todas las verificaciones de check.
- Punto de degradacion: outliers intermitentes de latencia con un maximo alto en una muestra puntual.
- Punto de quiebre: no alcanzado.

## Criterios de parada
- No se activo criterio de parada operativo (readyz consecutivo fallando, >5% error sostenido, p95 >10s sostenido, etc.).

## Observaciones por endpoint
- readyz p95: `952.39 ms`
- healthz p95: `646.30 ms`

## Conclusiones
- Escenario completado en produccion con checks funcionales en 200.
- Resultado util para comparacion antes/despues del baseline historico preopt.

## Recomendaciones
- Homelab actual: mantener progresion gradual y evitar cargas agresivas fuera de ventana controlada.
- Futuro servidor + fibra: repetir este escenario con observabilidad host-level completa.
