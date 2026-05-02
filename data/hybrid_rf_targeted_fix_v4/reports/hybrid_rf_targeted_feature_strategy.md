# Hybrid RF Targeted v4 - Feature Strategy

## Feature sets explored
| candidate_id | feature_set_id | n_features |
| --- | --- | --- |
| adhd__caregiver_1_3 | precision_oriented_subset | 24 |
| adhd__caregiver_1_3 | compact_robust_subset | 27 |
| adhd__caregiver_1_3 | stability_pruned_subset | 30 |
| adhd__caregiver_1_3 | balanced_subset | 32 |
| adhd__caregiver_1_3 | full_eligible | 59 |
| adhd__caregiver_2_3 | precision_oriented_subset | 45 |
| adhd__caregiver_2_3 | compact_robust_subset | 51 |
| adhd__caregiver_2_3 | stability_pruned_subset | 56 |
| adhd__caregiver_2_3 | balanced_subset | 62 |
| adhd__caregiver_2_3 | full_eligible | 113 |
| adhd__psychologist_1_3 | precision_oriented_subset | 28 |
| adhd__psychologist_1_3 | compact_robust_subset | 32 |
| adhd__psychologist_1_3 | stability_pruned_subset | 36 |
| adhd__psychologist_1_3 | balanced_subset | 39 |
| adhd__psychologist_1_3 | full_eligible | 71 |
| adhd__psychologist_2_3 | precision_oriented_subset | 54 |
| adhd__psychologist_2_3 | compact_robust_subset | 61 |
| adhd__psychologist_2_3 | stability_pruned_subset | 68 |
| adhd__psychologist_2_3 | balanced_subset | 75 |
| adhd__psychologist_2_3 | full_eligible | 136 |
| anxiety__caregiver_1_3 | precision_oriented_subset | 24 |
| anxiety__caregiver_1_3 | compact_robust_subset | 27 |
| anxiety__caregiver_1_3 | stability_pruned_subset | 30 |
| anxiety__caregiver_1_3 | balanced_subset | 32 |
| anxiety__caregiver_1_3 | full_eligible | 59 |
| anxiety__caregiver_2_3 | precision_oriented_subset | 45 |
| anxiety__caregiver_2_3 | compact_robust_subset | 51 |
| anxiety__caregiver_2_3 | stability_pruned_subset | 56 |
| anxiety__caregiver_2_3 | balanced_subset | 62 |
| anxiety__caregiver_2_3 | full_eligible | 113 |
| anxiety__caregiver_full | precision_oriented_subset | 68 |
| anxiety__caregiver_full | compact_robust_subset | 76 |
| anxiety__caregiver_full | stability_pruned_subset | 84 |
| anxiety__caregiver_full | balanced_subset | 93 |
| anxiety__caregiver_full | full_eligible | 169 |
| depression__caregiver_1_3 | precision_oriented_subset | 24 |
| depression__caregiver_1_3 | compact_robust_subset | 27 |
| depression__caregiver_1_3 | stability_pruned_subset | 30 |
| depression__caregiver_1_3 | balanced_subset | 32 |
| depression__caregiver_1_3 | full_eligible | 59 |
| depression__caregiver_2_3 | precision_oriented_subset | 45 |
| depression__caregiver_2_3 | compact_robust_subset | 51 |
| depression__caregiver_2_3 | stability_pruned_subset | 56 |
| depression__caregiver_2_3 | balanced_subset | 62 |
| depression__caregiver_2_3 | full_eligible | 113 |
| depression__caregiver_full | precision_oriented_subset | 68 |
| depression__caregiver_full | compact_robust_subset | 76 |
| depression__caregiver_full | stability_pruned_subset | 84 |
| depression__caregiver_full | balanced_subset | 93 |
| depression__caregiver_full | full_eligible | 169 |
| depression__psychologist_1_3 | precision_oriented_subset | 28 |
| depression__psychologist_1_3 | compact_robust_subset | 32 |
| depression__psychologist_1_3 | stability_pruned_subset | 36 |
| depression__psychologist_1_3 | balanced_subset | 39 |
| depression__psychologist_1_3 | full_eligible | 71 |
| depression__psychologist_2_3 | precision_oriented_subset | 54 |
| depression__psychologist_2_3 | compact_robust_subset | 61 |
| depression__psychologist_2_3 | stability_pruned_subset | 68 |
| depression__psychologist_2_3 | balanced_subset | 75 |
| depression__psychologist_2_3 | full_eligible | 136 |
| depression__psychologist_full | precision_oriented_subset | 81 |
| depression__psychologist_full | compact_robust_subset | 91 |
| depression__psychologist_full | stability_pruned_subset | 101 |
| depression__psychologist_full | balanced_subset | 111 |
| depression__psychologist_full | full_eligible | 202 |
| elimination__caregiver_1_3 | precision_oriented_subset | 24 |
| elimination__caregiver_1_3 | compact_robust_subset | 27 |
| elimination__caregiver_1_3 | stability_pruned_subset | 30 |
| elimination__caregiver_1_3 | balanced_subset | 32 |
| elimination__caregiver_1_3 | full_eligible | 59 |
| elimination__caregiver_2_3 | precision_oriented_subset | 45 |
| elimination__caregiver_2_3 | compact_robust_subset | 51 |
| elimination__caregiver_2_3 | stability_pruned_subset | 56 |
| elimination__caregiver_2_3 | balanced_subset | 62 |
| elimination__caregiver_2_3 | full_eligible | 113 |
| elimination__psychologist_1_3 | precision_oriented_subset | 28 |
| elimination__psychologist_1_3 | compact_robust_subset | 32 |
| elimination__psychologist_1_3 | stability_pruned_subset | 36 |
| elimination__psychologist_1_3 | balanced_subset | 39 |
| elimination__psychologist_1_3 | full_eligible | 71 |
| elimination__psychologist_2_3 | precision_oriented_subset | 54 |
| elimination__psychologist_2_3 | compact_robust_subset | 61 |
| elimination__psychologist_2_3 | stability_pruned_subset | 68 |
| elimination__psychologist_2_3 | balanced_subset | 75 |
| elimination__psychologist_2_3 | full_eligible | 136 |

