# elimination clean ablation and stress

## ablation

        mode             ablation_config family  n_features  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score  delta_ba_vs_winner
   caregiver  drop_source_specific_block     rf          17   0.874172 0.819876        0.848           0.833938 0.846154 0.912679 0.137181        0.062937                0.235904              0.851399            0.004000
   caregiver      drop_top1_corr_feature     rf          20   0.867550 0.813665        0.840           0.826832 0.839744 0.910843 0.137397        0.108392                0.165718              0.881119           -0.003106
   caregiver     drop_top3_corr_features     rf          18   0.850000 0.844720        0.808           0.826360 0.847352 0.909189 0.137212        0.174825                0.131695              0.887063           -0.003578
   caregiver             winner_selected     rf          21   0.862745 0.819876        0.832           0.825938 0.840764 0.915299 0.135959        0.195804                0.160093              0.839510           -0.004000
   caregiver      drop_self_report_block     rf          21   0.862745 0.819876        0.832           0.825938 0.840764 0.915299 0.135959        0.195804                0.160093              0.839510           -0.004000
   caregiver drop_engineered_clean_block     rf          16   0.875862 0.788820        0.856           0.822410 0.830065 0.908218 0.138206        0.104895                0.355469              0.869231           -0.007528
   caregiver             drop_cbcl_block     rf          17   0.838509 0.838509        0.792           0.815255 0.838509 0.904567 0.142554        0.178322                0.112808              0.809790           -0.014683
   caregiver              drop_sdq_block     rf          17   0.845161 0.813665        0.808           0.810832 0.829114 0.909795 0.139000        0.220280                0.185351              0.851399           -0.019106
   caregiver   minimal_reasonable_subset     rf          12   0.914530 0.664596        0.920           0.792298 0.769784 0.907228 0.147900        0.013986                0.280142              0.851399           -0.037640
psychologist     drop_top3_corr_features     rf          21   0.864516 0.832298        0.832           0.832149 0.848101 0.915582 0.138413        0.118881                0.043184              0.827622            0.000472
psychologist             winner_selected     rf          24   0.847561 0.863354        0.800           0.831677 0.855385 0.912164 0.134631        0.125874                0.034444              0.851399            0.000000
psychologist      drop_self_report_block     rf          22   0.862745 0.819876        0.832           0.825938 0.840764 0.906862 0.137320        0.188811                0.149745              0.839510           -0.005739
psychologist drop_engineered_clean_block     rf          18   0.876712 0.795031        0.856           0.825516 0.833876 0.911496 0.133381        0.101399                0.338790              0.857343           -0.006161
psychologist  drop_source_specific_block     rf          20   0.858065 0.826087        0.824           0.825043 0.841772 0.910471 0.137404        0.185315                0.155964              0.821678           -0.006634
psychologist      drop_top1_corr_feature     rf          23   0.858065 0.826087        0.824           0.825043 0.841772 0.904489 0.137214        0.192308                0.166234              0.839510           -0.006634
psychologist              drop_sdq_block     rf          20   0.864865 0.795031        0.840           0.817516 0.828479 0.910815 0.139636        0.062937                0.276534              0.786014           -0.014161
psychologist             drop_cbcl_block     rf          20   0.846154 0.819876        0.808           0.813938 0.832808 0.903915 0.140482        0.132867                0.211163              0.809790           -0.017739
psychologist   minimal_reasonable_subset     rf          12   0.914530 0.664596        0.920           0.792298 0.769784 0.907228 0.147900        0.013986                0.280142              0.851399           -0.039379

## shortcut comparator

        mode        shortcut_rule  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score
   caregiver cbcl_108_or_cbcl_112        1.0 0.937888          1.0           0.968944 0.967949 0.986427 0.034965             0.0               -0.034965               0.91958
psychologist cbcl_108_or_cbcl_112        1.0 0.937888          1.0           0.968944 0.967949 0.986427 0.034965             0.0               -0.034965               0.91958

