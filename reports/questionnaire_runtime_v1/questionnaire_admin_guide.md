# Questionnaire Runtime v1 - Gu?a admin

## Operaci?n m?nima
1. `POST /admin/bootstrap` para asegurar versi?n activa inicial.
2. Crear template adicional (`/admin/templates`) si se requiere nueva l?nea.
3. Crear versi?n (`/admin/templates/{id}/versions`) con `clone_from_active=true` para iterar.
4. Ajustar disclosures (`/admin/versions/{id}/disclosures`).
5. Publicar versi?n (`/admin/versions/{id}/publish`).

## Regla
- No editar destructivamente una versi?n ya publicada y usada.

