# .gitignore Rationale

## Objetivo
Evitar que el repositorio se convierta en un dump de artefactos pesados y archivos locales regenerables, sin perder trazabilidad final.

## Bloques agregados

### Python, caches y test artifacts
- `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`.
- Razon: archivos regenerables, sin valor de versionado.

### Entornos locales
- `venv/`, `.venv/`, `**/venv/`, `scripts/venv/`.
- Razon: entorno local dependiente de maquina.

### Secrets
- `.env`, `.env.*`.
- Razon: seguridad y portabilidad.

### Binarios de ML pesados
- `*.joblib`, `*.pkl`, `*.pickle`, `*.onnx`, `*.npy`, `*.npz`.
- Razon: peso alto y duplicacion frecuente; recomendados para storage externo + manifiestos.

### Artefactos generados pesados
- `artifacts/models/`, `artifacts/versioned_models/`, `artifacts/preprocessing/`, `artifacts/hybrid_dsm5_v2/models/`.
- Razon: alto volumen, mayormente regenerable.

### Datos procesados pesados
- `data/processed/`, `data/processed_dsm5_exact_v1/`, `data/processed_hybrid_dsm5_v2/`.
- Razon: datasets intermedios/finales de gran tamano que deben ir a storage externo.

## Excepciones explicitas (se mantienen en repo)
- `artifacts/inference_v4/` (scope de inferencia vigente).
- `data/normative_matrix/` (norma formal DSM-5).
- `data/final_closure_audit_v1/` (evidencia auditada de cierre).
- `reports/final_closure/` (cierre documental final).