## stress

        mode                           scenario  threshold_used  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score  delta_ba_vs_baseline_clean
   caregiver                     baseline_clean           0.420   0.868421 0.819876     0.840000           0.829938 0.843450 0.915299 0.135959        0.003497               -0.171930              0.777961                    0.000000
   caregiver borderline_cases_threshold_pm_0.08           0.420   0.750000 0.250000     0.928571           0.589286 0.375000 0.623750 0.245260        0.038462               -0.400000              0.760000                   -0.240652
   caregiver                 cbcl_coverage_drop           0.420   0.896296 0.751553     0.888000           0.819776 0.817568 0.912228 0.186339        0.006993               -0.190141              0.856195                   -0.010161
   caregiver      feature_perturbation_5pct_std           0.420   0.862745 0.819876     0.832000           0.825938 0.840764 0.913163 0.136637        0.000000               -0.174825              0.770280                   -0.004000
   caregiver            missingness_light_10pct           0.420   0.854430 0.838509     0.816000           0.827255 0.846395 0.909484 0.140392        0.003497               -0.171930              0.789849                   -0.002683
   caregiver         missingness_moderate_25pct           0.420   0.805195 0.770186     0.760000           0.765093 0.787302 0.872753 0.170129        0.003497                0.768421              0.916783                   -0.064845
   caregiver      partial_coverage_random_40pct           0.420   0.813253 0.838509     0.752000           0.795255 0.825688 0.877292 0.164496        0.000000               -0.199301              0.838811                   -0.034683
   caregiver                   source_mix_shift           0.420   0.837500 0.832298     0.792000           0.812149 0.834891 0.918391 0.136118        0.003497               -0.185965              0.787372                   -0.017789
   caregiver        threshold_stress_minus_0.05           0.370   0.868421 0.819876     0.840000           0.829938 0.843450 0.915299 0.135959        0.083916                0.222328              0.839510                    0.000000
   caregiver         threshold_stress_plus_0.05           0.470   0.868421 0.819876     0.840000           0.829938 0.843450 0.915299 0.135959        0.013986                0.079787              0.893007                    0.000000
psychologist                     baseline_clean           0.375   0.847561 0.863354     0.800000           0.831677 0.855385 0.912164 0.134631        0.125874                0.034444              0.851399                    0.000000
psychologist borderline_cases_threshold_pm_0.08           0.375   0.500000 0.285714     0.931034           0.608374 0.363636 0.333333 0.186675        1.000000                0.194444              1.000000                   -0.223303
psychologist                 cbcl_coverage_drop           0.375   0.862745 0.819876     0.832000           0.825938 0.840764 0.909591 0.169147        0.164336                0.172705              0.940559                   -0.005739
psychologist      feature_perturbation_5pct_std           0.375   0.857143 0.857143     0.816000           0.836571 0.857143 0.913288 0.135357        0.122378                0.012066              0.833566                    0.004894
psychologist            missingness_light_10pct           0.375   0.827381 0.863354     0.768000           0.815677 0.844985 0.903942 0.141692        0.136364                0.060729              0.851399                   -0.016000
psychologist         missingness_moderate_25pct           0.375   0.811765 0.857143     0.744000           0.800571 0.833837 0.900434 0.149457        0.178322                0.076179              0.881119                   -0.031106
psychologist      partial_coverage_random_40pct           0.375   0.762431 0.857143     0.656000           0.756571 0.807018 0.875503 0.166796        0.209790                0.087611              0.898951                   -0.075106
psychologist                   source_mix_shift           0.375   0.842424 0.863354     0.792000           0.827677 0.852761 0.912162 0.133263        0.139860                0.124593              0.863287                   -0.004000
psychologist        threshold_stress_minus_0.05           0.325   0.738462 0.894410     0.592000           0.743205 0.808989 0.912164 0.134631        0.153846                0.524793              0.839510                   -0.088472
psychologist         threshold_stress_plus_0.05           0.425   0.850932 0.850932     0.808000           0.829466 0.850932 0.912164 0.134631        0.129371                0.086617              0.815734                   -0.002211
