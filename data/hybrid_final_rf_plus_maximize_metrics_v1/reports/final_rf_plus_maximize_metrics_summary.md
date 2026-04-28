# Hybrid Final RF Plus Maximize Metrics v1

Generated: `2026-04-28T00:47:08.400280+00:00`

## Scope
- RF-based final campaign over 30 active v11 slots.
- RandomForestClassifier remains the required base estimator for every champion.
- Same feature_list_pipe per slot; no questionnaire/question text changes.
- Threshold selected on validation; holdout used only for final reporting.

## Core Results
- trials: `5400`
- final_active_rows: `30`
- rf_only_ok: `yes`
- remaining_guardrail_violations: `0`
- policy_violations: `0`
- unchanged_feature_contract_slots: `30/30`

## Final Class Summary
| final_operational_class | confidence_band | n |
| --- | --- | --- |
| ACTIVE_HIGH_CONFIDENCE | high | 2 |
| ACTIVE_LIMITED_USE | limited | 15 |
| ACTIVE_MODERATE_CONFIDENCE | moderate | 13 |

## v11 vs v12 RF
| domain | role | mode | old_model_family | old_f1 | new_f1 | delta_f1 | old_recall | new_recall | old_precision | new_precision | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver | caregiver_1_3 | rf | 0.809302 | 0.811321 | 0.002018 | 0.925532 | 0.914894 | 0.719008 | 0.728814 | best_guard_compliant_rf_based_candidate |
| adhd | caregiver | caregiver_2_3 | rf | 0.798206 | 0.800000 | 0.001794 | 0.946809 | 0.914894 | 0.689922 | 0.710744 | best_guard_compliant_rf_based_candidate |
| adhd | caregiver | caregiver_full | rf | 0.803653 | 0.805556 | 0.001903 | 0.936170 | 0.925532 | 0.704000 | 0.713115 | best_guard_compliant_rf_based_candidate |
| adhd | psychologist | psychologist_1_3 | rf | 0.790909 | 0.790909 | 0.000000 | 0.925532 | 0.925532 | 0.690476 | 0.690476 | f1_matched_with_recall_gain |
| adhd | psychologist | psychologist_2_3 | rf | 0.842105 | 0.842105 | 0.000000 | 0.851064 | 0.851064 | 0.833333 | 0.833333 | f1_matched_with_recall_gain |
| adhd | psychologist | psychologist_full | rf | 0.807512 | 0.810000 | 0.002488 | 0.914894 | 0.861702 | 0.722689 | 0.764151 | best_guard_compliant_rf_based_candidate |
| anxiety | caregiver | caregiver_1_3 | rf | 0.870056 | 0.870588 | 0.000532 | 0.895349 | 0.860465 | 0.846154 | 0.880952 | best_guard_compliant_rf_based_candidate |
| anxiety | caregiver | caregiver_2_3 | rf | 0.840237 | 0.840237 | 0.000000 | 0.825581 | 0.825581 | 0.855422 | 0.855422 | f1_matched_with_recall_gain |
| anxiety | caregiver | caregiver_full | rf | 0.818713 | 0.818713 | 0.000000 | 0.813953 | 0.813953 | 0.823529 | 0.823529 | f1_matched_with_recall_gain |
| anxiety | psychologist | psychologist_1_3 | rf | 0.835294 | 0.835294 | 0.000000 | 0.825581 | 0.825581 | 0.845238 | 0.845238 | f1_matched_with_recall_gain |
| anxiety | psychologist | psychologist_2_3 | rf | 0.837209 | 0.837209 | 0.000000 | 0.837209 | 0.837209 | 0.837209 | 0.837209 | f1_matched_with_recall_gain |
| anxiety | psychologist | psychologist_full | rf | 0.766234 | 0.766234 | 0.000000 | 0.686047 | 0.686047 | 0.867647 | 0.867647 | f1_matched_with_recall_gain |
| conduct | caregiver | caregiver_1_3 | rf | 0.890208 | 0.893617 | 0.003409 | 0.937500 | 0.918750 | 0.847458 | 0.869822 | best_guard_compliant_rf_based_candidate |
| conduct | caregiver | caregiver_2_3 | rf | 0.866279 | 0.866279 | 0.000000 | 0.931250 | 0.931250 | 0.809783 | 0.809783 | f1_matched_with_recall_gain |
| conduct | caregiver | caregiver_full | rf | 0.870871 | 0.876543 | 0.005672 | 0.906250 | 0.887500 | 0.838150 | 0.865854 | f1_improved_by_final_rf_plus |
| conduct | psychologist | psychologist_1_3 | rf | 0.888235 | 0.890966 | 0.002730 | 0.943750 | 0.893750 | 0.838889 | 0.888199 | best_guard_compliant_rf_based_candidate |
| conduct | psychologist | psychologist_2_3 | rf | 0.876543 | 0.876543 | 0.000000 | 0.887500 | 0.887500 | 0.865854 | 0.865854 | f1_matched_with_recall_gain |
| conduct | psychologist | psychologist_full | rf | 0.873846 | 0.874618 | 0.000772 | 0.887500 | 0.893750 | 0.860606 | 0.856287 | f1_matched_with_recall_gain |
| depression | caregiver | caregiver_1_3 | rf | 0.848837 | 0.863636 | 0.014799 | 0.890244 | 0.926829 | 0.811111 | 0.808511 | f1_improved_by_final_rf_plus |
| depression | caregiver | caregiver_2_3 | rf | 0.847458 | 0.862275 | 0.014818 | 0.914634 | 0.878049 | 0.789474 | 0.847059 | f1_improved_by_final_rf_plus |
| depression | caregiver | caregiver_full | rf | 0.842105 | 0.842105 | 0.000000 | 0.878049 | 0.878049 | 0.808989 | 0.808989 | f1_matched_with_recall_gain |
| depression | psychologist | psychologist_1_3 | rf | 0.855491 | 0.865169 | 0.009677 | 0.902439 | 0.939024 | 0.813187 | 0.802083 | f1_improved_by_final_rf_plus |
| depression | psychologist | psychologist_2_3 | rf | 0.860465 | 0.867470 | 0.007005 | 0.902439 | 0.878049 | 0.822222 | 0.857143 | f1_improved_by_final_rf_plus |
| depression | psychologist | psychologist_full | rf | 0.834286 | 0.834286 | 0.000000 | 0.890244 | 0.890244 | 0.784946 | 0.784946 | f1_matched_with_recall_gain |
| elimination | caregiver | caregiver_1_3 | rf | 0.836364 | 0.836364 | 0.000000 | 0.884615 | 0.884615 | 0.793103 | 0.793103 | f1_matched_with_recall_gain |
| elimination | caregiver | caregiver_2_3 | rf | 0.821429 | 0.844037 | 0.022608 | 0.884615 | 0.884615 | 0.766667 | 0.807018 | f1_improved_by_final_rf_plus |
| elimination | caregiver | caregiver_full | rf | 0.833333 | 0.840336 | 0.007003 | 0.961538 | 0.961538 | 0.735294 | 0.746269 | f1_improved_by_final_rf_plus |
| elimination | psychologist | psychologist_1_3 | rf | 0.813559 | 0.833333 | 0.019774 | 0.923077 | 0.961538 | 0.727273 | 0.735294 | f1_improved_by_final_rf_plus |
| elimination | psychologist | psychologist_2_3 | rf | 0.837607 | 0.847458 | 0.009851 | 0.942308 | 0.961538 | 0.753846 | 0.757576 | f1_improved_by_final_rf_plus |
| elimination | psychologist | psychologist_full | rf | 0.840336 | 0.833333 | -0.007003 | 0.961538 | 0.961538 | 0.746269 | 0.735294 | anti_clone_conservative_tradeoff |

