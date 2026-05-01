# Security Encryption Guide (v17)

## Overview
This backend adds two complementary protections for sensitive questionnaire v2 data:
1. Field encryption at rest (application layer).
2. Optional encrypted request/response envelope at application transport layer (in addition to HTTPS/TLS).

## TLS requirement
HTTPS/TLS remains mandatory in production.
App-level transport encryption does not replace TLS; it complements it for sensitive JSON bodies.

## Field encryption at rest

### Environment variables
- `COGNIA_ENABLE_FIELD_ENCRYPTION=true|false`
- `COGNIA_FIELD_ENCRYPTION_KEY` (base64url 32-byte key recommended)
- `COGNIA_FIELD_ENCRYPTION_KEY_ID` (key id label)

### Implementation
- Service: `api/services/crypto_service.py`
- Algorithm: `AES-256-GCM`
- Envelope fields include:
  - version
  - algorithm
  - key_id
  - nonce
  - ciphertext
  - purpose

### Dual-read compatibility
- If a value is encrypted: backend decrypts on read.
- If value is legacy plaintext: backend reads plaintext safely.

### Sensitive fields covered
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

## Application-level payload encryption

### Environment variables
- `COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION=true|false`
- `COGNIA_TRANSPORT_REQUIRE_ENCRYPTION_PROD=true|false`
- `COGNIA_TRANSPORT_ALLOW_PLAINTEXT_IN_DEV=true|false`
- `COGNIA_TRANSPORT_PRIVATE_KEY_PEM` (server private RSA key)
- `COGNIA_TRANSPORT_KEY_ID`
- `COGNIA_TRANSPORT_KEY_TTL_SECONDS`

### Implementation
- Service: `api/services/transport_crypto_service.py`
- Key endpoint: `GET /api/v2/security/transport-key`
- Envelope version: `transport_envelope_v1`
- Key exchange: `RSA-OAEP-256`
- Payload encryption: `AES-256-GCM`

### Sensitive endpoint behavior
- If encrypted transport is active and strict policy is enabled:
  - plaintext payloads are rejected for sensitive endpoints.
- If encrypted request is accepted:
  - sensitive response can be returned encrypted.

### Required headers for encrypted calls
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`

## Logging and secrets
- Secrets are read from environment only.
- Do not commit `.env`.
- Do not log private keys, field encryption keys, or plaintext clinical payloads.

## Validation artifacts
- `data/security_encryption_v17/validation/encryption_at_rest_validator.json`
- `data/security_encryption_v17/validation/encrypted_fields_smoke_test.json`
- `data/security_encryption_v17/validation/transport_payload_encryption_validator.json`
