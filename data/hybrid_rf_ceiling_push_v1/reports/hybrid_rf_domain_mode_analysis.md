# Hybrid RF Domain/Mode Analysis

## Winner table
| mode | domain | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | ceiling_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.656489 | 0.914894 | 0.899157 | 0.637216 | 0.078694 | marginal_room_left |
| caregiver_1_3 | anxiety | 0.878788 | 0.674419 | 0.827057 | 0.850825 | 0.052025 | ceiling_reached |
| caregiver_1_3 | conduct | 0.837500 | 0.842767 | 0.880885 | 0.915839 | 0.073995 | ceiling_reached |
| caregiver_1_3 | depression | 0.725000 | 0.707317 | 0.826020 | 0.738850 | 0.073784 | ceiling_reached |
| caregiver_1_3 | elimination | 0.803279 | 0.942308 | 0.957135 | 0.859292 | 0.024549 | marginal_room_left |
| caregiver_2_3 | adhd | 0.767857 | 0.914894 | 0.923768 | 0.808890 | 0.053512 | marginal_room_left |
| caregiver_2_3 | anxiety | 0.891304 | 0.953488 | 0.964054 | 0.929693 | 0.021603 | marginal_room_left |
| caregiver_2_3 | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001196 | ceiling_reached |
| caregiver_2_3 | depression | 0.847222 | 0.743902 | 0.858132 | 0.862956 | 0.052005 | marginal_room_left |
| caregiver_2_3 | elimination | 0.961538 | 0.961538 | 0.978433 | 0.974532 | 0.006001 | marginal_room_left |
| caregiver_full | adhd | 0.769912 | 0.925532 | 0.929087 | 0.768268 | 0.053527 | marginal_room_left |
| caregiver_full | anxiety | 0.941860 | 0.941860 | 0.964585 | 0.957131 | 0.020587 | marginal_room_left |
| caregiver_full | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001218 | marginal_room_left |
| caregiver_full | depression | 0.835616 | 0.743902 | 0.856876 | 0.869977 | 0.050932 | marginal_room_left |
| caregiver_full | elimination | 0.960784 | 0.942308 | 0.968817 | 0.959900 | 0.008054 | marginal_room_left |
| psychologist_1_3 | adhd | 0.677966 | 0.851064 | 0.876309 | 0.684220 | 0.074587 | marginal_room_left |
| psychologist_1_3 | anxiety | 0.900000 | 0.732558 | 0.857396 | 0.889588 | 0.041843 | ceiling_reached |
| psychologist_1_3 | conduct | 0.839506 | 0.855346 | 0.887175 | 0.913473 | 0.073242 | ceiling_reached |
| psychologist_1_3 | depression | 0.716049 | 0.707317 | 0.824764 | 0.745249 | 0.073161 | ceiling_reached |
| psychologist_1_3 | elimination | 0.867925 | 0.884615 | 0.934130 | 0.924453 | 0.018283 | marginal_room_left |
| psychologist_2_3 | adhd | 0.774775 | 0.914894 | 0.925063 | 0.769329 | 0.054965 | marginal_room_left |
| psychologist_2_3 | anxiety | 0.908046 | 0.918605 | 0.949150 | 0.939733 | 0.024940 | marginal_room_left |
| psychologist_2_3 | conduct | 0.987578 | 1.000000 | 0.996885 | 1.000000 | 0.001286 | ceiling_reached |
| psychologist_2_3 | depression | 0.835616 | 0.743902 | 0.856876 | 0.777922 | 0.058654 | marginal_room_left |
| psychologist_2_3 | elimination | 0.977273 | 0.826923 | 0.912293 | 0.974507 | 0.009834 | marginal_room_left |
| psychologist_full | adhd | 0.947917 | 0.968085 | 0.977566 | 0.945106 | 0.015459 | marginal_room_left |
| psychologist_full | anxiety | 0.896552 | 0.906977 | 0.942067 | 0.954613 | 0.022701 | marginal_room_left |
| psychologist_full | conduct | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001176 | marginal_room_left |
| psychologist_full | depression | 0.890625 | 0.695122 | 0.838767 | 0.900358 | 0.046736 | marginal_room_left |
| psychologist_full | elimination | 0.957447 | 0.865385 | 0.930356 | 0.952276 | 0.011423 | marginal_room_left |

## Answers to requested questions
1. Mejor modelo por dominio y modo: ver [tables/hybrid_rf_mode_domain_winners.csv](../tables/hybrid_rf_mode_domain_winners.csv).
2. Mejor modo global cuidador: caregiver_2_3.
3. Mejor modo global psicologo: psychologist_full.
4. Perdida 1/3->2/3 y 2/3->full: ver [tables/hybrid_rf_mode_step_losses.csv](../tables/hybrid_rf_mode_step_losses.csv).
5. Dominios mas afectados en modos cortos: revisar mayores caidas de BA/precision en `hybrid_rf_mode_step_losses.csv`.
6. Subidas de precision sin romper recall: ver `hybrid_rf_mode_domain_delta_vs_baseline.csv` (material_improvement=yes).
7. Donde aparece sobreentrenamiento: ver `hybrid_rf_overfitting_audit.md` y columna `overfit_warning`.
8. Donde calibracion mejora: ver `calibration/hybrid_rf_calibration_results.csv` por delta de brier/ece.
9. Donde llegamos al techo: ver `ceiling_status` en winners.
10. Combinaciones a descartar: trials con `overfit_gap_ba` alto y sin mejora material.
11. Defendibilidad de modos cortos: defendibles cuando BA>=0.75, precision>=0.75 y recall>=0.55.
12. Dataset hibrido mejora frente a anterior: yes.
13. Subset mas robusto: revisar winners por frecuencia de `winner_feature_set_id` y estabilidad bootstrap.
14. Aporte DSM-5 explicito: comparado via subsets compactos vs full; mantener si mejora material y no degrada robustez.
15. Generalizacion suficiente para cierre: yes.
