# Hybrid RF Max Real Metrics v1

Generated: `2026-04-27T05:19:18.082150+00:00`

## Scope
- RF-only campaign over 30 active v10 slots.
- Same feature_list_pipe per slot; no questionnaire/question text changes.
- Threshold selected on validation; holdout used only for final reporting.

## Core Results
- trials: `2160`
- final_active_rows: `30`
- rf_only_ok: `yes`
- remaining_guardrail_violations: `0`
- policy_violations: `0`
- unchanged_feature_contract_slots: `30/30`

## Final Class Summary
| final_operational_class | confidence_band | n |
| --- | --- | --- |
| ACTIVE_LIMITED_USE | limited | 15 |
| ACTIVE_MODERATE_CONFIDENCE | moderate | 15 |

## Old vs RF
| domain | role | mode | old_model_family | old_f1 | new_f1 | delta_f1 | old_recall | new_recall | old_precision | new_precision | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver | caregiver_1_3 | rf | 0.801843 | 0.809302 | 0.007459 | 0.925532 | 0.925532 | 0.707317 | 0.719008 | rf_improves_or_matches_previous_balance |
| adhd | caregiver | caregiver_2_3 | rf | 0.809091 | 0.798206 | -0.010885 | 0.946809 | 0.946809 | 0.706349 | 0.689922 | rf_only_mandate_best_valid_rf_even_if_regression |
| adhd | caregiver | caregiver_full | rf | 0.777778 | 0.803653 | 0.025875 | 0.819149 | 0.936170 | 0.740385 | 0.704000 | rf_improves_or_matches_previous_balance |
| adhd | psychologist | psychologist_1_3 | logreg | 0.765766 | 0.790909 | 0.025143 | 0.904255 | 0.925532 | 0.664062 | 0.690476 | rf_improves_or_matches_previous_balance |
| adhd | psychologist | psychologist_2_3 | logreg | 0.824121 | 0.842105 | 0.017985 | 0.872340 | 0.851064 | 0.780952 | 0.833333 | rf_improves_or_matches_previous_balance |
| adhd | psychologist | psychologist_full | logreg | 0.783410 | 0.807512 | 0.024102 | 0.904255 | 0.914894 | 0.691057 | 0.722689 | rf_improves_or_matches_previous_balance |
| anxiety | caregiver | caregiver_1_3 | rf | 0.855422 | 0.870056 | 0.014635 | 0.825581 | 0.895349 | 0.887500 | 0.846154 | rf_improves_or_matches_previous_balance |
| anxiety | caregiver | caregiver_2_3 | logreg | 0.867470 | 0.840237 | -0.027233 | 0.837209 | 0.825581 | 0.900000 | 0.855422 | rf_only_mandate_best_valid_rf_even_if_regression |
| anxiety | caregiver | caregiver_full | logreg | 0.843931 | 0.818713 | -0.025217 | 0.848837 | 0.813953 | 0.839080 | 0.823529 | rf_only_mandate_best_valid_rf_even_if_regression |
| anxiety | psychologist | psychologist_1_3 | logreg | 0.825397 | 0.835294 | 0.009897 | 0.906977 | 0.825581 | 0.757282 | 0.845238 | rf_only_mandate_best_valid_rf_even_if_regression |
| anxiety | psychologist | psychologist_2_3 | logreg | 0.875740 | 0.837209 | -0.038530 | 0.860465 | 0.837209 | 0.891566 | 0.837209 | rf_only_mandate_best_valid_rf_even_if_regression |
| anxiety | psychologist | psychologist_full | hgb | 0.840909 | 0.766234 | -0.074675 | 0.860465 | 0.686047 | 0.822222 | 0.867647 | rf_only_mandate_best_valid_rf_even_if_regression |
| conduct | caregiver | caregiver_1_3 | rf | 0.881789 | 0.890208 | 0.008419 | 0.862500 | 0.937500 | 0.901961 | 0.847458 | rf_improves_or_matches_previous_balance |
| conduct | caregiver | caregiver_2_3 | logreg | 0.887574 | 0.866279 | -0.021295 | 0.937500 | 0.931250 | 0.842697 | 0.809783 | rf_only_mandate_best_valid_rf_even_if_regression |
| conduct | caregiver | caregiver_full | rf | 0.859649 | 0.870871 | 0.011222 | 0.918750 | 0.906250 | 0.807692 | 0.838150 | rf_improves_or_matches_previous_balance |
| conduct | psychologist | psychologist_1_3 | rf | 0.858086 | 0.888235 | 0.030149 | 0.812500 | 0.943750 | 0.909091 | 0.838889 | rf_improves_or_matches_previous_balance |
| conduct | psychologist | psychologist_2_3 | rf | 0.873418 | 0.876543 | 0.003125 | 0.862500 | 0.887500 | 0.884615 | 0.865854 | rf_improves_or_matches_previous_balance |
| conduct | psychologist | psychologist_full | rf | 0.876877 | 0.873846 | -0.003031 | 0.912500 | 0.887500 | 0.843931 | 0.860606 | rf_only_mandate_best_valid_rf_even_if_regression |
| depression | caregiver | caregiver_1_3 | rf | 0.845714 | 0.848837 | 0.003123 | 0.902439 | 0.890244 | 0.795699 | 0.811111 | rf_improves_or_matches_previous_balance |
| depression | caregiver | caregiver_2_3 | extra_trees | 0.852273 | 0.847458 | -0.004815 | 0.914634 | 0.914634 | 0.797872 | 0.789474 | rf_recall_gain_with_small_f1_cost |
| depression | caregiver | caregiver_full | hgb | 0.837209 | 0.842105 | 0.004896 | 0.878049 | 0.878049 | 0.800000 | 0.808989 | rf_improves_or_matches_previous_balance |
| depression | psychologist | psychologist_1_3 | rf | 0.846626 | 0.855491 | 0.008866 | 0.841463 | 0.902439 | 0.851852 | 0.813187 | rf_improves_or_matches_previous_balance |
| depression | psychologist | psychologist_2_3 | extra_trees | 0.849162 | 0.860465 | 0.011303 | 0.926829 | 0.902439 | 0.783505 | 0.822222 | rf_only_mandate_best_valid_rf_even_if_regression |
| depression | psychologist | psychologist_full | hgb | 0.787879 | 0.834286 | 0.046407 | 0.792683 | 0.890244 | 0.783133 | 0.784946 | rf_improves_or_matches_previous_balance |
| elimination | caregiver | caregiver_1_3 | rf | 0.851852 | 0.836364 | -0.015488 | 0.884615 | 0.884615 | 0.821429 | 0.793103 | rf_only_mandate_best_valid_rf_even_if_regression |
| elimination | caregiver | caregiver_2_3 | hgb | 0.844037 | 0.821429 | -0.022608 | 0.884615 | 0.884615 | 0.807018 | 0.766667 | rf_only_mandate_best_valid_rf_even_if_regression |
| elimination | caregiver | caregiver_full | extra_trees | 0.837607 | 0.833333 | -0.004274 | 0.942308 | 0.961538 | 0.753846 | 0.735294 | rf_improves_or_matches_previous_balance |
| elimination | psychologist | psychologist_1_3 | hgb | 0.821429 | 0.813559 | -0.007869 | 0.884615 | 0.923077 | 0.766667 | 0.727273 | rf_improves_or_matches_previous_balance |
| elimination | psychologist | psychologist_2_3 | rf | 0.818182 | 0.837607 | 0.019425 | 0.865385 | 0.942308 | 0.775862 | 0.753846 | rf_improves_or_matches_previous_balance |
| elimination | psychologist | psychologist_full | extra_trees | 0.854701 | 0.840336 | -0.014365 | 0.961538 | 0.961538 | 0.769231 | 0.746269 | rf_only_mandate_best_valid_rf_even_if_regression |

