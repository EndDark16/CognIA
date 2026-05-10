# 2026-05-10 Backend Performance Final Report

## 1) Resumen ejecutivo

Se completo el flujo de promocion `perf/safe-backend-optimization-audit -> dev.enddark -> development -> main`, se verifico deploy en `main`, y se ejecutaron pruebas reales contra `https://www.cognia.lat` hasta que se activo criterio de parada obligatorio en `baseline`.

## 2) Contexto de infraestructura actual

- Servidor domestico limitado.
- Cliente de prueba: Mac 8 GB RAM, Intel Core i5-6360U x4, internet ~16 Mb.
- DB remota: Supabase.
- Este entorno **no representa** la capacidad final esperada tras migracion a servidor robusto + fibra.

## 3) Deploy y verificacion

- PRs y merges:
  - `#133` perf -> dev.enddark (merged)
  - `#134` dev.enddark -> development (merged)
  - `#135` development -> main (merged)
- SHA desplegado en `main`: `193de2ab1b71a79f2d60b9e3b131852220ca178c`
- Workflows verificados (GitHub Actions):
  - `CI Backend`: success
  - `Deploy Backend (Best Effort)`: success
- Health pattern real detectado:
  - `https://www.cognia.lat/healthz` -> 200
  - `https://www.cognia.lat/readyz` -> 200
  - `https://www.cognia.lat/api/healthz` -> 404
  - `https://www.cognia.lat/api/readyz` -> 404
- Configuracion efectiva de scripts:
  - `BASE_URL=https://www.cognia.lat`
  - `API_PREFIX=/api`

## 4) Ejecucion de carga real (produccion)

### Smoke (ejecutado)

- Script: `scripts/load/k6_smoke.js`
- Duracion/VUs: 30s / 5 VUs
- RPS: 1.6754
- Error rate: 2.74%
- p50/p90/p95/max: 1484.44 / 5086.28 / 6377.01 / 8166.51 ms
- Readyz pre/post: ready/ready
- Resultado: disponibilidad mantenida, thresholds de latencia/error cruzados.

### Baseline (ejecutado)

- Script: `scripts/load/k6_baseline.js`
- Duracion/VUs: 5m / 10 VUs
- RPS: 3.1213
- Error rate: 32.70%
- p50/p90/p95/max: 2396.63 / 6693.93 / 7615.34 / 12032.56 ms
- Readyz pre/post: ready/ready
- Resultado: degradacion severa sostenida.

### Load/Stress/Spike/Soak/Questionnaire_v2_flow

- Estado: no ejecutados.
- Motivo: criterio de parada obligatorio activado en baseline (`error rate > 5%` sostenido).
- Decision: detener escalamiento para no afectar `cognia.lat` ni saturar entorno domestico.

## 5) Punto de degradacion y punto de quiebre

- Punto de degradacion observado: baseline a 10 VUs.
- Punto de quiebre total: no alcanzado (servicio no cayo completamente).

## 6) Cuellos de botella probables (entorno actual)

- Capacidad limitada de CPU/RAM del host domestico.
- Latencia variable hacia Supabase.
- Throughput de red domestica.
- Sensibilidad del stack a concurrencia moderada en endpoints autenticados/runtime.

## 7) Recomendaciones para servidor actual

- Mantener pruebas de produccion en ventana de baja actividad.
- Limitar pruebas rutinarias a smoke y micro-baseline controlado.
- Ajustar rate limits/paths hot con foco en `auth_me`, `readyz` y `questionnaire active`.
- Evitar stress/spike en produccion mientras baseline siga mostrando error-rate elevado.

## 8) Recomendaciones para infraestructura futura (servidor robusto + fibra)

- Repetir la misma suite k6 con generador externo dedicado.
- Capturar status-code breakdown completo (4xx/5xx) y telemetria host-level durante pruebas.
- Recalibrar thresholds objetivo (p95 y error-rate) para capacidad superior.
- Ejecutar nuevamente load/stress/spike/soak/questionnaire_v2_flow.

## 9) Confirmaciones de alcance

- Frontend: no modificado.
- Contratos API publicos: no rotos por esta fase.
- Modelos/thresholds clinicos/metodologicos: no alterados.
- Datos reales: no usados para carga (se creo usuario sintetico `perf_loadtest_*`).
- Archivos sucios protegidos del workspace: preservados y fuera de commits de optimizacion.
