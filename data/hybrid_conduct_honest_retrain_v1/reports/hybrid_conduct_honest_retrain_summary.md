# Hybrid Conduct Honest Retrain v1 - Executive Summary

Focused on conduct active slots with perfect or near-perfect metrics and dataset_ease_flag=yes.

## Selected models
| domain | mode | feature_set_id | config_id | calibration | threshold_policy | threshold | precision | recall | specificity | balanced_accuracy | f1 | roc_auc | pr_auc | brier | quality_label | headline_cap_ok | generalization_ok | promotion_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conduct | caregiver_2_3 | engineered_compact_no_shortcuts_v1 | rf_balanced_subsample_v1 | none | precision_min_recall | 0.685000 | 0.928058 | 0.806250 | 0.968750 | 0.887500 | 0.862876 | 0.975859 | 0.947653 | 0.059813 | bueno | yes | yes | PROMOTE_NOW |
| conduct | caregiver_full | engineered_compact_no_shortcuts_v1 | rf_regularized_v1 | none | balanced | 0.445000 | 0.807692 | 0.918750 | 0.890625 | 0.904687 | 0.859649 | 0.974687 | 0.949959 | 0.062286 | aceptable | yes | yes | PROMOTE_NOW |
| conduct | psychologist_2_3 | engineered_compact_no_shortcuts_v1 | rf_regularized_v1 | isotonic | balanced | 0.380000 | 0.884615 | 0.862500 | 0.943750 | 0.903125 | 0.873418 | 0.971523 | 0.932444 | 0.059816 | bueno | yes | yes | PROMOTE_NOW |
| conduct | psychologist_full | engineered_compact_no_shortcuts_v1 | rf_balanced_subsample_v1 | isotonic | balanced | 0.335000 | 0.843931 | 0.912500 | 0.915625 | 0.914062 | 0.876877 | 0.975635 | 0.941329 | 0.060197 | aceptable | yes | yes | PROMOTE_NOW |

## Duplicate/split leak check
| dataset_rows | full_vector_duplicates_anywhere | train_rows | val_rows | holdout_rows | target_prevalence_train | target_prevalence_val | target_prevalence_holdout |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2400.000000 | 0.000000 | 1440.000000 | 480.000000 | 480.000000 | 0.332639 | 0.331250 | 0.333333 |

| split_a | split_b | exact_feature_vector_overlap |
| --- | --- | --- |
| train | val | 0 |
| train | holdout | 0 |
| val | holdout | 0 |

## Shortcut audit
| shortcut_feature | rule | holdout_tn | holdout_fp | holdout_fn | holdout_tp | holdout_precision | holdout_recall | holdout_balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conduct_impairment_global | conduct_impairment_global >= 2 | 318 | 2 | 0 | 160 | 0.987654 | 1.000000 | 0.996875 |
