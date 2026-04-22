# Hybrid RF Generalization Audit

## Summary
- evidencia_de_buena_generalizacion: yes
- pares_ok: 26/30

## Holdout performance matrix
| mode | domain | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.656489 | 0.914894 | 0.899157 | 0.637216 | 0.078694 |
| caregiver_1_3 | anxiety | 0.878788 | 0.674419 | 0.827057 | 0.850825 | 0.052025 |
| caregiver_1_3 | conduct | 0.837500 | 0.842767 | 0.880885 | 0.915839 | 0.073995 |
| caregiver_1_3 | depression | 0.725000 | 0.707317 | 0.826020 | 0.738850 | 0.073784 |
| caregiver_1_3 | elimination | 0.803279 | 0.942308 | 0.957135 | 0.859292 | 0.024549 |
| caregiver_2_3 | adhd | 0.767857 | 0.914894 | 0.923768 | 0.808890 | 0.053512 |
| caregiver_2_3 | anxiety | 0.891304 | 0.953488 | 0.964054 | 0.929693 | 0.021603 |
| caregiver_2_3 | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001196 |
| caregiver_2_3 | depression | 0.847222 | 0.743902 | 0.858132 | 0.862956 | 0.052005 |
| caregiver_2_3 | elimination | 0.961538 | 0.961538 | 0.978433 | 0.974532 | 0.006001 |
| caregiver_full | adhd | 0.769912 | 0.925532 | 0.929087 | 0.768268 | 0.053527 |
| caregiver_full | anxiety | 0.941860 | 0.941860 | 0.964585 | 0.957131 | 0.020587 |
| caregiver_full | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001218 |
| caregiver_full | depression | 0.835616 | 0.743902 | 0.856876 | 0.869977 | 0.050932 |
| caregiver_full | elimination | 0.960784 | 0.942308 | 0.968817 | 0.959900 | 0.008054 |
| psychologist_1_3 | adhd | 0.677966 | 0.851064 | 0.876309 | 0.684220 | 0.074587 |
| psychologist_1_3 | anxiety | 0.900000 | 0.732558 | 0.857396 | 0.889588 | 0.041843 |
| psychologist_1_3 | conduct | 0.839506 | 0.855346 | 0.887175 | 0.913473 | 0.073242 |
| psychologist_1_3 | depression | 0.716049 | 0.707317 | 0.824764 | 0.745249 | 0.073161 |
| psychologist_1_3 | elimination | 0.867925 | 0.884615 | 0.934130 | 0.924453 | 0.018283 |
| psychologist_2_3 | adhd | 0.774775 | 0.914894 | 0.925063 | 0.769329 | 0.054965 |
| psychologist_2_3 | anxiety | 0.908046 | 0.918605 | 0.949150 | 0.939733 | 0.024940 |
| psychologist_2_3 | conduct | 0.987578 | 1.000000 | 0.996885 | 1.000000 | 0.001286 |
| psychologist_2_3 | depression | 0.835616 | 0.743902 | 0.856876 | 0.777922 | 0.058654 |
| psychologist_2_3 | elimination | 0.977273 | 0.826923 | 0.912293 | 0.974507 | 0.009834 |
| psychologist_full | adhd | 0.947917 | 0.968085 | 0.977566 | 0.945106 | 0.015459 |
| psychologist_full | anxiety | 0.896552 | 0.906977 | 0.942067 | 0.954613 | 0.022701 |
| psychologist_full | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001176 |
| psychologist_full | depression | 0.890625 | 0.695122 | 0.838767 | 0.900358 | 0.046736 |
| psychologist_full | elimination | 0.957447 | 0.865385 | 0.930356 | 0.952276 | 0.011423 |

## Stability matrix
| mode | domain | seed_std_val_balanced_accuracy | precision_boot_ci_low | precision_boot_ci_high | balanced_accuracy_boot_ci_low | balanced_accuracy_boot_ci_high |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.008758 | 0.573704 | 0.722351 | 0.867525 | 0.932102 |
| caregiver_1_3 | anxiety | 0.010413 | 0.793839 | 0.951038 | 0.782043 | 0.879087 |
| caregiver_1_3 | conduct | 0.000902 | 0.777583 | 0.891314 | 0.846773 | 0.911071 |
| caregiver_1_3 | depression | 0.009916 | 0.624436 | 0.806143 | 0.773711 | 0.874451 |
| caregiver_1_3 | elimination | 0.000674 | 0.687009 | 0.896031 | 0.922552 | 0.985042 |
| caregiver_2_3 | adhd | 0.005394 | 0.691208 | 0.843863 | 0.893383 | 0.954757 |
| caregiver_2_3 | anxiety | 0.000000 | 0.836354 | 0.953488 | 0.932144 | 0.984333 |
| caregiver_2_3 | conduct | 0.000000 | 0.960631 | 1.000000 | 0.990286 | 1.000000 |
| caregiver_2_3 | depression | 0.000000 | 0.758635 | 0.922393 | 0.808434 | 0.903497 |
| caregiver_2_3 | elimination | 0.000000 | 0.904510 | 1.000000 | 0.954377 | 0.998030 |
| caregiver_full | adhd | 0.005804 | 0.694732 | 0.842783 | 0.903318 | 0.958387 |
| caregiver_full | anxiety | 0.000000 | 0.896140 | 0.987991 | 0.932689 | 0.987609 |
| caregiver_full | conduct | 0.000000 | 0.960631 | 1.000000 | 0.990286 | 1.000000 |
| caregiver_full | depression | 0.000000 | 0.743590 | 0.909091 | 0.807661 | 0.907384 |
| caregiver_full | elimination | 0.005247 | 0.901768 | 1.000000 | 0.928700 | 0.998844 |
| psychologist_1_3 | adhd | 0.004900 | 0.591825 | 0.751206 | 0.835705 | 0.911792 |
| psychologist_1_3 | anxiety | 0.028438 | 0.811379 | 0.957627 | 0.808161 | 0.904138 |
| psychologist_1_3 | conduct | 0.002387 | 0.789630 | 0.896714 | 0.852381 | 0.917704 |
| psychologist_1_3 | depression | 0.006714 | 0.609027 | 0.797689 | 0.768652 | 0.874924 |
| psychologist_1_3 | elimination | 0.018058 | 0.753420 | 0.948276 | 0.884921 | 0.975935 |
| psychologist_2_3 | adhd | 0.000827 | 0.701629 | 0.842783 | 0.894137 | 0.950900 |
| psychologist_2_3 | anxiety | 0.005981 | 0.855034 | 0.964202 | 0.915379 | 0.976811 |
| psychologist_2_3 | conduct | 0.000000 | 0.968040 | 1.000000 | 0.992220 | 1.000000 |
| psychologist_2_3 | depression | 0.003520 | 0.748974 | 0.916981 | 0.806334 | 0.902087 |
| psychologist_2_3 | elimination | 0.004877 | 0.923077 | 1.000000 | 0.857355 | 0.959619 |
| psychologist_full | adhd | 0.000000 | 0.903226 | 0.988235 | 0.959856 | 0.992703 |
| psychologist_full | anxiety | 0.008752 | 0.829065 | 0.955957 | 0.907118 | 0.970828 |
| psychologist_full | conduct | 0.000000 | 0.960631 | 1.000000 | 0.990286 | 1.000000 |
| psychologist_full | depression | 0.003520 | 0.803491 | 0.965239 | 0.786958 | 0.884170 |
| psychologist_full | elimination | 0.004877 | 0.891730 | 1.000000 | 0.883727 | 0.972659 |
