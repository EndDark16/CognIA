# What To Commit

## A) Subir si o si
- Codigo fuente: `api/`, `app/`, `core/`, `config/`, `scripts/`, `tests/`.
- Documentacion final: `README.md`, `reports/final_closure/`, `REPO_CONTENT_POLICY.md`.
- Capa normativa: `data/normative_matrix/`.
- Scope de inferencia vigente: `artifacts/inference_v4/`.
- Tablas auditadas de cierre (compactas): `data/final_closure_audit_v1/`.

## B) Subir opcionalmente (si el tamano lo permite)
- `reports/versioning/`, `reports/promotions/`, `reports/metrics/`, `reports/training/`.
- Carpetas de fases (`data/finalization_and_recovery_v1/`, `data/elimination_*`) en version liviana.

## Regla practica
Si el archivo es necesario para reproducir decisiones finales o para auditar cierre, se versiona. Si es pesado y regenerable, se referencia pero no se sube.
