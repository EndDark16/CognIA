# Final Deploy Smoke Test

Fecha: 2026-03-30

## Pruebas ejecutadas
1. Import de dependencias base en entorno local (`venv`): OK.
2. Creacion de app Flask (`from run import app`): OK.
3. Smoke inference minima (`predict_all_probabilities` con payload sintetico): OK.
4. Lectura de `artifacts/inference_v4/promotion_scope.json`: OK (`elimination` en hold).

## Resultado de inferencia minima
- salida: `{'adhd': 0.0}`

## Observacion tecnica
- En entorno local actual aparece warning de `InconsistentVersionWarning` (modelo serializado con scikit-learn 1.7.1 y entorno local 1.5.0).
- Se aplico correccion en `requirements.txt` a `scikit-learn==1.7.1` para build limpio en deploy.

## Docker build
- No se ejecuto build completo en esta fase para evitar cambios de entorno local no solicitados.
- Validacion de archivos de build/entrypoint: OK (`Dockerfile`, `docker/entrypoint.sh`, `requirements.txt`, `run.py`).
