# Backend Release 2026-04-22 r1

- Release ID: `backend_release_2026-04-22_r1`
- Backend version: `2026.04.22-r1`
- Base commit de referencia: `05f8f12`

## Scope
- Cierre documental backend de brechas 9-25.
- Alineacion de endpoints v1 legacy y reemplazos admin/v2.
- Correcciones backend detectadas por regresion de tests.
- Ingesta de playbook externo de despliegue.

## Cambios funcionales backend
- Nuevo endpoint `POST /api/admin/roles`.
- Nuevo endpoint `POST /api/admin/impersonate/{user_id}`.
- Ajuste de rate limit en `POST /api/auth/password/forgot`.

## Cambios de contrato/documentacion
- `docs/openapi.yaml` actualizado con:
  - deprecacion explicita de endpoints legacy v1 de cuestionario.
  - nuevos endpoints admin (`roles` POST e impersonacion).
  - aclaracion de entorno simulado en descripcion general.
- Actualizaciones en:
  - `docs/api_full_reference.md`
  - `docs/questionnaire_api_contract.md`
  - `docs/backend_gap_matrix_20260422.md`
  - `docs/deployment_playbook_ingest_20260422.md`

## Validacion
- Guardrail OpenAPI/runtime: `1 passed`.
- Suite completa: `pytest -q` => `139 passed, 3 skipped`.

## Estado de despliegue
- Evidencia de playbook externo incorporada.
- Cierre de despliegue productivo definitivo sigue `parcial` hasta versionar en repo todos los artefactos de deploy multi-repo/infra.

## Claim permitido
- Screening/apoyo profesional en entorno simulado.
- No diagnostico clinico automatico.
