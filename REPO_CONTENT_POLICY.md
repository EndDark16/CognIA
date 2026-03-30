# REPO Content Policy

## Proposito
Definir de forma operativa que contenido se versiona en git y que contenido se mantiene en storage externo para conservar higiene, trazabilidad y mantenibilidad.

## 1) Se versiona en git (obligatorio)
- Codigo fuente: `api/`, `app/`, `core/`, `config/`, `scripts/`, `tests/`.
- Documentacion final y de gobierno: `README.md`, `reports/final_closure/`, `REPO_CONTENT_POLICY.md`.
- Matriz normativa y tablas compactas de cierre: `data/normative_matrix/`, `data/final_closure_audit_v1/`.
- Scope de inferencia vigente: `artifacts/inference_v4/`.
- Binarios minimos de runtime real: `models/adhd_model.pkl` (hasta que exista externalizacion de modelos en deploy).

## 2) Se versiona en git (opcional, segun tamano)
- `reports/versioning/`, `reports/promotions/`, `reports/metrics/`, `reports/training/`.
- Outputs de fase que sean livianos y utiles para auditoria.

## 3) No se versiona en git (storage externo)
- Datasets procesados/intermedios pesados (`data/processed*`).
- Binarios historicos/intermedios de modelos (`*.joblib`, `*.pkl`, etc.) en `models/` y `artifacts/models/`, excepto `models/adhd_model.pkl`.
- Historiales intermedios pesados y duplicados regenerables.

## 3.1) Decision de arquitectura de esta iteracion
- No se usa la base de datos como almacenamiento principal de binarios de modelos.
- No se agrega descarga externa obligatoria de modelos en boot/build en esta iteracion.
- Se conserva en repo/deploy solo el binario minimo requerido por runtime para mantener simplicidad operativa.
- Mejora futura opcional (fuera de alcance actual): object storage + fetch controlado en build/boot.

## 4) Nunca se versiona
- Entornos locales (`venv/`, `.venv/`, `scripts/venv/`).
- Caches (`__pycache__/`, `.pytest_cache/`).
- Secretos (`.env`).
- Logs/temporales locales.

## 5) Regla de decision rapida
Antes de commitear, responder:
1. Es necesario para reproducir decisiones finales?
2. Es necesario para auditar el cierre metodologico?
3. Es liviano y mantenible en git?

Si la respuesta a (1) y (2) es no, o (3) es no, mover a storage externo y dejar manifiesto/ruta/checksum en repo.

## 6) Convencion de storage externo
Cada release pesada debe guardar:
- `version`
- `fecha`
- `hash/checksum`
- `ruta de origen`
- `script de regeneracion`

Esto permite repositorio limpio sin perder trazabilidad.
