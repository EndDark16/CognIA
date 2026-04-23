# Hybrid Operational Freeze v6 - Summary

## Final class counts
final_class
PRIMARY_WITH_CAVEAT    16
HOLD_FOR_LIMITATION    10
REJECT_AS_PRIMARY       3
ROBUST_PRIMARY          1

## Replacements
| domain | mode | old_active_model_id | promotion_decision | new_model_family | new_feature_set_id | delta_balanced_accuracy | delta_f1 | delta_pr_auc | delta_brier | root_cause_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | adhd__psychologist_full__rebuild_v2__rf__engineered_full | HOLD_FOR_LIMITATION | rf | engineered_pruned | 0.057353 | 0.045890 | 0.043180 | -0.006192 | secondary_metric_anomaly|weighting_boundary_adjustment |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.036891 | -0.030380 | -0.022808 | 0.027429 | secondary_metric_anomaly |
| anxiety | caregiver_full | anxiety__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | logreg | full_eligible | -0.043236 | -0.054946 | -0.053986 | 0.027384 | secondary_metric_anomaly |
| anxiety | psychologist_2_3 | anxiety__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | logreg | engineered_pruned_no_eng_v1 | -0.024731 | 0.001423 | -0.034918 | 0.024387 | secondary_metric_anomaly |
| anxiety | psychologist_full | anxiety__psychologist_full__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | hgb | dsm5_core_plus_context | 0.034884 | 0.035808 | 0.016959 | -0.005802 | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| conduct | caregiver_full | conduct__caregiver_full__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | PROMOTE_NOW | extra_trees | dsm5_core_plus_context | 0.093750 | 0.137236 | 0.050041 | -0.058222 | confidence_alignment_check|dsm5_core_signal_strengthened |
| conduct | psychologist_full | conduct__psychologist_full__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | PROMOTE_NOW | hgb | dsm5_core_plus_context | 0.084375 | 0.120008 | 0.058553 | -0.057787 | confidence_alignment_check|dsm5_core_signal_strengthened |
| depression | caregiver_1_3 | depression__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_only | 0.081045 | 0.046907 | 0.049782 | 0.001027 | limited_separability_or_underfit|recall_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | caregiver_2_3 | depression__caregiver_2_3__hybrid_final_decisive_rescue_v5__rf__precision_oriented_subset | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_plus_context | -0.015780 | -0.010577 | -0.009563 | 0.000936 | precision_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | caregiver_full | depression__caregiver_full__boosted_v3__catboost__full_eligible | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.005733 | -0.012445 | -0.001698 | 0.003341 | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | psychologist_1_3 | depression__psychologist_1_3__rebuild_v2__rf__stability_pruned_subset | HOLD_FOR_LIMITATION | extra_trees | dsm5_core_only | 0.029936 | -0.010870 | 0.046416 | 0.004564 | limited_separability_or_underfit|precision_tradeoff|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| depression | psychologist_full | depression__psychologist_full__boosted_v3__hgb__full_eligible | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | -0.002527 | -0.029726 | -0.015196 | 0.010031 | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | caregiver_1_3 | elimination__caregiver_1_3__boosted_v3__extra_trees__boosted_eng_full | HOLD_FOR_LIMITATION | rf | engineered_full | -0.019475 | -0.027473 | -0.006360 | -0.000981 | secondary_metric_anomaly |
| elimination | caregiver_2_3 | elimination__caregiver_2_3__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.001168 | 0.009169 | 0.046397 | 0.000090 | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | caregiver_full | elimination__caregiver_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | hgb | dsm5_core_plus_context | 0.001168 | 0.009169 | 0.054484 | -0.000363 | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
| elimination | psychologist_1_3 | elimination__psychologist_1_3__boosted_v3__extra_trees__boosted_eng_full | HOLD_FOR_LIMITATION | logreg | engineered_compact | 0.032381 | -0.007224 | -0.020771 | 0.011340 | secondary_metric_anomaly|weighting_boundary_adjustment |
| elimination | psychologist_2_3 | elimination__psychologist_2_3__final_honest_improvement_v1__rf__engineered_pruned | HOLD_FOR_LIMITATION | hgb | dsm5_core_only | 0.001168 | 0.009169 | 0.021352 | -0.000162 | secondary_metric_anomaly|dsm5_core_signal_strengthened |
| elimination | psychologist_full | elimination__psychologist_full__final_honest_improvement_v1__rf__engineered_compact | HOLD_FOR_LIMITATION | rf | dsm5_core_only | 0.002336 | 0.018514 | 0.008244 | 0.000402 | secondary_metric_anomaly|dsm5_core_signal_strengthened|weighting_boundary_adjustment |
