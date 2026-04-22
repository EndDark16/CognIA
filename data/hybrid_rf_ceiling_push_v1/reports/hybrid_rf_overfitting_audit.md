# Hybrid RF Overfitting Audit

## Summary
- evidencia_de_sobreentrenamiento: yes
- pares_con_bandera: 11/30

## Detailed table
| mode | domain | overfit_gap_train_val_ba | generalization_gap_val_holdout_ba | overfit_train_val | overfit_val_holdout | overfit_any |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.055406 | 0.035939 | False | False | False |
| caregiver_1_3 | anxiety | 0.098945 | 0.043236 | True | False | True |
| caregiver_1_3 | conduct | 0.058323 | 0.051927 | False | True | True |
| caregiver_1_3 | depression | 0.067187 | 0.083405 | True | True | True |
| caregiver_1_3 | elimination | 0.022351 | 0.014288 | False | False | False |
| caregiver_2_3 | adhd | 0.044179 | 0.030757 | False | False | False |
| caregiver_2_3 | anxiety | -0.000069 | 0.015435 | False | False | False |
| caregiver_2_3 | conduct | -0.001041 | 0.004673 | False | False | False |
| caregiver_2_3 | depression | 0.035082 | 0.053989 | False | True | True |
| caregiver_2_3 | elimination | 0.010005 | 0.010784 | False | False | False |
| caregiver_full | adhd | 0.038134 | 0.030620 | False | False | False |
| caregiver_full | anxiety | 0.012405 | -0.005814 | False | False | False |
| caregiver_full | conduct | -0.000520 | 0.004673 | False | False | False |
| caregiver_full | depression | 0.039215 | 0.055246 | False | True | True |
| caregiver_full | elimination | 0.018842 | 0.011952 | False | False | False |
| psychologist_1_3 | adhd | 0.065731 | 0.037234 | True | False | True |
| psychologist_1_3 | anxiety | 0.015681 | 0.035415 | False | False | False |
| psychologist_1_3 | conduct | 0.063542 | 0.045638 | True | False | True |
| psychologist_1_3 | depression | 0.064882 | 0.094344 | True | True | True |
| psychologist_1_3 | elimination | 0.040565 | 0.001168 | False | False | False |
| psychologist_2_3 | adhd | 0.045043 | 0.029462 | False | False | False |
| psychologist_2_3 | anxiety | 0.008529 | 0.015435 | False | False | False |
| psychologist_2_3 | conduct | -0.000520 | 0.003115 | False | False | False |
| psychologist_2_3 | depression | 0.038796 | 0.055246 | False | True | True |
| psychologist_2_3 | elimination | 0.028846 | 0.058861 | False | True | True |
| psychologist_full | adhd | 0.002159 | 0.019843 | False | False | False |
| psychologist_full | anxiety | 0.015858 | 0.010890 | False | False | False |
| psychologist_full | conduct | -0.000520 | 0.004673 | False | False | False |
| psychologist_full | depression | 0.035158 | 0.068513 | False | True | True |
| psychologist_full | elimination | 0.028846 | 0.040798 | False | False | False |

## Criteria
- train->val BA gap > 0.06
- val->holdout BA gap > 0.05
