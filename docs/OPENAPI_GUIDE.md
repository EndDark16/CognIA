# Guía de documentación OpenAPI (CognIA API)

Objetivo: mantener una documentación OpenAPI 3.0.3 consistente, clara y validada, alineada al comportamiento real de la API.

## Alcance
- Esta guía aplica a todos los endpoints nuevos y a los cambios de endpoints existentes.
- El spec oficial vive en `docs/openapi.yaml`.

## Convenciones generales
- `operationId`: único, estable y con convención verbo+sustantivo.
  - Ejemplos: `createUser`, `listUsers`, `getUserById`, `updateUserById`, `deleteUserById`.
- `tags`: por dominio (Auth, MFA, Users, Admin, Questionnaires, Evaluations, Health, Email, Predict).
- `components/schemas`: preferir componentes reutilizables y evitar schemas inline.
- Naming de campos:
  - En general, el JSON usa `snake_case`.
  - Excepción: endpoints de password (`/api/auth/password/*`) usan `camelCase` (p. ej. `currentPassword`), según `data_key` de Marshmallow.
- Descripciones: breves, accionables y enfocadas en reglas reales.

## Paginación estándar
Para endpoints list/paginados:
- Query params: `page` (default 1, min 1), `page_size` (default 20, min 1, max 100).
- Respuesta:
  - `data`: array del recurso
  - `pagination`: `{ page, page_size, total, pages }`
- Usar `components/schemas/Pagination` y wrappers `Paged*Response` si aplica.
- Agregar ejemplos con paginación realista por dominio.

## Errores estándar
Todos los endpoints deben documentar errores relevantes:
- Base mínima (según aplica): `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`.
- Formato estándar: `ErrorResponse`.
  - Campos: `msg`, `error`, opcional `details`, opcional `trace_id`.
- Si existe forma legacy, documentar como `deprecated` y/o `oneOf`.

## Seguridad
- Definir `components/securitySchemes` reales (JWT bearer + cookies + CSRF).
- Usar `security` global si aplica o por operación.
- Excluir endpoints públicos: login, register, health, etc.
- Si hay roles, documentar en `x-roles` o en description.

## Request/Response bodies
- `requestBody.required` en POST/PUT/PATCH.
- Definir `required` en schemas y reglas de validación (min/max, enum, pattern).
- `PATCH`: documentar como merge-patch si aplica.
- `201`: incluir header `Location` cuando corresponda.
- Respuestas deben reflejar el shape real del handler.

## Ejemplos
Para cada operación con body:
- Incluir `examples` (no solo `example`):
  - `typical`, `minimal`, `edge` si tiene sentido.
- Para listas: incluir ejemplo con `pagination`.
- Los ejemplos deben respetar validaciones reales y ser coherentes entre sí.

## Status codes
- `201` para creaciones, `200` para lecturas/actualizaciones, `204` solo cuando no hay body.
- Evitar usar `200` cuando el handler retorna `201`.
- Documentar códigos especiales (p. ej. `423 Locked` en login si hay lockout).

## Checklist antes de merge
1. `operationId` único y estable.
2. `tags` correctos y consistentes.
3. Schemas en `components` (sin inline innecesarios).
4. Paginación estándar aplicada donde corresponde.
5. Errores estándar documentados.
6. Seguridad declarada correctamente.
7. Ejemplos realistas.
8. Spec válido OpenAPI 3.0.3 (sin refs rotos).

## Validación
Si está disponible:
- Validar el spec con un validador OpenAPI 3.0.3.
- En local se puede usar `openapi-spec-validator` (Python).
