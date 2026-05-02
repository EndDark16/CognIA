# Final Model Recommendations

Este reporte resume recomendaciones para producción experimental (no diagnóstico clínico definitivo).

## Recomendación por trastorno (baseline strict_no_leakage)
- **adhd**: `dataset_adhd_clinical` (strict_no_leakage) | balanced_accuracy=0.8374, recall=0.7937, specificity=0.8810, f1=0.8411, threshold=0.6563 (youden_j)
- **anxiety**: `dataset_anxiety_items` (strict_no_leakage) | balanced_accuracy=0.8497, recall=0.7619, specificity=0.9375, f1=0.8276, threshold=0.6642 (youden_j)
- **conduct**: `dataset_conduct_minimal` (strict_no_leakage) | balanced_accuracy=0.8868, recall=0.9048, specificity=0.8689, f1=0.6786, threshold=0.1655 (youden_j)
- **depression**: `dataset_depression_parent` (strict_no_leakage) | balanced_accuracy=0.8797, recall=0.9000, specificity=0.8594, f1=0.5806, threshold=0.1164 (youden_j)
- **elimination**: `dataset_elimination_core` (strict_no_leakage) | balanced_accuracy=0.6998, recall=0.7647, specificity=0.6349, f1=0.3421, threshold=0.1152 (youden_j)

## Mejor modelo multietiqueta
- `master_multilabel_ready` (strict_no_leakage) | micro_f1=0.7582, macro_f1=0.5691, subset_accuracy=0.5280, hamming_loss=0.1231

## Strict vs Research (resumen)
- adhd/clinical: Δbalanced_accuracy(research-strict)=0.0427
- adhd/items: Δbalanced_accuracy(research-strict)=0.0214
- adhd/minimal: Δbalanced_accuracy(research-strict)=0.0622
- anxiety/combined: Δbalanced_accuracy(research-strict)=0.0571
- anxiety/items: Δbalanced_accuracy(research-strict)=0.0186
- anxiety/parent: Δbalanced_accuracy(research-strict)=0.0756
- conduct/clinical: Δbalanced_accuracy(research-strict)=0.0690
- conduct/items: Δbalanced_accuracy(research-strict)=0.0641
- conduct/minimal: Δbalanced_accuracy(research-strict)=0.0168
- depression/combined: Δbalanced_accuracy(research-strict)=0.0049
- depression/items: Δbalanced_accuracy(research-strict)=0.0079
- depression/parent: Δbalanced_accuracy(research-strict)=-0.0012
- elimination/core: Δbalanced_accuracy(research-strict)=0.1417
- elimination/items: Δbalanced_accuracy(research-strict)=0.0233

## Estado exploratorio
- Elimination se mantiene exploratorio por menor cobertura específica y mayor sensibilidad a ruido de features.

## Advertencias
- Los resultados son experimentales en entorno simulado.
- Deben interpretarse como alerta temprana, no diagnóstico definitivo.
- En clases minoritarias, priorizar sensibilidad con control de especificidad según contexto operativo.
