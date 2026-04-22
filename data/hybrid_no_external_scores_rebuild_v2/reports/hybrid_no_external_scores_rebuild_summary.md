# Hybrid No External Scores Rebuild v2 - Summary

## Final models (30)
| domain | mode | precision | recall | balanced_accuracy | pr_auc | brier | quality_label | ceiling_status | final_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver_1_3 | 0.621212 | 0.872340 | 0.871403 | 0.631918 | 0.086828 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| adhd | caregiver_2_3 | 0.701754 | 0.851064 | 0.881490 | 0.704422 | 0.072567 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| adhd | caregiver_full | 0.740385 | 0.819149 | 0.874600 | 0.711879 | 0.068722 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| adhd | psychologist_1_3 | 0.614815 | 0.882979 | 0.874132 | 0.637545 | 0.084173 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| adhd | psychologist_2_3 | 0.728972 | 0.829787 | 0.877329 | 0.733739 | 0.068004 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| adhd | psychologist_full | 0.929412 | 0.840426 | 0.912441 | 0.927131 | 0.030233 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| anxiety | caregiver_1_3 | 0.887500 | 0.825581 | 0.901369 | 0.926692 | 0.036836 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| anxiety | caregiver_2_3 | 0.873563 | 0.883721 | 0.927901 | 0.952481 | 0.030676 | bueno | ceiling_confirmed | FROZEN_PRIMARY |
| anxiety | caregiver_full | 0.916667 | 0.895349 | 0.938791 | 0.946538 | 0.027444 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| anxiety | psychologist_1_3 | 0.953846 | 0.720930 | 0.856658 | 0.916729 | 0.035571 | aceptable | near_ceiling | FROZEN_WITH_CAVEAT |
| anxiety | psychologist_2_3 | 0.905882 | 0.895349 | 0.937522 | 0.930288 | 0.030218 | muy_bueno | ceiling_confirmed | FROZEN_PRIMARY |
| anxiety | psychologist_full | 0.915663 | 0.883721 | 0.932977 | 0.944218 | 0.026761 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| conduct | caregiver_1_3 | 0.901961 | 0.862500 | 0.907813 | 0.950080 | 0.056385 | bueno | marginal_room_left | FROZEN_PRIMARY |
| conduct | caregiver_2_3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.001274 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| conduct | caregiver_full | 1.000000 | 0.993750 | 0.996875 | 1.000000 | 0.001327 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| conduct | psychologist_1_3 | 0.909091 | 0.812500 | 0.885938 | 0.954263 | 0.058544 | aceptable | near_ceiling | FROZEN_WITH_CAVEAT |
| conduct | psychologist_2_3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.001095 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| conduct | psychologist_full | 1.000000 | 0.993750 | 0.996875 | 1.000000 | 0.001248 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| depression | caregiver_1_3 | 0.805970 | 0.658537 | 0.812937 | 0.764765 | 0.060067 | malo | near_ceiling | HOLD_FOR_LIMITATION |
| depression | caregiver_2_3 | 0.831325 | 0.841463 | 0.903144 | 0.843414 | 0.045455 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| depression | caregiver_full | 0.848101 | 0.817073 | 0.893461 | 0.866538 | 0.046033 | aceptable | marginal_room_left | FROZEN_WITH_CAVEAT |
| depression | psychologist_1_3 | 0.797468 | 0.768293 | 0.864046 | 0.768131 | 0.056530 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| depression | psychologist_2_3 | 0.827160 | 0.817073 | 0.890949 | 0.833041 | 0.047903 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| depression | psychologist_full | 0.837500 | 0.817073 | 0.892205 | 0.940602 | 0.039160 | aceptable | marginal_room_left | FROZEN_WITH_CAVEAT |
| elimination | caregiver_1_3 | 0.941176 | 0.615385 | 0.805356 | 0.878649 | 0.021929 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| elimination | caregiver_2_3 | 0.925926 | 0.961538 | 0.976096 | 0.955948 | 0.010039 | muy_bueno | ceiling_confirmed | FROZEN_PRIMARY |
| elimination | caregiver_full | 0.961538 | 0.961538 | 0.978433 | 0.958261 | 0.008134 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| elimination | psychologist_1_3 | 0.850000 | 0.653846 | 0.819914 | 0.882802 | 0.023767 | malo | marginal_room_left | HOLD_FOR_LIMITATION |
| elimination | psychologist_2_3 | 0.961538 | 0.961538 | 0.978433 | 0.957705 | 0.008223 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |
| elimination | psychologist_full | 0.943396 | 0.961538 | 0.977265 | 0.973474 | 0.009137 | muy_bueno | marginal_room_left | FROZEN_PRIMARY |

- quality_counts: {'muy_bueno': 13, 'malo': 11, 'aceptable': 4, 'bueno': 2}
- ceiling_counts: {'marginal_room_left': 24, 'ceiling_confirmed': 3, 'near_ceiling': 3}
- keep_improving_counts: {'yes': 14, 'only_if_new_signal': 11, 'no_practical_ceiling_confirmed': 3, 'no': 2}