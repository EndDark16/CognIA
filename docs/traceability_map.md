# Traceability Map

## Objective
Provide a single map for campaign/versioned artifacts so teams can find source-of-truth without guessing folder intent.

## Naming convention

For data/artifact campaign folders, the canonical pattern is:

- `<scope>_<purpose>_<version>`

Examples:
- `hybrid_rf_final_ceiling_push_v3`
- `hybrid_operational_freeze_v1`
- `final_ceiling_check_v15`
- `questionnaire_final_ceiling_v4`

Where:
- `scope`: domain/workstream (`hybrid`, `final`, `questionnaire`, etc.)
- `purpose`: what the campaign did (`rebuild`, `consolidation`, `freeze`, `check`)
- `version`: monotonic campaign version (`vN`)

## Source-of-truth pointers

### Questionnaire and runtime
- Active questionnaire inputs/version:
  - `data/cuestionario_v16.4/`
- Runtime/API contract references:
  - `docs/questionnaire_api_contract.md`
  - `docs/questionnaire_backend_architecture.md`
  - `docs/auth_mfa_recovery_flow_and_endpoint_versioning_20260421.md`
  - `docs/backend_gap_matrix_20260422.md`
  - `docs/deployment_playbook_ingest_20260422.md`

### Backend release governance
- `VERSION`
- `CHANGELOG.md`
- `docs/backend_versioning_policy.md`
- `docs/backend_release_workflow.md`
- `docs/backend_release_registry.csv`
- `docs/releases/backend_release_2026-04-22_r1.md`
- `artifacts/backend_release_registry/backend_release_2026-04-22_r1_manifest.json`

### Model activation and champions
- Active 30-mode activation:
  - `data/hybrid_active_modes_freeze_v7/`
  - `artifacts/hybrid_active_modes_freeze_v7/`
- Operational champions:
  - `data/hybrid_operational_freeze_v7/`
  - `artifacts/hybrid_operational_freeze_v7/`

Audit lines:
- `data/hybrid_secondary_honest_retrain_v1/`
- `data/hybrid_final_honest_improvement_v1/`
- `data/hybrid_final_decisive_rescue_v5/`
- `data/hybrid_final_aggressive_rescue_v6/`
- `data/hybrid_final_aggressive_honest_rescue_v7/`
- `data/hybrid_operational_freeze_v3/`
- `data/hybrid_operational_freeze_v4/`
- `data/hybrid_operational_freeze_v5/`
- `data/hybrid_operational_freeze_v6/`
- `data/hybrid_operational_freeze_v7/`
- `data/hybrid_active_modes_freeze_v3/`
- `data/hybrid_active_modes_freeze_v4/`
- `data/hybrid_active_modes_freeze_v5/`
- `data/hybrid_active_modes_freeze_v6/`
- `data/hybrid_active_modes_freeze_v7/`
- `artifacts/hybrid_secondary_honest_retrain_v1/`
- `artifacts/hybrid_final_honest_improvement_v1/`
- `artifacts/hybrid_final_decisive_rescue_v5/`
- `artifacts/hybrid_final_aggressive_rescue_v6/`
- `artifacts/hybrid_final_aggressive_honest_rescue_v7/`
- `artifacts/hybrid_operational_freeze_v3/`
- `artifacts/hybrid_operational_freeze_v4/`
- `artifacts/hybrid_operational_freeze_v5/`
- `artifacts/hybrid_operational_freeze_v6/`
- `artifacts/hybrid_operational_freeze_v7/`
- `artifacts/hybrid_active_modes_freeze_v3/`
- `artifacts/hybrid_active_modes_freeze_v4/`
- `artifacts/hybrid_active_modes_freeze_v5/`
- `artifacts/hybrid_active_modes_freeze_v6/`
- `artifacts/hybrid_active_modes_freeze_v7/`
- Estado (2026-04-21): evidencia versionada de auditoria secundaria con `replaced_pairs=0`.
- Estado (2026-04-22): campana `hybrid_final_honest_improvement_v1` con `replaced_pairs=9` desplaza la fuente operativa a `*_freeze_v4`.
- Estado (2026-04-22): campana final decisiva `hybrid_final_decisive_rescue_v5` con `replaced_pairs=1` desplaza la fuente operativa a `*_freeze_v5`.
- Estado (2026-04-22): campana final agresiva `hybrid_final_aggressive_rescue_v6` con `replaced_pairs=2` desplaza la fuente operativa a `*_freeze_v6`.
- Estado (2026-04-23): campana final agresiva honesta `hybrid_final_aggressive_honest_rescue_v7` con `replaced_pairs=0` y gate duro `<0.98`; se recalcula confianza/clase y la fuente operativa pasa a `*_freeze_v7`.

Historical lines retained for traceability:
- `data/hybrid_active_modes_freeze_v1/`
- `data/hybrid_operational_freeze_v1/`
 - `data/hybrid_active_modes_freeze_v2/`
 - `data/hybrid_operational_freeze_v2/`

### Final closure and methodological scope
- Final closure reports:
  - `reports/final_closure/`
- Inference scope:
  - `artifacts/inference_v4/`

## Runtime-generated (not source-of-truth)

These are operational outputs, not canonical evidence:

- `artifacts/runtime_reports/`
- `artifacts/problem_reports/uploads/`
- any per-request generated PDF/export cache

They should be regenerated as needed and excluded from Git.

## Practical rule

If a folder does not clearly communicate:

1. what campaign it belongs to,
2. what decision it supports,
3. and which version it is,

it must be documented/renamed before being considered stable traceability.
