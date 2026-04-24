# Elimination operating modes v11

- objective prioritizes balanced_accuracy + recall + precision + PR-AUC + calibration proxy.

## Recommended per mode

        mode operating_mode  threshold  uncertainty_band  precision   recall  balanced_accuracy   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score
   caregiver       balanced       0.20              0.08   0.993421 0.937888           0.964944 0.985234 0.035061        0.391608                0.068863              0.994056
psychologist       balanced       0.29              0.08   1.000000 0.937888           0.968944 0.986281 0.034229        0.076923                0.109848              0.964336

## Full operating mode table

        mode           operating_mode  threshold  uncertainty_band  precision   recall  specificity  balanced_accuracy       f1   pr_auc    brier  uncertain_rate  uncertainty_usefulness  output_realism_score  objective
   caregiver                 balanced       0.20              0.08   0.993421 0.937888        0.992           0.964944 0.964856 0.985234 0.035061        0.391608                0.068863              0.994056   0.963438
   caregiver    uncertainty_preferred       0.20              0.14   0.993421 0.937888        0.992           0.964944 0.964856 0.985234 0.035061        0.444056                0.072451              0.994056   0.963438
   caregiver   recall_first_screening       0.64              0.08   1.000000 0.937888        1.000           0.968944 0.967949 0.985234 0.035061        0.003497               -0.035088              0.919507   0.962765
   caregiver conservative_probability       0.64              0.06   1.000000 0.937888        1.000           0.968944 0.967949 0.985234 0.035061        0.003497               -0.035088              0.919507   0.962765
psychologist                 balanced       0.29              0.08   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229        0.076923                0.109848              0.964336   0.964713
psychologist   recall_first_screening       0.29              0.08   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229        0.076923                0.109848              0.964336   0.964713
psychologist    uncertainty_preferred       0.29              0.14   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229        0.083916                0.098282              0.964336   0.964713
psychologist conservative_probability       0.29              0.06   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229        0.069930                0.123684              0.964336   0.964713
psychologist professional_detail_only       0.62              0.16   1.000000 0.937888        1.000           0.968944 0.967949 0.986281 0.034229        0.000000               -0.034965              0.919580   0.962923
