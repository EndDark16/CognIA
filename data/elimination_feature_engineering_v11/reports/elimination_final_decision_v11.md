# Elimination final decision v11

- decision: **close_with_updated_operating_mode**
- global_material_improvement: yes
- campaign_scope: elimination-only feature engineering (finite, strict_no_leakage).
- rounds_executed: 3 strong + 1 confirm-equivalent selection pass.

## Mode-level decision

        mode selected_operating_mode  delta_precision  delta_recall  delta_balanced_accuracy  delta_pr_auc  delta_brier   approval_status
   caregiver                balanced         0.074722      0.236025                 0.154012      0.095618    -0.113521 ready_with_caveat
psychologist                balanced         0.074380      0.242236                 0.157118      0.097670    -0.110347 ready_with_caveat

## Practical interpretation

- If gains remain marginal, elimination should stay with high caveat and uncertainty-aware interpretation.
- If one mode shows material gain, keep caveat but adopt improved operating point for that mode.
