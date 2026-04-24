# Hybrid RF Feature Strategy Report

## Feature set summary
| feature_set_id | avg_n_features | min_n_features | max_n_features | mode_domain_coverage | winner_count |
| --- | --- | --- | --- | --- | --- |
| precision_oriented_subset | 50.000000 | 24 | 81 | 30 | 8 |
| compact_robust_subset | 56.333333 | 27 | 91 | 30 | 3 |
| stability_pruned_subset | 62.500000 | 30 | 101 | 30 | 6 |
| balanced_subset | 68.666667 | 32 | 111 | 30 | 6 |
| top_importance_filtered | 87.333333 | 41 | 141 | 30 | 0 |
| full_eligible | 125.000000 | 59 | 202 | 30 | 7 |

## Winners by feature set
| mode | domain | winner_feature_set_id | n_features | selection_score |
| --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | precision_oriented_subset | 24 | 0.716770 |
| caregiver_1_3 | anxiety | compact_robust_subset | 27 | 0.829784 |
| caregiver_1_3 | conduct | full_eligible | 59 | 0.814582 |
| caregiver_1_3 | depression | precision_oriented_subset | 24 | 0.773908 |
| caregiver_1_3 | elimination | stability_pruned_subset | 30 | 0.843782 |
| caregiver_2_3 | adhd | stability_pruned_subset | 56 | 0.792533 |
| caregiver_2_3 | anxiety | precision_oriented_subset | 45 | 0.895506 |
| caregiver_2_3 | conduct | stability_pruned_subset | 56 | 0.940000 |
| caregiver_2_3 | depression | full_eligible | 113 | 0.849080 |
| caregiver_2_3 | elimination | precision_oriented_subset | 45 | 0.940000 |
| caregiver_full | adhd | compact_robust_subset | 76 | 0.800968 |
| caregiver_full | anxiety | balanced_subset | 93 | 0.887336 |
| caregiver_full | conduct | stability_pruned_subset | 84 | 0.940000 |
| caregiver_full | depression | precision_oriented_subset | 68 | 0.856879 |
| caregiver_full | elimination | precision_oriented_subset | 68 | 0.940000 |
| psychologist_1_3 | adhd | full_eligible | 71 | 0.716304 |
| psychologist_1_3 | anxiety | precision_oriented_subset | 28 | 0.863444 |
| psychologist_1_3 | conduct | full_eligible | 71 | 0.817016 |
| psychologist_1_3 | depression | balanced_subset | 39 | 0.786824 |
| psychologist_1_3 | elimination | full_eligible | 71 | 0.858700 |
| psychologist_2_3 | adhd | balanced_subset | 75 | 0.792288 |
| psychologist_2_3 | anxiety | compact_robust_subset | 61 | 0.890999 |
| psychologist_2_3 | conduct | stability_pruned_subset | 68 | 0.940000 |
| psychologist_2_3 | depression | stability_pruned_subset | 68 | 0.852379 |
| psychologist_2_3 | elimination | balanced_subset | 75 | 0.940000 |
| psychologist_full | adhd | full_eligible | 202 | 0.934849 |
| psychologist_full | anxiety | balanced_subset | 111 | 0.892640 |
| psychologist_full | conduct | balanced_subset | 111 | 0.940000 |
| psychologist_full | depression | full_eligible | 202 | 0.860468 |
| psychologist_full | elimination | precision_oriented_subset | 81 | 0.940000 |

## DSM5 vs clean-base
| mode | domain | hybrid_minus_clean_precision | hybrid_minus_clean_recall | hybrid_minus_clean_balanced_accuracy | hybrid_minus_clean_pr_auc | hybrid_minus_clean_brier | dsm5_only_balanced_accuracy | dsm5_material_gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| caregiver_full | adhd | 0.108583 | 0.340426 | 0.174099 | 0.153124 | -0.040589 | 0.955959 | yes |
| psychologist_2_3 | adhd | 0.162459 | 0.085106 | 0.082709 | 0.092369 | -0.033482 | 0.954663 | yes |
| psychologist_full | adhd | 0.451216 | 0.021277 | 0.122037 | 0.337389 | -0.079288 | 0.993523 | yes |
| caregiver_2_3 | anxiety | 0.021429 | 0.279070 | 0.139535 | 0.110941 | -0.035870 | 0.849575 | yes |
| caregiver_full | anxiety | 0.141111 | 0.058140 | 0.048105 | 0.054574 | -0.015132 | 0.961516 | yes |
| psychologist_2_3 | anxiety | 0.059075 | 0.069767 | 0.041229 | 0.053030 | -0.014181 | 0.958240 | yes |
| psychologist_full | anxiety | -0.025210 | 0.139535 | 0.065960 | 0.057556 | -0.014944 | 0.965323 | yes |
| caregiver_full | conduct | 0.101266 | 0.112500 | 0.081250 | 0.068796 | -0.058350 | 1.000000 | yes |
| psychologist_2_3 | conduct | 0.114458 | 0.081250 | 0.070312 | 0.081258 | -0.058004 | 1.000000 | yes |
| psychologist_full | conduct | 0.111111 | 0.100000 | 0.078125 | 0.061471 | -0.057367 | 1.000000 | yes |
| caregiver_2_3 | depression | 0.198598 | 0.158537 | 0.109419 | 0.307156 | -0.047609 | 0.916227 | yes |
| caregiver_full | depression | 0.202578 | 0.073171 | 0.070505 | 0.146351 | -0.031201 | 0.922325 | yes |
| psychologist_2_3 | depression | 0.141892 | 0.073171 | 0.051661 | 0.115743 | -0.023974 | 0.887547 | yes |
| psychologist_full | depression | 0.216490 | 0.048780 | 0.059566 | 0.178157 | -0.034718 | 0.917668 | yes |
| caregiver_full | elimination | 0.829617 | 0.423077 | 0.406632 | 0.834360 | -0.094734 | 1.000000 | yes |
| psychologist_2_3 | elimination | 0.823899 | 0.519231 | 0.414989 | 0.850247 | -0.095669 | 0.997664 | yes |
| psychologist_full | elimination | 0.808293 | 0.461538 | 0.386143 | 0.834378 | -0.093856 | 0.998832 | yes |
