# Hybrid Active Modes Freeze v2 - Summary

Only conduct easy-dataset-inflated slots were replaced with honest retrained models.

## Active class counts
final_operational_class
ACTIVE_HIGH_CONFIDENCE        16
ACTIVE_LIMITED_USE             9
ACTIVE_MODERATE_CONFIDENCE     5

## Conduct active rows
| domain | mode | active_model_id | source_campaign | feature_set_id | precision | recall | specificity | balanced_accuracy | f1 | roc_auc | pr_auc | brier | dataset_ease_flag | final_operational_class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conduct | caregiver_2_3 | conduct__caregiver_2_3__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 0.928058 | 0.806250 | 0.968750 | 0.887500 | 0.862876 | 0.975859 | 0.947653 | 0.059813 | no | ACTIVE_MODERATE_CONFIDENCE |
| conduct | caregiver_full | conduct__caregiver_full__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 0.807692 | 0.918750 | 0.890625 | 0.904687 | 0.859649 | 0.974687 | 0.949959 | 0.062286 | no | ACTIVE_MODERATE_CONFIDENCE |
| conduct | psychologist_2_3 | conduct__psychologist_2_3__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 0.884615 | 0.862500 | 0.943750 | 0.903125 | 0.873418 | 0.971523 | 0.932444 | 0.059816 | no | ACTIVE_HIGH_CONFIDENCE |
| conduct | psychologist_full | conduct__psychologist_full__conduct_honest_retrain_v1__rf__engineered_compact_no_shortcuts_v1 | conduct_honest_retrain_v1 | engineered_compact_no_shortcuts_v1 | 0.843931 | 0.912500 | 0.915625 | 0.914062 | 0.876877 | 0.975635 | 0.941329 | 0.060197 | no | ACTIVE_MODERATE_CONFIDENCE |
