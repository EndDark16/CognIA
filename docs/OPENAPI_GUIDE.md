# Guia de documentacion OpenAPI (CognIA API)

Objetivo: mantener una especificacion OpenAPI 3.0.3 profesional, consistente y alineada con el runtime real del backend.

## Fuente de verdad
- Contrato publico activo: `docs/openapi.yaml`.
- Referencias historicas: `docs/archive/openapi/` (no usar como fuente operativa).
- Matriz contractual de endpoints: `docs/endpoint_lifecycle_matrix.md`.

## Alcance obligatorio de documentacion
Cada operacion (`get/post/put/patch/delete`) debe incluir:
1. `summary` claro y especifico.
2. `description` completa en espanol con secciones:
   - Objetivo funcional
   - Cuando debe usarse
   - Actor que lo consume
   - Seguridad aplicable
   - Entrada esperada
   - Resultado exitoso
   - Errores posibles y causa funcional
   - Estado contractual
3. `operationId` unico y estable.
4. `responses` con descripciones reales (no usar `Success`/`OK`).
5. `x-contract-status` con uno de:
   - `KEEP_ACTIVE`
   - `KEEP_ACTIVE_BUT_LEGACY`
   - `INTERNAL_ONLY`
   - `DEPRECATE_PUBLIC`
   - `REMOVE_AFTER_COMPAT_WINDOW`
   - `DUPLICATE_TO_CONSOLIDATE`

## Politica de convivencia y deprecacion
- v2 (`/api/v2/*`) es la linea operativa principal.
- v1 clasico y runtime v1 se mantienen con estatus legacy cuando aplica.
- endpoints experimentales deben marcarse como `deprecated` y con estado contractual explicito.
- no eliminar endpoints en caliente sin ventana de compatibilidad y trazabilidad.

## Seguridad en el contrato OpenAPI
- Declarar `bearerAuth` en rutas protegidas.
- Declarar `cookieAuth + csrfHeader` en `/api/auth/refresh`.
- Endpoints admin deben incluir `x-roles: [ADMIN]`.
- Endpoints publicos (salud/docs/email unsubscribe/predict experimental) no deben quedar marcados como autenticados por error.

## Alineacion runtime vs spec
- Guardrail de alineacion: `tests/contracts/test_openapi_runtime_alignment.py`.
- Guardrail de calidad documental: `tests/contracts/test_openapi_documentation_quality.py`.
- Script de mantenimiento contractual:
  - `python scripts/openapi_professionalize.py`

## Checklist de PR (OpenAPI)
1. `docs/openapi.yaml` actualizado.
2. `docs/endpoint_lifecycle_matrix.md` actualizado.
3. `tests/contracts/test_openapi_runtime_alignment.py` en verde.
4. `tests/contracts/test_openapi_documentation_quality.py` en verde.
5. Sin descripciones vacias/genericas y sin respuestas `Success`.
6. Estado contractual consistente (activo/legacy/deprecated/internal).

## Referencias
- `docs/openapi.yaml`
- `docs/endpoint_lifecycle_matrix.md`
- `docs/api_full_reference.md`
- `docs/problem_reporting_backend.md`
- `docs/security_hardening_20260416.md`