## Ablation highlights
| candidate_id | ablation_type | k | delta_ba_vs_winner | delta_pr_auc_vs_winner | dominant_feature_share |
| --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | drop_topk | 1 | -0.017997 | 0.013459 | 0.361840 |
| adhd__caregiver_1_3 | drop_topk | 3 | -0.020863 | -0.019422 | 0.361840 |
| adhd__caregiver_1_3 | drop_topk | 5 | -0.022296 | 0.003812 | 0.361840 |
| adhd__caregiver_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.361840 |
| adhd__caregiver_2_3 | drop_topk | 1 | -0.017391 | 0.039866 | 0.387410 |
| adhd__caregiver_2_3 | drop_topk | 3 | -0.087835 | -0.091431 | 0.387410 |
| adhd__caregiver_2_3 | drop_topk | 5 | -0.071602 | -0.097624 | 0.387410 |
| adhd__caregiver_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.387410 |
| adhd__psychologist_1_3 | drop_topk | 1 | -0.008461 | 0.025449 | 0.109711 |
| adhd__psychologist_1_3 | drop_topk | 3 | -0.022848 | -0.001432 | 0.109711 |
| adhd__psychologist_1_3 | drop_topk | 5 | -0.048286 | 0.005753 | 0.109711 |
| adhd__psychologist_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.109711 |
| adhd__psychologist_2_3 | drop_topk | 1 | -0.002591 | 0.020158 | 0.322545 |
| adhd__psychologist_2_3 | drop_topk | 3 | -0.063003 | -0.094118 | 0.322545 |
| adhd__psychologist_2_3 | drop_topk | 5 | -0.054542 | -0.083111 | 0.322545 |
| adhd__psychologist_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.322545 |
| anxiety__caregiver_1_3 | drop_topk | 1 | -0.004545 | -0.010967 | 0.125174 |
| anxiety__caregiver_1_3 | drop_topk | 3 | 0.011097 | -0.040455 | 0.125174 |
| anxiety__caregiver_1_3 | drop_topk | 5 | 0.004752 | -0.090483 | 0.125174 |
| anxiety__caregiver_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.125174 |
| anxiety__caregiver_2_3 | drop_topk | 1 | -0.060678 | -0.032891 | 0.454109 |
| anxiety__caregiver_2_3 | drop_topk | 3 | -0.044505 | -0.049086 | 0.454109 |
| anxiety__caregiver_2_3 | drop_topk | 5 | -0.050319 | -0.059270 | 0.454109 |
| anxiety__caregiver_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.454109 |
| anxiety__caregiver_full | drop_topk | 1 | 0.000000 | -0.009721 | 0.420102 |
| anxiety__caregiver_full | drop_topk | 3 | -0.041967 | -0.038160 | 0.420102 |
| anxiety__caregiver_full | drop_topk | 5 | -0.041967 | -0.058848 | 0.420102 |
| anxiety__caregiver_full | winner_top_features | 0 | 0.000000 | 0.000000 | 0.420102 |
| depression__caregiver_1_3 | drop_topk | 1 | 0.003401 | 0.014309 | 0.172867 |
| depression__caregiver_1_3 | drop_topk | 3 | -0.013635 | -0.018851 | 0.172867 |
| depression__caregiver_1_3 | drop_topk | 5 | -0.001624 | -0.029824 | 0.172867 |
| depression__caregiver_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.172867 |
| depression__caregiver_2_3 | drop_topk | 1 | -0.034257 | -0.035107 | 0.482209 |
| depression__caregiver_2_3 | drop_topk | 3 | -0.046452 | -0.096649 | 0.482209 |
| depression__caregiver_2_3 | drop_topk | 5 | -0.029599 | -0.079317 | 0.482209 |
| depression__caregiver_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.482209 |
| depression__caregiver_full | drop_topk | 1 | -0.039282 | -0.081776 | 0.464240 |
| depression__caregiver_full | drop_topk | 3 | -0.031223 | -0.120936 | 0.464240 |
| depression__caregiver_full | drop_topk | 5 | -0.049332 | -0.111873 | 0.464240 |
| depression__caregiver_full | winner_top_features | 0 | 0.000000 | 0.000000 | 0.464240 |
| depression__psychologist_1_3 | drop_topk | 1 | 0.007170 | -0.005535 | 0.175334 |
| depression__psychologist_1_3 | drop_topk | 3 | 0.000889 | -0.022280 | 0.175334 |
| depression__psychologist_1_3 | drop_topk | 5 | -0.031928 | -0.020752 | 0.175334 |
| depression__psychologist_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.175334 |
| depression__psychologist_2_3 | drop_topk | 1 | -0.013635 | -0.015460 | 0.464046 |
| depression__psychologist_2_3 | drop_topk | 3 | -0.039649 | -0.109831 | 0.464046 |
| depression__psychologist_2_3 | drop_topk | 5 | -0.070842 | -0.105526 | 0.464046 |
| depression__psychologist_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.464046 |
| depression__psychologist_full | drop_topk | 1 | -0.020805 | -0.031657 | 0.470854 |
| depression__psychologist_full | drop_topk | 3 | -0.078012 | -0.118585 | 0.470854 |
| depression__psychologist_full | drop_topk | 5 | -0.036064 | -0.126597 | 0.470854 |
| depression__psychologist_full | winner_top_features | 0 | 0.000000 | 0.000000 | 0.470854 |
| elimination__caregiver_1_3 | drop_topk | 1 | -0.409957 | -0.692477 | 0.730687 |
| elimination__caregiver_1_3 | drop_topk | 3 | -0.424425 | -0.832370 | 0.730687 |
| elimination__caregiver_1_3 | drop_topk | 5 | -0.388839 | -0.812005 | 0.730687 |
| elimination__caregiver_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.730687 |
| elimination__caregiver_2_3 | drop_topk | 1 | -0.025701 | -0.065189 | 0.370707 |
| elimination__caregiver_2_3 | drop_topk | 3 | -0.030374 | -0.304900 | 0.370707 |
| elimination__caregiver_2_3 | drop_topk | 5 | -0.342559 | -0.811963 | 0.370707 |
| elimination__caregiver_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.370707 |
| elimination__psychologist_1_3 | drop_topk | 1 | -0.317577 | -0.686267 | 0.452252 |
| elimination__psychologist_1_3 | drop_topk | 3 | -0.381380 | -0.758604 | 0.452252 |
| elimination__psychologist_1_3 | drop_topk | 5 | -0.381380 | -0.757911 | 0.452252 |
| elimination__psychologist_1_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.452252 |
| elimination__psychologist_2_3 | drop_topk | 1 | -0.024533 | -0.070849 | 0.511843 |
| elimination__psychologist_2_3 | drop_topk | 3 | -0.056884 | -0.360165 | 0.511843 |
| elimination__psychologist_2_3 | drop_topk | 5 | -0.421100 | -0.838761 | 0.511843 |
| elimination__psychologist_2_3 | winner_top_features | 0 | 0.000000 | 0.000000 | 0.511843 |
