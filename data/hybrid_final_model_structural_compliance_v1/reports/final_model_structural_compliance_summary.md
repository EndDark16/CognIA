# Hybrid Final Model Structural Compliance v1

Generated: `2026-04-26T20:45:01.756562+00:00`

- source_active: `data\hybrid_active_modes_freeze_v9\tables\hybrid_active_models_30_modes.csv`
- output_active: `data\hybrid_active_modes_freeze_v10\tables\hybrid_active_models_30_modes.csv`
- initial_guardrail_violations: `0`
- target_slots_for_retrain: `20`
- selected_promotions: `5`
- anti_clone_reverted_promotions: `3`
- retained_after_retrain_attempt: `15`
- remaining_guardrail_violations: `0`
- policy_violations: `0`
- question_text_changes: `0`

## Promotions
| domain | mode | old_active_model_id | active_model_id | old_f1 | f1 | old_recall | recall | old_precision | precision | old_balanced_accuracy | balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_1_3 | adhd__psychologist_1_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_1_3 | adhd__psychologist_1_3__hybrid_final_model_structural_compliance_v1__logreg__structural_ranked_direct | 0.762332 | 0.765766 | 0.904255 | 0.904255 | 0.658915 | 0.664062 | 0.895133 | 0.896428 |
| anxiety | psychologist_1_3 | anxiety__psychologist_1_3__hybrid_structural_mode_rescue_v1__logreg__registry_stability_pruned_subset | anxiety__psychologist_1_3__hybrid_final_model_structural_compliance_v1__logreg__legacy_structural_intersection | 0.810256 | 0.825397 | 0.918605 | 0.906977 | 0.724771 | 0.757282 | 0.921231 | 0.921762 |
| depression | caregiver_full | depression__caregiver_full__v6_hotfix_v1__hgb__no_shortcut_v1 | depression__caregiver_full__hybrid_final_model_structural_compliance_v1__hgb__structural_ranked_direct | 0.775758 | 0.837209 | 0.780488 | 0.878049 | 0.771084 | 0.800000 | 0.866375 | 0.916411 |
| depression | psychologist_1_3 | depression__psychologist_1_3__hybrid_structural_mode_rescue_v1__rf__structural_compact_1_3 | depression__psychologist_1_3__hybrid_final_model_structural_compliance_v1__rf__dsm5_core_plus_context | 0.822086 | 0.846626 | 0.817073 | 0.841463 | 0.827160 | 0.851852 | 0.890949 | 0.905656 |
| elimination | psychologist_full | elimination__psychologist_full__hybrid_elimination_structural_audit_rescue_v1__extra_trees__structural_no_top2_direct | elimination__psychologist_full__hybrid_final_model_structural_compliance_v1__extra_trees__legacy_structural_intersection | 0.840336 | 0.854701 | 0.961538 | 0.961538 | 0.746269 | 0.769231 | 0.960909 | 0.963246 |

