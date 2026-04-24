# Hybrid Classification Normalization v1

Normalizacion metodologica de `final_class` (dos capas): clase principal + flags de riesgo.

## Resumen
| line | rows | legacy_robust | normalized_robust | normalized_caveat | normalized_hold | normalized_reject | downgrades | violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2 | 30 | 17 | 1 | 19 | 9 | 1 | 17 | 0 |
| v3 | 30 | 17 | 1 | 19 | 9 | 1 | 17 | 0 |

## Top review priority (v2, focus full y 2_3)
| domain | mode | legacy_final_class | normalized_final_class | review_bucket | priority_score | secondary_metric_anomaly_flag | overfit_risk_flag | shortcut_risk_flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| anxiety | caregiver_2_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| anxiety | caregiver_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| anxiety | psychologist_2_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| anxiety | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| depression | caregiver_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| depression | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| elimination | caregiver_2_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| elimination | caregiver_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| elimination | psychologist_2_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| elimination | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 9 | yes | no | no |
| conduct | caregiver_2_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | bajar_a_primary_with_caveat | 5 | no | no | no |
| adhd | caregiver_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | mantener_igual | 3 | no | no | no |
| adhd | caregiver_full | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | mantener_igual | 3 | no | no | no |
| adhd | psychologist_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | mantener_igual | 3 | no | no | no |
| conduct | caregiver_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | mantener_igual | 3 | no | no | no |
| conduct | psychologist_2_3 | ROBUST_PRIMARY | ROBUST_PRIMARY | mantener_igual | 3 | no | no | no |
| conduct | psychologist_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | mantener_igual | 3 | no | no | no |
| depression | caregiver_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | mantener_igual | 3 | no | no | no |
| depression | psychologist_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | mantener_igual | 3 | no | no | no |

## Policy violations
- v2: 0
- v3: 0
