# Hybrid RF Consolidation v2 - Analysis

## Reproduced Candidates
| candidate_id | domain | mode | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | reproduced_material |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__psychologist_2_3 | adhd | psychologist_2_3 | 0.774775 | 0.914894 | 0.925063 | 0.769329 | 0.054965 | yes |
| adhd__psychologist_full | adhd | psychologist_full | 0.947917 | 0.968085 | 0.977566 | 0.945106 | 0.015459 | yes |
| anxiety__caregiver_2_3 | anxiety | caregiver_2_3 | 0.891304 | 0.953488 | 0.964054 | 0.929693 | 0.021603 | yes |
| anxiety__caregiver_full | anxiety | caregiver_full | 0.941860 | 0.941860 | 0.964585 | 0.957131 | 0.020587 | yes |
| conduct__caregiver_2_3 | conduct | caregiver_2_3 | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001196 | yes |
| conduct__psychologist_2_3 | conduct | psychologist_2_3 | 0.987578 | 1.000000 | 0.996885 | 1.000000 | 0.001286 | yes |
| conduct__psychologist_full | conduct | psychologist_full | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001176 | yes |
| depression__caregiver_2_3 | depression | caregiver_2_3 | 0.847222 | 0.743902 | 0.858132 | 0.862956 | 0.052005 | yes |
| depression__caregiver_full | depression | caregiver_full | 0.835616 | 0.743902 | 0.856876 | 0.869977 | 0.050932 | yes |
| depression__psychologist_full | depression | psychologist_full | 0.890625 | 0.695122 | 0.838767 | 0.900358 | 0.046736 | yes |
| elimination__caregiver_2_3 | elimination | caregiver_2_3 | 0.961538 | 0.961538 | 0.978433 | 0.974532 | 0.006001 | yes |
| elimination__caregiver_full | elimination | caregiver_full | 0.960784 | 0.942308 | 0.968817 | 0.959900 | 0.008054 | yes |
| elimination__psychologist_full | elimination | psychologist_full | 0.957447 | 0.865385 | 0.930356 | 0.952276 | 0.011423 | yes |

## Stability Summary
| candidate_id | stability_grade | seed_std_balanced_accuracy | split_std_balanced_accuracy | bootstrap_balanced_accuracy_ci_width | worst_stress_delta_balanced_accuracy |
| --- | --- | --- | --- | --- | --- |
| adhd__psychologist_2_3 | fragile | 0.002660 | 0.002845 | 0.055861 | -0.142046 |
| adhd__psychologist_full | fragile | 0.009213 | 0.001832 | 0.036239 | -0.078409 |
| anxiety__caregiver_2_3 | fragile | 0.003357 | 0.001941 | 0.044807 | -0.464054 |
| anxiety__caregiver_full | fragile | 0.008881 | 0.057555 | 0.048355 | -0.464585 |
| conduct__caregiver_2_3 | fragile | 0.000000 | 0.000000 | 0.012057 | -0.495327 |
| conduct__psychologist_2_3 | fragile | 0.000899 | 0.000000 | 0.008258 | -0.496885 |
| conduct__psychologist_full | fragile | 0.000000 | 0.000000 | 0.012057 | -0.495327 |
| depression__caregiver_2_3 | fragile | 0.002795 | 0.026758 | 0.097215 | -0.358132 |
| depression__caregiver_full | fragile | 0.003520 | 0.007735 | 0.103815 | -0.356876 |
| depression__psychologist_full | fragile | 0.003064 | 0.027646 | 0.097004 | -0.338767 |
| elimination__caregiver_2_3 | fragile | 0.009754 | 0.017919 | 0.055939 | -0.468817 |
| elimination__caregiver_full | fragile | 0.004577 | 0.036664 | 0.064652 | -0.468817 |
| elimination__psychologist_full | fragile | 0.028739 | 0.051089 | 0.087715 | -0.430356 |

