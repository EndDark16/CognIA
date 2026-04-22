# Hybrid RF Executive Summary

- line: `hybrid_rf_final_ceiling_push_v3`
- mode_domain_pairs_trained: 30
- evidence_overfitting: yes
- evidence_good_generalization: yes
- hybrid_dataset_material_improvement_vs_previous: yes
- ceiling_status_counts: {"marginal_room_left": 25, "ceiling_reached": 5}

## Best by domain (holdout BA)
| domain | mode | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc |
| --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | 0.948454 | 0.978723 | 0.982885 | 0.980874 |
| anxiety | caregiver_full | 0.911111 | 0.953488 | 0.966592 | 0.933569 |
| conduct | caregiver_2_3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| depression | caregiver_full | 0.804348 | 0.902439 | 0.928606 | 0.911586 |
| elimination | caregiver_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 |

## Best mode by role
| mode | mean_holdout_precision | mean_holdout_recall | mean_holdout_balanced_accuracy | mean_holdout_pr_auc |
| --- | --- | --- | --- | --- |
| caregiver_full | 0.888118 | 0.969058 | 0.969452 | 0.922980 |
| psychologist_full | 0.934563 | 0.950311 | 0.968081 | 0.973943 |
