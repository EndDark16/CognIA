# stress

        mode                   scenario  threshold_used  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  delta_ba_vs_clean
   caregiver             baseline_clean            0.20   0.993421 0.937888        0.992           0.964944 0.964856 0.985234 0.035061           0.000000
   caregiver          missingness_light            0.20   0.992908 0.869565        0.992           0.930783 0.927152 0.973818 0.066619          -0.034161
   caregiver       missingness_moderate            0.20   0.992126 0.782609        0.992           0.887304 0.875000 0.954360 0.103132          -0.077640
   caregiver partial_coverage_drop_cbcl            0.20   0.923077 0.074534        0.992           0.533267 0.137931 0.784143 0.410935          -0.431677
   caregiver  partial_coverage_drop_sdq            0.20   0.993421 0.937888        0.992           0.964944 0.964856 0.984950 0.036046           0.000000
   caregiver       threshold_minus_0.05            0.15   0.986928 0.937888        0.984           0.960944 0.961783 0.985234 0.035061          -0.004000
   caregiver        threshold_plus_0.05            0.25   0.993421 0.937888        0.992           0.964944 0.964856 0.985234 0.035061           0.000000
psychologist             baseline_clean            0.29   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229           0.000000
psychologist          missingness_light            0.29   1.000000 0.894410        1.000           0.947205 0.944262 0.985379 0.045996          -0.021739
psychologist       missingness_moderate            0.29   1.000000 0.801242        1.000           0.900621 0.889655 0.972703 0.086661          -0.068323
psychologist partial_coverage_drop_cbcl            0.29   1.000000 0.155280        1.000           0.577640 0.268817 0.941175 0.296339          -0.391304
psychologist  partial_coverage_drop_sdq            0.29   0.986928 0.937888        0.984           0.960944 0.961783 0.986035 0.035155          -0.008000
psychologist       threshold_minus_0.05            0.24   0.905882 0.956522        0.872           0.914261 0.930514 0.986281 0.034229          -0.054683
psychologist        threshold_plus_0.05            0.34   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229           0.000000
