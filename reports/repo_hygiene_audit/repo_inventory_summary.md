# Repo Inventory Summary

- generated_at_utc: 2026-03-30T14:34:02.412436Z
- total_paths_audited: 37
- existing_paths: 36
- total_size_audited_mb: 2421.653

## keep_in_repo
- count: 18
- size_mb_approx: 12.813
- top_paths:
  - `scripts` (12.320 MB)
  - `api` (0.173 MB)
  - `docs` (0.112 MB)

## keep_but_slim_down
- count: 8
- size_mb_approx: 50.828
- top_paths:
  - `data/questionnaire_dsm5_v1` (22.056 MB)
  - `reports` (20.762 MB)
  - `data/HBN_synthetic_release11_focused_subset_csv` (6.365 MB)

## move_to_external_storage
- count: 5
- size_mb_approx: 1873.975
- top_paths:
  - `artifacts` (633.757 MB)
  - `models` (593.120 MB)
  - `data/processed_hybrid_dsm5_v2` (376.292 MB)

## ignore_from_repo
- count: 4
- size_mb_approx: 484.033
- top_paths:
  - `venv` (472.694 MB)
  - `scripts/venv` (11.339 MB)
  - `notebooks` (0.000 MB)

## template_only
- count: 1
- size_mb_approx: 0.002
- top_paths:
  - `.env.example` (0.002 MB)

## env_only
- count: 1
- size_mb_approx: 0.002
- top_paths:
  - `.env` (0.002 MB)

## Observaciones clave
- `data/`, `models/` y `artifacts/` concentran la mayor parte del peso y duplicacion.
- Existen duplicados binarios entre `models/*` y `artifacts/*` para varios pipelines/calibradores.
- Archivos de deploy (Dockerfile/entrypoint/requirements/run.py) deben preservarse en repo.
- `.env` contiene secretos reales: debe mantenerse fuera de git y sustituirse por `.env.example`.