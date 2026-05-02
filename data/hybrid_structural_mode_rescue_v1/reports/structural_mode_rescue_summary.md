# Hybrid Structural Mode Rescue v1

- generated_at_utc: 2026-04-26T04:22:47.686121+00:00
- source_active: data\hybrid_active_modes_freeze_v6_hotfix_v1\tables\hybrid_active_models_30_modes.csv
- source_operational: data\hybrid_operational_freeze_v6_hotfix_v1\tables\hybrid_operational_final_champions.csv
- output_active: data\hybrid_active_modes_freeze_v8\tables\hybrid_active_models_30_modes.csv
- output_operational: data\hybrid_operational_freeze_v8\tables\hybrid_operational_final_champions.csv
- blacklisted_active_initial: 14
- blacklisted_active_final: 0
- structural_extra_rescue_initial: 3
- structural_extra_rescue_final: 0
- single_feature_active_final: 0
- guardrail_violations_initial: 0
- guardrail_violations_final: 0
- retrained_structural_replacements: 17
- accepted_existing_fallbacks: 0

## Corrected Slots
| domain | mode | old_active_model_id | new_active_model_id | old_f1 | new_f1 | old_recall | new_recall | old_precision | new_precision | old_balanced_accuracy | new_balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver_1_3 | adhd__caregiver_1_3__rebuild_v2__rf__engineered_full | adhd__caregiver_1_3__hybrid_structural_mode_rescue_v1__rf__structural_dsm5_plus_context_1_3 | 0.725664 | 0.801843 | 0.872340 | 0.925532 | 0.621212 | 0.707317 | 0.871403 | 0.916134 |
| adhd | caregiver_2_3 | adhd__caregiver_2_3__rebuild_v2__rf__engineered_compact | adhd__caregiver_2_3__hybrid_structural_mode_rescue_v1__rf__structural_compact_2_3 | 0.769231 | 0.809091 | 0.851064 | 0.946809 | 0.701754 | 0.706349 | 0.881490 | 0.925477 |
| adhd | psychologist_1_3 | adhd__psychologist_1_3__rebuild_v2__rf__engineered_compact | adhd__psychologist_1_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_1_3 | 0.724891 | 0.762332 | 0.882979 | 0.904255 | 0.614815 | 0.658915 | 0.874132 | 0.895133 |
| adhd | psychologist_2_3 | adhd__psychologist_2_3__rebuild_v2__rf__engineered_pruned | adhd__psychologist_2_3__hybrid_structural_mode_rescue_v1__logreg__structural_ranked_2_3 | 0.776119 | 0.824121 | 0.829787 | 0.872340 | 0.728972 | 0.780952 | 0.877329 | 0.906377 |
| anxiety | psychologist_1_3 | anxiety__psychologist_1_3__v6_hotfix_v1__hgb__engineered_full | anxiety__psychologist_1_3__hybrid_structural_mode_rescue_v1__logreg__registry_stability_pruned_subset | 0.849462 | 0.810256 | 0.918605 | 0.918605 | 0.790000 | 0.724771 | 0.932653 | 0.921231 |
| anxiety | psychologist_full | anxiety__psychologist_full__v6_hotfix_v1__logreg__dsm5_core_single__sep_anx_symptom_count | anxiety__psychologist_full__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_full | 0.817204 | 0.840909 | 0.883721 | 0.860465 | 0.760000 | 0.822222 | 0.911404 | 0.909928 |
| conduct | caregiver_2_3 | conduct__caregiver_2_3__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | conduct__caregiver_2_3__hybrid_structural_mode_rescue_v1__logreg__registry_stability_pruned_subset | 0.862876 | 0.887574 | 0.806250 | 0.937500 | 0.928058 | 0.842697 | 0.887500 | 0.925000 |
| depression | caregiver_1_3 | depression__caregiver_1_3__rebuild_v2__rf__precision_oriented_subset | depression__caregiver_1_3__hybrid_structural_mode_rescue_v1__rf__structural_ranked_1_3 | 0.724832 | 0.845714 | 0.658537 | 0.902439 | 0.805970 | 0.795699 | 0.812937 | 0.927350 |
| depression | caregiver_2_3 | depression__caregiver_2_3__hybrid_final_decisive_rescue_v5__rf__precision_oriented_subset | depression__caregiver_2_3__hybrid_structural_mode_rescue_v1__extra_trees__structural_compact_2_3 | 0.836158 | 0.852273 | 0.902439 | 0.914634 | 0.778947 | 0.797872 | 0.924838 | 0.933448 |
| depression | psychologist_1_3 | depression__psychologist_1_3__rebuild_v2__rf__stability_pruned_subset | depression__psychologist_1_3__hybrid_structural_mode_rescue_v1__rf__structural_compact_1_3 | 0.782609 | 0.822086 | 0.768293 | 0.817073 | 0.797468 | 0.827160 | 0.864046 | 0.890949 |
| depression | psychologist_2_3 | depression__psychologist_2_3__final_honest_improvement_v1__rf__compact_subset | depression__psychologist_2_3__hybrid_structural_mode_rescue_v1__extra_trees__structural_compact_2_3 | 0.840909 | 0.849162 | 0.902439 | 0.926829 | 0.787234 | 0.783505 | 0.926094 | 0.937033 |
| elimination | caregiver_1_3 | elimination__caregiver_1_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__caregiver_1_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_1_3 | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |
| elimination | caregiver_2_3 | elimination__caregiver_2_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__caregiver_2_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_2_3 | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |
| elimination | caregiver_full | elimination__caregiver_full__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__caregiver_full__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_full | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |
| elimination | psychologist_1_3 | elimination__psychologist_1_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__psychologist_1_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_1_3 | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |
| elimination | psychologist_2_3 | elimination__psychologist_2_3__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__psychologist_2_3__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_2_3 | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |
| elimination | psychologist_full | elimination__psychologist_full__v6_hotfix_v1__logreg__dsm5_core_single__enuresis_duration_months_consecutive | elimination__psychologist_full__hybrid_structural_mode_rescue_v1__hgb__structural_ranked_full | 0.828829 | 0.844037 | 0.884615 | 0.884615 | 0.779661 | 0.807018 | 0.927121 | 0.929457 |

