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
- `questionnaire_session_pdf_exports.metadata_json`
- `qr_evaluation_response.answer_raw`
- `qr_evaluation_response.answer_normalized`
- `qr_domain_result.recommendation_text`
- `qr_domain_result.explanation_short`
- `qr_domain_result.contributors_json`
- `qr_domain_result.caveats_json`
- `qr_notification.title`
- `qr_notification.body`
- `qr_notification.payload_json`
- `problem_reports.description`
- `problem_reports.admin_notes`
- `problem_reports.metadata_json`
- `problem_report_attachments.metadata_json`

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
- Key bootstrap endpoint: `GET /api/v2/security/transport-key` (public, no JWT required)
- Transport key bootstrap rate limit: `QV2_TRANSPORT_KEY_RATE_LIMIT` (default `60 per minute`)
- Envelope version: `transport_envelope_v1`
- Key exchange: `RSA-OAEP-256`
- Payload encryption: `AES-256-GCM`
- Public bootstrap response only contains: `key_id`, `algorithm`, `public_key_jwk`, `expires_at`, `version`.
- Private key material is never exposed.

### Headers for encrypted requests
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`
- Header validation is strict in sensitive endpoints:
  - invalid `X-CognIA-Encrypted` -> `encrypted_payload_invalid`
  - missing/invalid `X-CognIA-Crypto-Version` in encrypted mode -> `invalid_crypto_version`
  - encrypted payload without `X-CognIA-Encrypted: 1` -> `encrypted_payload_invalid`

## Sensitive endpoint matrix

### `POST /api/v2/questionnaires/sessions`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `invalid_crypto_version`
  - `validation_error`

### `PATCH /api/v2/questionnaires/sessions/{session_id}/answers`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `invalid_session_id`
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `invalid_crypto_version`
  - `validation_error`

### `POST /api/v2/questionnaires/sessions/{session_id}/submit`
- request: plaintext or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `runtime_artifact_unavailable` (503)
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `invalid_crypto_version`

### `POST /api/v2/questionnaires/history/{session_id}/results-secure`
- request: `{}` or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `invalid_session_id`
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `invalid_crypto_version`

### `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`
- request: `{}` or encrypted envelope (policy dependent).
- response: plaintext or encrypted envelope.
- notable errors:
  - `clinical_summary_failed` (500)
  - `runtime_artifact_unavailable` (503)
  - `plaintext_not_allowed`
  - `encrypted_payload_invalid`
  - `invalid_crypto_version`

## Legacy compatibility
- Legacy plaintext endpoint remains:
  - `GET /api/v2/questionnaires/history/{session_id}/results`
- It is JWT-protected and returns:
  - `X-CognIA-Endpoint-Status: legacy_plaintext`
  - `X-CognIA-Replacement: /api/v2/questionnaires/history/{session_id}/results-secure`
  - `Cache-Control: no-store`
- It should be treated as compatibility path, while secure endpoints are preferred.

## Operational safety
- Never commit `.env`.
- Never log private keys or plaintext clinical payloads.
- Avoid persisting decrypted frontend payloads to browser storage.
