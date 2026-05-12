# 2026-05-10 A4 Bottleneck Analysis

## 1) Linea de tiempo
- ventana ejecutada: `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/`
- inicio (raw): `2026-05-12T16:39:01.939816-05:00`
- fin (raw): `2026-05-12T16:39:25.218315-05:00`
- primer aumento p95 detectable en timeline: `por confirmar`
- primer error: no observado en endpoints de corrida (`healthz/readyz` en fase default)
- senal de degradacion relativa (helper k6): endpoint `readyz`, `relative_timestamp_ms=11045`

## 2) Endpoint culpable (evidencia disponible)
- escenario ejecutado: `k6_diagnostic_health_vs_api` con `REQUIRE_AUTH=false` (sin token).
- p95 por endpoint:
  - `healthz`: `481.86 ms`
  - `readyz`: `1025.67 ms`
- checks por endpoint:
  - `endpoint__healthz__status 200`: `pass=154 fail=0`
  - `endpoint__readyz__status 200`: `pass=154 fail=0`
- conclusion parcial de esta ventana:
  - dentro del subconjunto medido (`healthz/readyz`), `readyz` domina la latencia p95.
  - no hubo errores funcionales en esos endpoints durante la fase default.

## 3) Host
- snapshot host before/during/after: `no disponible` en esta ventana.
- razon:
  - `scripts/diagnostics/*.sh` no se pudieron ejecutar localmente porque no hay bash operativo (solo launcher WSL sin distro funcional).
  - comando intentado: `bash -n scripts/diagnostics/capture_host_snapshot.sh ...`
  - error exacto: `<3>WSL (9 - Relay) ERROR: CreateProcessCommon:798: execvpe(/bin/bash) failed: No such file or directory`
- impacto:
  - CPU/RAM/swap/memory pressure y Docker stats quedan `por confirmar`.

## 4) DB/Supabase
- captura SQL Supabase: `no ejecutada` (sin acceso SQL configurado en esta ventana).
- comando de verificacion local: `where.exe psql` -> `missing`
- logs backend correlables de produccion: `por confirmar`.
- impacto:
  - waits/locks/connections/pool timeout DB quedan `por confirmar`.

## 5) Red
- snapshot de red before/during/after: `no disponible` en esta ventana (dependia de scripts shell).
- medicion indirecta disponible:
  - `healthz` y `readyz` medidos via k6 desde el cliente de prueba.
- impacto:
  - jitter/packet loss/connect/starttransfer detallado queda `por confirmar`.

## 6) Clasificacion de cuello (esta ventana)
- primario: `no concluyente`
- secundario: `endpoint readiness (readyz) con p95 mayor que healthz en corrida limitada`
- descartado: `ninguno con confianza suficiente`
- no concluyente:
  - CPU
  - RAM/swap
  - red domestica
  - Supabase/DB
  - SQLAlchemy pool
  - Gunicorn workers/threads
  - WAF/CDN
  - auth_me / qv2_active (no medidos en esta corrida por falta de credenciales)
  - cache hit/miss correlado

## 7) Confianza
- nivel global: `baja`
- motivo:
  - solo corrida parcial de diagnostico (`healthz/readyz`) en esta ventana local.
  - faltan credenciales sinteticas para `auth_me/qv2_active`.
  - faltan snapshots host/log/DB/WAF ejecutados en la misma ventana temporal.

## 8) Evidencia y comandos
- artifacts principales:
  - `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/k6_summary_export.json`
  - `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/k6_raw_output.json`
  - `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/k6_handle_summary/*_summary.md`
  - `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/diagnostic_analysis.md`
  - `artifacts/diagnostics/20260512T163900_manual_health_noauth_v7_raw/diagnostic_analysis.json`
- comando ejecutado:
  - `k6 run --summary-export ... --out json=... scripts/load/k6_diagnostic_health_vs_api.js` con `BASE_URL=https://www.cognia.lat`, `API_PREFIX=/api`, `SAFE_MODE=true`, `REQUIRE_AUTH=false`, `K6_VUS=10`, `K6_DURATION=20s`.
- limitaciones documentadas:
  - sin bash operativo para orquestador shell completo.
  - sin credenciales sinteticas para flujos autenticados.
  - sin acceso SQL/WAF en la misma ventana.
