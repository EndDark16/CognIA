# Guia de documentacion OpenAPI (CognIA API)

Objetivo: mantener una especificacion OpenAPI 3.0.3 consistente, clara y alineada al comportamiento real del backend.

## Alcance
- Aplica a endpoints nuevos y cambios de endpoints existentes.
- La fuente oficial vive en `docs/openapi.yaml`.
- `docs/archive/openapi/` conserva snapshots historicos y no debe usarse como contrato activo.

## Convenciones
- `operationId`: unico y estable, formato verbo+sustantivo.
- `tags`: por dominio funcional (`Auth`, `MFA`, `Admin`, `Questionnaires`, `Evaluations`, `ProblemReports`, etc.).
- Reutilizar `components/schemas` y evitar esquemas inline innecesarios.
- Mantener naming de payloads consistente con la API real.
- `summary`: accion concreta y legible para consumidor funcional (evitar `GET foo`, `POST bar`).
- `description` por endpoint: obligatoria y en espanol tecnico, incluyendo:
  - objetivo funcional real;
  - actor/rol esperado;
  - seguridad aplicable;
  - parametros (path/query/header/cookie);
  - body (obligatorio/opcional y content-type);
  - comportamiento esperado;
  - respuesta exitosa + significado;
  - errores posibles;
  - persistencia/workflow/trazabilidad;
  - clasificacion (publico/autenticado/admin/legacy/experimental).

## Paginacion estandar
Para listados:
- Query: `page`, `page_size`
- Respuesta:
  - `items` o `data` (segun endpoint legacy)
  - `pagination = {page, page_size, total, pages}`

## Errores
Formato base esperado:
```json
{
  "msg": "Validation error",
  "error": "validation_error",
  "details": {}
}
```

Documentar segun aplique: `400`, `401`, `403`, `404`, `409`, `429`, `500`.

## Seguridad
- Declarar JWT Bearer en operaciones protegidas.
- Documentar restricciones por rol con `x-roles` cuando aplique.
- No marcar como protegidos endpoints publicos de salud/docs.

## Checklist de mantenimiento
1. `operationId` unico.
2. Request/response reflejan el handler real.
3. Errores y codigos HTTP consistentes.
4. Ejemplos validos y realistas.
5. Rutas nuevas agregadas al spec y a docs operativas.
6. Cero endpoints sin `description`.
7. Sin summaries mecanicos tipo `GET x` / `POST y`.
8. Validacion runtime-vs-spec en `tests/contracts/test_openapi_runtime_alignment.py` en verde.

## Referencias
- `docs/openapi.yaml`
- `docs/api_full_reference.md`
- `docs/problem_reporting_backend.md`
