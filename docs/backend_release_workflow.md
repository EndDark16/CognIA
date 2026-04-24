# Backend Release Workflow

## Objetivo
Estandarizar como se versiona, sube y promueve backend CognIA con trazabilidad completa.

## Flujo oficial de ramas
- Trabajo diario: `dev.enddark`
- Integracion: `development`
- Release final: `main`

Referencia base: `CONTRIBUTING.md`.

## Flujo operativo por entrega
1. Crear/actualizar feature branch desde `dev.enddark`.
2. Implementar cambios + tests.
3. Actualizar versionado release:
   - `VERSION`
   - `CHANGELOG.md`
   - release note en `docs/releases/`
   - manifiesto en `artifacts/backend_release_registry/`
4. Actualizar trazabilidad:
   - `docs/traceability_map.md`
   - `docs/traceability_map.md`
5. Abrir PR hacia `dev.enddark` usando `.github/pull_request_template.md`.
6. Merge de PR hacia `dev.enddark`.
7. Abrir PR de promocion `dev.enddark -> development`.
8. Merge de promocion hacia `development`.
9. Solo para cierre productivo aprobado: PR `development -> main`.

## Buenas practicas obligatorias
- No subir secretos ni `.env`.
- PR enfocado (un release coherente, no cambios mixtos sin trazabilidad).
- Adjuntar evidencia de test ejecutado.
- Mantener claim metodologico: screening/apoyo en entorno simulado; no diagnostico automatico.

## Plantilla minima de PR
Completar siempre:
- `Summary`
- `Change Type`
- `Database / Migrations`
- `Config / Env`
- `Testing`
- `Security / Privacy`
- `Notes / Risks` (incluye rollback plan)

## Estrategia de merge recomendada
- Preferir `squash` para mantener historial limpio por release.
- Titulo de merge sugerido:
  - `release(backend): <version> <scope breve>`

## Checklist de promocion dev.enddark -> development
- PR a `dev.enddark` mergeado y verde.
- Release files consistentes (`VERSION`, `CHANGELOG`, note, manifest).
- Guardrails de contrato/API en verde.
- `pytest -q` de release ejecutado.
