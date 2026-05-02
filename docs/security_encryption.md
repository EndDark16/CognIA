# Security Encryption Guide (v17)

## Overview
The backend applies two complementary controls for questionnaire v2 sensitive data:
1. Field encryption at rest (application layer).
2. Optional encrypted request/response envelope at application transport layer.

TLS/HTTPS remains mandatory in production.

## Encryption at rest

### Key env vars
- `COGNIA_ENABLE_FIELD_ENCRYPTION`
- `COGNIA_FIELD_ENCRYPTION_KEY`
- `COGNIA_FIELD_ENCRYPTION_KEY_ID`

### Service and algorithm
- Service: `api/services/crypto_service.py`
- Algorithm: `AES-256-GCM`

### Covered fields
- `questionnaire_sessions.metadata_json`
- `questionnaire_session_answers.answer_raw`
- `questionnaire_session_answers.answer_normalized`
- `questionnaire_session_internal_features.feature_value_*`
- `questionnaire_session_results.summary_text`
- `questionnaire_session_results.operational_recommendation`
- `questionnaire_session_results.metadata_json`
- `questionnaire_session_result_domains.result_summary`
- `questionnaire_session_result_comorbidity.domains_json`
- `questionnaire_session_result_comorbidity.summary`

## Encrypted transport (application layer)

### Key env vars
- `COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION`
- `COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD`
- `COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV`
- `COGNIA_TRANSPORT_PRIVATE_KEY_PEM`
- `COGNIA_TRANSPORT_KEY_ID`
- `COGNIA_TRANSPORT_KEY_TTL_SECONDS`

### Service and algorithm
- Service: `api/services/transport_crypto_service.py`
- Key bootstrap endpoint: `GET /api/v2/security/transport-key`
- Envelope version: `transport_envelope_v1`
- Key exchange: `RSA-OAEP-256`
- Payload encryption: `AES-256-GCM`

### Headers for encrypted requests
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`

## Sensitive endpoint matrix

### `POST /api/v2/questionnaires/sessions`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `validation_error`

### `PATCH /api/v2/questionnaires/sessions/{session_id}/answers`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `invalid_session_id`
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `validation_error`

### `POST /api/v2/questionnaires/sessions/{session_id}/submit`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `runtime_artifact_unavailable` (503)
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`

### `POST /api/v2/questionnaires/history/{session_id}/results-secure`
- request: `{}` or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `invalid_session_id`
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`

### `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`
- request: `{}` or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `clinical_summary_failed` (500)
  - `runtime_artifact_unavailable` (503)
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`

## Legacy compatibility
- Legacy plaintext endpoint remains:
  - `GET /api/v2/questionnaires/history/{session_id}/results`
- It should be treated as compatibility path, while secure endpoints are preferred.

## Operational safety
- Never commit `.env`.
- Never log private keys or plaintext clinical payloads.
- Avoid persisting decrypted frontend payloads to browser storage.
