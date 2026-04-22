# Final ceiling detection analysis

        mode      domain               status  delta_balanced_accuracy  delta_pr_auc  delta_brier   family feature_variant           target_variant
   caregiver        adhd marginal_improvement                 0.004872     -0.007612    -0.000568       rf      engineered                 baseline
   caregiver     conduct marginal_improvement                 0.005037      0.002391    -0.001841       rf      engineered                 baseline
   caregiver elimination material_improvement                 0.020000      0.017147    -0.014848  xgboost      engineered elimination_any_baseline
   caregiver     anxiety material_improvement                 0.031692      0.032211    -0.016215 lightgbm      engineered                 baseline
   caregiver  depression marginal_improvement                -0.026062      0.009236    -0.004593 catboost      engineered                 baseline
psychologist        adhd         near_ceiling                 0.002789     -0.001879    -0.000661       rf            base                 baseline
psychologist     conduct material_improvement                 0.022042     -0.003550    -0.006802 catboost      engineered                 baseline
psychologist elimination material_improvement                 0.024528      0.021247    -0.011477 lightgbm      engineered elimination_any_baseline
psychologist     anxiety material_improvement                 0.017803      0.028696    -0.011504 lightgbm      engineered                 baseline
psychologist  depression marginal_improvement                -0.001890      0.007969    -0.001403 catboost      engineered                 baseline
