# Hybrid RF Overfitting Resolution

- candidates_with_overfit_warning: 3/13

| candidate_id | domain | mode | overfit_gap_train_val_ba | generalization_gap_val_holdout_ba | overfit_warning | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- |
| adhd__psychologist_2_3 | adhd | psychologist_2_3 | 0.045043 | 0.029462 | False | HOLD_FOR_TARGETED_FIX |
| adhd__psychologist_full | adhd | psychologist_full | 0.002159 | 0.019843 | False | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_2_3 | anxiety | caregiver_2_3 | -0.000069 | 0.015435 | False | PROMOTE_WITH_CAVEAT |
| anxiety__caregiver_full | anxiety | caregiver_full | 0.012405 | -0.005814 | False | PROMOTE_WITH_CAVEAT |
| conduct__caregiver_2_3 | conduct | caregiver_2_3 | -0.001041 | 0.004673 | False | PROMOTE_WITH_CAVEAT |
| conduct__psychologist_2_3 | conduct | psychologist_2_3 | -0.000520 | 0.003115 | False | PROMOTE_WITH_CAVEAT |
| conduct__psychologist_full | conduct | psychologist_full | -0.000520 | 0.004673 | False | PROMOTE_WITH_CAVEAT |
| depression__caregiver_2_3 | depression | caregiver_2_3 | 0.035082 | 0.053989 | True | HOLD_FOR_TARGETED_FIX |
| depression__caregiver_full | depression | caregiver_full | 0.039215 | 0.055246 | True | HOLD_FOR_TARGETED_FIX |
| depression__psychologist_full | depression | psychologist_full | 0.035158 | 0.068513 | True | HOLD_FOR_TARGETED_FIX |
| elimination__caregiver_2_3 | elimination | caregiver_2_3 | 0.010005 | 0.010784 | False | PROMOTE_WITH_CAVEAT |
| elimination__caregiver_full | elimination | caregiver_full | 0.018842 | 0.011952 | False | HOLD_FOR_TARGETED_FIX |
| elimination__psychologist_full | elimination | psychologist_full | 0.028846 | 0.040798 | False | HOLD_FOR_TARGETED_FIX |

- Rule: train-val BA gap > 0.06 or val-holdout BA gap > 0.05.
