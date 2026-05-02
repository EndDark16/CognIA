# Elimination output readiness analysis v11

        mode      domain selected_operating_mode probability_score_ready risk_band_ready confidence_evidence_ready uncertainty_abstention_ready short_explanation_ready professional_detail_ready caveat_level   approval_status  precision   recall  specificity  balanced_accuracy   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score  output_readiness_score
   caregiver elimination                balanced                     yes             yes                       yes                          yes                     yes                       yes         high ready_with_caveat   0.993421 0.937888        0.992           0.964944 0.985234 0.035061        0.391608                0.068863              0.994056                     1.0
psychologist elimination                balanced                     yes             yes                       yes                          yes                     yes                       yes         high ready_with_caveat   1.000000 0.937888        1.000           0.968944 0.986281 0.034229        0.076923                0.109848              0.964336                     1.0

Interpretation:
- `approval_status` is constrained by recall, BA, Brier and realism together.
- Elimination remains caveat-high by policy even when readiness improves.
