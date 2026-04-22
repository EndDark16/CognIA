# Pass B - Cuestionario + capa intermedia

## Resultado macro (promedio 5 dominios)
- precision: **0.9414**
- recall: **0.6420**
- specificity: **0.9537**
- balanced_accuracy: **0.7978**
- f1: **0.7443**
- roc_auc: **0.9222**
- pr_auc: **0.9188**
- brier_score: **0.1791**

## Resultado por dominio
- `adhd` -> BA=0.8908, P=0.9272, R=0.8696, Spec=0.9120, F1=0.8974
- `conduct` -> BA=0.9076, P=0.9706, R=0.8250, Spec=0.9903, F1=0.8919
- `elimination` -> BA=0.6876, P=0.8351, R=0.5031, Spec=0.8720, F1=0.6279
- `anxiety` -> BA=0.8409, P=1.0000, R=0.6818, Spec=1.0000, F1=0.8108
- `depression` -> BA=0.6623, P=0.9744, R=0.3304, Spec=0.9942, F1=0.4935

## Notas metodológicas
- Se aplicaron reglas de derivación/proxy explícitas y trazables.
- Los faltantes residuales se imputaron con estadísticas de train (strict_full) por dominio.
- Las derivaciones self-report <- caregiver se marcan como aproximadas y no equivalentes clínicas.