## Elimination Anti-Clone
| domain | role_a | mode_a | role_b | mode_b | threshold_a | threshold_b | probability_correlation | prediction_agreement | identical_predictions | near_metric_clone_flag | max_metric_abs_delta | feature_jaccard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elimination | caregiver | caregiver_1_3 | caregiver | caregiver_2_3 | 0.720000 | 0.580000 | 0.976092 | 0.975000 | no | no | 0.140000 | 0.375000 |
| elimination | caregiver | caregiver_1_3 | caregiver | caregiver_full | 0.720000 | 0.620000 | 0.946072 | 0.979167 | no | no | 0.100000 | 0.181818 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_1_3 | 0.720000 | 0.762991 | 0.948902 | 0.979167 | no | no | 0.065831 | 0.285714 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_2_3 | 0.720000 | 0.880000 | 0.944520 | 0.977083 | no | no | 0.160000 | 0.181818 |
| elimination | caregiver | caregiver_1_3 | psychologist | psychologist_full | 0.720000 | 0.680000 | 0.947060 | 0.981250 | no | no | 0.076923 | 0.142857 |
| elimination | caregiver | caregiver_2_3 | caregiver | caregiver_full | 0.580000 | 0.620000 | 0.943266 | 0.979167 | no | no | 0.076923 | 0.600000 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_1_3 | 0.580000 | 0.762991 | 0.942417 | 0.983333 | no | no | 0.182991 | 0.714286 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_2_3 | 0.580000 | 0.880000 | 0.940825 | 0.981250 | no | no | 0.300000 | 0.600000 |
| elimination | caregiver | caregiver_2_3 | psychologist | psychologist_full | 0.580000 | 0.680000 | 0.945573 | 0.981250 | no | no | 0.100000 | 0.461538 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_1_3 | 0.620000 | 0.762991 | 0.992972 | 0.995833 | no | no | 0.142991 | 0.555556 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_2_3 | 0.620000 | 0.880000 | 0.996083 | 0.993750 | no | no | 0.260000 | 0.636364 |
| elimination | caregiver | caregiver_full | psychologist | psychologist_full | 0.620000 | 0.680000 | 0.996253 | 0.997917 | no | no | 0.060000 | 0.750000 |
| elimination | psychologist | psychologist_1_3 | psychologist | psychologist_2_3 | 0.762991 | 0.880000 | 0.992859 | 0.993750 | no | no | 0.117009 | 0.555556 |
| elimination | psychologist | psychologist_1_3 | psychologist | psychologist_full | 0.762991 | 0.680000 | 0.993856 | 0.993750 | no | no | 0.082991 | 0.416667 |
| elimination | psychologist | psychologist_2_3 | psychologist | psychologist_full | 0.880000 | 0.680000 | 0.993689 | 0.995833 | no | no | 0.200000 | 0.750000 |
