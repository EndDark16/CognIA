# v13 Real Prediction Anti-Clone Audit

Generated: `2026-05-01T00:54:15.134474+00:00`

## Scope
- Real prediction recomputation for all active v13 champions.
- No retraining and no champion replacement in this audit.
- Holdout reconstruction follows v10/v11/v12 split logic (participant_id stratified split).

## Source Validation
- loader active line: `v13`
- loader operational line: `v13`
- loader points to v13: `yes`
- active rows: `30`
- RF rows in active: `30`
- contract_compatible yes (validator): `30`/`30`
- guardrail violations (validator): `0`

## Recompute Status
- prediction_recomputed yes: `30`/`30`
- artifacts_available yes: `30`/`30`
- metrics_match_registered yes: `30`/`30`

## Anti-Clone Results
- all_domains_real_clone_count: `4`
- elimination_real_clone_count: `4`
- all_domains_near_clone_warning_count: `23`
- artifact_duplicate_hash_count: `0`
- final_audit_status: `fail`

## Elimination Pairwise
| slot_a | slot_b | prediction_agreement | probability_correlation | binary_predictions_identical | metric_max_abs_delta | threshold_abs_delta | feature_jaccard | shared_error_overlap | real_clone_flag | near_clone_warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elimination/caregiver_1_3 | elimination/caregiver_2_3 | 0.98125 | 0.9912334563095123 | no | 0.034078885494892464 | 0.040000000000000036 | 0.375 | 0.5909090909090909 | no | yes |
| elimination/caregiver_1_3 | elimination/caregiver_full | 0.98125 | 0.949211640214761 | no | 0.17773518857849135 | 0.12 | 0.18181818181818182 | 0.6086956521739131 | no | yes |
| elimination/caregiver_1_3 | elimination/psychologist_1_3 | 0.9791666666666666 | 0.9458352416213981 | no | 0.16123735224117863 | 0.040000000000000036 | 0.2857142857142857 | 0.5833333333333334 | no | no |
| elimination/caregiver_1_3 | elimination/psychologist_2_3 | 0.9791666666666666 | 0.9468825260163518 | no | 0.13752557782530328 | 0.09999999999999998 | 0.18181818181818182 | 0.5652173913043478 | no | no |
| elimination/caregiver_1_3 | elimination/psychologist_full | 0.98125 | 0.9470595761939975 | no | 0.12225189907047773 | 0.040000000000000036 | 0.14285714285714285 | 0.6086956521739131 | no | yes |
| elimination/caregiver_2_3 | elimination/caregiver_full | 0.9791666666666666 | 0.9534040195632875 | no | 0.15970196282422033 | 0.16000000000000003 | 0.6 | 0.5652173913043478 | no | no |
| elimination/caregiver_2_3 | elimination/psychologist_1_3 | 0.9770833333333333 | 0.9510048787182974 | no | 0.1432041264869076 | 0.0 | 0.7142857142857143 | 0.5416666666666666 | no | yes |
| elimination/caregiver_2_3 | elimination/psychologist_2_3 | 0.9770833333333333 | 0.9516191949566277 | no | 0.11949235207103226 | 0.14 | 0.6 | 0.5217391304347826 | no | no |
| elimination/caregiver_2_3 | elimination/psychologist_full | 0.9791666666666666 | 0.9528475082301638 | no | 0.10421867331620671 | 0.0 | 0.46153846153846156 | 0.5652173913043478 | no | yes |
| elimination/caregiver_full | elimination/psychologist_1_3 | 0.9979166666666667 | 0.996801418203226 | no | 0.01649783633731272 | 0.16000000000000003 | 0.5555555555555556 | 0.95 | yes | yes |
| elimination/caregiver_full | elimination/psychologist_2_3 | 0.9979166666666667 | 0.999159998180702 | no | 0.040209610753188074 | 0.020000000000000018 | 0.6363636363636364 | 0.9473684210526315 | yes | yes |
| elimination/caregiver_full | elimination/psychologist_full | 1.0 | 0.9949863462379728 | yes | 0.05548328950801362 | 0.16000000000000003 | 0.75 | 1.0 | yes | yes |
| elimination/psychologist_1_3 | elimination/psychologist_2_3 | 0.9958333333333333 | 0.9953192673136141 | no | 0.023711774415875353 | 0.14 | 0.5555555555555556 | 0.9 | yes | yes |
| elimination/psychologist_1_3 | elimination/psychologist_full | 0.9979166666666667 | 0.9945736721872976 | no | 0.0389854531707009 | 0.0 | 0.4166666666666667 | 0.95 | no | yes |
| elimination/psychologist_2_3 | elimination/psychologist_full | 0.9979166666666667 | 0.9947339990107856 | no | 0.015273678754825548 | 0.14 | 0.75 | 0.9473684210526315 | no | yes |

## Plots
- `data/hybrid_v13_real_prediction_anti_clone_audit/plots/elimination_probability_correlation_heatmap.png`
- `data/hybrid_v13_real_prediction_anti_clone_audit/plots/elimination_prediction_agreement_heatmap.png`
- `data/hybrid_v13_real_prediction_anti_clone_audit/plots/elimination_confusion_matrices.png`
- `data/hybrid_v13_real_prediction_anti_clone_audit/plots/all_domains_pairwise_prediction_agreement.png`
- `data/hybrid_v13_real_prediction_anti_clone_audit/plots/registered_vs_recomputed_metric_deltas.png`

## Caveats
- This audit validates prediction behavior using locally available artifacts; clinical claims remain screening/support only in simulated context.
- If any slot had missing artifact or recomputation blocker, it is explicitly marked in tables and validators.
