# Hybrid RF Final Ceiling Push v3 - Modeling Inventory

## Inventory Table
| item | value |
| --- | --- |
| campaign_line | hybrid_rf_final_ceiling_push_v3 |
| dataset_path | data/hybrid_dsm5_rebuild_v1/hybrid_dataset_synthetic_complete_final.csv |
| n_rows_dataset | 2400 |
| n_columns_dataset | 224 |
| n_domains | 5 |
| n_modes | 6 |
| n_mode_domain_pairs | 30 |
| rf_configs_explored | 6 |
| threshold_policies_explored | 5 |
| calibrations_explored | none\|sigmoid\|isotonic |
| stage2_seeds | 20260712\|20260729 |
| trial_count_total | 2850 |
| winner_count | 30 |
| generated_at_utc | 2026-04-13T02:45:26.099478+00:00 |

## Notes
- Main model family: RandomForestClassifier.
- Holdout split remained untouched during search; used only for winner validation/audit.
- Targets were detected from current hybrid dataset columns and documented in domain_target_registry.
