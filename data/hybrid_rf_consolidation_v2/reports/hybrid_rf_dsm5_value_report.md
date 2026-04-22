# Hybrid RF DSM-5 Value Report

## Per-domain hybrid vs clean-base contribution
| domain | hybrid_minus_clean_precision | hybrid_minus_clean_recall | hybrid_minus_clean_balanced_accuracy | hybrid_minus_clean_pr_auc | hybrid_minus_clean_brier | dsm5_only_balanced_accuracy | dsm5_material_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | 0.390870 | 0.085106 | 0.121569 | 0.344149 | -0.075017 | 0.993523 | yes |
| anxiety | 0.088979 | 0.151163 | 0.084465 | 0.082267 | -0.030383 | 0.962785 | yes |
| conduct | 0.179885 | 0.075472 | 0.089138 | 0.079295 | -0.067913 | 0.995327 | yes |
| depression | 0.180556 | 0.182927 | 0.106539 | 0.259059 | -0.045594 | 0.858132 | yes |
| elimination | 0.837261 | 0.134615 | 0.418943 | 0.816873 | -0.089247 | 0.995327 | yes |

## Detailed experiment table
| domain | representative_mode | candidate_id | variant | n_features | status | holdout_precision | holdout_recall | holdout_specificity | holdout_balanced_accuracy | holdout_f1 | holdout_roc_auc | holdout_pr_auc | holdout_brier | delta_precision_vs_clean | delta_recall_vs_clean | delta_balanced_accuracy_vs_clean | delta_pr_auc_vs_clean | delta_brier_vs_clean | delta_precision_vs_hybrid_full | delta_recall_vs_hybrid_full | delta_balanced_accuracy_vs_hybrid_full | delta_pr_auc_vs_hybrid_full | delta_brier_vs_hybrid_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | adhd__psychologist_full | clean_base_only | 23 | ok | 0.557047 | 0.882979 | 0.829016 | 0.855997 | 0.683128 | 0.895574 | 0.600957 | 0.090476 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -0.390870 | -0.085106 | -0.121569 | -0.344149 | 0.075017 |
| adhd | psychologist_full | adhd__psychologist_full | dsm5_only | 88 | ok | 0.949495 | 1.000000 | 0.987047 | 0.993523 | 0.974093 | 0.996004 | 0.968555 | 0.009029 | 0.392448 | 0.117021 | 0.137526 | 0.367598 | -0.081447 | 0.001578 | 0.031915 | 0.015957 | 0.023449 | -0.006430 |
| adhd | psychologist_full | adhd__psychologist_full | hybrid_full | 111 | ok | 0.947917 | 0.968085 | 0.987047 | 0.977566 | 0.957895 | 0.980322 | 0.945106 | 0.015459 | 0.390870 | 0.085106 | 0.121569 | 0.344149 | -0.075017 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3 | clean_base_only | 8 | ok | 0.802326 | 0.802326 | 0.956853 | 0.879589 | 0.802326 | 0.960350 | 0.847425 | 0.051986 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -0.088979 | -0.151163 | -0.084465 | -0.082267 | 0.030383 |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3 | dsm5_only | 71 | ok | 0.881720 | 0.953488 | 0.972081 | 0.962785 | 0.916201 | 0.969322 | 0.902713 | 0.026145 | 0.079395 | 0.151163 | 0.083196 | 0.055288 | -0.025841 | -0.009584 | 0.000000 | -0.001269 | -0.026979 | 0.004542 |
| anxiety | caregiver_2_3 | anxiety__caregiver_2_3 | hybrid_full | 79 | ok | 0.891304 | 0.953488 | 0.974619 | 0.964054 | 0.921348 | 0.986734 | 0.929693 | 0.021603 | 0.088979 | 0.151163 | 0.084465 | 0.082267 | -0.030383 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| conduct | psychologist_2_3 | conduct__psychologist_2_3 | clean_base_only | 10 | ok | 0.807692 | 0.924528 | 0.890966 | 0.907747 | 0.862170 | 0.968975 | 0.920705 | 0.069199 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -0.179885 | -0.075472 | -0.089138 | -0.079295 | 0.067913 |
| conduct | psychologist_2_3 | conduct__psychologist_2_3 | dsm5_only | 44 | ok | 0.981481 | 1.000000 | 0.990654 | 0.995327 | 0.990654 | 1.000000 | 1.000000 | 0.001182 | 0.173789 | 0.075472 | 0.087580 | 0.079295 | -0.068017 | -0.006096 | 0.000000 | -0.001558 | 0.000000 | -0.000104 |
| conduct | psychologist_2_3 | conduct__psychologist_2_3 | hybrid_full | 54 | ok | 0.987578 | 1.000000 | 0.993769 | 0.996885 | 0.993750 | 1.000000 | 1.000000 | 0.001286 | 0.179885 | 0.075472 | 0.089138 | 0.079295 | -0.067913 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| depression | caregiver_2_3 | depression__caregiver_2_3 | clean_base_only | 6 | ok | 0.666667 | 0.560976 | 0.942211 | 0.751593 | 0.609272 | 0.858132 | 0.603897 | 0.097599 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -0.180556 | -0.182927 | -0.106539 | -0.259059 | 0.045594 |
| depression | caregiver_2_3 | depression__caregiver_2_3 | dsm5_only | 56 | ok | 0.847222 | 0.743902 | 0.972362 | 0.858132 | 0.792208 | 0.967950 | 0.852728 | 0.052871 | 0.180556 | 0.182927 | 0.106539 | 0.248831 | -0.044728 | 0.000000 | 0.000000 | 0.000000 | -0.010228 | 0.000866 |
| depression | caregiver_2_3 | depression__caregiver_2_3 | hybrid_full | 62 | ok | 0.847222 | 0.743902 | 0.972362 | 0.858132 | 0.792208 | 0.969604 | 0.862956 | 0.052005 | 0.180556 | 0.182927 | 0.106539 | 0.259059 | -0.045594 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| elimination | caregiver_2_3 | elimination__caregiver_2_3 | clean_base_only | 5 | ok | 0.124277 | 0.826923 | 0.292056 | 0.559490 | 0.216080 | 0.639446 | 0.157659 | 0.095248 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -0.837261 | -0.134615 | -0.418943 | -0.816873 | 0.089247 |
| elimination | caregiver_2_3 | elimination__caregiver_2_3 | dsm5_only | 40 | ok | 0.928571 | 1.000000 | 0.990654 | 0.995327 | 0.962963 | 0.998495 | 0.975532 | 0.004360 | 0.804294 | 0.173077 | 0.435838 | 0.817872 | -0.090888 | -0.032967 | 0.038462 | 0.016894 | 0.000999 | -0.001642 |
| elimination | caregiver_2_3 | elimination__caregiver_2_3 | hybrid_full | 45 | ok | 0.961538 | 0.961538 | 0.995327 | 0.978433 | 0.961538 | 0.998382 | 0.974532 | 0.006001 | 0.837261 | 0.134615 | 0.418943 | 0.816873 | -0.089247 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
