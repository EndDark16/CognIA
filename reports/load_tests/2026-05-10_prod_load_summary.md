# 2026-05-10 Production Load Summary

- Fecha: 2026-05-10
- Commit SHA objetivo: `193de2ab1b71a79f2d60b9e3b131852220ca178c`
- Rama: `main`
- Estado: **NO EJECUTADO**

## Motivo operativo

- `baseline` reporto `http_req_failed=32.70%` sostenido durante 5 minutos.
- Esto activa criterio de parada obligatorio (`error rate > 5% por mas de 60s`).
- Para no degradar `cognia.lat`, no se ejecuto `scripts/load/k6_load.js`.

## Campos requeridos

- Duracion/VUs/RPS/latencias/error rate/status codes: `N/A (no ejecutado por criterio de parada)`
- Readyz: estable fuera de prueba (`ready` en muestreo post-baseline)
- Punto de degradacion: ya alcanzado en baseline (10 VUs)
- Punto de quiebre: no alcanzado
