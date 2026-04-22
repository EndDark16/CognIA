# Hybrid RF Targeted Fix v4 - Inventory

## Candidates
| candidate_id | domain | mode | role | v3_feature_set_id | v3_config_id | v3_calibration | v3_threshold_policy | v3_threshold | v3_holdout_precision | v3_holdout_recall | v3_holdout_ba | v3_holdout_pr_auc | v3_holdout_brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | adhd | caregiver_1_3 | caregiver | precision_oriented_subset | rf_regularized | isotonic | balanced | 0.050000 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 |
| adhd__caregiver_2_3 | adhd | caregiver_2_3 | caregiver | stability_pruned_subset | rf_positive_push_strong | isotonic | default_0_5 | 0.500000 | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 |
| adhd__psychologist_1_3 | adhd | psychologist_1_3 | psychologist | full_eligible | rf_baseline | isotonic | default_0_5 | 0.500000 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 |
| adhd__psychologist_2_3 | adhd | psychologist_2_3 | psychologist | balanced_subset | rf_regularized | isotonic | balanced | 0.050000 | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 |
| anxiety__caregiver_1_3 | anxiety | caregiver_1_3 | caregiver | compact_robust_subset | rf_recall_guard | isotonic | precision_min_recall | 0.605000 | 0.900000 | 0.627907 | 0.806339 | 0.803065 | 0.059892 |
| anxiety__caregiver_2_3 | anxiety | caregiver_2_3 | caregiver | precision_oriented_subset | rf_positive_push_strong | isotonic | precision_min_recall | 0.505000 | 0.950000 | 0.883721 | 0.936784 | 0.940513 | 0.020749 |
| anxiety__caregiver_full | anxiety | caregiver_full | caregiver | balanced_subset | rf_positive_push_strong | isotonic | balanced | 0.145000 | 0.911111 | 0.953488 | 0.966592 | 0.933569 | 0.025594 |
| depression__caregiver_1_3 | depression | caregiver_1_3 | caregiver | precision_oriented_subset | rf_recall_guard | isotonic | recall_guard | 0.335000 | 0.758242 | 0.841463 | 0.893094 | 0.797190 | 0.055149 |
| depression__caregiver_2_3 | depression | caregiver_2_3 | caregiver | full_eligible | rf_precision_push | isotonic | balanced | 0.130000 | 0.750000 | 0.878049 | 0.908874 | 0.880904 | 0.046740 |
| depression__caregiver_full | depression | caregiver_full | caregiver | precision_oriented_subset | rf_positive_push_strong | isotonic | balanced | 0.090000 | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 |
| depression__psychologist_1_3 | depression | psychologist_1_3 | psychologist | balanced_subset | rf_recall_guard | isotonic | default_0_5 | 0.500000 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 |
| depression__psychologist_2_3 | depression | psychologist_2_3 | psychologist | stability_pruned_subset | rf_positive_push_strong | isotonic | precision_min_recall | 0.620000 | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 |
| depression__psychologist_full | depression | psychologist_full | psychologist | full_eligible | rf_precision_push | none | recall_guard | 0.365000 | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 |
| elimination__caregiver_1_3 | elimination | caregiver_1_3 | caregiver | stability_pruned_subset | rf_precision_push | none | default_0_5 | 0.500000 | 0.781818 | 0.826923 | 0.899443 | 0.938264 | 0.022472 |
| elimination__caregiver_2_3 | elimination | caregiver_2_3 | caregiver | precision_oriented_subset | rf_positive_push_strong | isotonic | balanced | 0.050000 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 |
| elimination__psychologist_1_3 | elimination | psychologist_1_3 | psychologist | full_eligible | rf_baseline | isotonic | default_0_5 | 0.500000 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 |
| elimination__psychologist_2_3 | elimination | psychologist_2_3 | psychologist | balanced_subset | rf_positive_push_strong | isotonic | balanced | 0.050000 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000437 |

## Scope Notes
- Campaign is surgical: only fragile/insufficient pairs from v3 were attacked.
- Holdout split is reused from v3 and remains untouched for tuning.
- RandomForest remains the principal and only model family.
