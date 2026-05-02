# Hybrid RF Targeted v4 - Generalization Audit

## Holdout metrics and stability
| candidate_id | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | seed_ba_std | seed_precision_std | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 | 0.002310 | 0.001938 | HOLD_FOR_FINAL_LIMITATION |
| adhd__caregiver_2_3 | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 | 0.005093 | 0.002079 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_1_3 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 | 0.003851 | 0.001757 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_2_3 | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 | 0.004739 | 0.004132 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_1_3 | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 | 0.008944 | 0.006243 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_2_3 | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 | 0.056243 | 0.007604 | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_full | 0.916667 | 0.895349 | 0.938791 | 0.936379 | 0.030046 | 0.000000 | 0.000000 | REJECT_AS_PRIMARY |
| depression__caregiver_1_3 | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 | 0.008103 | 0.018133 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_2_3 | 0.800000 | 0.878049 | 0.916411 | 0.882349 | 0.044623 | 0.001648 | 0.024853 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_full | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 | 0.007404 | 0.006983 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_1_3 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 | 0.006934 | 0.022763 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_2_3 | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 | 0.002227 | 0.021433 | PROMOTE_WITH_CAVEAT |
| depression__psychologist_full | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 | 0.000536 | 0.019308 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_1_3 | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 | 0.019161 | 0.013158 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 | 0.000584 | 0.009434 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |
| elimination__psychologist_1_3 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 | 0.037627 | 0.031861 | HOLD_FOR_FINAL_LIMITATION |
| elimination__psychologist_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 | 0.000000 | 0.000000 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |

- generalization_evidence: yes
