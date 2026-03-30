# What Not To Commit

## C) Mejor en storage externo
- Datasets procesados grandes: `data/processed*/`.
- Binarios de modelos masivos: `models/` (subcarpetas de `.joblib`/`.pkl`) y `artifacts/models/`.
- Historiales y artefactos intermedios muy pesados en `artifacts/preprocessing/`.

## D) Ignorar siempre
- Entornos locales: `venv/`, `scripts/venv/`.
- Caches: `__pycache__/`, `.pytest_cache/`, `.ipynb_checkpoints/`.
- Secretos/local config: `.env`.
- Logs y temporales: `*.log`, `tmp/`, `temp/`.

## E) Revisar manualmente antes de decidir
- `artifacts/inference_v5/` (no vigente para esta iteracion).
- Figuras muy pesadas y outputs duplicados historicos.
