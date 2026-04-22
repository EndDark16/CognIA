# elimination clean final decision

Decision: `APPROVE_V12_WITH_CAVEAT`

1) valid clean improvement: yes
2) recall improved useful: yes
3) robustness improved: yes
4) shortcut dependence removed: yes
5) can replace previous: yes
6) caveat: high caveat + confidence clipping + automatic extreme audit
7) closure: close with caveat

        mode      domain  selected_operating_mode  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  worst_stress_ba  shortcut_max_metric_diff shortcut_independence probability_ready risk_band_ready confidence_ready uncertainty_ready professional_detail_ready   final_output_status visible_user_prob_cap visible_prof_prob_cap extreme_performance_audit_trigger
   caregiver elimination conservative_probability   0.868421 0.819876         0.84           0.829938 0.843450 0.915299 0.135959         0.765093                      0.16                   yes               yes             yes               no                no                       yes uncertainty_preferred           [0.01,0.99]         [0.005,0.995]                                no
psychologist elimination                 balanced   0.847561 0.863354         0.80           0.831677 0.855385 0.912164 0.134631         0.743205                      0.20                   yes               yes             yes              yes               yes                       yes uncertainty_preferred           [0.01,0.99]         [0.005,0.995]                                no
