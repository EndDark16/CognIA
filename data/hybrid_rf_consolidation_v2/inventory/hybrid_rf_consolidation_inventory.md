# Hybrid RF Consolidation v2 - Inventory

## Inventory
| item | value |
| --- | --- |
| campaign_line | hybrid_rf_consolidation_v2 |
| dataset_path | data/hybrid_dsm5_rebuild_v1/hybrid_dataset_synthetic_complete_final.csv |
| dataset_n_rows | 2400 |
| dataset_n_columns | 229 |
| candidates_requested | 13 |
| candidates_loaded | 13 |
| audit_scope | targeted_candidates_only |
| seed_variants | 0\|17\|43 |
| alt_split_seeds | 20260721\|20260819 |
| threshold_policies | default_0_5\|precision_oriented\|balanced\|recall_constrained |
| created_at_utc | 2026-04-12T15:56:28.524356+00:00 |

## Candidate Scope
| candidate_id | domain | mode | role_tag | winner_feature_set_id | winner_config_id | winner_calibration | winner_threshold_policy | winner_threshold | winner_seed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__psychologist_full | adhd | psychologist_full | primary | balanced_subset | rf_precision_push | isotonic | balanced | 0.050000 | 20260429 |
| adhd__psychologist_2_3 | adhd | psychologist_2_3 | fallback | top_importance_filtered | rf_precision_push | isotonic | default_0_5 | 0.500000 | 20260412 |
| anxiety__caregiver_2_3 | anxiety | caregiver_2_3 | primary | top_importance_filtered | rf_regularized | isotonic | default_0_5 | 0.500000 | 20260429 |
| anxiety__caregiver_full | anxiety | caregiver_full | compare | precision_oriented_subset | rf_precision_push | sigmoid | precision_oriented | 0.495000 | 20260429 |
| conduct__psychologist_2_3 | conduct | psychologist_2_3 | review | precision_oriented_subset | rf_precision_push | isotonic | balanced | 0.050000 | 20260412 |
| conduct__caregiver_2_3 | conduct | caregiver_2_3 | review | precision_oriented_subset | rf_precision_push | isotonic | balanced | 0.050000 | 20260412 |
| conduct__psychologist_full | conduct | psychologist_full | review | precision_oriented_subset | rf_precision_push | isotonic | balanced | 0.050000 | 20260412 |
| depression__caregiver_2_3 | depression | caregiver_2_3 | primary | balanced_subset | rf_precision_push | none | precision_oriented | 0.590000 | 20260513 |
| depression__caregiver_full | depression | caregiver_full | compare | full_eligible | rf_precision_push | none | precision_oriented | 0.615000 | 20260412 |
| depression__psychologist_full | depression | psychologist_full | compare | top_importance_filtered | rf_precision_push | none | precision_oriented | 0.660000 | 20260513 |
| elimination__caregiver_2_3 | elimination | caregiver_2_3 | primary | precision_oriented_subset | rf_recall_guard | isotonic | balanced | 0.255000 | 20260513 |
| elimination__caregiver_full | elimination | caregiver_full | compare | precision_oriented_subset | rf_recall_guard | isotonic | recall_constrained | 0.255000 | 20260412 |
| elimination__psychologist_full | elimination | psychologist_full | compare | precision_oriented_subset | rf_recall_guard | isotonic | recall_constrained | 0.405000 | 20260429 |

## Split Registry (reused from v1)
| domain | source | train_n | val_n | holdout_n | train_ids_path | val_ids_path | holdout_ids_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | hybrid_rf_ceiling_push_v1 | 1440 | 480 | 480 | data/hybrid_rf_ceiling_push_v1/splits/domain_adhd/ids_train.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_adhd/ids_val.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_adhd/ids_holdout.csv |
| conduct | hybrid_rf_ceiling_push_v1 | 1440 | 480 | 480 | data/hybrid_rf_ceiling_push_v1/splits/domain_conduct/ids_train.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_conduct/ids_val.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_conduct/ids_holdout.csv |
| elimination | hybrid_rf_ceiling_push_v1 | 1440 | 480 | 480 | data/hybrid_rf_ceiling_push_v1/splits/domain_elimination/ids_train.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_elimination/ids_val.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_elimination/ids_holdout.csv |
| anxiety | hybrid_rf_ceiling_push_v1 | 1440 | 480 | 480 | data/hybrid_rf_ceiling_push_v1/splits/domain_anxiety/ids_train.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_anxiety/ids_val.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_anxiety/ids_holdout.csv |
| depression | hybrid_rf_ceiling_push_v1 | 1440 | 480 | 480 | data/hybrid_rf_ceiling_push_v1/splits/domain_depression/ids_train.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_depression/ids_val.csv | data/hybrid_rf_ceiling_push_v1/splits/domain_depression/ids_holdout.csv |

## Mode Coverage
| mode | role | direct_features_from_priority_matrix | direct_features_usable_in_dataset | transparent_derived_eligible | total_eligible_features |
| --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | caregiver | 49 | 49 | 10 | 59 |
| caregiver_2_3 | caregiver | 98 | 98 | 15 | 113 |
| caregiver_full | caregiver | 147 | 147 | 22 | 169 |
| psychologist_1_3 | psychologist | 60 | 60 | 11 | 71 |
| psychologist_2_3 | psychologist | 120 | 120 | 16 | 136 |
| psychologist_full | psychologist | 180 | 180 | 22 | 202 |
