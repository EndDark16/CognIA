# elimination v14 coverage gate analysis

        mode             gate_name  threshold  coverage_rate  uncertain_rate  precision_decided  recall_decided  specificity_decided  balanced_accuracy_decided  f1_decided  pr_auc_decided  brier_decided  gate_objective
   caregiver             gate_none      0.310       1.000000        0.000000           0.860759        0.844720             0.824000                   0.834360    0.852665        0.911523       0.132678        0.871000
   caregiver  gate_combined_strict      0.310       0.958042        0.041958           0.860759        0.860759             0.810345                   0.835552    0.860759        0.915555       0.130951        0.868749
   caregiver    gate_total_ge_0.50      0.310       0.986014        0.013986           0.860759        0.844720             0.818182                   0.831451    0.852665        0.912317       0.133733        0.867647
   caregiver     gate_cbcl_ge_0.35      0.310       0.961538        0.038462           0.860759        0.855346             0.810345                   0.832845    0.858044        0.914955       0.132226        0.866936
   caregiver gate_combined_relaxed      0.310       0.961538        0.038462           0.860759        0.855346             0.810345                   0.832845    0.858044        0.914955       0.132226        0.866936
psychologist             gate_none      0.375       1.000000        0.000000           0.847561        0.863354             0.800000                   0.831677    0.855385        0.912164       0.134631        0.872478
psychologist    gate_total_ge_0.50      0.375       0.986014        0.013986           0.847561        0.863354             0.793388                   0.828371    0.855385        0.912882       0.135729        0.868984
psychologist     gate_cbcl_ge_0.35      0.375       0.961538        0.038462           0.851852        0.867925             0.793103                   0.830514    0.859813        0.915466       0.134367        0.867658
psychologist gate_combined_relaxed      0.375       0.961538        0.038462           0.851852        0.867925             0.793103                   0.830514    0.859813        0.915466       0.134367        0.867658
psychologist  gate_combined_strict      0.375       0.958042        0.041958           0.850932        0.867089             0.793103                   0.830096    0.858934        0.915694       0.133542        0.866726
