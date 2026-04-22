# Hybrid RF Domain/Mode Analysis

## Winner table
| mode | domain | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | ceiling_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| caregiver_1_3 | adhd | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 | marginal_room_left |
| caregiver_1_3 | anxiety | 0.900000 | 0.627907 | 0.806339 | 0.803065 | 0.059892 | ceiling_reached |
| caregiver_1_3 | conduct | 0.884146 | 0.906250 | 0.923438 | 0.932896 | 0.056245 | ceiling_reached |
| caregiver_1_3 | depression | 0.758242 | 0.841463 | 0.893094 | 0.797190 | 0.055149 | marginal_room_left |
| caregiver_1_3 | elimination | 0.781818 | 0.826923 | 0.899443 | 0.938264 | 0.022472 | marginal_room_left |
| caregiver_2_3 | adhd | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 | marginal_room_left |
| caregiver_2_3 | anxiety | 0.950000 | 0.883721 | 0.936784 | 0.940513 | 0.020749 | marginal_room_left |
| caregiver_2_3 | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000455 | ceiling_reached |
| caregiver_2_3 | depression | 0.750000 | 0.878049 | 0.908874 | 0.880904 | 0.046740 | marginal_room_left |
| caregiver_2_3 | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 | marginal_room_left |
| caregiver_full | adhd | 0.744000 | 0.989362 | 0.953230 | 0.769742 | 0.053720 | marginal_room_left |
| caregiver_full | anxiety | 0.911111 | 0.953488 | 0.966592 | 0.933569 | 0.025594 | marginal_room_left |
| caregiver_full | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000416 | ceiling_reached |
| caregiver_full | depression | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 | marginal_room_left |
| caregiver_full | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000826 | marginal_room_left |
| psychologist_1_3 | adhd | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 | marginal_room_left |
| psychologist_1_3 | anxiety | 0.887500 | 0.825581 | 0.901369 | 0.929537 | 0.043643 | ceiling_reached |
| psychologist_1_3 | conduct | 0.916129 | 0.887500 | 0.923437 | 0.940778 | 0.059582 | marginal_room_left |
| psychologist_1_3 | depression | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 | marginal_room_left |
| psychologist_1_3 | elimination | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 | marginal_room_left |
| psychologist_2_3 | adhd | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 | marginal_room_left |
| psychologist_2_3 | anxiety | 0.919540 | 0.930233 | 0.956233 | 0.942496 | 0.024691 | marginal_room_left |
| psychologist_2_3 | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000657 | marginal_room_left |
| psychologist_2_3 | depression | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 | marginal_room_left |
| psychologist_2_3 | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000437 | marginal_room_left |
| psychologist_full | adhd | 0.948454 | 0.978723 | 0.982885 | 0.980874 | 0.010648 | marginal_room_left |
| psychologist_full | anxiety | 0.917647 | 0.906977 | 0.944605 | 0.941091 | 0.028518 | marginal_room_left |
| psychologist_full | conduct | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000006 | marginal_room_left |
| psychologist_full | depression | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 | marginal_room_left |
| psychologist_full | elimination | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000078 | marginal_room_left |

## Answers to requested questions
1. Mejor modelo por dominio y modo: ver [tables/hybrid_rf_mode_domain_winners.csv](../tables/hybrid_rf_mode_domain_winners.csv).
2. Mejor modo global cuidador: caregiver_full.
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
