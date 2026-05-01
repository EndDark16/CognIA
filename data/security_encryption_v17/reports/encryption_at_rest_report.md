# Encryption At Rest - v17

- encryption_at_rest_enabled: yes
- sensitive_new_fields_encrypted: yes
- legacy_plaintext_supported: yes
- db_plaintext_sample_check: pass

## Transport Encryption
- app_payload_encryption_enabled: yes
- encrypted_response_ok: yes

Notes:
- This report validates cryptographic roundtrip and non-leak behavior for encrypted payload envelopes.
- Frontend must consume transport contract documentation for encrypted request/response usage.