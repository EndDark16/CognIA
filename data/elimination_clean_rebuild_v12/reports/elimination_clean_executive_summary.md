# elimination clean executive summary

- decision: APPROVE_V12_WITH_CAVEAT
- shortcut_independence_global: yes
- robust_global: yes
- recall_useful_global: yes
- rounds_policy: max 3 strong + 1 confirm

        mode  delta_precision_v12_vs_baseline  delta_recall_v12_vs_baseline  delta_specificity_v12_vs_baseline  delta_ba_v12_vs_baseline  delta_f1_v12_vs_baseline  delta_pr_auc_v12_vs_baseline  delta_brier_v12_vs_baseline  delta_precision_v12_vs_v11  delta_recall_v12_vs_v11  delta_specificity_v12_vs_v11  delta_ba_v12_vs_v11  delta_f1_v12_vs_v11  delta_pr_auc_v12_vs_v11  delta_brier_v12_vs_v11  delta_stress_robustness_v12 delta_output_readiness_v12_vs_baseline
   caregiver                        -0.050278                      0.118012                             -0.080                  0.019006                  0.047676                           NaN                    -0.012624                   -0.125000                -0.118012                        -0.152            -0.135006            -0.121406                -0.069936                0.100898                    -0.064845                  uncertainty_preferred
psychologist                        -0.078059                      0.167702                             -0.128                  0.019851                  0.061058                           NaN                    -0.009946                   -0.152439                -0.074534                        -0.200            -0.137267            -0.112564                -0.074117                0.100401                    -0.088472                  uncertainty_preferred

Confidence policy: user [1%,99%], professional [0.5%,99.5%], internal raw preserved.
