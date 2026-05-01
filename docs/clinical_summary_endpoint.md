# Clinical Summary Endpoint (v17)

## Endpoint
- `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`

## Purpose
Returns a simulated professional narrative summary for screening support, organized by sections and accompanied by mandatory disclaimer.

## Legacy compatibility
- Existing endpoint `GET /api/v2/questionnaires/history/{session_id}/results` remains available as legacy/plaintext compatibility path.
- New encrypted-first path for results:
  - `POST /api/v2/questionnaires/history/{session_id}/results-secure`

## Clinical summary sections
The response includes:
1. `sintesis_general`
2. `niveles_de_compatibilidad`
3. `indicadores_principales_observados`
4. `impacto_funcional`
5. `recomendacion_profesional`
6. `aclaracion_importante`

## Risk levels
Per-domain and global levels use:
- `baja`
- `intermedia`
- `relevante`
- `alta`

## Comorbidity logic
`has_comorbidity_signal=true` when two or more domains are at `relevante` or `alta`.

## Mandatory disclaimer
The response always includes an explicit statement that the output is not a clinical diagnosis and does not replace professional evaluation.

## Language policy
The generated narrative must avoid confirmed-diagnosis wording and use screening-compatible language.

## Encrypted transport support
The endpoint supports application-level encrypted envelope requests/responses when transport encryption is enabled.
