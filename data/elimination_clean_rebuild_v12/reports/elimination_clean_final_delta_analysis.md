# elimination clean final delta

## absolute

        mode          version  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  stress_worst_ba           output_status
   caregiver baseline_pre_v11   0.918699 0.701863        0.920           0.810932 0.795775      NaN 0.148582              NaN           legacy_caveat
   caregiver     v11_inflated   0.993421 0.937888        0.992           0.964944 0.964856 0.985234 0.035061              NaN hold_v11_needs_revision
   caregiver        v12_clean   0.868421 0.819876        0.840           0.829938 0.843450 0.915299 0.135959         0.765093   uncertainty_preferred
psychologist baseline_pre_v11   0.925620 0.695652        0.928           0.811826 0.794326      NaN 0.144576              NaN           legacy_caveat
psychologist     v11_inflated   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229              NaN hold_v11_needs_revision
psychologist        v12_clean   0.847561 0.863354        0.800           0.831677 0.855385 0.912164 0.134631         0.743205   uncertainty_preferred

## deltas

        mode  delta_precision_v12_vs_baseline  delta_recall_v12_vs_baseline  delta_specificity_v12_vs_baseline  delta_ba_v12_vs_baseline  delta_f1_v12_vs_baseline  delta_pr_auc_v12_vs_baseline  delta_brier_v12_vs_baseline  delta_precision_v12_vs_v11  delta_recall_v12_vs_v11  delta_specificity_v12_vs_v11  delta_ba_v12_vs_v11  delta_f1_v12_vs_v11  delta_pr_auc_v12_vs_v11  delta_brier_v12_vs_v11  delta_stress_robustness_v12 delta_output_readiness_v12_vs_baseline
   caregiver                        -0.050278                      0.118012                             -0.080                  0.019006                  0.047676                           NaN                    -0.012624                   -0.125000                -0.118012                        -0.152            -0.135006            -0.121406                -0.069936                0.100898                    -0.064845                  uncertainty_preferred
psychologist                        -0.078059                      0.167702                             -0.128                  0.019851                  0.061058                           NaN                    -0.009946                   -0.152439                -0.074534                        -0.200            -0.137267            -0.112564                -0.074117                0.100401                    -0.088472                  uncertainty_preferred
