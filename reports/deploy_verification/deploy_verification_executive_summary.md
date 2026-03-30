# Deploy Verification Executive Summary

## Resultado
El repo "limpio" es desplegable **solo si** se resuelve el acceso al binario de modelo requerido en runtime (`models/adhd_model.pkl`).

## Docker/Render
- Dockerfile + entrypoint + requirements + run.py: OK.
- DB requerida para migraciones y runtime real: debe configurarse via env vars/secrets.

## inference_v4
- Provee solo scope. No incluye modelos. Runtime requiere `models/`.

## Exclusiones
- Seguras: `data/processed*`, `artifacts/models/`, `artifacts/versioned_models/`, caches.
- Peligrosa: excluir `models/` sin alternativa de descarga.

## Recomendacion
Antes de push final:
1. Decidir estrategia de modelos: mantener binarios finales en repo o externalizar y descargar en build/boot.
2. Mantener `.env.example` en repo y `.env` fuera.
