# Questionnaire Runtime v1 - Seguridad

## Medidas aplicadas
- PIN de acceso profesional almacenado con hash bcrypt (`pin_hash`).
- Control de intentos fallidos y lock temporal de PIN.
- Separaci?n de permisos por rol/propietario.
- Soft delete sin exposici?n de re-apertura.
- Logs de auditor?a en acciones cr?ticas (`QR_DRAFT_CREATED`, `QR_EVALUATION_DRAFT_CREATED`).

## Datos sensibles
- Se evita almacenar PII no necesaria del ni?o por dise?o de esquema.

