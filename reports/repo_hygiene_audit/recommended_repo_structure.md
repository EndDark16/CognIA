# Recommended Repo Structure

## Objetivo
Separar claramente codigo/documentacion versionable de artefactos pesados regenerables.

## Estructura recomendada
- `api/`, `app/`, `core/`, `config/`, `scripts/`, `tests/`  -> nucleo de codigo.
- `docs/` y `reports/final_closure/` -> documentacion oficial de cierre.
- `data/normative_matrix/` + `data/final_closure_audit_v1/` -> trazabilidad minima en repo.
- `artifacts/inference_v4/` -> scope de inferencia vigente.
- `reports/versioning/`, `reports/promotions/`, `reports/metrics/` -> evidencia auditada compacta.

## Fuera de git (storage externo recomendado)
- `data/processed*/` completos.
- `models/` binarios pesados.
- `artifacts/models/`, `artifacts/versioned_models/`, `artifacts/preprocessing/`.
- Tablas long/intermedias masivas y figuras de alto peso.

## Practica operativa
1. Publicar en git: codigo + docs + manifiestos + tablas compactas.
2. Publicar en storage externo: datasets/modelos pesados por release.
3. En git dejar: ruta de storage, hash, version y script de reproduccion.
