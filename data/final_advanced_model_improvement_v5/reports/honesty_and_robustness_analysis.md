# Honesty and robustness analysis

        mode      domain   family           target_variant  default_dependency  imputation_dependency  source_mix_risk overfit_risk leakage_risk  complexity_cost  honesty_score  robustness_score  combined_honesty_robustness
   caregiver        adhd       rf                 baseline            0.058741               0.058741             0.20          low          low             0.10       0.873636          0.905268                     0.889452
   caregiver     conduct       rf                 baseline            0.023492               0.023492             0.20          low          low             0.10       0.919460          0.929851                     0.924656
   caregiver elimination  xgboost elimination_any_baseline            0.021497               0.021497             0.20          low          low             0.25       0.847054          0.965812                     0.906433
   caregiver     anxiety lightgbm                 baseline            0.070572               0.070572             0.20          low          low             0.25       0.783256          0.904124                     0.843690
   caregiver  depression catboost                 baseline            0.045080               0.045080             0.20          low          low             0.25       0.816396          0.895554                     0.855975
psychologist        adhd       rf                 baseline            0.363337               0.363337             0.25          low          low             0.10       0.477662          0.536024                     0.506843
psychologist     conduct catboost                 baseline            0.024681               0.024681             0.25          low          low             0.25       0.842914          0.961991                     0.902453
psychologist elimination lightgbm elimination_any_baseline            0.022353               0.022353             0.25          low          low             0.25       0.845942          0.950799                     0.898370
psychologist     anxiety lightgbm                 baseline            0.125617               0.125617             0.25          low          low             0.25       0.711698          0.849260                     0.780479
psychologist  depression catboost                 baseline            0.045937               0.045937             0.25          low          low             0.25       0.815282          0.919701                     0.867492