## Structural Subsets
| domain | role | mode | feature_set_id | full_universe_n | target_n | n_features |
| --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver | caregiver_1_3 | structural_ranked_1_3 | 126 | 42 | 42 |
| adhd | caregiver | caregiver_1_3 | structural_dsm5_plus_context_1_3 | 126 | 42 | 36 |
| adhd | caregiver | caregiver_1_3 | structural_compact_1_3 | 126 | 42 | 34 |
| adhd | caregiver | caregiver_1_3 | structural_pruned_1_3 | 126 | 42 | 42 |
| adhd | caregiver | caregiver_1_3 | registry_stability_pruned_subset | 126 | 42 | 24 |
| adhd | caregiver | caregiver_2_3 | structural_ranked_2_3 | 126 | 84 | 84 |
| adhd | caregiver | caregiver_2_3 | structural_dsm5_plus_context_2_3 | 126 | 84 | 56 |
| adhd | caregiver | caregiver_2_3 | structural_compact_2_3 | 126 | 84 | 69 |
| adhd | caregiver | caregiver_2_3 | structural_pruned_2_3 | 126 | 84 | 84 |
| adhd | caregiver | caregiver_2_3 | registry_stability_pruned_subset | 126 | 84 | 49 |
| adhd | caregiver | caregiver_full | structural_ranked_full | 126 | 126 | 126 |
| adhd | caregiver | caregiver_full | structural_dsm5_plus_context_full | 126 | 126 | 91 |
| adhd | caregiver | caregiver_full | structural_compact_full | 126 | 126 | 103 |
| adhd | caregiver | caregiver_full | structural_pruned_full | 126 | 126 | 119 |
| adhd | psychologist | psychologist_1_3 | structural_ranked_1_3 | 151 | 50 | 50 |
| adhd | psychologist | psychologist_1_3 | structural_dsm5_plus_context_1_3 | 151 | 50 | 44 |
| adhd | psychologist | psychologist_1_3 | structural_compact_1_3 | 151 | 50 | 41 |
| adhd | psychologist | psychologist_1_3 | structural_pruned_1_3 | 151 | 50 | 50 |
| adhd | psychologist | psychologist_1_3 | registry_stability_pruned_subset | 151 | 50 | 30 |
| adhd | psychologist | psychologist_2_3 | structural_ranked_2_3 | 151 | 101 | 101 |
| adhd | psychologist | psychologist_2_3 | structural_dsm5_plus_context_2_3 | 151 | 101 | 66 |
| adhd | psychologist | psychologist_2_3 | structural_compact_2_3 | 151 | 101 | 83 |
| adhd | psychologist | psychologist_2_3 | structural_pruned_2_3 | 151 | 101 | 101 |
| adhd | psychologist | psychologist_full | structural_ranked_full | 151 | 151 | 151 |
| adhd | psychologist | psychologist_full | structural_dsm5_plus_context_full | 151 | 151 | 101 |
| adhd | psychologist | psychologist_full | structural_compact_full | 151 | 151 | 124 |
| adhd | psychologist | psychologist_full | structural_pruned_full | 151 | 151 | 144 |
| anxiety | caregiver | caregiver_full | structural_ranked_full | 126 | 126 | 126 |
| anxiety | caregiver | caregiver_full | structural_dsm5_plus_context_full | 126 | 126 | 86 |
| anxiety | caregiver | caregiver_full | structural_compact_full | 126 | 126 | 103 |
| anxiety | caregiver | caregiver_full | structural_pruned_full | 126 | 126 | 119 |
| anxiety | psychologist | psychologist_1_3 | structural_ranked_1_3 | 151 | 50 | 50 |
| anxiety | psychologist | psychologist_1_3 | structural_dsm5_plus_context_1_3 | 151 | 50 | 48 |
| anxiety | psychologist | psychologist_1_3 | structural_compact_1_3 | 151 | 50 | 41 |
| anxiety | psychologist | psychologist_1_3 | structural_pruned_1_3 | 151 | 50 | 50 |
| anxiety | psychologist | psychologist_1_3 | registry_stability_pruned_subset | 151 | 50 | 30 |
| anxiety | psychologist | psychologist_full | structural_ranked_full | 151 | 151 | 151 |
| anxiety | psychologist | psychologist_full | structural_dsm5_plus_context_full | 151 | 151 | 105 |
| anxiety | psychologist | psychologist_full | structural_compact_full | 151 | 151 | 124 |
| anxiety | psychologist | psychologist_full | structural_pruned_full | 151 | 151 | 144 |
| conduct | caregiver | caregiver_2_3 | structural_ranked_2_3 | 126 | 84 | 84 |
| conduct | caregiver | caregiver_2_3 | structural_dsm5_plus_context_2_3 | 126 | 84 | 67 |
| conduct | caregiver | caregiver_2_3 | structural_compact_2_3 | 126 | 84 | 69 |
| conduct | caregiver | caregiver_2_3 | structural_pruned_2_3 | 126 | 84 | 84 |
| conduct | caregiver | caregiver_2_3 | registry_stability_pruned_subset | 126 | 84 | 49 |
| conduct | caregiver | caregiver_full | structural_ranked_full | 126 | 126 | 126 |
| conduct | caregiver | caregiver_full | structural_dsm5_plus_context_full | 126 | 126 | 95 |
| conduct | caregiver | caregiver_full | structural_compact_full | 126 | 126 | 103 |
| conduct | caregiver | caregiver_full | structural_pruned_full | 126 | 126 | 119 |
| conduct | psychologist | psychologist_full | structural_ranked_full | 151 | 151 | 151 |
| conduct | psychologist | psychologist_full | structural_dsm5_plus_context_full | 151 | 151 | 105 |
| conduct | psychologist | psychologist_full | structural_compact_full | 151 | 151 | 124 |
| conduct | psychologist | psychologist_full | structural_pruned_full | 151 | 151 | 144 |
| depression | caregiver | caregiver_1_3 | structural_ranked_1_3 | 126 | 42 | 42 |
| depression | caregiver | caregiver_1_3 | structural_dsm5_plus_context_1_3 | 126 | 42 | 36 |
| depression | caregiver | caregiver_1_3 | structural_compact_1_3 | 126 | 42 | 34 |
| depression | caregiver | caregiver_1_3 | structural_pruned_1_3 | 126 | 42 | 42 |
| depression | caregiver | caregiver_1_3 | registry_stability_pruned_subset | 126 | 42 | 24 |
| depression | caregiver | caregiver_2_3 | structural_ranked_2_3 | 126 | 84 | 84 |
| depression | caregiver | caregiver_2_3 | structural_dsm5_plus_context_2_3 | 126 | 84 | 58 |
| depression | caregiver | caregiver_2_3 | structural_compact_2_3 | 126 | 84 | 69 |
| depression | caregiver | caregiver_2_3 | structural_pruned_2_3 | 126 | 84 | 84 |
| depression | caregiver | caregiver_2_3 | registry_stability_pruned_subset | 126 | 84 | 49 |
| depression | caregiver | caregiver_full | structural_ranked_full | 126 | 126 | 126 |
| depression | caregiver | caregiver_full | structural_dsm5_plus_context_full | 126 | 126 | 95 |
| depression | caregiver | caregiver_full | structural_compact_full | 126 | 126 | 103 |
| depression | caregiver | caregiver_full | structural_pruned_full | 126 | 126 | 119 |
| depression | psychologist | psychologist_1_3 | structural_ranked_1_3 | 151 | 50 | 50 |
| depression | psychologist | psychologist_1_3 | structural_dsm5_plus_context_1_3 | 151 | 50 | 44 |
| depression | psychologist | psychologist_1_3 | structural_compact_1_3 | 151 | 50 | 41 |
| depression | psychologist | psychologist_1_3 | structural_pruned_1_3 | 151 | 50 | 50 |
| depression | psychologist | psychologist_1_3 | registry_stability_pruned_subset | 151 | 50 | 30 |
| depression | psychologist | psychologist_2_3 | structural_ranked_2_3 | 151 | 101 | 101 |
| depression | psychologist | psychologist_2_3 | structural_dsm5_plus_context_2_3 | 151 | 101 | 75 |
| depression | psychologist | psychologist_2_3 | structural_compact_2_3 | 151 | 101 | 83 |
| depression | psychologist | psychologist_2_3 | structural_pruned_2_3 | 151 | 101 | 101 |
| depression | psychologist | psychologist_full | structural_ranked_full | 151 | 151 | 151 |
| depression | psychologist | psychologist_full | structural_dsm5_plus_context_full | 151 | 151 | 115 |
| depression | psychologist | psychologist_full | structural_compact_full | 151 | 151 | 124 |
| depression | psychologist | psychologist_full | structural_pruned_full | 151 | 151 | 144 |