## Retained
| domain | mode | active_model_id | retention_reason | old_f1 | old_recall | old_precision | old_balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver_1_3 | adhd__caregiver_1_3__hybrid_structural_mode_rescue_v1__rf__structural_dsm5_plus_context_1_3 | no_materially_better_candidate | 0.801843 | 0.925532 | 0.707317 | 0.916134 |
| adhd | caregiver_2_3 | adhd__caregiver_2_3__hybrid_structural_mode_rescue_v1__rf__structural_compact_2_3 | no_materially_better_candidate | 0.809091 | 0.946809 | 0.706349 | 0.925477 |
| adhd | caregiver_full | adhd__caregiver_full__rebuild_v2__rf__engineered_compact | no_guard_precision_compliant_candidate | 0.777778 | 0.819149 | 0.740385 | 0.874600 |
| adhd | psychologist_2_3 | adhd__psychologist_2_3__hybrid_structural_mode_rescue_v1__logreg__structural_ranked_2_3 | no_guard_precision_compliant_candidate | 0.824121 | 0.872340 | 0.780952 | 0.906377 |
| adhd | psychologist_full | adhd__psychologist_full__v6_hotfix_v1__logreg__dsm5_core_only | no_guard_precision_compliant_candidate | 0.783410 | 0.904255 | 0.691057 | 0.902905 |
| anxiety | psychologist_full | anxiety__psychologist_full__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_full | no_guard_precision_compliant_candidate | 0.840909 | 0.860465 | 0.822222 | 0.909928 |
| conduct | caregiver_2_3 | conduct__caregiver_2_3__hybrid_structural_mode_rescue_v1__logreg__registry_stability_pruned_subset | no_materially_better_candidate | 0.887574 | 0.937500 | 0.842697 | 0.925000 |
| depression | caregiver_1_3 | depression__caregiver_1_3__hybrid_structural_mode_rescue_v1__rf__structural_ranked_1_3 | no_materially_better_candidate | 0.845714 | 0.902439 | 0.795699 | 0.927350 |
| depression | caregiver_2_3 | depression__caregiver_2_3__hybrid_structural_mode_rescue_v1__extra_trees__structural_compact_2_3 | no_materially_better_candidate | 0.852273 | 0.914634 | 0.797872 | 0.933448 |
| depression | psychologist_2_3 | depression__psychologist_2_3__hybrid_structural_mode_rescue_v1__extra_trees__structural_compact_2_3 | no_materially_better_candidate | 0.849162 | 0.926829 | 0.783505 | 0.937033 |
| elimination | caregiver_1_3 | elimination__caregiver_1_3__hybrid_elimination_structural_audit_rescue_v1__rf__structural_ranked_direct | no_materially_better_candidate | 0.851852 | 0.884615 | 0.821429 | 0.930625 |
| elimination | caregiver_full | elimination__caregiver_full__hybrid_elimination_structural_audit_rescue_v1__extra_trees__structural_no_top2_direct | no_materially_better_candidate | 0.837607 | 0.942308 | 0.753846 | 0.952462 |
| elimination | caregiver_2_3 | elimination__caregiver_2_3__hybrid_elimination_structural_audit_rescue_v1__hgb__structural_no_top1_direct | anti_clone_retained_v9_champion | 0.844037 | 0.884615 | 0.807018 | 0.929457 |
| elimination | psychologist_1_3 | elimination__psychologist_1_3__hybrid_elimination_structural_audit_rescue_v1__hgb__structural_no_top2_direct | anti_clone_retained_v9_champion | 0.821429 | 0.884615 | 0.766667 | 0.925953 |
| elimination | psychologist_2_3 | elimination__psychologist_2_3__hybrid_elimination_structural_audit_rescue_v1__rf__structural_no_top2_direct | anti_clone_retained_v9_champion | 0.818182 | 0.865385 | 0.775862 | 0.917505 |

## Final Elimination anti-clone audit

- pair_count: `15`
- identical_prediction_pairs: `0`
- near_metric_clone_pairs: `0`
- prediction file: `data/hybrid_final_model_structural_compliance_v1/validation/final_elimination_holdout_predictions_v10.csv`
- similarity file: `data/hybrid_final_model_structural_compliance_v1/validation/final_elimination_prediction_similarity_v10.csv`
- slot metric audit: `data/hybrid_final_model_structural_compliance_v1/validation/final_elimination_anti_clone_audit_v10.csv`


## Questionnaire/backend/Supabase sync

- Reconstructed missing `feature_list_pipe` for 5 retained legacy champions from their source registries.
- Final active DB verification: `active_model_activations=30`, `active_model_versions=30`, `active_model_versions_without_feature_columns=0`, `duplicate_active_domain_mode_rows=0`.
- Questionnaire loaded to DB: `questions=146`; visible included counts by mode are recorded in `questionnaire_sync/supabase_sync_verification_v10.json`.
- Question text changes vs `origin/development`: `0`; only mode inclusion flags changed.
- Model input mapping caveat: `1361` active model inputs map to reused full-question rows; `72` remain non-visible/unmapped in the visible questionnaire audit (`42` internal/transparent-derived, `30` direct inputs present in `hybrid_questionnaire_inputs_master` but absent from the visible full-question CSV). They were not converted into new questions; see `questionnaire_sync/unmapped_model_inputs_v10.csv`.
- Loader hardening: sync now clears stale activations by `domain/mode`, preventing old `caregiver` rows from coexisting with canonical `guardian` rows.
