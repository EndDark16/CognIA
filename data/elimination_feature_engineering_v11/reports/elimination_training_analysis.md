# Elimination training analysis v11

- total_trials: 60
- model_families_tested: rf, lightgbm, xgboost
- feature_sets_per_mode: 10
- rounds_policy: {'max_strong_rounds': 3, 'max_confirm_rounds': 1}

## Best trial by mode

        mode                 feature_set   family  objective  precision   recall  balanced_accuracy   pr_auc    brier
   caregiver                proxy_pruned lightgbm   0.965729   0.993421 0.937888           0.964944 0.985234 0.035061
psychologist compact_clinical_engineered lightgbm   0.966012   1.000000 0.937888           0.968944 0.986281 0.034229

## Top 12 trials

     mode                   feature_set   family  precision   recall  specificity  balanced_accuracy       f1  roc_auc   pr_auc    brier  seed_std_balanced_accuracy  objective
caregiver                  proxy_pruned lightgbm   0.993421 0.937888        0.992           0.964944 0.964856 0.971950 0.985234 0.035061                1.885618e-03   0.965729
caregiver                 subtype_aware       rf   0.993421 0.937888        0.992           0.964944 0.964856 0.974311 0.986781 0.035096                1.463989e-03   0.965676
caregiver                  proxy_pruned  xgboost   0.986928 0.937888        0.984           0.960944 0.961783 0.972323 0.985167 0.034840                6.390209e-03   0.963731
caregiver   compact_clinical_engineered  xgboost   0.993421 0.937888        0.992           0.964944 0.964856 0.973416 0.986125 0.035508                3.771236e-03   0.962827
caregiver                  proxy_pruned       rf   0.974359 0.944099        0.968           0.956050 0.958991 0.978981 0.988784 0.035564                1.110223e-16   0.962572
caregiver hybrid_engineered_best_effort       rf   0.980519 0.937888        0.976           0.956944 0.958730 0.972124 0.985877 0.034836                1.714146e-03   0.961844
caregiver   compact_clinical_engineered lightgbm   0.986928 0.937888        0.984           0.960944 0.961783 0.971056 0.985227 0.036324                1.885618e-03   0.961809
caregiver        source_semantics_aware lightgbm   0.987013 0.944099        0.984           0.964050 0.965079 0.974186 0.986691 0.032877                0.000000e+00   0.960492
caregiver             burden_composites lightgbm   0.993421 0.937888        0.992           0.964944 0.964856 0.970559 0.984804 0.034622                1.885618e-03   0.959204
caregiver             burden_composites  xgboost   1.000000 0.937888        1.000           0.968944 0.967949 0.977043 0.987562 0.033394                9.662975e-03   0.957786
caregiver                impact_focused lightgbm   0.980645 0.944099        0.976           0.960050 0.962025 0.976646 0.987342 0.033529                3.771236e-03   0.957534
caregiver             missingness_aware lightgbm   0.980645 0.944099        0.976           0.960050 0.962025 0.974460 0.986442 0.032561                3.265986e-03   0.957486
