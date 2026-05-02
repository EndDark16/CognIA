# Pass C - Remodelado cuidador-compatible

## Resultado macro (promedio 5 dominios)
- precision: **0.8844**
- recall: **0.8807**
- specificity: **0.9161**
- balanced_accuracy: **0.8984**
- f1: **0.8801**
- roc_auc: **0.9635**
- pr_auc: **0.9660**
- brier_score: **0.0661**

## Resultado por dominio
- `adhd` -> BA=0.8815, P=0.9257, R=0.8509, Spec=0.9120, F1=0.8867
- `conduct` -> BA=0.9229, P=0.9211, R=0.8750, Spec=0.9709, F1=0.8974
- `elimination` -> BA=0.8055, P=0.8477, R=0.7950, Spec=0.8160, F1=0.8205
- `anxiety` -> BA=0.9462, P=0.7901, R=0.9697, Spec=0.9227, F1=0.8707
- `depression` -> BA=0.9361, P=0.9375, R=0.9130, Spec=0.9591, F1=0.9251

## Notas metodológicas
- Se entrenó nueva línea RF usando solo features caregiver-compatible + sistema.
- Selección de umbral en validación, confirmación en test (strict_full).
- Se reporta estabilidad por seeds, split alterno research_full y robustez con ruido.

- Nota: en los artefactos actuales, `research_full` y `strict_full` comparten los mismos IDs por dominio; la estabilidad por split queda limitada y se interpreta con cautela.
