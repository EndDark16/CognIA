# Hybrid RF Generalization Audit

## Summary
- evidencia_de_buena_generalizacion: yes
- pares_ok: 25/30

## Holdout performance matrix
| mode | domain | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 |
| caregiver_1_3 | anxiety | 0.900000 | 0.627907 | 0.806339 | 0.803065 | 0.059892 |
| caregiver_1_3 | conduct | 0.884146 | 0.906250 | 0.923438 | 0.932896 | 0.056245 |
| caregiver_1_3 | depression | 0.758242 | 0.841463 | 0.893094 | 0.797190 | 0.055149 |
| caregiver_1_3 | elimination | 0.781818 | 0.826923 | 0.899443 | 0.938264 | 0.022472 |
| caregiver_2_3 | adhd | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 |
| caregiver_2_3 | anxiety | 0.950000 | 0.883721 | 0.936784 | 0.940513 | 0.020749 |
| caregiver_2_3 | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000455 |
| caregiver_2_3 | depression | 0.750000 | 0.878049 | 0.908874 | 0.880904 | 0.046740 |
| caregiver_2_3 | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 |
| caregiver_full | adhd | 0.744000 | 0.989362 | 0.953230 | 0.769742 | 0.053720 |
| caregiver_full | anxiety | 0.911111 | 0.953488 | 0.966592 | 0.933569 | 0.025594 |
| caregiver_full | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000416 |
| caregiver_full | depression | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 |
| caregiver_full | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000826 |
| psychologist_1_3 | adhd | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 |
| psychologist_1_3 | anxiety | 0.887500 | 0.825581 | 0.901369 | 0.929537 | 0.043643 |
| psychologist_1_3 | conduct | 0.916129 | 0.887500 | 0.923437 | 0.940778 | 0.059582 |
| psychologist_1_3 | depression | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 |
| psychologist_1_3 | elimination | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 |
| psychologist_2_3 | adhd | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 |
| psychologist_2_3 | anxiety | 0.919540 | 0.930233 | 0.956233 | 0.942496 | 0.024691 |
| psychologist_2_3 | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000657 |
| psychologist_2_3 | depression | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 |
| psychologist_2_3 | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000437 |
| psychologist_full | adhd | 0.948454 | 0.978723 | 0.982885 | 0.980874 | 0.010648 |
| psychologist_full | anxiety | 0.917647 | 0.906977 | 0.944605 | 0.941091 | 0.028518 |
| psychologist_full | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000006 |
| psychologist_full | depression | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 |
| psychologist_full | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000078 |

## Stability matrix
| mode | domain | seed_std_val_balanced_accuracy | precision_boot_ci_low | precision_boot_ci_high | balanced_accuracy_boot_ci_low | balanced_accuracy_boot_ci_high |
| --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.004677 | 0.544002 | 0.692548 | 0.901131 | 0.942637 |
| caregiver_1_3 | anxiety | 0.006427 | 0.822581 | 0.965094 | 0.758373 | 0.856791 |
| caregiver_1_3 | conduct | 0.013446 | 0.829191 | 0.928028 | 0.893333 | 0.949763 |
| caregiver_1_3 | depression | 0.002535 | 0.670239 | 0.831395 | 0.850093 | 0.929564 |
| caregiver_1_3 | elimination | 0.000826 | 0.668197 | 0.883882 | 0.844412 | 0.950187 |
| caregiver_2_3 | adhd | 0.001832 | 0.642407 | 0.800000 | 0.914344 | 0.962379 |
| caregiver_2_3 | anxiety | 0.000000 | 0.898330 | 0.997443 | 0.906004 | 0.969679 |
| caregiver_2_3 | conduct | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| caregiver_2_3 | depression | 0.000888 | 0.676391 | 0.823266 | 0.875969 | 0.945838 |
| caregiver_2_3 | elimination | 0.000000 | 0.938063 | 1.000000 | 0.996450 | 1.000000 |
| caregiver_full | adhd | 0.002845 | 0.665225 | 0.821429 | 0.938756 | 0.970865 |
| caregiver_full | anxiety | 0.000000 | 0.853333 | 0.962646 | 0.938281 | 0.988593 |
| caregiver_full | conduct | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| caregiver_full | depression | 0.000000 | 0.724276 | 0.875999 | 0.893828 | 0.964878 |
| caregiver_full | elimination | 0.000000 | 0.938063 | 1.000000 | 0.996450 | 1.000000 |
| psychologist_1_3 | adhd | 0.000916 | 0.543735 | 0.684831 | 0.894631 | 0.935781 |
| psychologist_1_3 | anxiety | 0.000897 | 0.820364 | 0.942783 | 0.853274 | 0.939245 |
| psychologist_1_3 | conduct | 0.014589 | 0.865375 | 0.955536 | 0.890908 | 0.948396 |
| psychologist_1_3 | depression | 0.006088 | 0.679794 | 0.846649 | 0.832381 | 0.912879 |
| psychologist_1_3 | elimination | 0.012772 | 0.675217 | 0.893446 | 0.819270 | 0.934957 |
| psychologist_2_3 | adhd | 0.000000 | 0.639558 | 0.795232 | 0.923658 | 0.962411 |
| psychologist_2_3 | anxiety | 0.000000 | 0.861305 | 0.967311 | 0.928626 | 0.984882 |
| psychologist_2_3 | conduct | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| psychologist_2_3 | depression | 0.000000 | 0.821901 | 0.961570 | 0.848192 | 0.938839 |
| psychologist_2_3 | elimination | 0.000000 | 0.938063 | 1.000000 | 0.996450 | 1.000000 |
| psychologist_full | adhd | 0.000000 | 0.902756 | 0.988514 | 0.965741 | 0.995083 |
| psychologist_full | anxiety | 0.000000 | 0.859155 | 0.966206 | 0.913483 | 0.974182 |
| psychologist_full | conduct | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| psychologist_full | depression | 0.005958 | 0.741790 | 0.904007 | 0.869946 | 0.944265 |
| psychologist_full | elimination | 0.000000 | 0.938063 | 1.000000 | 0.996450 | 1.000000 |
