# Questionnaire Runtime v1 - Pol?tica de retenci?n

## Pol?tica implementada
- Drafts: `QR_RETENTION_DRAFT_DAYS` (default 30 d?as).
- Evaluaciones completadas/fallidas: `QR_RETENTION_COMPLETED_DAYS` (default 1095 d?as).
- Evaluaciones borradas por usuario: `QR_RETENTION_DELETED_DAYS` (default 90 d?as).
- Notificaciones: `QR_RETENTION_NOTIFICATION_DAYS` (default 180 d?as).

## Borrado del usuario
- Operaci?n `soft delete` (`status=deleted_by_user`, `deleted_by_user=true`, `deleted_at`).
- Si existe psic?logo asignado, recibe notificaci?n de eliminaci?n.

