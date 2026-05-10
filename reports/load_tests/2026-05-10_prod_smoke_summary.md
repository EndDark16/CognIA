# 2026-05-10 Production Smoke Summary

- Fecha: 2026-05-10 13:46 (America/Bogota)
- Commit SHA probado (main): `193de2ab1b71a79f2d60b9e3b131852220ca178c`
- Rama: `main`
- URL objetivo: `https://www.cognia.lat`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`
- Infraestructura actual: Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb, DB Supabase remota.
- Tipo de ejecucion: carga externa desde esta maquina (no desde el mismo host de backend).

## Configuracion escenario

- Script: `scripts/load/k6_smoke.js`
- Duracion: 30s
- VUs max: 5
- SAFE_MODE: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## Resultados

- RPS: `1.6754`
- http_req_failed: `2.74%` (2/73 aprox no-200)
- Latencia p50: `1484.44 ms`
- Latencia p90: `5086.28 ms`
- Latencia p95: `6377.01 ms`
- Latencia p99: `N/A` (no exportada por summary)
- Latencia max: `8166.51 ms`
- Readyz antes/despues: `ready` / `ready`

## Status codes y errores

- Checks de estado por endpoint en smoke:
  - `healthz`: 17 pass, 0 fail
  - `readyz`: 17 pass, 0 fail
  - `auth me`: 17 pass, 0 fail
  - `questionnaire active`: 17 pass, 0 fail
- Se observaron respuestas no-200 en el agregado HTTP (`2.74%`), pero `summary-export` no desglosa codigos exactos 4xx/5xx por tipo.

## Degradacion / quiebre

- Degradacion observada: latencia p95 alta para healthz/readyz y error-rate por encima del threshold de smoke.
- Punto de quiebre: no alcanzado.
- Criterios de parada obligatorios: no activados en smoke.

## Conclusion

- El backend permanece disponible, pero smoke ya muestra latencia y errores por encima de thresholds esperados para este entorno.
- Se continua a baseline con precaucion para validar estabilidad sostenida.
