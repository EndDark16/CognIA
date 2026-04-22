# Elimination ceiling analysis v11

        mode      domain selected_operating_mode  delta_balanced_accuracy  delta_recall  delta_pr_auc  delta_brier    improvement_level          stop_rule_result structural_limit_signal                                        notes
   caregiver elimination                balanced                 0.154012      0.236025      0.095618    -0.113521 material_improvement single_confirm_round_only                      no Improvement detected above noise thresholds.
psychologist elimination                balanced                 0.157118      0.242236      0.097670    -0.110347 material_improvement single_confirm_round_only                      no Improvement detected above noise thresholds.

Stop rules used:
- material: delta_BA>=0.010 and delta_recall>=0.020, or delta_PR-AUC>=0.012 with better/equal Brier.
- marginal: smaller positive gains not robust enough for another large round.
- near_ceiling_or_structural_limit: no robust gain despite broad engineered sets.
