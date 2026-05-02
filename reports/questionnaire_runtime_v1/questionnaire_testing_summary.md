# Questionnaire Runtime v1 - Resumen de testing

## Tests nuevos
- `tests/api/test_questionnaire_runtime_api.py`
- `tests/models/test_questionnaire_runtime_service.py`
- `tests/smoke/test_questionnaire_runtime_smoke.py`

## Cobertura funcional
- Bootstrap y cuestionario activo.
- Draft/save/submit/resultados/export.
- Acceso profesional por referencia+PIN y etiquetado.
- Soft delete y bloqueo de acceso profesional a evaluacion borrada.
- Hash/verify de PIN y politica de dominio.

## Ejecucion real
- Comando ejecutado:
  - `pytest -q tests/models/test_questionnaire_runtime_service.py tests/smoke/test_questionnaire_runtime_smoke.py tests/api/test_questionnaire_runtime_api.py tests/test_questionnaires.py tests/test_evaluations.py tests/models/test_model_service_runtime.py tests/api/test_predict_api_runtime.py`
- Resultado:
  - `21 passed, 12 warnings`
- Warnings observados:
  - `InconsistentVersionWarning` de scikit-learn por version de serializacion de modelos; no bloquea ejecucion.
