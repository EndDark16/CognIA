# Hybrid RF Targeted v4 - Ceiling Decision

## Material gain vs v3
| candidate_id | material_improvement_vs_v3 | delta_balanced_accuracy_vs_v3 | delta_pr_auc_vs_v3 | delta_precision_vs_v3 | delta_recall_vs_v3 | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- |
| adhd__caregiver_1_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | HOLD_FOR_FINAL_LIMITATION |
| adhd__caregiver_2_3 | no | 0.000000 | 0.000000 | 0.000000 | -0.000000 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_1_3 | no | -0.000000 | 0.000000 | 0.000000 | -0.000000 | HOLD_FOR_FINAL_LIMITATION |
| adhd__psychologist_2_3 | no | 0.000000 | 0.000000 | 0.000000 | -0.000000 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_1_3 | yes | 0.018180 | 0.012033 | -0.047059 | 0.046512 | HOLD_FOR_FINAL_LIMITATION |
| anxiety__caregiver_2_3 | no | 0.005814 | -0.000338 | 0.000617 | 0.011628 | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_full | no | -0.027801 | 0.002810 | 0.005556 | -0.058140 | REJECT_AS_PRIMARY |
| depression__caregiver_1_3 | no | -0.014340 | -0.001035 | 0.064543 | -0.048780 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_2_3 | yes | 0.007538 | 0.001445 | 0.050000 | 0.000000 | HOLD_FOR_FINAL_LIMITATION |
| depression__caregiver_full | no | 0.000000 | 0.000000 | 0.000000 | -0.000000 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_1_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | HOLD_FOR_FINAL_LIMITATION |
| depression__psychologist_2_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PROMOTE_WITH_CAVEAT |
| depression__psychologist_full | no | -0.000000 | -0.000000 | 0.000000 | 0.000000 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_1_3 | yes | 0.030014 | 0.005013 | 0.025199 | 0.057692 | HOLD_FOR_FINAL_LIMITATION |
| elimination__caregiver_2_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |
| elimination__psychologist_1_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | HOLD_FOR_FINAL_LIMITATION |
| elimination__psychologist_2_3 | no | 0.000000 | 0.000000 | 0.000000 | 0.000000 | CEILING_CONFIRMED_NO_MATERIAL_GAIN |

- candidates_material_gain_count: 3
- candidates_no_material_gain_count: 14
- CEILING_CONFIRMED_NO_MATERIAL_GAIN is assigned when stability is acceptable and no material gain appears.
