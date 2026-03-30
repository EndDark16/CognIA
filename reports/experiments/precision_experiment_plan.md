# Precision Experiment Plan

Campaign objective: improve precision/PPV while preserving validation rigor and frozen splits.

## Champions at start
- adhd: rf_adhd_v1_baseline
- anxiety: rf_anxiety_v1_baseline
- conduct: rf_conduct_v1_baseline
- depression: rf_depression_v1_baseline
- elimination: rf_elimination_v1_baseline
- multilabel: rf_multilabel_v1_baseline

## Planned challengers
- rf_depression_v4_precision_thresholded: disorder=depression, dataset=dataset_depression_parent, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=none, priority=primary, experimental=False
- rf_depression_v5_precision_calibrated: disorder=depression, dataset=dataset_depression_parent, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=sigmoid, priority=primary, experimental=False
- rf_depression_v6_precision_pruned: disorder=depression, dataset=dataset_depression_combined, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced, calibration=sigmoid, priority=primary, experimental=False
- rf_conduct_v4_precision_thresholded: disorder=conduct, dataset=dataset_conduct_minimal, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=none, priority=primary, experimental=False
- rf_conduct_v5_precision_calibrated: disorder=conduct, dataset=dataset_conduct_clinical, scope=strict_no_leakage, feature_strategy=externalizing_focus, class_balance=balanced_subsample, calibration=sigmoid, priority=primary, experimental=False
- rf_conduct_v6_precision_externalizing_pruned: disorder=conduct, dataset=dataset_conduct_clinical, scope=strict_no_leakage, feature_strategy=externalizing_focus, class_balance=balanced, calibration=none, priority=primary, experimental=False
- rf_elimination_v5_precision_missingness: disorder=elimination, dataset=dataset_elimination_core, scope=strict_no_leakage, feature_strategy=missingness_augmented, class_balance=balanced_subsample, calibration=sigmoid, priority=primary, experimental=False
- rf_elimination_v6_precision_proxy_pruned: disorder=elimination, dataset=dataset_elimination_items, scope=strict_no_leakage, feature_strategy=proxy_pruned, class_balance=balanced, calibration=sigmoid, priority=primary, experimental=False
- rf_elimination_v7_precision_experimental_research: disorder=elimination, dataset=dataset_elimination_core, scope=research_extended, feature_strategy=missingness_augmented, class_balance=balanced_subsample, calibration=sigmoid, priority=primary, experimental=True
- rf_adhd_v2_precision_sanity: disorder=adhd, dataset=dataset_adhd_clinical, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=none, priority=sanity, experimental=False
- rf_anxiety_v2_precision_sanity: disorder=anxiety, dataset=dataset_anxiety_items, scope=strict_no_leakage, feature_strategy=mi_top_k, class_balance=balanced_subsample, calibration=none, priority=sanity, experimental=False
