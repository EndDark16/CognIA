# Hybrid RF Overfitting Audit

## Summary
- evidencia_de_sobreentrenamiento: yes
- pares_con_bandera: 8/30

## Detailed table
| mode | domain | overfit_gap_train_val_ba | generalization_gap_val_holdout_ba | overfit_train_val | overfit_val_holdout | overfit_any |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.006477 | 0.009205 | False | False | False |
| caregiver_1_3 | anxiety | 0.104582 | 0.044505 | True | False | True |
| caregiver_1_3 | conduct | 0.097066 | -0.022068 | True | False | True |
| caregiver_1_3 | depression | 0.074987 | 0.021878 | True | False | True |
| caregiver_1_3 | elimination | 0.075647 | 0.017793 | True | False | True |
| caregiver_2_3 | adhd | 0.032815 | 0.021139 | False | False | False |
| caregiver_2_3 | anxiety | 0.018888 | 0.012897 | False | False | False |
| caregiver_2_3 | conduct | -0.000520 | 0.000000 | False | False | False |
| caregiver_2_3 | depression | 0.038689 | 0.040722 | False | False | False |
| caregiver_2_3 | elimination | -0.002724 | 0.001168 | False | False | False |
| caregiver_full | adhd | 0.032521 | 0.003886 | False | False | False |
| caregiver_full | anxiety | 0.021603 | 0.005814 | False | False | False |
| caregiver_full | conduct | -0.000520 | 0.000000 | False | False | False |
| caregiver_full | depression | 0.033428 | 0.027087 | False | False | False |
| caregiver_full | elimination | -0.002724 | 0.001168 | False | False | False |
| psychologist_1_3 | adhd | 0.046200 | 0.015820 | False | False | False |
| psychologist_1_3 | anxiety | 0.050427 | 0.046512 | False | False | False |
| psychologist_1_3 | conduct | 0.101333 | -0.026858 | True | False | True |
| psychologist_1_3 | depression | 0.075819 | 0.043939 | True | False | True |
| psychologist_1_3 | elimination | 0.071202 | 0.046639 | True | False | True |
| psychologist_2_3 | adhd | 0.005613 | 0.015820 | False | False | False |
| psychologist_2_3 | anxiety | 0.017550 | 0.017442 | False | False | False |
| psychologist_2_3 | conduct | -0.000520 | 0.000000 | False | False | False |
| psychologist_2_3 | depression | 0.082101 | 0.009866 | True | False | True |
| psychologist_2_3 | elimination | -0.002724 | 0.001168 | False | False | False |
| psychologist_full | adhd | 0.001295 | 0.015820 | False | False | False |
| psychologist_full | anxiety | 0.016881 | 0.029070 | False | False | False |
| psychologist_full | conduct | -0.000520 | 0.000000 | False | False | False |
| psychologist_full | depression | 0.052136 | 0.027087 | False | False | False |
| psychologist_full | elimination | 0.000000 | 0.001168 | False | False | False |

## Criteria
- train->val BA gap > 0.06
- val->holdout BA gap > 0.05
