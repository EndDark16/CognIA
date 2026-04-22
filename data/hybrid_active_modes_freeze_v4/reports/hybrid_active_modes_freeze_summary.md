# Hybrid Active Modes Freeze v4 - Summary

Final honest improvement campaign focused on full and 2_3 modes.

## Active class counts
final_operational_class
ACTIVE_MODERATE_CONFIDENCE    13
ACTIVE_HIGH_CONFIDENCE         9
ACTIVE_LIMITED_USE             8

## Replaced active rows
| domain | mode | active_model_id | source_campaign | feature_set_id | precision | recall | specificity | balanced_accuracy | f1 | roc_auc | pr_auc | brier | confidence_pct | confidence_band | final_operational_class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3__final_honest_improvement_v1__rf__engineered_pruned | final_honest_improvement_v1 | engineered_pruned | 0.868132 | 0.918605 | 0.969543 | 0.944074 | 0.892655 | 0.991914 | 0.957210 | 0.026805 | 79.400000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| anxiety | caregiver_full | anxiety__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | final_honest_improvement_v1 | engineered_compact | 0.869565 | 0.930233 | 0.969543 | 0.949888 | 0.898876 | 0.992947 | 0.970439 | 0.026002 | 80.800000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| anxiety | psychologist_2_3 | anxiety__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | final_honest_improvement_v1 | engineered_pruned | 0.824742 | 0.930233 | 0.956853 | 0.943543 | 0.874317 | 0.991884 | 0.966313 | 0.027676 | 75.200000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| anxiety | psychologist_full | anxiety__psychologist_full__final_honest_improvement_v1__rf__engineered_pruned | final_honest_improvement_v1 | engineered_pruned | 0.842105 | 0.930233 | 0.961929 | 0.946081 | 0.883978 | 0.991914 | 0.959182 | 0.026435 | 78.900000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| depression | psychologist_2_3 | depression__psychologist_2_3__final_honest_improvement_v1__rf__compact_subset | final_honest_improvement_v1 | compact_subset | 0.787234 | 0.902439 | 0.949749 | 0.926094 | 0.840909 | 0.979409 | 0.867512 | 0.042901 | 74.300000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| elimination | caregiver_2_3 | elimination__caregiver_2_3__final_honest_improvement_v1__rf__engineered_compact | final_honest_improvement_v1 | engineered_compact | 0.945455 | 1.000000 | 0.992991 | 0.996495 | 0.971963 | 0.997551 | 0.941643 | 0.006191 | 86.700000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| elimination | caregiver_full | elimination__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | final_honest_improvement_v1 | engineered_compact | 0.945455 | 1.000000 | 0.992991 | 0.996495 | 0.971963 | 0.997484 | 0.943352 | 0.006432 | 86.700000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| elimination | psychologist_2_3 | elimination__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | final_honest_improvement_v1 | engineered_pruned | 0.945455 | 1.000000 | 0.992991 | 0.996495 | 0.971963 | 0.997843 | 0.966688 | 0.006444 | 87.700000 | moderate | ACTIVE_MODERATE_CONFIDENCE |
| elimination | psychologist_full | elimination__psychologist_full__final_honest_improvement_v1__rf__engineered_compact | final_honest_improvement_v1 | engineered_compact | 0.945455 | 1.000000 | 0.992991 | 0.996495 | 0.971963 | 0.999056 | 0.991756 | 0.006284 | 88.300000 | high | ACTIVE_HIGH_CONFIDENCE |
