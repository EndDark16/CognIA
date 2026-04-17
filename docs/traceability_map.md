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

### Model activation and champions
- Active 30-mode activation:
  - `data/hybrid_active_modes_freeze_v1/`
  - `artifacts/hybrid_active_modes_freeze_v1/`
- Operational champions:
  - `data/hybrid_operational_freeze_v1/`
  - `artifacts/hybrid_operational_freeze_v1/`

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
