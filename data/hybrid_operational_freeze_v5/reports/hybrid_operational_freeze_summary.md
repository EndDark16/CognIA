# Hybrid Operational Freeze v5 - Summary

## Final class counts
final_class
PRIMARY_WITH_CAVEAT    19
HOLD_FOR_LIMITATION     7
REJECT_AS_PRIMARY       3
ROBUST_PRIMARY          1

## Replacements
| domain | mode | old_active_model_id | promotion_decision | new_model_family | new_feature_set_id | delta_balanced_accuracy | delta_f1 | delta_pr_auc | delta_brier | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | adhd__psychologist_full__rebuild_v2__rf__engineered_full | HOLD_FOR_LIMITATION | extra_trees | engineered_full | 0.057491 | 0.032741 | 0.055628 | -0.008457 | secondary_metric_anomaly |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.035622 | -0.025185 | -0.027595 | 0.029976 | secondary_metric_anomaly |
| anxiety | caregiver_full | anxiety__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | logreg | full_eligible | -0.043236 | -0.054946 | -0.053986 | 0.027384 | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | anxiety__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.029276 | -0.000065 | -0.040674 | 0.026372 | secondary_metric_anomaly |
| anxiety | psychologist_full | anxiety__psychologist_full__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | hgb | full_eligible | 0.025794 | 0.034055 | 0.012659 | -0.004829 | secondary_metric_anomaly |
| depression | caregiver_1_3 | depression__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset | HOLD_FOR_LIMITATION | rf | precision_oriented_subset | 0.092873 | 0.032744 | 0.042450 | 0.000068 | limited_separability_or_underfit|recall_tradeoff |
| depression | caregiver_2_3 | depression__caregiver_2_3__rebuild_v2__rf__full_eligible | PROMOTE_NOW | rf | precision_oriented_subset | 0.021694 | -0.000205 | 0.075091 | -0.001475 | confidence_alignment_check |
| depression | caregiver_full | depression__caregiver_full__boosted_v3__catboost__full_eligible | HOLD_FOR_LIMITATION | rf | precision_oriented_subset | -0.018473 | -0.019473 | -0.017128 | 0.010475 | secondary_metric_anomaly |
| depression | psychologist_1_3 | depression__psychologist_1_3__rebuild_v2__rf__stability_pruned_subset | HOLD_FOR_LIMITATION | rf | stability_pruned_subset | 0.045900 | 0.015206 | 0.062538 | 0.003230 | limited_separability_or_underfit|precision_tradeoff |
| depression | psychologist_full | depression__psychologist_full__boosted_v3__hgb__full_eligible | HOLD_FOR_LIMITATION | hgb | full_eligible | -0.007184 | -0.012346 | -0.022911 | 0.011017 | secondary_metric_anomaly |
| elimination | caregiver_1_3 | elimination__caregiver_1_3__boosted_v3__extra_trees__boosted_eng_full | HOLD_FOR_LIMITATION | logreg | boosted_eng_full | -0.006086 | -0.045330 | -0.044580 | 0.018106 | secondary_metric_anomaly |
| elimination | caregiver_2_3 | elimination__caregiver_2_3__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | hgb | engineered_compact_no_eng_v1 | 0.001168 | 0.009169 | 0.056070 | -0.003449 | secondary_metric_anomaly |
| elimination | caregiver_full | elimination__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | rf | engineered_compact_no_eng_v1 | 0.000000 | -0.000000 | 0.056285 | -0.001991 | secondary_metric_anomaly |
| elimination | psychologist_1_3 | elimination__psychologist_1_3__boosted_v3__extra_trees__boosted_eng_full | HOLD_FOR_LIMITATION | logreg | boosted_eng_full | -0.027647 | -0.083779 | -0.056150 | 0.019734 | secondary_metric_anomaly |
| elimination | psychologist_2_3 | elimination__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | hgb | engineered_pruned_no_eng_v1 | 0.000000 | -0.000000 | 0.030615 | -0.003229 | secondary_metric_anomaly |
| elimination | psychologist_full | elimination__psychologist_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | rf | engineered_compact_no_shortcut_v1 | 0.000000 | -0.000000 | 0.006749 | -0.001845 | secondary_metric_anomaly |
