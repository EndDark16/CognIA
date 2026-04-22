# Hybrid No External Scores - Modeling Decision

## Champions
| domain | champion_mode | champion_feature_set_id | champion_config_id | champion_calibration | champion_threshold_policy | champion_final_status | precision | recall | balanced_accuracy | pr_auc | brier | ceiling_status | should_keep_improving |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | engineered_full | rf_precision_push | isotonic | precision_min_recall | FROZEN_PRIMARY | 0.929412 | 0.840426 | 0.912441 | 0.927131 | 0.030233 | marginal_room_left | yes |
| anxiety | caregiver_full | precision_oriented_subset | rf_precision_push | isotonic | balanced | FROZEN_PRIMARY | 0.916667 | 0.895349 | 0.938791 | 0.946538 | 0.027444 | marginal_room_left | yes |
| conduct | psychologist_2_3 | engineered_compact | rf_balanced_subsample | isotonic | recall_constrained | FROZEN_PRIMARY | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.001095 | marginal_room_left | yes |
| depression | psychologist_full | engineered_full | rf_pos_weight_mid | sigmoid | balanced | FROZEN_WITH_CAVEAT | 0.837500 | 0.817073 | 0.892205 | 0.940602 | 0.039160 | marginal_room_left | yes |
| elimination | psychologist_full | engineered_compact | rf_baseline | isotonic | precision_min_recall | FROZEN_PRIMARY | 0.943396 | 0.961538 | 0.977265 | 0.973474 | 0.009137 | marginal_room_left | yes |

## Viability
- Strictly aligned with product reality (no external scores/subscales).
- Promote as new primary only where quality+stability are defendable.