## Promotion Decisions
| candidate_id | promotion_decision | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | risk_flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adhd__psychologist_2_3 | HOLD_FOR_TARGETED_FIX | 0.774775 | 0.914894 | 0.925063 | 0.769329 | 0.054965 | stress_fragility\|top_feature_dependency |
| adhd__psychologist_full | PROMOTE_WITH_CAVEAT | 0.947917 | 0.968085 | 0.977566 | 0.945106 | 0.015459 | top_feature_dependency |
| anxiety__caregiver_2_3 | PROMOTE_WITH_CAVEAT | 0.891304 | 0.953488 | 0.964054 | 0.929693 | 0.021603 | stress_fragility\|top_feature_dependency |
| anxiety__caregiver_full | PROMOTE_WITH_CAVEAT | 0.941860 | 0.941860 | 0.964585 | 0.957131 | 0.020587 | split_instability\|stress_fragility |
| conduct__caregiver_2_3 | PROMOTE_WITH_CAVEAT | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001196 | stress_fragility\|top_feature_dependency |
| conduct__psychologist_2_3 | PROMOTE_WITH_CAVEAT | 0.987578 | 1.000000 | 0.996885 | 1.000000 | 0.001286 | stress_fragility\|top_feature_dependency |
| conduct__psychologist_full | PROMOTE_WITH_CAVEAT | 0.981481 | 1.000000 | 0.995327 | 1.000000 | 0.001176 | stress_fragility\|top_feature_dependency |
| depression__caregiver_2_3 | HOLD_FOR_TARGETED_FIX | 0.847222 | 0.743902 | 0.858132 | 0.862956 | 0.052005 | split_instability\|stress_fragility\|top_feature_dependency\|val_holdout_gap\|wide_bootstrap_ci |
| depression__caregiver_full | HOLD_FOR_TARGETED_FIX | 0.835616 | 0.743902 | 0.856876 | 0.869977 | 0.050932 | stress_fragility\|top_feature_dependency\|val_holdout_gap\|wide_bootstrap_ci |
| depression__psychologist_full | HOLD_FOR_TARGETED_FIX | 0.890625 | 0.695122 | 0.838767 | 0.900358 | 0.046736 | split_instability\|stress_fragility\|top_feature_dependency\|val_holdout_gap\|wide_bootstrap_ci |
| elimination__caregiver_2_3 | PROMOTE_WITH_CAVEAT | 0.961538 | 0.961538 | 0.978433 | 0.974532 | 0.006001 | stress_fragility\|top_feature_dependency |
| elimination__caregiver_full | HOLD_FOR_TARGETED_FIX | 0.960784 | 0.942308 | 0.968817 | 0.959900 | 0.008054 | split_instability\|stress_fragility\|top_feature_dependency |
| elimination__psychologist_full | HOLD_FOR_TARGETED_FIX | 0.957447 | 0.865385 | 0.930356 | 0.952276 | 0.011423 | seed_instability\|split_instability\|stress_fragility\|top_feature_dependency\|wide_bootstrap_ci |

## 2/3 vs Full
| domain | role | mode_2_3 | mode_full | decision_2_3 | decision_full | delta_precision_full_minus_2_3 | delta_recall_full_minus_2_3 | delta_balanced_accuracy_full_minus_2_3 | delta_pr_auc_full_minus_2_3 | full_material_gain | prefer_2_3_practical |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist | psychologist_2_3 | psychologist_full | HOLD_FOR_TARGETED_FIX | PROMOTE_WITH_CAVEAT | 0.173142 | 0.053191 | 0.052502 | 0.175777 | yes | no |
| anxiety | caregiver | caregiver_2_3 | caregiver_full | PROMOTE_WITH_CAVEAT | PROMOTE_WITH_CAVEAT | 0.050556 | -0.011628 | 0.000531 | 0.027438 | yes | no |
| conduct | psychologist | psychologist_2_3 | psychologist_full | PROMOTE_WITH_CAVEAT | PROMOTE_WITH_CAVEAT | -0.006096 | 0.000000 | -0.001558 | 0.000000 | no | yes |
| depression | caregiver | caregiver_2_3 | caregiver_full | HOLD_FOR_TARGETED_FIX | HOLD_FOR_TARGETED_FIX | -0.011606 | 0.000000 | -0.001256 | 0.007021 | no | yes |
| elimination | caregiver | caregiver_2_3 | caregiver_full | PROMOTE_WITH_CAVEAT | HOLD_FOR_TARGETED_FIX | -0.000754 | -0.019231 | -0.009615 | -0.014632 | no | no |
