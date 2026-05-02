# Runtime Model Resolution Report

Fecha: 2026-03-30

## Resultado
El runtime real actual usa un solo binario de modelo: `models/adhd_model.pkl`.

## Evidencia tecnica
- `core/models/predictor.py`: construye ruta `models/{model_name}_model.pkl` y carga con `joblib.load`.
- `api/services/model_service.py`: llama `load_model("adhd")` de forma activa.
- `api/services/model_service.py`: carga de anxiety esta comentada y no se ejecuta.
- `artifacts/inference_v4/promotion_scope.json`: mantiene `elimination` en hold.

## Resolucion final aplicada
- Modelo minimo obligatorio para runtime: `models/adhd_model.pkl`.
- Binarios historicos/challengers fuera de runtime final: no necesarios para arranque/inferencia actual.

## Coherencia con scope final
- `inference_v4` sigue vigente como politica de dominios.
- Runtime API de este backend sigue centrado en flujo ADHD (sin activar elimination).
- No se abrio refactor funcional para ampliar dominios en esta fase de cierre.
