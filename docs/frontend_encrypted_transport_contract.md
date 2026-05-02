# Frontend Encrypted Transport Contract (v17)

## Alcance
Contrato operativo para transporte cifrado de endpoints sensibles en `api/v2/questionnaires`.
La fuente de verdad machine-readable es `docs/openapi.yaml`.

## Endpoints cubiertos (quirurgico)

### `GET /api/v2/security/transport-key`
- estado: `activo`.
- auth: publico (sin JWT obligatorio).
- body: no aplica.
- success `200`: `key_id`, `algorithm`, `public_key_jwk`, `expires_at`, `version`.
- errores principales:
  - `429 rate_limited`
  - `500 transport_key_failed`
- rate limit: `QV2_TRANSPORT_KEY_RATE_LIMIT` (default `60 per minute`).

### `POST /api/v2/questionnaires/sessions`
- estado: `activo` (sensible).
- auth: bearer obligatorio.
- headers opcionales cifrado:
  - `X-CognIA-Encrypted: 1`
  - `X-CognIA-Crypto-Version: transport_envelope_v1`
- body:
  - plaintext (solo si politica lo permite): `mode`, `role`, `child_age_years`, `child_sex_assigned_at_birth`, `metadata`.
  - encrypted envelope: ver formato abajo.
- success `201`: respuesta plaintext (`session`) o envelope cifrado.
- errores principales:
  - `400 plaintext_not_allowed|encrypted_payload_invalid|invalid_crypto_version|validation_error`
  - `401 invalid_user|unauthorized`
  - `500 db_error|session_create_failed`
  - `503 db_unavailable|runtime_assets_unavailable`

### `PATCH /api/v2/questionnaires/sessions/{session_id}/answers`
- estado: `activo` (sensible).
- auth: bearer obligatorio.
- headers cifrado: mismos que arriba.
- body plaintext: `answers[]` + `mark_final` (opcional).
- success `200`: `session` + `saved_answers` (plaintext o cifrado).
- errores principales:
  - `400 invalid_session_id|plaintext_not_allowed|encrypted_payload_invalid|invalid_crypto_version|validation_error`
  - `401 invalid_user|unauthorized`
  - `403 forbidden`
  - `404 not_found`
  - `500 db_error|save_failed`
  - `503 db_unavailable|runtime_assets_unavailable`

### `POST /api/v2/questionnaires/sessions/{session_id}/submit`
- estado: `activo` (sensible).
- auth: bearer obligatorio.
- headers cifrado: mismos que arriba.
- body plaintext: `force_reprocess` (opcional).
- success `200`: resultados finales de sesion (plaintext o cifrado).
- errores principales:
  - `400 invalid_session_id|plaintext_not_allowed|encrypted_payload_invalid|invalid_crypto_version|validation_error`
  - `401 invalid_user|unauthorized`
  - `403 forbidden`
  - `404 not_found`
  - `500 db_error|submit_failed`
  - `503 runtime_artifact_unavailable|runtime_assets_unavailable|db_unavailable`

### `POST /api/v2/questionnaires/history/{session_id}/results-secure`
- estado: `active secure replacement`.
- reemplaza funcionalmente a:
  - legacy plaintext: `GET /api/v2/questionnaires/history/{session_id}/results`
- auth: bearer obligatorio.
- body: `{}` o encrypted envelope segun politica.
- success `200`: `session/result/domains/comorbidity` (plaintext o cifrado).
- errores principales:
  - `400 invalid_session_id|plaintext_not_allowed|encrypted_payload_invalid|invalid_crypto_version`
  - `401 invalid_user|unauthorized`
  - `403 forbidden`
  - `404 not_found`

### `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`
- estado: `activo` (sensible).
- auth: bearer obligatorio.
- body: `{}` o encrypted envelope segun politica.
- success `200`: `clinical_summary_v1` (plaintext o cifrado).
- errores principales:
  - `400 invalid_session_id|plaintext_not_allowed|encrypted_payload_invalid|invalid_crypto_version|validation_error`
  - `401 invalid_user|unauthorized`
  - `403 forbidden`
  - `404 not_found`
  - `500 clinical_summary_failed|db_error`
  - `503 runtime_artifact_unavailable|runtime_assets_unavailable|db_unavailable`

## Envelope cifrado
Headers para request cifrada:
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`

Request envelope:
```json
{
  "encrypted": true,
  "version": "transport_envelope_v1",
  "key_id": "transport-key-v1",
  "alg": "AES-256-GCM",
  "encrypted_key": "...",
  "iv": "...",
  "ciphertext": "...",
  "aad": "transport_envelope_v1|frontend"
}
```

Response envelope:
```json
{
  "encrypted": true,
  "version": "transport_envelope_v1",
  "key_id": "transport-key-v1",
  "alg": "AES-256-GCM",
  "iv": "...",
  "ciphertext": "...",
  "aad": "transport_envelope_v1|transport-key-v1"
}
```

## Notas de seguridad frontend
- no persistir payload clinico plaintext en `localStorage/sessionStorage`.
- no loggear payload sensible en consola.
- mantener decrypted payload en memoria volatil.
- esta capa no reemplaza TLS ni controles de autorizacion backend.
