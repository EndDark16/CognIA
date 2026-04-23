# Hybrid Final Decisive Rescue v5 - Executive Summary

Decisive campaign to align performance, methodological class, confidence and active operational status.

## Focus slots
| domain | mode | source_campaign | feature_set_id | confidence_pct | confidence_band | secondary_metric_anomaly_flag | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | rebuild_v2 | engineered_full | 91.700000 | high | yes | secondary_metric_anomaly |
| anxiety | caregiver_2_3 | final_honest_improvement_v1 | engineered_pruned | 79.400000 | moderate | yes | secondary_metric_anomaly |
| anxiety | caregiver_full | final_honest_improvement_v1 | engineered_compact | 80.800000 | moderate | yes | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 75.200000 | moderate | yes | secondary_metric_anomaly |
| anxiety | psychologist_full | final_honest_improvement_v1 | engineered_pruned | 78.900000 | moderate | yes | secondary_metric_anomaly |
| depression | caregiver_1_3 | rebuild_v2 | precision_oriented_subset | 18.600000 | limited | no | limited_separability_or_underfit|recall_tradeoff |
| depression | caregiver_2_3 | rebuild_v2 | full_eligible | 56.300000 | low | no | confidence_alignment_check |
| depression | caregiver_full | boosted_v3 | full_eligible | 91.400000 | high | yes | secondary_metric_anomaly |
| depression | psychologist_1_3 | rebuild_v2 | stability_pruned_subset | 24.500000 | limited | no | limited_separability_or_underfit|precision_tradeoff |
| depression | psychologist_full | boosted_v3 | full_eligible | 92.800000 | high | yes | secondary_metric_anomaly |
| elimination | caregiver_1_3 | boosted_v3 | boosted_eng_full | 92.400000 | high | yes | secondary_metric_anomaly |
| elimination | caregiver_2_3 | final_honest_improvement_v1 | engineered_compact | 86.700000 | moderate | yes | secondary_metric_anomaly |
| elimination | caregiver_full | final_honest_improvement_v1 | engineered_compact | 86.700000 | moderate | yes | secondary_metric_anomaly |
| elimination | psychologist_1_3 | boosted_v3 | boosted_eng_full | 96.900000 | high | yes | secondary_metric_anomaly |
| elimination | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 87.700000 | moderate | yes | secondary_metric_anomaly |
| elimination | psychologist_full | final_honest_improvement_v1 | engineered_compact | 88.300000 | high | yes | secondary_metric_anomaly |

## Selection result
| domain | mode | promotion_decision | model_family | feature_set_id | delta_balanced_accuracy | delta_f1 | delta_pr_auc | old_secondary_anomaly | new_secondary_anomaly | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | HOLD_FOR_LIMITATION | extra_trees | engineered_full | 0.057491 | 0.032741 | 0.055628 | yes | yes | secondary_metric_anomaly |
| anxiety | caregiver_2_3 | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.035622 | -0.025185 | -0.027595 | yes | no | secondary_metric_anomaly |
| anxiety | caregiver_full | HOLD_FOR_LIMITATION | logreg | full_eligible | -0.043236 | -0.054946 | -0.053986 | yes | no | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.029276 | -0.000065 | -0.040674 | yes | no | secondary_metric_anomaly |
| anxiety | psychologist_full | HOLD_FOR_LIMITATION | hgb | full_eligible | 0.025794 | 0.034055 | 0.012659 | yes | yes | secondary_metric_anomaly |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | rf | precision_oriented_subset | 0.092873 | 0.032744 | 0.042450 | no | no | limited_separability_or_underfit|recall_tradeoff |
| depression | caregiver_2_3 | PROMOTE_NOW | rf | precision_oriented_subset | 0.021694 | -0.000205 | 0.075091 | no | no | confidence_alignment_check |
| depression | caregiver_full | HOLD_FOR_LIMITATION | rf | precision_oriented_subset | -0.018473 | -0.019473 | -0.017128 | yes | yes | secondary_metric_anomaly |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | rf | stability_pruned_subset | 0.045900 | 0.015206 | 0.062538 | no | no | limited_separability_or_underfit|precision_tradeoff |
| depression | psychologist_full | HOLD_FOR_LIMITATION | hgb | full_eligible | -0.007184 | -0.012346 | -0.022911 | yes | yes | secondary_metric_anomaly |
| elimination | caregiver_1_3 | HOLD_FOR_LIMITATION | logreg | boosted_eng_full | -0.006086 | -0.045330 | -0.044580 | yes | yes | secondary_metric_anomaly |
| elimination | caregiver_2_3 | HOLD_FOR_LIMITATION | hgb | engineered_compact_no_eng_v1 | 0.001168 | 0.009169 | 0.056070 | yes | yes | secondary_metric_anomaly |
| elimination | caregiver_full | HOLD_FOR_LIMITATION | rf | engineered_compact_no_eng_v1 | 0.000000 | -0.000000 | 0.056285 | yes | yes | secondary_metric_anomaly |
| elimination | psychologist_1_3 | HOLD_FOR_LIMITATION | logreg | boosted_eng_full | -0.027647 | -0.083779 | -0.056150 | yes | yes | secondary_metric_anomaly |
| elimination | psychologist_2_3 | HOLD_FOR_LIMITATION | hgb | engineered_pruned_no_eng_v1 | 0.000000 | -0.000000 | 0.030615 | yes | yes | secondary_metric_anomaly |
| elimination | psychologist_full | HOLD_FOR_LIMITATION | rf | engineered_compact_no_shortcut_v1 | 0.000000 | -0.000000 | 0.006749 | yes | yes | secondary_metric_anomaly |

## Active class counts v5
final_operational_class
ACTIVE_LIMITED_USE            13
ACTIVE_LOW_CONFIDENCE         11
ACTIVE_MODERATE_CONFIDENCE     6

## Confidence bands v5
confidence_band
limited     13
low         11
moderate     6

## Policy violations v5
- violations=0
