# v15 Elimination Caregiver Full Metric Rescue Report

Generated: `2026-05-01T06:32:58.666175+00:00`

## Scope
- Focal rescue on elimination/caregiver_full with anti-clone constraints.
- Other 5 elimination slots kept fixed from v14 unless strict anti-clone need.
- 24 non-elimination slots kept identical to v14.
- RF-only policy enforced.

## Results
- prediction_recomputed_slots: `30/30`
- elimination_real_clone_count: `0`
- all_domains_real_clone_count: `0`
- all_domains_near_clone_warning_count: `22`
- artifact_duplicate_hash_count: `0`
- guardrail_violation_count: `0`
- caregiver_full_improved_clearly: `yes`
- changed_elimination_modes: `caregiver_full`
- final_audit_status: `pass_with_warnings`

## Acceptance Checklist
- elimination_real_clone_count == 0: `yes`
- all_domains_real_clone_count == 0: `yes`
- artifact_duplicate_hash_count == 0: `yes`
- 24 non-elimination unchanged: `yes`
- contract exact all 30: `yes`

## caregiver_full v14 -> v15
- v14_f1: `0.712871` -> v15_f1: `0.820513`
- v14_recall: `0.692308` -> v15_recall: `0.923077`
- v14_precision: `0.734694` -> v15_precision: `0.738462`
- v14_balanced_accuracy: `0.830967` -> v15_balanced_accuracy: `0.941679`

## Selected Elimination Candidates
| slot_index | role | mode | candidate_key | source_type | source_model_id | config_id | calibration | threshold_policy | threshold | f1 | recall | precision | balanced_accuracy | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | caregiver | caregiver_1_3 | caregiver_1_3::v14_fixed::elimination__caregiver_1_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13::thr::0.762162 | fixed_v14_active | elimination__caregiver_1_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13 | rf_v14_guard_randomized | none | fixed_v14_active | 0.7621616091094605 | 0.8598130841121495 | 0.8846153846153846 | 0.8363636363636363 | 0.9317936736161034 | 0.0728182623595568 |
| 2 | caregiver | caregiver_2_3 | caregiver_2_3::v14_fixed::elimination__caregiver_2_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13::thr::0.560107 | fixed_v14_active | elimination__caregiver_2_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13 | rf_v14_guard_randomized | none | fixed_v14_active | 0.5601072169221989 | 0.8103448275862069 | 0.9038461538461539 | 0.734375 | 0.9320632638389648 | 0.1285448510648098 |
| 3 | caregiver | caregiver_full | caregiver_full::train::rf_v14_calibrated_isotonic::20270493::isotonic::max_f1_precision_guard::0.750000 | trained_rf_v15 | trained_rf_v15 | rf_v14_calibrated_isotonic | isotonic | max_f1_precision_guard | 0.7499999999999999 | 0.8205128205128205 | 0.9230769230769231 | 0.7384615384615385 | 0.9416786484543493 | 0.029669213987851193 |
| 4 | psychologist | psychologist_1_3 | psychologist_1_3::v14_fixed::elimination__psychologist_1_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13::thr::0.280000 | fixed_v14_active | elimination__psychologist_1_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13 | rf_v14_calibrated_isotonic | isotonic | fixed_v14_active | 0.2799999999999999 | 0.8264462809917356 | 0.9615384615384616 | 0.7246376811594203 | 0.9585729690869877 | 0.030801180479088575 |
| 5 | psychologist | psychologist_2_3 | psychologist_2_3::v14_fixed::elimination__psychologist_2_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13::thr::0.660000 | fixed_v14_active | elimination__psychologist_2_3__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13 | rf_calibrated_regularized | none | fixed_v14_active | 0.6599999999999999 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.03625781718024713 |
| 6 | psychologist | psychologist_full | psychologist_full::v14_fixed::elimination__psychologist_full__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13::thr::0.525000 | fixed_v14_active | elimination__psychologist_full__hybrid_elimination_v14_real_anti_clone_rescue__rf__same_inputs_v13 | rf_calibrated_regularized | isotonic | fixed_v14_active | 0.5249999999999999 | 0.8333333333333334 | 0.9615384615384616 | 0.7352941176470589 | 0.9597411933860532 | 0.029570457099249457 |
