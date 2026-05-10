# Repo Cleanup Report

## Alcance
- Limpieza focal de archivos generados sueltos en raiz.
- Conservacion de trazabilidad historica (no se borro documentacion historica ni artefactos versionados de campanas).

## Fuente de verdad
- OpenAPI activa: `docs/openapi.yaml`.
- OpenAPI historica permitida: `docs/archive/openapi/`.

## Cambios aplicados
- Se movieron artefactos temporales de calidad Sonar/coverage fuera de raiz hacia `artifacts/quality/sonar/legacy_root_snapshot_20260502/`.
- Se actualizaron referencias de tooling para que nuevos outputs queden en `artifacts/quality/sonar/latest/`.

## Resumen cuantitativo
- root_level_files_before=24
- root_level_files_after=20
- root_temp_files_remaining=0
- openapi_contradictory_copies_outside_archive=0

## Conservado intencionalmente
- `docs/archive/openapi/openapi_questionnaire_runtime_v1.yaml` como referencia historica.
- Historico de campanas en `data/` y `artifacts/` sin modificaciones destructivas.
