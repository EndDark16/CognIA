# Training Strategy Recommendations

## A) Binary strategy (one model per disorder)
- conduct: use `dataset_conduct_clinical_strict_no_leakage.csv`
- adhd: use `dataset_adhd_clinical_strict_no_leakage.csv`
- elimination: use `dataset_elimination_core_strict_no_leakage.csv` (exploratory)
- anxiety: use `dataset_anxiety_combined_strict_no_leakage.csv`
- depression: use `dataset_depression_combined_strict_no_leakage.csv`

Recommended estimator: `RandomForestClassifier(class_weight='balanced_subsample', random_state=42)` with threshold tuning per disorder.

## B) Multilabel strategy
- Use `master_multilabel_ready_strict_no_leakage.csv`
- Recommended wrapper: `MultiOutputClassifier(RandomForestClassifier(...))`
- Preserve label pattern distribution in splits when feasible.

## Priority for immediate training
1. ADHD
2. Anxiety
3. Depression
4. Conduct
5. Elimination (exploratory)
