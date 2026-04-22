# Hybrid RF Targeted v4 - Overfitting Audit

## Candidate gaps
| candidate_id | overfit_gap_train_val_ba | generalization_gap_val_holdout_ba | seed_ba_std | worst_stress_ba_drop | promotion_decision |
| --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | 0.006477 | 0.009205 | 0.002310 | -0.036214 | HOLD_FOR_FINAL_LIMITATION |
| adhd__caregiver_2_3 | 0.032815 | 0.021139 | 0.005093 | -0.052034 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_1_3 | 0.046200 | 0.015820 | 0.003851 | -0.017666 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_2_3 | 0.005613 | 0.015820 | 0.004739 | -0.032053 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_1_3 | 0.094155 | 0.067761 | 0.008944 | -0.080864 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_2_3 | 0.019980 | 0.007083 | 0.056243 | -0.190591 | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_full | 0.017304 | 0.034884 | 0.000000 | -0.073043 | REJECT_AS_PRIMARY |
| depression__caregiver_1_3 | 0.120830 | 0.002513 | 0.008103 | -0.197267 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_2_3 | 0.044758 | 0.024758 | 0.001648 | -0.148302 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_full | 0.033428 | 0.027087 | 0.007404 | -0.133779 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_1_3 | 0.075819 | 0.043939 | 0.006934 | -0.109388 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_2_3 | 0.082101 | 0.009866 | 0.002227 | -0.194938 | PROMOTE_WITH_CAVEAT |
| depression__psychologist_full | 0.052136 | 0.027087 | 0.000536 | -0.110645 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_1_3 | 0.052401 | 0.011053 | 0.019161 | -0.103433 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_2_3 | -0.002724 | 0.001168 | 0.000584 | -0.067308 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |
| elimination__psychologist_1_3 | 0.071202 | 0.046639 | 0.037627 | -0.074587 | HOLD_FOR_FINAL_LIMITATION |
| elimination__psychologist_2_3 | -0.002335 | 0.001168 | 0.000000 | -0.039630 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |

- overfitting_evidence: yes
- thresholds: train-val BA gap > 0.07 or val-holdout BA gap > 0.06.
