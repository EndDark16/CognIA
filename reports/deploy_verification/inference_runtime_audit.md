# Inference Runtime Audit

## inference_v4 contenido
- `promotion_scope.json` (scope de dominios activos/hold).

## Observacion clave
- La inferencia real depende de `models/adhd_model.pkl` via `core/models/predictor.py`.
- `artifacts/inference_v4/` no incluye binarios de modelo.

## Conclusion
- Con la politica actual de excluir `models/`, el runtime quedaria sin modelo.
- Se requiere: mantener al menos los binarios finales en repo, o descargar desde storage externo en build/boot.