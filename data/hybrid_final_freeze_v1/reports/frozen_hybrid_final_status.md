# Frozen Hybrid Final Status v1

## Champions (30 pares)
| domain | mode | final_status | precision | recall | balanced_accuracy | pr_auc | brier | quality_label | ceiling_status_final | should_keep_improving |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver_1_3 | HOLD_FOR_LIMITATION | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 | malo | near_ceiling | only_if_new_signal |
| adhd | caregiver_2_3 | HOLD_FOR_LIMITATION | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 | malo | near_ceiling | only_if_new_signal |
| adhd | caregiver_full | HOLD_FOR_LIMITATION | 0.744000 | 0.989362 | 0.953230 | 0.769742 | 0.053720 | malo | marginal_room_left | only_if_new_signal |
| adhd | psychologist_1_3 | HOLD_FOR_LIMITATION | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 | malo | near_ceiling | only_if_new_signal |
| adhd | psychologist_2_3 | HOLD_FOR_LIMITATION | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 | malo | near_ceiling | only_if_new_signal |
| adhd | psychologist_full | FROZEN_PRIMARY | 0.948454 | 0.978723 | 0.982885 | 0.980874 | 0.010648 | muy_bueno | marginal_room_left | no |
| anxiety | caregiver_1_3 | HOLD_FOR_LIMITATION | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 | malo | marginal_room_left | only_if_new_signal |
| anxiety | caregiver_2_3 | FROZEN_WITH_CAVEAT | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 | muy_bueno | near_ceiling | no |
| anxiety | caregiver_full | REJECT_AS_PRIMARY | 0.916667 | 0.895349 | 0.938791 | 0.936379 | 0.030046 | muy_bueno | near_ceiling | only_if_new_signal |
| anxiety | psychologist_1_3 | FROZEN_WITH_CAVEAT | 0.887500 | 0.825581 | 0.901369 | 0.929537 | 0.043643 | muy_bueno | ceiling_confirmed | no_practical_ceiling_confirmed |
| anxiety | psychologist_2_3 | FROZEN_PRIMARY | 0.919540 | 0.930233 | 0.956233 | 0.942496 | 0.024691 | muy_bueno | marginal_room_left | no |
| anxiety | psychologist_full | FROZEN_PRIMARY | 0.917647 | 0.906977 | 0.944605 | 0.941091 | 0.028518 | muy_bueno | marginal_room_left | no |
| conduct | caregiver_1_3 | FROZEN_WITH_CAVEAT | 0.884146 | 0.906250 | 0.923438 | 0.932896 | 0.056245 | aceptable | ceiling_confirmed | no_practical_ceiling_confirmed |
| conduct | caregiver_2_3 | FROZEN_PRIMARY | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000455 | muy_bueno | ceiling_confirmed | no_practical_ceiling_confirmed |
| conduct | caregiver_full | FROZEN_PRIMARY | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000416 | muy_bueno | ceiling_confirmed | no_practical_ceiling_confirmed |
| conduct | psychologist_1_3 | FROZEN_WITH_CAVEAT | 0.916129 | 0.887500 | 0.923438 | 0.940778 | 0.059582 | aceptable | marginal_room_left | yes |
| conduct | psychologist_2_3 | FROZEN_PRIMARY | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000657 | muy_bueno | marginal_room_left | no |
| conduct | psychologist_full | FROZEN_PRIMARY | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000006 | muy_bueno | marginal_room_left | no |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 | malo | near_ceiling | only_if_new_signal |
| depression | caregiver_2_3 | HOLD_FOR_LIMITATION | 0.800000 | 0.878049 | 0.916411 | 0.882349 | 0.044623 | aceptable | marginal_room_left | only_if_new_signal |
| depression | caregiver_full | HOLD_FOR_LIMITATION | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 | aceptable | near_ceiling | only_if_new_signal |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 | malo | near_ceiling | only_if_new_signal |
| depression | psychologist_2_3 | FROZEN_WITH_CAVEAT | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 | aceptable | near_ceiling | no |
| depression | psychologist_full | HOLD_FOR_LIMITATION | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 | aceptable | near_ceiling | only_if_new_signal |
| elimination | caregiver_1_3 | HOLD_FOR_LIMITATION | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 | aceptable | marginal_room_left | only_if_new_signal |
| elimination | caregiver_2_3 | CEILING_CONFIRMED_BEST_PRACTICAL_POINT | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 | muy_bueno | ceiling_confirmed | no_practical_ceiling_confirmed |
| elimination | caregiver_full | FROZEN_PRIMARY | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000826 | muy_bueno | marginal_room_left | no |
| elimination | psychologist_1_3 | HOLD_FOR_LIMITATION | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 | malo | near_ceiling | only_if_new_signal |
| elimination | psychologist_2_3 | CEILING_CONFIRMED_BEST_PRACTICAL_POINT | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 | muy_bueno | ceiling_confirmed | no_practical_ceiling_confirmed |
| elimination | psychologist_full | FROZEN_PRIMARY | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000078 | muy_bueno | marginal_room_left | no |

## Conteos
- quality: {'muy_bueno': 14, 'malo': 9, 'aceptable': 7}
- ceiling: {'near_ceiling': 12, 'marginal_room_left': 12, 'ceiling_confirmed': 6}
- should_keep_improving: {'only_if_new_signal': 14, 'no': 9, 'no_practical_ceiling_confirmed': 6, 'yes': 1}

## Caveats de fuentes
- `hybrid_input_audit_classification_final.csv`: por_confirmar (no encontrado en repo).
- `hybrid_dataset_final_registry_v1.csv`: por_confirmar (no encontrado en repo).
