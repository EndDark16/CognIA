# v14 Elimination Real Anti-Clone Rescue Report

Generated: `2026-05-01T03:15:21.734784+00:00`

## Scope
- Focal rescue only for 6 elimination slots.
- No campaign over other domains.
- 24 non-elimination slots kept identical to v13.
- RF-only policy enforced.

## Results
- prediction_recomputed_slots: `30/30`
- elimination_real_clone_count: `0`
- all_domains_real_clone_count: `0`
- all_domains_near_clone_warning_count: `18`
- artifact_duplicate_hash_count: `0`
- guardrail_violation_count: `0`
- final_audit_status: `pass_with_warnings`

## Acceptance Checklist
- elimination_real_clone_count == 0: `yes`
- all_domains_real_clone_count == 0: `yes`
- artifact_duplicate_hash_count == 0: `yes`
- 24 non-elimination unchanged: `yes`
- contract exact all 30: `yes`

## Selected Elimination Candidates
| slot_index | role | mode | candidate_key | source_type | source_model_id | config_id | calibration | threshold_policy | threshold | f1 | recall | precision | balanced_accuracy | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | caregiver | caregiver_1_3 | caregiver_1_3::train::rf_v14_guard_randomized::20270421::none::max_f1_precision_guard::0.740000 | trained_rf_v14 | trained_rf_v14 | rf_v14_guard_randomized | none | max_f1_precision_guard | 0.74 | 0.8363636363636363 | 0.8846153846153846 | 0.7931034482758621 | 0.9282890007189073 | 0.0728182623595568 |
| 2 | caregiver | caregiver_2_3 | caregiver_2_3::train::rf_v14_guard_randomized::20270457::none::max_f1_precision_guard::0.570000 | trained_rf_v14 | trained_rf_v14 | rf_v14_guard_randomized | none | max_f1_precision_guard | 0.57 | 0.8214285714285714 | 0.8846153846153846 | 0.7666666666666667 | 0.9259525521207764 | 0.1285448510648098 |
| 3 | caregiver | caregiver_full | caregiver_full::train::rf_v14_calibrated_isotonic::20270421::isotonic::max_f1_precision_guard::0.600000 | trained_rf_v14 | trained_rf_v14 | rf_v14_calibrated_isotonic | isotonic | max_f1_precision_guard | 0.6 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.0294761435733749 |
| 4 | psychologist | psychologist_1_3 | psychologist_1_3::train::rf_v14_calibrated_isotonic::20270457::isotonic::max_f1_precision_guard::0.410000 | trained_rf_v14 | trained_rf_v14 | rf_v14_calibrated_isotonic | isotonic | max_f1_precision_guard | 0.4099999999999999 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.03080118047908858 |
| 5 | psychologist | psychologist_2_3 | psychologist_2_3::hist::v10_selected::elimination__psychologist_2_3__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10::fixed::0.880000 | historical_v10_selected | elimination__psychologist_2_3__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10 | rf_calibrated_regularized | none | fixed_from_source | 0.8799999999999999 | 0.8376068376068376 | 0.9423076923076923 | 0.7538461538461538 | 0.9524622573687994 | 0.03625781718024713 |
| 6 | psychologist | psychologist_full | psychologist_full::hist::v13_active::elimination__psychologist_full__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10::fixed::0.680000 | historical_v13_active | elimination__psychologist_full__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10 | rf_calibrated_regularized | isotonic | fixed_from_source | 0.6799999999999999 | 0.8403361344537815 | 0.9615384615384616 | 0.746268656716418 | 0.9609094176851186 | 0.029570457099249468 |
| 1 | caregiver | caregiver_1_3 | caregiver_1_3::train::rf_v14_guard_randomized::20270421::none::max_f1_precision_guard::0.740000::joint_thr::0.762162 | trained_rf_v14 | trained_rf_v14 | rf_v14_guard_randomized | none | joint_anti_clone_threshold_tuning | 0.7621616091094605 | 0.8598130841121495 | 0.8846153846153846 | 0.8363636363636363 | 0.9317936736161034 | 0.0728182623595568 |
| 2 | caregiver | caregiver_2_3 | caregiver_2_3::train::rf_v14_guard_randomized::20270457::none::max_f1_precision_guard::0.570000::joint_thr::0.560107 | trained_rf_v14 | trained_rf_v14 | rf_v14_guard_randomized | none | joint_anti_clone_threshold_tuning | 0.5601072169221989 | 0.8214285714285714 | 0.8846153846153846 | 0.7666666666666667 | 0.9259525521207764 | 0.1285448510648098 |
| 3 | caregiver | caregiver_full | caregiver_full::train::rf_v14_calibrated_isotonic::20270421::isotonic::max_f1_precision_guard::0.600000::joint_thr::0.750000 | trained_rf_v14 | trained_rf_v14 | rf_v14_calibrated_isotonic | isotonic | joint_anti_clone_threshold_tuning | 0.7499999999999999 | 0.7128712871287128 | 0.6923076923076923 | 0.7346938775510204 | 0.8309669302659957 | 0.0294761435733749 |
| 4 | psychologist | psychologist_1_3 | psychologist_1_3::train::rf_v14_calibrated_isotonic::20270457::isotonic::max_f1_precision_guard::0.410000::joint_thr::0.280000 | trained_rf_v14 | trained_rf_v14 | rf_v14_calibrated_isotonic | isotonic | joint_anti_clone_threshold_tuning | 0.27999999999999997 | 0.8264462809917356 | 0.9615384615384616 | 0.7246376811594203 | 0.9585729690869877 | 0.03080118047908858 |
| 5 | psychologist | psychologist_2_3 | psychologist_2_3::hist::v10_selected::elimination__psychologist_2_3__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10::fixed::0.880000::joint_thr::0.660000 | historical_v10_selected | elimination__psychologist_2_3__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10 | rf_calibrated_regularized | none | joint_anti_clone_threshold_tuning | 0.6599999999999999 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.03625781718024713 |
| 6 | psychologist | psychologist_full | psychologist_full::hist::v13_active::elimination__psychologist_full__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10::fixed::0.680000::joint_thr::0.525000 | historical_v13_active | elimination__psychologist_full__hybrid_rf_max_real_metrics_v1__rf__same_inputs_v10 | rf_calibrated_regularized | isotonic | joint_anti_clone_threshold_tuning | 0.5249999999999999 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.029570457099249468 |
