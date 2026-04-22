# elimination v14 model family analysis

        mode   family            best_feature_set  precision   recall  specificity  balanced_accuracy       f1  roc_auc   pr_auc    brier  objective
   caregiver lightgbm r3_hybrid_clean_best_effort   0.868966 0.782609        0.848           0.815304 0.823529 0.864025 0.902986 0.144032   0.840933
   caregiver       rf r3_hybrid_clean_best_effort   0.860759 0.844720        0.824           0.834360 0.852665 0.881193 0.911523 0.132678   0.862079
   caregiver  xgboost r3_hybrid_clean_best_effort   0.850649 0.813665        0.816           0.814832 0.831746 0.869217 0.905367 0.140067   0.843597
psychologist lightgbm               r1_v12_replay   0.844595 0.776398        0.816           0.796199 0.809061 0.860770 0.898452 0.148965   0.821547
psychologist       rf               r1_v12_replay   0.847561 0.863354        0.800           0.831677 0.855385 0.885242 0.912164 0.134631   0.861521
psychologist  xgboost               r1_v12_replay   0.858108 0.788820        0.832           0.810410 0.822006 0.870137 0.905720 0.145462   0.837316
