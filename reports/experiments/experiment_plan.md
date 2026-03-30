# Versioned Experiment Plan

Campaign scope: Depression, Conduct, Elimination using frozen splits and strict_no_leakage baseline.

## Current champions at campaign start
- adhd: rf_adhd_v1_baseline
- anxiety: rf_anxiety_v1_baseline
- conduct: rf_conduct_v1_baseline
- depression: rf_depression_v1_baseline
- elimination: rf_elimination_v1_baseline
- multilabel: rf_multilabel_v1_baseline

## Planned experiments
- rf_depression_v2_feature_pruned: disorder=depression, dataset=dataset_depression_parent, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=sigmoid, threshold=youden_j
- rf_depression_v3_calibrated: disorder=depression, dataset=dataset_depression_combined, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=isotonic, threshold=sensitivity_priority
- rf_conduct_v2_externalizing_focus: disorder=conduct, dataset=dataset_conduct_clinical, scope=strict_no_leakage, feature_strategy=externalizing_focus, class_balance=balanced_subsample, calibration=sigmoid, threshold=youden_j
- rf_conduct_v3_balanced_subsample: disorder=conduct, dataset=dataset_conduct_minimal, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=sigmoid, threshold=sensitivity_priority
- rf_elimination_v2_missingness_augmented: disorder=elimination, dataset=dataset_elimination_core, scope=strict_no_leakage, feature_strategy=missingness_augmented, class_balance=balanced_subsample, calibration=sigmoid, threshold=youden_j
- rf_elimination_v3_proxy_pruned: disorder=elimination, dataset=dataset_elimination_items, scope=strict_no_leakage, feature_strategy=proxy_pruned, class_balance=balanced, calibration=sigmoid, threshold=best_f1
- rf_elimination_v4_experimental_research: disorder=elimination, dataset=dataset_elimination_core, scope=research_extended, feature_strategy=missingness_augmented, class_balance=balanced_subsample, calibration=sigmoid, threshold=youden_j
