# Security Transport & Encryption Audit Report

- generated_at_utc: 2026-05-03T03:23:26.535729+00:00
- endpoint_matrix: `data/security_sensitive_endpoint_audit/endpoint_sensitivity_matrix.csv`
- field_encryption_audit: `data/security_sensitive_endpoint_audit/field_encryption_audit.csv`
- legacy_plaintext_audit: `data/security_sensitive_endpoint_audit/legacy_plaintext_endpoint_audit.csv`

## Key Results
- sensitive_endpoints_without_encryption_count: see `encrypted_transport_endpoint_validator.json`
- fields_sensitive_unencrypted_count: 0
- openapi_valid: True

## Method Caveat
- La clasificacion operativa de endpoints se deriva de rutas reales en codigo y reglas de auditoria de esta ventana.
- Algunos replacements runtime v1 legacy quedan `por confirmar` hasta definir endpoint seguro POST equivalente.
