# Focused improvement analysis

Dominios focalizados: elimination (ambos), adhd (ambos), depression cuidador/psicólogo.

## Resultados finales focalizados

 precision   recall  specificity  balanced_accuracy       f1  roc_auc  pr_auc    brier         mode      domain chosen_family chosen_feature_variant chosen_threshold_policy  improvement_level  delta_balanced_accuracy  delta_recall  delta_brier  delta_precision  delta_specificity  delta_f1  delta_roc_auc  delta_pr_auc  n_features
  0.949500 0.817800     0.944000           0.880900 0.878800 0.948400 0.95000 0.084200    caregiver        adhd            rf             engineered       precision_guarded none_baseline_kept                 0.000000      0.000000     0.000000              NaN                NaN       NaN            NaN           NaN         NaN
  0.858723 0.946488     0.895187           0.920837 0.900347 0.979397 0.96077 0.057874    caregiver  depression      catboost             engineered          recall_guarded           material                 0.032437      0.163888     0.003774        -0.130277          -0.099013  0.026547      -0.002803      -0.00803        28.0
  0.948300 0.683200     0.952000           0.817600 0.794200 0.875900 0.89070 0.133100    caregiver elimination       xgboost             engineered       precision_guarded none_baseline_kept                 0.000000      0.000000     0.000000              NaN                NaN       NaN            NaN           NaN         NaN
  0.956200 0.813700     0.952000           0.882800 0.879200 0.952200 0.95440 0.082900 psychologist        adhd            rf                   base       precision_guarded none_baseline_kept                 0.000000      0.000000     0.000000              NaN                NaN       NaN            NaN           NaN         NaN
  0.858723 0.946488     0.895187           0.920837 0.900347 0.979397 0.96077 0.057874 psychologist  depression      catboost             engineered          recall_guarded           marginal                 0.006137      0.050788     0.000974        -0.043577          -0.038513  0.002247      -0.000903      -0.00253        29.0
  0.940200 0.683200     0.944000           0.813600 0.791400 0.877000 0.89580 0.137100 psychologist elimination      lightgbm             engineered       precision_guarded none_baseline_kept                 0.000000      0.000000     0.000000              NaN                NaN       NaN            NaN           NaN         NaN

## Resumen
- Máximo 2 rondas fuertes + 1 refinamiento adicional solo con señal.
- Se conserva baseline v5 cuando no hay mejora robusta.
