# 2026-05-10 A3 postopt warmup summary

- Fecha: 2026-05-10
- Commit SHA probado en producción: `f69252321cd26d8c5f8657223a0a027183bd52e5`
- URL objetivo: `https://www.cognia.lat` + `API_PREFIX=/api`
- Usuario: sintético `perf_loadtest_*` (sin usuarios reales)

## Warmup Python (`scripts/warmup_backend.py`)
- Estado: `OK`
- Resultado: `200` en todas las rutas no destructivas:
  - `/healthz`
  - `/readyz`
  - `/api/auth/login`
  - `/api/auth/me`
  - `/api/v2/security/transport-key`
  - `/api/v2/questionnaires/active` (`guardian/psychologist`, `short/medium`)
- Evidencia: `artifacts/load_tests/2026-05-10_a3_postopt_warmup/warmup.log`

## Warmup shell (`scripts/warmup_backend.sh`)
- Primer intento: fallo por Schannel revocation (`curl` sin `--ssl-no-revoke`) en Windows.
- Ajuste interno aplicado (no contractual):
  - nuevo flag opcional `WARMUP_CURL_SSL_NO_REVOKE=true`
  - fix de parseo de token de login (el body no llegaba al parser Python por uso incorrecto de heredoc + pipe)
- Reintento: `OK`, `200` en todas las rutas no destructivas.
- Evidencia: `artifacts/load_tests/2026-05-10_a3_postopt_warmup/warmup_shell.log`

## Seguridad operativa
- No se ejecutaron acciones destructivas.
- No se crearon sesiones/questionnaire submit/PDF.
- No se imprimieron password ni tokens.
