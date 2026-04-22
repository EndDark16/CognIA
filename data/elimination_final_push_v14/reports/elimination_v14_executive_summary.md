# elimination v14 executive summary

- decision: KEEP_V12
- improved_modes_vs_v12: 0/2
- rf_champion_policy: maintained
- subtype_trials_run: yes
- confidence_policy: user [1%,99%], professional [0.5%,99.5%], raw preserved

        mode  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  worst_stress_ba   final_output_status
   caregiver   0.860759 0.844720        0.824           0.834360 0.852665 0.911523 0.132678         0.741466 uncertainty_preferred
psychologist   0.847561 0.863354        0.800           0.831677 0.855385 0.912164 0.134631         0.756571 uncertainty_preferred
