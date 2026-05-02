# Random Forest Evaluation Specification

Required metrics per binary model:
- accuracy
- balanced_accuracy
- precision
- recall / sensitivity
- specificity
- f1
- roc_auc
- pr_auc
- confusion_matrix
- normalized_confusion_matrix
- calibration_curve
- brier_score
- feature_importance_gini
- permutation_importance
- top_positive_contributors (approx local explanation)

Subgroup metrics:
- by age
- by sex (if available)
- by comorbidity_count_5targets

Multilabel metrics:
- macro/micro/weighted precision-recall-f1
- subset accuracy
- hamming loss
- per-label confusion matrices
- comorbidity-aware slices by label_pattern

Clinical output contract:
- risk score 0..1 per disorder
- category: low/moderate/high
- suspected comorbidity flag
- evidence quality: weak/medium/strong
- critical missingness flags reducing confidence
