# Elimination base summary v11

- dataset: `C:\Users\andre\Documents\Workspace Academic\Backend Tesis\cognia_app\data\processed_hybrid_dsm5_v2\final\model_ready\strict_no_leakage_hybrid\dataset_hybrid_model_ready_strict_no_leakage_hybrid.csv`
- split_dir: `C:\Users\andre\Documents\Workspace Academic\Backend Tesis\cognia_app\data\processed_hybrid_dsm5_v2\splits\domain_elimination_strict_full`
- baseline rows loaded: 2
- strict_no_leakage rows: 1905
- strict_no_leakage cols: 1018
- engineered features generated: 28

## Baseline by mode

        mode      domain                    baseline_source model_family feature_variant  n_features  precision   recall  specificity  balanced_accuracy       f1    brier  threshold  uncertainty_band calibration                                  current_caveat                              known_problem
   caregiver elimination final_hardening_v10 baseline trial     lightgbm      engineered          30   0.918699 0.701863        0.920           0.810932 0.795775 0.148582      0.505              0.07    isotonic experimental_line_more_useful_not_product_ready recall_bottleneck_and_source_mix_fragility
psychologist elimination final_hardening_v10 baseline trial     lightgbm      engineered          31   0.925620 0.695652        0.928           0.811826 0.794326 0.144576      0.505              0.07    isotonic experimental_line_more_useful_not_product_ready recall_bottleneck_and_source_mix_fragility

## Known open weaknesses (v10)

        mode                weakness_type                        metric_name  metric_value                                                             note
   caregiver                fragile_slice delta_balanced_accuracy_vs_overall     -0.114555                         Fragile slice source_mix=mid_gap (n=53).
psychologist                fragile_slice delta_balanced_accuracy_vs_overall     -0.115449                         Fragile slice source_mix=mid_gap (n=53).
   caregiver                   low_recall                             recall      0.701863                  Recall below desired hardening target (>=0.82).
psychologist                   low_recall                             recall      0.695652                  Recall below desired hardening target (>=0.82).
   caregiver output_caveat_or_uncertainty                risk_uncertain_rate      0.164336           High uncertain/caveat pressure in operational outputs.
psychologist output_caveat_or_uncertainty                risk_uncertain_rate      0.006993           High uncertain/caveat pressure in operational outputs.
   caregiver        source_mix_shift_risk                   flagged_patterns      1.000000 Pattern-level signal suggests source/coverage shift sensitivity.
psychologist        source_mix_shift_risk                   flagged_patterns      1.000000 Pattern-level signal suggests source/coverage shift sensitivity.

## Calibration registry reference (v10)

        mode      domain  v9_threshold      selected_policy  selected_threshold probability_source  uncertainty_band         selection_reason  precision   recall  specificity  balanced_accuracy       f1    brier
   caregiver elimination         0.505 light_ensemble_blend               0.505         prob_blend              0.08 elimination_final_attack    0.92000 0.714286        0.920           0.817143 0.804196 0.146346
psychologist elimination         0.505 recall_first_low_thr               0.425        probability              0.08 elimination_final_attack    0.92623 0.701863        0.928           0.814932 0.798587 0.144576
