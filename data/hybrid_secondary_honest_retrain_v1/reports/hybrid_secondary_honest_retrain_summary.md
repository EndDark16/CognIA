# Hybrid Secondary Honest Retrain v1 - Executive Summary

Focused on remaining suspicious slots after Conduct retrain (priority: depression short modes).

## Suspicion inventory (outside conduct)
| domain | mode | source_campaign | secondary_max_metric | secondary_gt_098 | overfit_flag | shortcut_dominance_flag | best_single_feature | best_single_feature_ba | feature_audit_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | rebuild_v2 | 0.989265 | yes | no | no | eng_adhd_core_mean | 0.893645 | exact_v2 |
| anxiety | caregiver_2_3 | rebuild_v2 | 0.991884 | yes | no | no | social_anxiety_almost_always_triggered | 0.884754 | exact_v2 |
| anxiety | caregiver_full | rebuild_v2 | 0.991146 | yes | no | no | social_anxiety_almost_always_triggered | 0.884754 | exact_v2 |
| anxiety | psychologist_1_3 | rebuild_v2 | 0.992386 | yes | no | yes | eng_anxiety_core_mean | 0.936460 | exact_v2 |
| anxiety | psychologist_2_3 | rebuild_v2 | 0.989818 | yes | no | no | social_anxiety_almost_always_triggered | 0.884754 | exact_v2 |
| anxiety | psychologist_full | rebuild_v2 | 0.991161 | yes | no | no | social_anxiety_almost_always_triggered | 0.884754 | exact_v2 |
| depression | caregiver_1_3 | rebuild_v2 | 0.967337 | no | yes | no | mdd_08_concentration_or_decision_difficulty | 0.839073 | exact_v2 |
| depression | caregiver_full | boosted_v3 | 0.990911 | yes | no | no | mdd_impairment | 0.888773 | mapped_v2_by_name_por_confirmar |
| depression | psychologist_1_3 | rebuild_v2 | 0.959799 | no | yes | no | mdd_08_concentration_or_decision_difficulty | 0.839073 | exact_v2 |
| depression | psychologist_full | boosted_v3 | 0.992314 | yes | no | no | mdd_impairment | 0.888773 | mapped_v2_by_name_por_confirmar |
| elimination | caregiver_1_3 | boosted_v3 | 0.996778 | yes | no | no | enuresis_event_frequency_per_week | 0.864486 | base_only_por_confirmar_engv3 |
| elimination | caregiver_2_3 | rebuild_v2 | 0.997079 | yes | no | no | eng_elimination_intensity | 0.965852 | exact_v2 |
| elimination | caregiver_full | rebuild_v2 | 0.997214 | yes | no | no | eng_elimination_intensity | 0.965852 | exact_v2 |
| elimination | psychologist_1_3 | boosted_v3 | 0.996572 | yes | no | no | enuresis_event_frequency_per_week | 0.864486 | base_only_por_confirmar_engv3 |
| elimination | psychologist_2_3 | rebuild_v2 | 0.997192 | yes | no | no | eng_elimination_intensity | 0.965852 | exact_v2 |
| elimination | psychologist_full | rebuild_v2 | 0.998090 | yes | no | no | eng_elimination_intensity | 0.965852 | exact_v2 |

## Retrain targets
| domain | mode | role | active_model_id | source_campaign | feature_set_id | overfit_flag | secondary_gt_098 | shortcut_dominance_flag | best_single_feature |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anxiety | psychologist_1_3 | psychologist | anxiety__psychologist_1_3__rebuild_v2__rf__engineered_full | rebuild_v2 | engineered_full | no | yes | yes | eng_anxiety_core_mean |
| depression | caregiver_1_3 | caregiver | depression__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset | rebuild_v2 | precision_oriented_subset | yes | no | no | mdd_08_concentration_or_decision_difficulty |
| depression | psychologist_1_3 | psychologist | depression__psychologist_1_3__rebuild_v2__rf__stability_pruned_subset | rebuild_v2 | stability_pruned_subset | yes | no | no | mdd_08_concentration_or_decision_difficulty |

## Selection result
| domain | mode | feature_set_id | config_id | calibration | threshold_policy | threshold | precision | recall | specificity | balanced_accuracy | f1 | roc_auc | pr_auc | brier | quality_label | secondary_max_metric | secondary_cap_ok | generalization_ok | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anxiety | psychologist_1_3 | engineered_full | rf_precision_guard_v2 | isotonic | balanced | 0.125000 | 0.847826 | 0.906977 | 0.964467 | 0.935722 | 0.876404 | 0.985554 | 0.929788 | 0.033599 | bueno | 0.985554 | no | yes | HOLD_FOR_LIMITATION |
| depression | caregiver_1_3 | stability_pruned_subset | rf_regularized_v2 | none | balanced | 0.450000 | 0.700935 | 0.914634 | 0.919598 | 0.917116 | 0.793651 | 0.961147 | 0.765738 | 0.062363 | malo | 0.961147 | yes | no | HOLD_FOR_LIMITATION |
| depression | psychologist_1_3 | stability_pruned_subset | rf_precision_guard_v2 | none | balanced | 0.400000 | 0.723404 | 0.829268 | 0.934673 | 0.881971 | 0.772727 | 0.956674 | 0.789220 | 0.060188 | malo | 0.956674 | yes | no | HOLD_FOR_LIMITATION |
