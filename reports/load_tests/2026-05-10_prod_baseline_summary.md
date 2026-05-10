# 2026-05-10 Production Baseline Summary

- Fecha: 2026-05-10 13:47-13:52 (America/Bogota)
- Commit SHA probado (main): `193de2ab1b71a79f2d60b9e3b131852220ca178c`
- Rama: `main`
- URL objetivo: `https://www.cognia.lat`
- BASE_URL: `https://www.cognia.lat`
- API_PREFIX: `/api`
- Infraestructura actual: Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb, DB Supabase remota.

## Configuracion escenario

- Script: `scripts/load/k6_baseline.js`
- Duracion: 5m
- VUs max: 10
- SAFE_MODE: `true`
- SKIP_WRITE_HEAVY: `true`
- SKIP_PDF: `true`
- SKIP_SUBMIT: `true`

## Resultados

- RPS: `3.1213`
- http_req_failed: `32.70%` (326/997)
- Latencia p50: `2396.63 ms`
- Latencia p90: `6693.93 ms`
- Latencia p95: `7615.34 ms`
- Latencia p99: `N/A` (no exportada por summary)
- Latencia max: `12032.56 ms`
- Readyz antes/despues: `ready` / `ready`
- Muestreo post-baseline de readyz: 5/5 `ready`, latencia aproximada `813.94-1149.40 ms`.

## Status codes y errores

- Checks por endpoint:
  - `healthz`: 169 pass, 79 fail (no-200)
  - `readyz`: 167 pass, 81 fail (no-200)
  - `auth me`: 166 pass, 82 fail (no-200)
  - `questionnaire active`: 166 pass, 82 fail (no-200)
- `summary-export` no desglosa codigos exactos 4xx/5xx, solo tasa agregada de no-200.

## Degradacion / quiebre

- Degradacion observada: severa y sostenida.
- Punto de degradacion operativo: dentro de baseline a 10 VUs.
- Punto de quiebre duro (caida total): no alcanzado (servicio siguio respondiendo).

## Criterios de parada

- Activado criterio obligatorio: `error rate > 5% por mas de 60s`.
- Implicacion: se detuvo el avance a `load/stress/spike/soak/questionnaire_v2_flow` para no afectar estabilidad de produccion.

## Conclusion

- En infraestructura actual, baseline ya excede los limites de estabilidad aceptables para continuar pruebas mas agresivas en produccion.
- Se prioriza preservacion del servicio sobre ampliar carga.
