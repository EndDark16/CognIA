# Hybrid Operational Freeze v3 - Summary

Targeted secondary audit/retrain over freeze_v2 (Conduct preserved).

## Final class counts
final_class
ROBUST_PRIMARY         17
HOLD_FOR_LIMITATION     9
PRIMARY_WITH_CAVEAT     4

## Retrained comparison
| domain | mode | promotion_decision | precision_old | precision_new | balanced_accuracy_old | balanced_accuracy_new | roc_auc_old | roc_auc_new | pr_auc_old | pr_auc_new |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anxiety | psychologist_1_3 | HOLD_FOR_LIMITATION | 0.953846 | 0.847826 | 0.856658 | 0.935722 | 0.983606 | 0.985554 | 0.916729 | 0.929788 |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | 0.805970 | 0.700935 | 0.812937 | 0.917116 | 0.958282 | 0.961147 | 0.764765 | 0.765738 |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | 0.797468 | 0.723404 | 0.864046 | 0.881971 | 0.948385 | 0.956674 | 0.768131 | 0.789220 |
