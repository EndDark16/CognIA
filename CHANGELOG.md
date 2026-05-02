# Changelog

Este changelog usa CalVer de backend (`YYYY.MM.DD-rN`).

## [2026.04.22-r1] - 2026-04-22
- Documentacion backend cerrada para brechas 9-25 con evidencia de codigo.
- OpenAPI y referencia API alineadas para endpoints legacy v1 vs reemplazos admin/v2.
- Endpoints backend agregados/corregidos:
  - `POST /api/admin/roles`
  - `POST /api/admin/impersonate/{user_id}`
- Ajuste de rate limit para `POST /api/auth/password/forgot` respetando configuracion `PASSWORD_FORGOT_RATE_LIMIT`.
- Ingesta versionada de playbook externo de despliegue.
- Validacion completa ejecutada: `pytest -q` en verde (`139 passed, 3 skipped`).
