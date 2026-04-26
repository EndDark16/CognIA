# Hybrid Classification Normalization v2 (v5)

## Summary
| line | rows | normalized_robust | normalized_caveat | normalized_hold | normalized_reject | downgrades | violations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v5 | 30 | 1 | 19 | 7 | 3 | 10 | 0 |

## Priority review
| domain | mode | legacy_final_class | normalized_final_class | secondary_metric_anomaly_flag | overfit_risk_flag | shortcut_risk_flag | easy_dataset_flag | classification_reason_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| anxiety | caregiver_2_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| anxiety | caregiver_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| anxiety | psychologist_2_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| anxiety | psychologist_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| depression | caregiver_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| depression | psychologist_full | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| elimination | caregiver_1_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | yes | no | no | no | useful_with_explicit_caveat |
| elimination | caregiver_2_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| elimination | caregiver_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| elimination | psychologist_1_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | yes | no | no | no | useful_with_explicit_caveat |
| elimination | psychologist_2_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| elimination | psychologist_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | yes | no | no | no | robust_metrics_blocked_by_unresolved_secondary_anomaly |
| anxiety | psychologist_1_3 | PRIMARY_WITH_CAVEAT | REJECT_AS_PRIMARY | yes | no | yes | no | hard_blocker_easy_or_shortcut |
| adhd | caregiver_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | no | no | no | fails_minimum_gate_or_has_strong_risk |
| adhd | caregiver_full | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | no | no | no | fails_minimum_gate_or_has_strong_risk |
| adhd | psychologist_1_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | no | no | no | fails_minimum_gate_or_has_strong_risk |
| adhd | psychologist_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | no | no | no | fails_minimum_gate_or_has_strong_risk |
| depression | caregiver_1_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | yes | no | no | fails_minimum_gate_or_has_strong_risk |
| depression | caregiver_2_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | no | no | no | fails_minimum_gate_or_has_strong_risk |
| depression | psychologist_1_3 | HOLD_FOR_LIMITATION | HOLD_FOR_LIMITATION | no | yes | no | no | fails_minimum_gate_or_has_strong_risk |
| anxiety | caregiver_1_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| conduct | caregiver_1_3 | ROBUST_PRIMARY | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| conduct | caregiver_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| conduct | psychologist_1_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| conduct | psychologist_full | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| depression | psychologist_2_3 | PRIMARY_WITH_CAVEAT | PRIMARY_WITH_CAVEAT | no | no | no | no | useful_with_explicit_caveat |
| adhd | caregiver_1_3 | HOLD_FOR_LIMITATION | REJECT_AS_PRIMARY | no | no | yes | no | hard_blocker_easy_or_shortcut |
| conduct | caregiver_2_3 | ROBUST_PRIMARY | REJECT_AS_PRIMARY | no | no | yes | no | hard_blocker_easy_or_shortcut |
| conduct | psychologist_2_3 | ROBUST_PRIMARY | ROBUST_PRIMARY | no | no | no | no | passes_robust_gate_without_blockers |
