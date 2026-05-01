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
  - `docs/deployment_ubuntu_self_hosted.md`
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
  - `data/hybrid_active_modes_freeze_v14/`
  - `artifacts/hybrid_active_modes_freeze_v14/`
- Operational champions:
  - `data/hybrid_operational_freeze_v14/`
  - `artifacts/hybrid_operational_freeze_v14/`

Audit lines:
- `data/hybrid_secondary_honest_retrain_v1/`
- `data/hybrid_final_honest_improvement_v1/`
- `data/hybrid_final_decisive_rescue_v5/`
- `data/hybrid_final_aggressive_rescue_v6/`
- `data/hybrid_v6_quick_champion_guard_hotfix_v1/`
- `data/hybrid_structural_mode_rescue_v1/`
- `data/hybrid_elimination_structural_audit_rescue_v1/`
- `data/hybrid_final_model_structural_compliance_v1/`
- `data/hybrid_rf_max_real_metrics_v1/`
- `data/hybrid_final_rf_plus_maximize_metrics_v1/`
- `data/hybrid_global_contract_compatible_rf_champion_selection_v13/`
- `data/hybrid_elimination_v14_real_anti_clone_rescue/`
- `data/hybrid_operational_freeze_v3/`
- `data/hybrid_operational_freeze_v4/`
- `data/hybrid_operational_freeze_v5/`
- `data/hybrid_operational_freeze_v6/`
- `data/hybrid_operational_freeze_v6_hotfix_v1/`
- `data/hybrid_operational_freeze_v8/`
- `data/hybrid_operational_freeze_v9/`
- `data/hybrid_operational_freeze_v10/`
- `data/hybrid_operational_freeze_v11/`
- `data/hybrid_operational_freeze_v12/`
- `data/hybrid_operational_freeze_v13/`
- `data/hybrid_operational_freeze_v14/`
- `data/hybrid_active_modes_freeze_v3/`
- `data/hybrid_active_modes_freeze_v4/`
- `data/hybrid_active_modes_freeze_v5/`
- `data/hybrid_active_modes_freeze_v6/`
- `data/hybrid_active_modes_freeze_v6_hotfix_v1/`
- `data/hybrid_active_modes_freeze_v8/`
- `data/hybrid_active_modes_freeze_v9/`
- `data/hybrid_active_modes_freeze_v10/`
- `data/hybrid_active_modes_freeze_v11/`
- `data/hybrid_active_modes_freeze_v12/`
- `data/hybrid_active_modes_freeze_v13/`
- `data/hybrid_active_modes_freeze_v14/`
- `artifacts/hybrid_secondary_honest_retrain_v1/`
- `artifacts/hybrid_final_honest_improvement_v1/`
- `artifacts/hybrid_final_decisive_rescue_v5/`
- `artifacts/hybrid_final_aggressive_rescue_v6/`
- `artifacts/hybrid_v6_quick_champion_guard_hotfix_v1/`
- `artifacts/hybrid_structural_mode_rescue_v1/`
- `artifacts/hybrid_elimination_structural_audit_rescue_v1/`
- `artifacts/hybrid_final_model_structural_compliance_v1/`
- `artifacts/hybrid_rf_max_real_metrics_v1/`
- `artifacts/hybrid_final_rf_plus_maximize_metrics_v1/`
- `artifacts/hybrid_global_contract_compatible_rf_champion_selection_v13/`
- `artifacts/hybrid_elimination_v14_real_anti_clone_rescue/`
- `artifacts/hybrid_operational_freeze_v3/`
- `artifacts/hybrid_operational_freeze_v4/`
- `artifacts/hybrid_operational_freeze_v5/`
- `artifacts/hybrid_operational_freeze_v6/`
- `artifacts/hybrid_operational_freeze_v6_hotfix_v1/`
- `artifacts/hybrid_operational_freeze_v8/`
- `artifacts/hybrid_operational_freeze_v9/`
- `artifacts/hybrid_operational_freeze_v10/`
- `artifacts/hybrid_operational_freeze_v11/`
- `artifacts/hybrid_operational_freeze_v12/`
- `artifacts/hybrid_operational_freeze_v13/`
- `artifacts/hybrid_operational_freeze_v14/`
- `artifacts/hybrid_active_modes_freeze_v3/`
- `artifacts/hybrid_active_modes_freeze_v4/`
- `artifacts/hybrid_active_modes_freeze_v5/`
- `artifacts/hybrid_active_modes_freeze_v6/`
- `artifacts/hybrid_active_modes_freeze_v6_hotfix_v1/`
- `artifacts/hybrid_active_modes_freeze_v8/`
- `artifacts/hybrid_active_modes_freeze_v9/`
- `artifacts/hybrid_active_modes_freeze_v10/`
- `artifacts/hybrid_active_modes_freeze_v11/`
- `artifacts/hybrid_active_modes_freeze_v12/`
- `artifacts/hybrid_active_modes_freeze_v13/`
- `artifacts/hybrid_active_modes_freeze_v14/`
- Estado (2026-04-21): evidencia versionada de auditoria secundaria con `replaced_pairs=0`.
- Estado (2026-04-22): campana `hybrid_final_honest_improvement_v1` con `replaced_pairs=9` desplaza la fuente operativa a `*_freeze_v4`.
- Estado (2026-04-22): campana final decisiva `hybrid_final_decisive_rescue_v5` con `replaced_pairs=1` desplaza la fuente operativa a `*_freeze_v5`.
- Estado (2026-04-22): campana final agresiva `hybrid_final_aggressive_rescue_v6` con `replaced_pairs=2` desplaza la fuente operativa a `*_freeze_v6`.
- Estado (2026-04-24): hotfix `hybrid_v6_quick_champion_guard_hotfix_v1` deja `remaining_guard_violations=0` y desplaza la fuente operativa a `*_freeze_v6_hotfix_v1`.
- Estado (2026-04-26): `hybrid_structural_mode_rescue_v1` reemplaza los 14 champions 1_3/2_3 prohibidos y 3 champions extra degenerados de una sola variable, deja `blacklisted_active_final=0`, `structural_extra_rescue_final=0`, `single_feature_active_final=0`, `guardrail_violations_final=0`, `policy_violations_final=0` y desplaza la fuente operativa a `*_freeze_v8`.
- Estado (2026-04-26): `hybrid_elimination_structural_audit_rescue_v1` reentrena los 6 slots Elimination, elimina el clonado (`old_prediction_pairs_identical=15/15` a `new_prediction_pairs_identical=0/15`), deja `guardrail_violations_final=0`, `policy_violations_final=0` y desplaza la fuente operativa a `*_freeze_v9`.
- Estado (2026-04-26): `hybrid_final_model_structural_compliance_v1` ejecuta retrain focal de 20 slots sobre v9, promueve 5 champions, revierte 3 challengers Elimination por anti-clonado, deja `guardrail_violations_final=0`, `policy_violations_final=0` y desplaza la fuente operativa a `*_freeze_v10`.
- Estado (2026-04-27): `hybrid_rf_max_real_metrics_v1` reentrena 30/30 slots con RandomForestClassifier exclusivamente, mantiene feature contracts v10, deja `remaining_guardrail_violations=0`, `policy_violations=0`, `rf_only_ok=yes`, `elimination_identical_prediction_pairs=0` y desplaza la fuente operativa a `*_freeze_v11`.
- Estado (2026-04-27): `hybrid_final_rf_plus_maximize_metrics_v1` reentrena/evalua 30/30 slots RF-based sobre v11 con tecnicas complementarias RF, mantiene mismos inputs/outputs, deja `remaining_guardrail_violations=0`, `policy_violations=0`, `rf_only_ok=yes`, `feature_contract_mismatches=0`, `questionnaire_changed=no`, `elimination_identical_prediction_pairs=0` y desplaza la fuente operativa a `*_freeze_v12`.
- Estado (2026-04-29): `hybrid_global_contract_compatible_rf_champion_selection_v13` corrige seleccion de champions sin reentrenamiento, recupera 17 RF v11 contract-compatible y retiene 13 RF v12, mantiene mismo contrato exacto de features/outputs, deja `guardrail_violations=0`, `policy_violations=0`, `near_clone_proxy_pairs=0` y desplaza la fuente operativa a `*_freeze_v13`.
- Estado (2026-05-01): `hybrid_elimination_v14_real_anti_clone_rescue` corrige clonado conductual real en los 6 slots Elimination con seleccion conjunta y recomputacion real 30/30; deja `elimination_real_clone_count=0`, `all_domains_real_clone_count=0`, `artifact_duplicate_hash_count=0`, `guardrail_violations=0`, `final_audit_status=pass_with_warnings` y desplaza la fuente operativa a `*_freeze_v14`.

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


- Estado (2026-05-01): `hybrid_elimination_v15_caregiver_full_metric_rescue` aplica rescate focal de `elimination/caregiver_full` sobre base v14, genera `*_freeze_v15`, mantiene `0` clones reales (global y Elimination), `0` guardrail violations, y deja evidencia en `data/hybrid_elimination_v15_caregiver_full_metric_rescue/` con `final_audit_status=pass_with_warnings`.
- Estado (2026-05-01): `hybrid_final_clean_champion_resolution_v16` ejecuta cierre final limpio sobre v15, corrige drift registrado vs recomputado en 2 slots historicos Elimination, reclasifica near-clone con evidencia (sin pendientes reales), deja `final_audit_status=pass`, `metrics_match_registered=30/30`, `all_domains_real_clone_count=0`, `elimination_real_clone_count=0`, `unresolved_near_clone_warning_count=0`, `guardrail_violations=0`, y desplaza la fuente operativa a `*_freeze_v16`.
