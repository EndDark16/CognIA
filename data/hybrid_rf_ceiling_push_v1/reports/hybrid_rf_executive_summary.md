# Hybrid RF Executive Summary

- line: `hybrid_rf_ceiling_push_v1`
- mode_domain_pairs_trained: 30
- evidence_overfitting: yes
- evidence_good_generalization: yes
- hybrid_dataset_material_improvement_vs_previous: yes
- ceiling_status_counts: {"marginal_room_left": 22, "ceiling_reached": 8}

## Best by domain (holdout BA)
| domain | mode | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc |
| --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | 0.947917 | 0.968085 | 0.977566 | 0.945106 |
| anxiety | caregiver_full | 0.941860 | 0.941860 | 0.964585 | 0.957131 |
| conduct | psychologist_2_3 | 0.987578 | 1.000000 | 0.996885 | 1.000000 |
| depression | caregiver_2_3 | 0.847222 | 0.743902 | 0.858132 | 0.862956 |
| elimination | caregiver_2_3 | 0.961538 | 0.961538 | 0.978433 | 0.974532 |

## Best mode by role
| mode | mean_holdout_precision | mean_holdout_recall | mean_holdout_balanced_accuracy | mean_holdout_pr_auc |
| --- | --- | --- | --- | --- |
| caregiver_2_3 | 0.889881 | 0.914765 | 0.943943 | 0.915214 |
| psychologist_full | 0.934804 | 0.887114 | 0.936817 | 0.950470 |
