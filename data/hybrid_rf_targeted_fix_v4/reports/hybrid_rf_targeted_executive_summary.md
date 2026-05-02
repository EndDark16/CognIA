# Hybrid RF Targeted v4 - Executive Summary

## Final decisions by candidate
| candidate_id | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | material_improvement_vs_v3 | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 | no | HOLD_FOR_FINAL_LIMITATION |
| adhd__caregiver_2_3 | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 | no | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_1_3 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 | no | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_2_3 | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 | no | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_1_3 | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 | yes | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_2_3 | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 | no | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_full | 0.916667 | 0.895349 | 0.938791 | 0.936379 | 0.030046 | no | REJECT_AS_PRIMARY |
| depression__caregiver_1_3 | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 | no | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_2_3 | 0.800000 | 0.878049 | 0.916411 | 0.882349 | 0.044623 | yes | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_full | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 | no | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_1_3 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 | no | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_2_3 | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 | no | PROMOTE_WITH_CAVEAT |
| depression__psychologist_full | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 | no | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_1_3 | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 | yes | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 | no | CEILING_CONFIRMED_NO_MATERIAL_GAIN |
| elimination__psychologist_1_3 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 | no | HOLD_FOR_FINAL_LIMITATION |
| elimination__psychologist_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 | no | CEILING_CONFIRMED_NO_MATERIAL_GAIN |

## 2/3 vs full (targeted comparisons)
| domain | role | ba_full_minus_2_3 | pr_auc_full_minus_2_3 | precision_full_minus_2_3 | preferred_mode_operational |
| --- | --- | --- | --- | --- | --- |
| anxiety | caregiver | -0.003807 | -0.003796 | -0.033951 | caregiver_2_3 |
| depression | caregiver | 0.012195 | 0.029237 | 0.004348 | caregiver_full |
| depression | psychologist | 0.021694 | 0.068243 | -0.066310 | psychologist_full |

## DSM-5 contribution snapshot
| candidate_id | variant | status | n_features | precision | recall | balanced_accuracy | pr_auc | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| adhd__caregiver_1_3 | dsm5_only | ok | 24 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 |
| adhd__caregiver_1_3 | hybrid_full | ok | 24 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 |
| adhd__caregiver_2_3 | clean_base_only | insufficient_features | 1 |  |  |  |  |  |
| adhd__caregiver_2_3 | dsm5_only | ok | 55 | 0.726562 | 0.989362 | 0.949344 | 0.754642 | 0.056239 |
| adhd__caregiver_2_3 | hybrid_full | ok | 56 | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 |
| adhd__psychologist_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| adhd__psychologist_1_3 | dsm5_only | ok | 71 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 |
| adhd__psychologist_1_3 | hybrid_full | ok | 71 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 |
| adhd__psychologist_2_3 | clean_base_only | ok | 14 | 0.585714 | 0.872340 | 0.861041 | 0.603575 | 0.098616 |
| adhd__psychologist_2_3 | dsm5_only | ok | 61 | 0.717557 | 1.000000 | 0.952073 | 0.736479 | 0.057729 |
| adhd__psychologist_2_3 | hybrid_full | ok | 75 | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 |
| anxiety__caregiver_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| anxiety__caregiver_1_3 | dsm5_only | ok | 59 | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 |
| anxiety__caregiver_1_3 | hybrid_full | ok | 59 | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 |
| anxiety__caregiver_2_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| anxiety__caregiver_2_3 | dsm5_only | ok | 45 | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 |
| anxiety__caregiver_2_3 | hybrid_full | ok | 45 | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 |
| anxiety__caregiver_full | clean_base_only | ok | 20 | 0.902778 | 0.755814 | 0.869024 | 0.875024 | 0.042404 |
| anxiety__caregiver_full | dsm5_only | ok | 64 | 0.921348 | 0.953488 | 0.967861 | 0.925249 | 0.022348 |
| anxiety__caregiver_full | hybrid_full | ok | 84 | 0.916667 | 0.895349 | 0.938791 | 0.936379 | 0.030046 |
| depression__caregiver_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| depression__caregiver_1_3 | dsm5_only | ok | 59 | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 |
| depression__caregiver_1_3 | hybrid_full | ok | 59 | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 |
| depression__caregiver_2_3 | clean_base_only | insufficient_features | 2 |  |  |  |  |  |
| depression__caregiver_2_3 | dsm5_only | ok | 60 | 0.829268 | 0.829268 | 0.897046 | 0.875443 | 0.043562 |
| depression__caregiver_2_3 | hybrid_full | ok | 62 | 0.800000 | 0.878049 | 0.916411 | 0.882349 | 0.044623 |
| depression__caregiver_full | clean_base_only | ok | 15 | 0.644231 | 0.817073 | 0.862054 | 0.753381 | 0.070404 |
| depression__caregiver_full | dsm5_only | ok | 53 | 0.800000 | 0.878049 | 0.916411 | 0.894162 | 0.038911 |
| depression__caregiver_full | hybrid_full | ok | 68 | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 |
| depression__psychologist_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| depression__psychologist_1_3 | dsm5_only | ok | 39 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 |
| depression__psychologist_1_3 | hybrid_full | ok | 39 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 |
| depression__psychologist_2_3 | clean_base_only | ok | 18 | 0.670103 | 0.792683 | 0.856140 | 0.770783 | 0.069229 |
| depression__psychologist_2_3 | dsm5_only | ok | 50 | 0.915493 | 0.792683 | 0.888804 | 0.887749 | 0.041642 |
| depression__psychologist_2_3 | hybrid_full | ok | 68 | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 |
| depression__psychologist_full | clean_base_only | ok | 30 | 0.681319 | 0.756098 | 0.841617 | 0.781174 | 0.067431 |
| depression__psychologist_full | dsm5_only | ok | 172 | 0.876543 | 0.865854 | 0.920364 | 0.950566 | 0.032774 |
| depression__psychologist_full | hybrid_full | ok | 202 | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 |
| elimination__caregiver_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| elimination__caregiver_1_3 | dsm5_only | ok | 27 | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 |
| elimination__caregiver_1_3 | hybrid_full | ok | 27 | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 |
| elimination__caregiver_2_3 | clean_base_only | insufficient_features | 1 |  |  |  |  |  |
| elimination__caregiver_2_3 | dsm5_only | ok | 44 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000008 |
| elimination__caregiver_2_3 | hybrid_full | ok | 45 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 |
| elimination__psychologist_1_3 | clean_base_only | insufficient_features | 0 |  |  |  |  |  |
| elimination__psychologist_1_3 | dsm5_only | ok | 71 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 |
| elimination__psychologist_1_3 | hybrid_full | ok | 71 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 |
| elimination__psychologist_2_3 | clean_base_only | ok | 19 | 0.137143 | 0.461538 | 0.554367 | 0.168693 | 0.095591 |
| elimination__psychologist_2_3 | dsm5_only | ok | 42 | 0.962963 | 1.000000 | 0.997664 | 1.000000 | 0.001002 |
| elimination__psychologist_2_3 | hybrid_full | ok | 61 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 |

- overfitting_evidence: yes
- good_generalization_evidence: yes
- fits_total: 980
- trees_total: 311700
