# Pass A - Cuestionario básico directo

## Resultado macro (promedio 5 dominios)
- precision: **0.8361**
- recall: **0.6994**
- specificity: **0.8896**
- balanced_accuracy: **0.7945**
- f1: **0.7112**
- roc_auc: **0.9166**
- pr_auc: **0.9128**
- brier_score: **0.2276**

## Resultado por dominio
- `adhd` -> BA=0.8859, P=0.9156, R=0.8758, Spec=0.8960, F1=0.8952
- `conduct` -> BA=0.8913, P=0.9844, R=0.7875, Spec=0.9951, F1=0.8750
- `elimination` -> BA=0.6836, P=0.8265, R=0.5031, Spec=0.8640, F1=0.6255
- `anxiety` -> BA=0.8523, P=0.5038, R=1.0000, Spec=0.7045, F1=0.6701
- `depression` -> BA=0.6594, P=0.9500, R=0.3304, Spec=0.9883, F1=0.4903

## Notas metodológicas
- Se evaluó con modelos champions actuales y umbrales recomendados por metadata.
- Inputs fuera de cobertura se completaron con defaults del runtime actual.
- No se usaron proxies ni reentrenamiento.
