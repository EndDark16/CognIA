# Questionnaire Runtime v1 - Plan de migraci?n

## Migraci?n implementada
- `migrations/versions/20260330_01_add_questionnaire_runtime_v1.py`
- `down_revision = 20260208_01`

## Estrategia
- Adici?n paralela (`qr_*`) sin destruir tablas legacy.
- Compatibilidad con flujos previos del backend existente.
- Rutas nuevas consumen ?nicamente esquema `qr_*`.

## Ejecuci?n esperada
- `alembic upgrade head`
- Verificar creaci?n de ?ndices y constraints ?nicos.

