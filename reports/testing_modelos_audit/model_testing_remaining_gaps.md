# Model Testing Remaining Gaps
Fecha: 2026-03-30

## Cobertura pendiente (no bloqueante para esta fase)

1. **Inferencia multi-dominio runtime en API principal**
   - Estado actual: `/api/predict` opera en practica sobre ADHD.
   - Implicacion: no hay ruta runtime productiva para validar en API los 4 dominios activos de `inference_v4`.
   - Motivo de gap: limite funcional actual del backend (no de tests).

2. **Endpoints de resultado explicable por evaluacion**
   - Faltan endpoints user-facing para `result/explanation/uncertainty` por `evaluation_id`.
   - Impide pruebas de contrato final de salida no binaria en flujo E2E cuestionario->resultado.

3. **Cobertura E2E de evaluacion -> prediccion persistida**
   - Tablas `evaluation_prediction*` existen, pero no hay pipeline API activo que las alimente en flujo normal.
   - Se cubrio consistencia de artefactos y runtime actual, no ese E2E inexistente.

4. **Advertencia de compatibilidad sklearn en runtime local**
   - Al cargar `adhd_model.pkl` aparece `InconsistentVersionWarning` (modelo serializado con 1.7.1 vs runtime 1.5.0).
   - No rompe tests actuales, pero es riesgo operacional a monitorear.

5. **Fallo preexistente de suite completa ajeno a modelos**
   - `tests/test_password_reset.py::test_rate_limit_basic_for_forgot` falla (espera 429, obtiene 200).
   - Reproducido fuera de la suite nueva de modelos.
   - No se tocó porque no pertenece al objetivo de esta fase.

## Evaluacion final de cobertura de esta fase
- Para el apartado modelos/inferencia/runtime **actualmente implementado**, la cobertura agregada es razonable y util contra regresiones.
- Los gaps remanentes dependen de capacidades funcionales aun no expuestas por API (no de ausencia de tests en componentes existentes).
