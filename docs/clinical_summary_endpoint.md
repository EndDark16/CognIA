# Clinical Summary Endpoint (v17)

## Endpoint
- `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`

## Estado
- `activo` y sensible (soporta transporte cifrado por envelope).
- No reemplaza evaluacion clinica profesional.

## Auth y headers
- bearer JWT obligatorio.
- headers opcionales para modo cifrado:
  - `X-CognIA-Encrypted: 1`
  - `X-CognIA-Crypto-Version: transport_envelope_v1`
- cuando el body va cifrado, ambos headers son obligatorios.

## Request
- path param: `session_id` (uuid).
- body permitido:
  - `{}` en modo plaintext permitido por politica.
  - envelope cifrado (`transport_envelope_v1`).

## Response `200`
- plaintext o envelope cifrado segun politica/contexto.
- payload funcional (`clinical_summary_v1`):
  - `session_id`
  - `report_version`
  - `generated_at`
  - `overall_risk_level` (`baja|intermedia|relevante|alta`)
  - `simulated_diagnostic_text`:
    - `sintesis_general`
    - `niveles_de_compatibilidad`
    - `indicadores_principales_observados`
    - `impacto_funcional`
    - `recomendacion_profesional`
    - `aclaracion_importante`
  - `domains[]`
  - `comorbidity`
  - `disclaimer`

## Errores especificos
- `400 invalid_session_id`
- `400 plaintext_not_allowed`
- `400 encrypted_payload_invalid`
- `400 invalid_crypto_version`
- `400 validation_error`
- `401 invalid_user|unauthorized`
- `403 forbidden`
- `404 not_found`
- `429 rate_limited`
- `500 clinical_summary_failed|db_error|server_error`
- `503 runtime_artifact_unavailable|runtime_assets_unavailable|db_unavailable`

## Compatibilidad y diferencia frente a resultados legacy
- Legacy plaintext de resultados sigue en `GET /api/v2/questionnaires/history/{session_id}/results`.
- Flujo recomendado para datos sensibles:
  - `POST /api/v2/questionnaires/history/{session_id}/results-secure`
  - `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`

## Caveat metodologico
- Salida apta para screening/apoyo profesional en entorno simulado.
- No apta para diagnostico automatico o interpretacion clinica fuerte sin profesional.
