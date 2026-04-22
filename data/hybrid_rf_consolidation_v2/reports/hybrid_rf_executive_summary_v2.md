# Hybrid RF Executive Summary v2

- candidate_count: 13
- promoted_now: 0
- promoted_with_caveat: 7
- hold_for_fix: 6
- rejected: 0
- overfitting_evidence: yes
- generalization_evidence: no
- close_main_modeling_stage: no

## Final Champions
| domain | champion_candidate_id | champion_mode | champion_role | champion_decision | champion_precision | champion_recall | champion_specificity | champion_balanced_accuracy | champion_f1 | champion_roc_auc | champion_pr_auc | champion_brier | selection_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | adhd__psychologist_full | psychologist_full | psychologist | PROMOTE_WITH_CAVEAT | 0.947917 | 0.968085 | 0.987047 | 0.977566 | 0.957895 | 0.980322 | 0.945106 | 0.015459 | best_decision_rank_and_metrics |
| anxiety | anxiety__caregiver_full | caregiver_full | caregiver | PROMOTE_WITH_CAVEAT | 0.941860 | 0.941860 | 0.987310 | 0.964585 | 0.941860 | 0.993566 | 0.957131 | 0.020587 | best_decision_rank_and_metrics |
| conduct | conduct__psychologist_2_3 | psychologist_2_3 | psychologist | PROMOTE_WITH_CAVEAT | 0.987578 | 1.000000 | 0.993769 | 0.996885 | 0.993750 | 1.000000 | 1.000000 | 0.001286 | best_decision_rank_and_metrics |
| depression | depression__caregiver_2_3 | caregiver_2_3 | caregiver | HOLD_FOR_TARGETED_FIX | 0.847222 | 0.743902 | 0.972362 | 0.858132 | 0.792208 | 0.969604 | 0.862956 | 0.052005 | best_decision_rank_and_metrics |
| elimination | elimination__caregiver_2_3 | caregiver_2_3 | caregiver | PROMOTE_WITH_CAVEAT | 0.961538 | 0.961538 | 0.995327 | 0.978433 | 0.961538 | 0.998382 | 0.974532 | 0.006001 | best_decision_rank_and_metrics |