## Overfit / Generalization
| domain | mode | overfit_gap_train_val_ba | generalization_gap_val_holdout_ba | f1_std_across_seeds | balanced_accuracy_std_across_seeds | stress_missing10_ba_drop | stress_drop_top1_ba_drop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | caregiver_1_3 | 0.021506 | 0.016977 | 0.004636 | 0.004739 | 0.037372 | 0.027202 |
| adhd | caregiver_2_3 | 0.011162 | 0.017115 | 0.007625 | 0.006600 | 0.032053 | 0.025907 |
| adhd | psychologist_1_3 | -0.001929 | 0.021001 | 0.000000 | 0.000000 | 0.081358 | 0.034974 |
| adhd | psychologist_2_3 | 0.009729 | 0.042278 | 0.000000 | 0.000000 | 0.033348 | 0.010363 |
| anxiety | psychologist_1_3 | -0.035769 | 0.033202 | 0.000000 | 0.000000 | 0.025263 | 0.003276 |
| anxiety | psychologist_full | -0.014097 | 0.000531 | 0.000000 | 0.000000 | 0.041435 | 0.409928 |
| conduct | caregiver_2_3 | -0.008893 | 0.009403 | 0.000000 | 0.000000 | 0.006250 | 0.000000 |
| depression | caregiver_1_3 | 0.017270 | 0.010755 | 0.007068 | 0.008932 | 0.038730 | 0.242095 |
| depression | caregiver_2_3 | 0.012450 | 0.020621 | 0.011858 | 0.011946 | 0.086438 | 0.077828 |
| depression | psychologist_1_3 | 0.015120 | 0.045012 | 0.009947 | 0.010622 | 0.104731 | 0.277608 |
| depression | psychologist_2_3 | 0.013312 | 0.021878 | 0.028604 | 0.031903 | 0.088767 | 0.087511 |
| elimination | caregiver_1_3 | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.018063 | 0.429457 |
| elimination | caregiver_2_3 | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.018063 | 0.429457 |
| elimination | caregiver_full | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.056524 | 0.429457 |
| elimination | psychologist_1_3 | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.037293 | 0.429457 |
| elimination | psychologist_2_3 | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.046909 | 0.429457 |
| elimination | psychologist_full | 0.001574 | 0.021567 | 0.000000 | 0.000000 | 0.046909 | 0.429457 |
