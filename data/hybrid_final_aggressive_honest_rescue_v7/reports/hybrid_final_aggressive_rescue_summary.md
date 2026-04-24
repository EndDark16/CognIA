# Hybrid Final Aggressive Honest Rescue v7 - Executive Summary

Aggressive final campaign to maximize real model quality while preserving methodological honesty and operational contract.

## Focus slots
| domain | mode | source_campaign | feature_set_id | confidence_pct | confidence_band | secondary_metric_anomaly_flag | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | rebuild_v2 | engineered_full | 56.400000 | limited | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal |
| anxiety | caregiver_2_3 | final_honest_improvement_v1 | engineered_pruned | 63.100000 | low | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance |
| anxiety | caregiver_full | final_honest_improvement_v1 | engineered_compact | 68.100000 | low | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance |
| anxiety | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 65.300000 | low | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance |
| anxiety | psychologist_full | final_honest_improvement_v1 | engineered_pruned | 66.300000 | low | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance |
| conduct | caregiver_full | hybrid_final_aggressive_rescue_v6 | dsm5_core_plus_context | 67.700000 | low | yes | secondary_metric_anomaly |
| conduct | psychologist_full | hybrid_final_aggressive_rescue_v6 | dsm5_core_plus_context | 80.700000 | moderate | yes | secondary_metric_anomaly |
| depression | caregiver_1_3 | rebuild_v2 | precision_oriented_subset | 21.300000 | limited | no | limited_separability_or_underfit|recall_tradeoff|precision_recall_tradeoff |
| depression | caregiver_2_3 | hybrid_final_decisive_rescue_v5 | precision_oriented_subset | 48.300000 | limited | no | insufficient_dsm5_core_signal|low_precision_due_to_boundary_noise|precision_recall_tradeoff |
| depression | caregiver_full | boosted_v3 | full_eligible | 42.400000 | limited | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| depression | psychologist_1_3 | rebuild_v2 | stability_pruned_subset | 30.000000 | limited | no | insufficient_dsm5_core_signal|limited_separability_or_underfit|low_precision_due_to_boundary_noise|precision_recall_tradeoff |
| depression | psychologist_2_3 | final_honest_improvement_v1 | compact_subset | 57.400000 | limited | no | insufficient_dsm5_core_signal|low_precision_due_to_boundary_noise |
| depression | psychologist_full | boosted_v3 | full_eligible | 62.300000 | low | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| elimination | caregiver_1_3 | boosted_v3 | boosted_eng_full | 41.900000 | limited | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| elimination | caregiver_2_3 | final_honest_improvement_v1 | engineered_compact | 80.300000 | moderate | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal |
| elimination | caregiver_full | final_honest_improvement_v1 | engineered_compact | 80.400000 | moderate | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal |
| elimination | psychologist_1_3 | boosted_v3 | boosted_eng_full | 46.100000 | limited | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| elimination | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 76.700000 | moderate | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal |
| elimination | psychologist_full | final_honest_improvement_v1 | engineered_compact | 81.700000 | moderate | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal |

## Selection result
| domain | mode | promotion_decision | model_family | feature_set_id | delta_balanced_accuracy | delta_f1 | delta_pr_auc | old_secondary_anomaly | new_secondary_anomaly | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | HOLD_FOR_LIMITATION | rf | engineered_full | 0.040100 | 0.024535 | 0.051632 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal|weighting_boundary_adjustment |
| anxiety | caregiver_2_3 | HOLD_FOR_LIMITATION | xgb | engineered_pruned_no_shortcut_v1 | 0.018711 | 0.023546 | 0.010667 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|weighting_boundary_adjustment |
| anxiety | caregiver_full | HOLD_FOR_LIMITATION | extra_trees | balanced_subset | 0.008352 | 0.016378 | -0.011617 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance |
| anxiety | psychologist_2_3 | HOLD_FOR_LIMITATION | xgb | engineered_pruned_no_eng_v1 | 0.030870 | 0.053860 | -0.002315 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|weighting_boundary_adjustment |
| anxiety | psychologist_full | HOLD_FOR_LIMITATION | xgb | engineered_pruned_no_eng_v1 | 0.012159 | 0.031276 | 0.007821 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|weighting_boundary_adjustment |
| conduct | caregiver_full | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_plus_context | -0.007812 | -0.006348 | 0.000000 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| conduct | psychologist_full | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_only | -0.010937 | -0.009543 | 0.000117 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | rf | stability_pruned_subset | 0.039803 | 0.016344 | 0.053531 | no | no | limited_separability_or_underfit|recall_tradeoff|precision_recall_tradeoff|weighting_boundary_adjustment |
| depression | caregiver_2_3 | HOLD_FOR_LIMITATION | extra_trees | precision_oriented_subset | -0.015780 | -0.010577 | -0.002997 | no | no | insufficient_dsm5_core_signal|low_precision_due_to_boundary_noise|precision_recall_tradeoff |
| depression | caregiver_full | HOLD_FOR_LIMITATION | rf | compact_subset | -0.023314 | -0.020978 | -0.016195 | yes | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | hgb | stability_pruned_subset | -0.023502 | -0.056418 | 0.016147 | no | no | insufficient_dsm5_core_signal|limited_separability_or_underfit|low_precision_due_to_boundary_noise|precision_recall_tradeoff |
| depression | psychologist_2_3 | HOLD_FOR_LIMITATION | hgb | engineered_compact | -0.037842 | -0.045587 | 0.031693 | no | no | insufficient_dsm5_core_signal|low_precision_due_to_boundary_noise |
| depression | psychologist_full | HOLD_FOR_LIMITATION | xgb | full_eligible | -0.064391 | -0.065792 | -0.007749 | yes | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal|weighting_boundary_adjustment |
| elimination | caregiver_1_3 | HOLD_FOR_LIMITATION | xgb | engineered_pruned | -0.048322 | -0.061086 | -0.017324 | yes | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| elimination | caregiver_2_3 | HOLD_FOR_LIMITATION | hgb | stability_pruned_subset | -0.008447 | -0.000534 | 0.056158 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal|weighting_boundary_adjustment |
| elimination | caregiver_full | HOLD_FOR_LIMITATION | hgb | engineered_compact_no_eng_v1 | -0.007279 | 0.008807 | 0.055538 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal|weighting_boundary_adjustment |
| elimination | psychologist_1_3 | HOLD_FOR_LIMITATION | hgb | stability_pruned_subset | -0.021806 | -0.044818 | -0.013865 | yes | yes | secondary_metric_anomaly|insufficient_dsm5_core_signal |
| elimination | psychologist_2_3 | HOLD_FOR_LIMITATION | hgb | stability_pruned_subset | 0.001168 | 0.009169 | 0.031425 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal|weighting_boundary_adjustment |
| elimination | psychologist_full | HOLD_FOR_LIMITATION | hgb | engineered_compact_no_eng_v1 | -0.007279 | 0.008807 | 0.007881 | yes | yes | secondary_metric_anomaly|anomaly_due_to_feature_dominance|insufficient_dsm5_core_signal|weighting_boundary_adjustment |

## Active class counts v7
final_operational_class
ACTIVE_LIMITED_USE            15
ACTIVE_LOW_CONFIDENCE          8
ACTIVE_MODERATE_CONFIDENCE     7

## Confidence bands v7
confidence_band
limited     15
low          8
moderate     7

## Policy violations v7
- violations=0
