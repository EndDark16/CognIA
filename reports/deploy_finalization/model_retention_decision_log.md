# Model Retention Decision Log

Fecha: 2026-03-30

## Decision final de retencion
- Se conserva en runtime solo `models/adhd_model.pkl`.
- No se activa carga runtime para anxiety/conduct/depression/elimination en esta fase.
- `elimination` permanece fuera de scope productivo (hold).

## Decision sobre modelos fuera de runtime
- `models/` historicos/challengers: fuera de commit final recomendado.
- `artifacts/models/` y `artifacts/versioned_models/`: fuera de repo de deploy (storage externo o interno no publico).
- Se evita dependencia de DB para binarios en esta iteracion.

## Razon
- Preservar deploy con minima complejidad operativa.
- Evitar romper inferencia real por excluir todos los binarios.
- Mantener repo limpio sin eliminar artefactos criticos.