## Elimination Anti-Clone
| domain | role_a | mode_a | role_b | mode_b | threshold_a | threshold_b | probability_correlation | prediction_agreement | identical_predictions | near_metric_clone_flag | max_metric_abs_delta | feature_jaccard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elimination | caregiver | caregiver_1_3 | caregiver | caregiver_2_3 | 0.720000 | 0.680000 | 0.991233 | 0.981250 | no | no | 0.040000 | 0.375000 |
| elimination | caregiver | caregiver_1_3 | caregiver | caregiver_full | 0.720000 | 0.840000 | 0.949212 | 0.981250 | no | no | 0.120000 | 0.181818 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_1_3 | 0.720000 | 0.680000 | 0.945835 | 0.979167 | no | no | 0.076923 | 0.285714 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_2_3 | 0.720000 | 0.820000 | 0.946883 | 0.979167 | no | no | 0.100000 | 0.181818 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_full | 0.720000 | 0.410000 | 0.957060 | 0.979167 | no | no | 0.310000 | 0.142857 |
| elimination | caregiver | caregiver_2_3 | caregiver | caregiver_full | 0.680000 | 0.840000 | 0.953404 | 0.979167 | no | no | 0.160000 | 0.600000 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_1_3 | 0.680000 | 0.680000 | 0.951005 | 0.977083 | no | no | 0.076923 | 0.714286 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_2_3 | 0.680000 | 0.820000 | 0.951619 | 0.977083 | no | no | 0.140000 | 0.600000 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_full | 0.680000 | 0.410000 | 0.964510 | 0.977083 | no | no | 0.270000 | 0.461538 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_1_3 | 0.840000 | 0.680000 | 0.996801 | 0.997917 | no | no | 0.160000 | 0.555556 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_2_3 | 0.840000 | 0.820000 | 0.999160 | 0.997917 | no | no | 0.020000 | 0.636364 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_full | 0.840000 | 0.410000 | 0.995033 | 0.997917 | no | no | 0.430000 | 0.750000 |
| elimination | psychologist | psychologist_1_3 | psychologist | psychologist_2_3 | 0.680000 | 0.820000 | 0.995319 | 0.995833 | no | no | 0.140000 | 0.555556 |
| elimination | psychologist | psychologist_1_3 | psychologist | psychologist_full | 0.680000 | 0.410000 | 0.994780 | 0.995833 | no | no | 0.270000 | 0.416667 |
| elimination | psychologist | psychologist_2_3 | psychologist | psychologist_full | 0.820000 | 0.410000 | 0.994046 | 0.995833 | no | no | 0.410000 | 0.750000 |
