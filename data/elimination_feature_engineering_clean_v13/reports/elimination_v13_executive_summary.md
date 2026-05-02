# elimination v13 executive summary

- decision: UNCERTAINTY_PREFERRED_ONLY
- improved_modes_vs_v12: 0/2
- shortcut_independence_global: yes
- round_policy: {'max_strong_rounds': 3, 'max_confirm_rounds': 1}
- confidence policy: user [1%,99%], professional [0.5%,99.5%], internal raw preserved

        mode  delta_precision_v13_vs_baseline  delta_recall_v13_vs_baseline  delta_specificity_v13_vs_baseline  delta_ba_v13_vs_baseline  delta_f1_v13_vs_baseline  delta_pr_auc_v13_vs_baseline  delta_brier_v13_vs_baseline  delta_precision_v13_vs_v12  delta_recall_v13_vs_v12  delta_specificity_v13_vs_v12  delta_ba_v13_vs_v12  delta_f1_v13_vs_v12  delta_pr_auc_v13_vs_v12  delta_brier_v13_vs_v12  delta_robustness_v13_vs_v12              delta_output_readiness_v13_vs_v12
   caregiver                        -0.041001                      0.055901                             -0.056                 -0.000050                  0.017559                           NaN                    -0.010505                    0.009277                -0.062112                         0.024            -0.019056            -0.030117                -0.001804                0.002118                    -0.036646 uncertainty_preferred -> uncertainty_preferred
psychologist                        -0.046187                      0.074534                             -0.064                  0.005267                  0.026866                           NaN                    -0.007813                    0.031872                -0.093168                         0.064            -0.014584            -0.034193                 0.001049                0.002132                    -0.008124 uncertainty_preferred -> uncertainty_preferred
