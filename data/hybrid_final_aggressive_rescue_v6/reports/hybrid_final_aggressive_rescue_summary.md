# Hybrid Final Aggressive Rescue v6 - Executive Summary

Aggressive final campaign to maximize real model quality while preserving methodological honesty and operational contract.

## Focus slots
| domain | mode | source_campaign | feature_set_id | confidence_pct | confidence_band | secondary_metric_anomaly_flag | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | rebuild_v2 | engineered_full | 60.300000 | low | yes | secondary_metric_anomaly |
| anxiety | caregiver_2_3 | final_honest_improvement_v1 | engineered_pruned | 68.500000 | low | yes | secondary_metric_anomaly |
| anxiety | caregiver_full | final_honest_improvement_v1 | engineered_compact | 71.600000 | low | yes | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 69.300000 | low | yes | secondary_metric_anomaly |
| anxiety | psychologist_full | final_honest_improvement_v1 | engineered_pruned | 70.500000 | low | yes | secondary_metric_anomaly |
| conduct | caregiver_full | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 67.100000 | low | no | confidence_alignment_check |
| conduct | psychologist_full | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 72.400000 | moderate | no | confidence_alignment_check |
| depression | caregiver_1_3 | rebuild_v2 | precision_oriented_subset | 2.700000 | limited | no | limited_separability_or_underfit|recall_tradeoff |
| depression | caregiver_2_3 | hybrid_final_decisive_rescue_v5 | precision_oriented_subset | 48.400000 | limited | no | precision_tradeoff |
| depression | caregiver_full | boosted_v3 | full_eligible | 57.900000 | limited | yes | secondary_metric_anomaly |
| depression | psychologist_1_3 | rebuild_v2 | stability_pruned_subset | 11.700000 | limited | no | limited_separability_or_underfit|precision_tradeoff |
| depression | psychologist_full | boosted_v3 | full_eligible | 68.200000 | low | yes | secondary_metric_anomaly |
| elimination | caregiver_1_3 | boosted_v3 | boosted_eng_full | 54.800000 | limited | yes | secondary_metric_anomaly |
| elimination | caregiver_2_3 | final_honest_improvement_v1 | engineered_compact | 80.300000 | moderate | yes | secondary_metric_anomaly |
| elimination | caregiver_full | final_honest_improvement_v1 | engineered_compact | 80.400000 | moderate | yes | secondary_metric_anomaly |
| elimination | psychologist_1_3 | boosted_v3 | boosted_eng_full | 59.200000 | limited | yes | secondary_metric_anomaly |
| elimination | psychologist_2_3 | final_honest_improvement_v1 | engineered_pruned | 75.700000 | moderate | yes | secondary_metric_anomaly |
| elimination | psychologist_full | final_honest_improvement_v1 | engineered_compact | 81.700000 | moderate | yes | secondary_metric_anomaly |

## Selection result
| domain | mode | promotion_decision | model_family | feature_set_id | delta_balanced_accuracy | delta_f1 | delta_pr_auc | old_secondary_anomaly | new_secondary_anomaly | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | HOLD_FOR_LIMITATION | rf | engineered_pruned | 0.057353 | 0.045890 | 0.043180 | yes | yes | secondary_metric_anomaly|weighting_boundary_adjustment |
| anxiety | caregiver_2_3 | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.036891 | -0.030380 | -0.022808 | yes | no | secondary_metric_anomaly |
| anxiety | caregiver_full | HOLD_FOR_LIMITATION | logreg | full_eligible | -0.043236 | -0.054946 | -0.053986 | yes | no | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.024731 | 0.001423 | -0.034918 | yes | no | secondary_metric_anomaly |
| anxiety | psychologist_full | HOLD_FOR_LIMITATION | hgb | dsm5_core_plus_context | 0.034884 | 0.035808 | 0.016959 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| conduct | caregiver_full | PROMOTE_NOW | extra_trees | dsm5_core_plus_context | 0.093750 | 0.137236 | 0.050041 | no | yes | confidence_alignment_check|dsm5_core_signal_strengthened |
| conduct | psychologist_full | PROMOTE_NOW | hgb | dsm5_core_plus_context | 0.084375 | 0.120008 | 0.058553 | no | yes | confidence_alignment_check|dsm5_core_signal_strengthened |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_only | 0.081045 | 0.046907 | 0.049782 | no | no | limited_separability_or_underfit|recall_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | caregiver_2_3 | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_plus_context | -0.015780 | -0.010577 | -0.009563 | no | no | precision_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | caregiver_full | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.005733 | -0.012445 | -0.001698 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_only | 0.029936 | -0.010870 | 0.046416 | no | no | limited_separability_or_underfit|precision_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | psychologist_full | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | -0.002527 | -0.029726 | -0.015196 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | caregiver_1_3 | HOLD_FOR_LIMITATION | rf | engineered_full | -0.019475 | -0.027473 | -0.006360 | yes | yes | secondary_metric_anomaly |
| elimination | caregiver_2_3 | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.001168 | 0.009169 | 0.046397 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | caregiver_full | HOLD_FOR_LIMITATION | hgb | dsm5_core_plus_context | 0.001168 | 0.009169 | 0.054484 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| elimination | psychologist_1_3 | HOLD_FOR_LIMITATION | logreg | engineered_compact | 0.032381 | -0.007224 | -0.020771 | yes | yes | secondary_metric_anomaly|weighting_boundary_adjustment |
| elimination | psychologist_2_3 | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.001168 | 0.009169 | 0.021352 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | psychologist_full | HOLD_FOR_LIMITATION | rf | dsm5_core_only | 0.002336 | 0.018514 | 0.008244 | yes | yes | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |

## Active class counts v6
final_operational_class
ACTIVE_LIMITED_USE            15
ACTIVE_LOW_CONFIDENCE          9
ACTIVE_MODERATE_CONFIDENCE     6

## Confidence bands v6
confidence_band
limited     15
low          9
moderate     6

## Policy violations v6
- violations=0
