# Questionnaire API Gap Analysis
Fecha: 2026-03-30

## Gaps funcionales para cuestionario real
1. No hay endpoint dedicado para **save draft**.
2. No hay endpoint para **validacion por seccion**.
3. No hay endpoint para **submit final** separado de draft.
4. No hay endpoint para **obtener template por version/ID** (solo activa).
5. No hay endpoint user-facing para **resultado por evaluacion**.
6. No hay endpoint de **explanation / uncertainty / abstention** por evaluacion.
7. No hay flujo API para **reanudar borrador**.

## Contratos acoplados al placeholder
- Frontend actual consume solo `GET /api/v1/questionnaires/active`.
- Tipos frontend (`likert|boolean|integer|text`) no coinciden con tipos backend detallados.
- `POST /api/v1/evaluations` existe pero no se usa desde UI.

## Endpoints esperados para la fase de diseno/implementacion
- `POST /api/v1/evaluations/draft`
- `POST /api/v1/evaluations/{id}/sections/{section_id}/validate`
- `POST /api/v1/evaluations/{id}/submit`
- `GET /api/v1/questionnaires/{template_id_or_version}`
- `GET /api/v1/evaluations/{id}/result`
- `GET /api/v1/evaluations/{id}/explanation`
- `GET /api/v1/evaluations/{id}/uncertainty`

## Impacto separado
- Backend/API: definir contrato final y ciclo de vida draft->submit->result.
- Frontend/handoff: adoptar nuevos payloads, estados y manejo de errores por seccion.
