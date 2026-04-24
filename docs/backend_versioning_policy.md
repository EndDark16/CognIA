# Backend Versioning Policy

## Objetivo
Definir un manejo de versiones profesional, repetible y auditable para backend CognIA.

## Esquema de version
- Formato oficial: `YYYY.MM.DD-rN`.
- Ejemplo: `2026.04.22-r1`.
- `rN` incrementa cuando hay mas de una entrega backend el mismo dia.

## Fuente de verdad de version
- Archivo raiz: `VERSION`.
- Historial humano: `CHANGELOG.md`.
- Release notes por entrega: `docs/releases/backend_release_<fecha>_rN.md`.
- Manifiesto de auditoria: `artifacts/backend_release_registry/backend_release_<fecha>_rN_manifest.json`.

## Regla de incremento
- `rN` nuevo cuando cambia cualquiera de estos bloques:
  - contratos API (`docs/openapi.yaml`, rutas/schemas)
  - comportamiento runtime/backend
  - seguridad/hardening operativo
  - migraciones
  - decisiones metodologicas en AGENTS/HANDOFF
- Solo cambios cosmeticos de texto sin impacto operativo pueden agruparse en la release activa del dia.

## Checklist de cierre de release
1. Actualizar `VERSION`.
2. Agregar entrada en `CHANGELOG.md`.
3. Crear/actualizar release note en `docs/releases/`.
4. Publicar manifiesto JSON en `artifacts/backend_release_registry/`.
5. Actualizar `AGENTS.md` y `docs/HANDOFF.md` en la misma ventana.
6. Ejecutar validacion:
   - minima: guardrails de contrato relevantes
   - completa: `pytest -q` cuando hay cambio de comportamiento.

## Caveat metodologico permanente
- El versionado backend no habilita claims clinicos fuertes.
- CognIA se mantiene como screening/apoyo profesional en entorno simulado.
