# A2 postopt warmup

- Fecha UTC: 2026-05-10T23:18:39.591617+00:00
- Script objetivo: `scripts/warmup_backend.py`
- Resultado del script Python: bloqueado en este cliente por CDN/WAF (`403`, `error code: 1010`) al consultar `/healthz`.
- Comando ejecutado:
  - `BASE_URL=https://www.cognia.lat API_PREFIX=/api USERNAME=<test> PASSWORD=<test> SAFE_MODE=true python scripts/warmup_backend.py`
- Error observado:
  - `RuntimeError: warmup failed at /healthz: status=403 payload=error code: 1010`
- Mitigacion operativa aplicada en la misma ventana:
  - warmup manual con `curl --ssl-no-revoke` (healthz/readyz/login/auth/me/transport-key/qv2 active guardian+psychologist short+medium), todos `200`.
- Evidencia: `artifacts/load_tests/2026-05-10_a2_postopt/warmup_manual.log`.
