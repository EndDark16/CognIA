# Consistency validation

## File integrity
- required_files: 23
- missing_files: 0 -> []
- empty_files: 0 -> []

## Numeric consistency
- max_diff_precision: 0.000000000000
- max_diff_recall: 0.000000000000
- max_diff_specificity: 0.000000000000
- max_diff_balanced_accuracy: 0.000000000000
- max_diff_f1: 0.000000000000
- max_diff_roc_auc: 0.000000000000
- max_diff_pr_auc: 0.000000000000
- max_diff_brier: 0.000000000000
- max_diff_imputed_fill_pct: 0.000000000000
- max_diff_derived_fill_pct: 0.000000000000

## Decision consistency
- decision_contains_C_global: True
- decision_contains_A_global: False
- hybrid_only_BC: True
- macro_best_route: C

## Notes
- `hybrid_candidate_matrix.csv` evalua combinacion B/C por diseno (A descartada como ruta final).
- No se detectaron inconsistencias materiales entre `route_macro_comparison.csv`, `hybrid_candidate_matrix.csv` y `final_route_decision.md`.
