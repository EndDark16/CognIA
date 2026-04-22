# Suspicious Pattern Audit (v9)

## Scope
- Anxiety psychologist near-perfect metrics.
- Near-equality caregiver/psychologist in conduct, elimination, depression.
- Hash/reuse checks and high-signal feature scan.

- flagged_checks: 5
- pass_checks: 5

- [ANX_PSY_001] anxiety/near_perfect_metrics: Near-perfect performance needs leakage/reuse audit. (BA >= 0.99 on strict test.)
- [ANX_PSY_004] anxiety/distribution_separation: Very sharp separation between probabilities and labels; could reflect strong signal, not leakage by itself. (mean_abs_prob_error=0.0041)
- [CONDUCT_EQ_001] conduct/metric_delta_between_modes: Very small metric delta across modes. (BA_care=0.9493, BA_psy=0.9514)
- [ELIMINATION_EQ_001] elimination/metric_delta_between_modes: Very small metric delta across modes. (BA_care=0.8109, BA_psy=0.8118)
- [ANX_PSY_005] anxiety/high_signal_feature_scan: Very high-signal anxiety features exist; may explain near-perfect without direct leakage. (scared_sr_total:0.995; scared_sr_generalized_anxiety:0.992; scared_p_total:0.990; scared_sr_separation_anxiety:0.990; scared_sr_panic_somatic:0.985)

## Conclusions
- No direct evidence of prediction artifact reuse (prediction hashes differ across modes).
- Anxiety-psychologist remains suspiciously high but is explainable by richer feature coverage/self-report and high-signal anxiety variables; leakage remains unproven.
- Similarity in conduct/elimination/depression appears due to overlapping signal and operating points, not identical prediction vectors.
