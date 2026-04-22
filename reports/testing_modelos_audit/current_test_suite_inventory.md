# Current Test Suite Inventory
Fecha: 2026-03-30

## Resumen del suite actual
- Framework: `pytest` (declarado en `requirements.txt`).
- Config pytest dedicada (`pytest.ini`/`pyproject`) no encontrada.
- `conftest.py` no existe; fixtures se definen de forma local por archivo.
- CI actual (`.github/workflows/ci.yml`) corre `pytest` completo y lint `ruff --select F api tests`.

## Estructura observada en `tests/`
- Archivos existentes (15): auth, users, admin, questionnaires, evaluations, health/docs/metrics, seguridad, email, db connectivity, seed script.
- Cobertura actual fuerte en:
  - autenticacion/autorizacion,
  - CRUD de cuestionarios y evaluaciones (persistencia base),
  - rutas de salud/docs,
  - hardening de seguridad y flujo admin.
- Cobertura actual ausente en:
  - runtime de modelos (`core/models/predictor.py`),
  - servicio de inferencia (`api/services/model_service.py`),
  - endpoint `/api/predict`,
  - coherencia `artifacts/inference_v4` vs runtime,
  - regresiones de scope activo/hold.

## Patrones de testing ya usados
- Cada archivo crea su propio `app`/`client` fixture o helper local.
- Se usa `TestingConfig` con SQLite in-memory para tests de API.
- No hay dependencia de frontend en el suite.
- Los tests privilegian validaciones de status code y shape JSON.

## Gap operativo principal
Tras las fases finales de modelos/inferencia, quedó deuda de tests en:
- carga real de binarios de runtime,
- consistencia de artifacts de inferencia (`inference_v4`),
- contrato básico del endpoint de predicción,
- protección contra activación accidental de `elimination` en scope productivo.

## Implicación
El backend base está bien cubierto, pero el apartado de modelos/inferencia no tenía protección suficiente contra regresiones antes de esta fase.
