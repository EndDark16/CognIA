# Anxiety Psychologist Extreme Audit (v10)

- baseline_calibrated: BA=0.9977, Recall=1.0000, Precision=0.9851, Brier=0.0035

## Worst degradations under adversarial tests
- drop_scared_sr: dBA=-0.0235, dRecall=-0.0152, dBrier=0.0122 (dropped 49 features)
- drop_top15_importance: dBA=-0.0212, dRecall=-0.0152, dBrier=0.0073 (dropped 15 features)
- drop_all_scared: dBA=-0.0167, dRecall=-0.0152, dBrier=0.0069 (dropped 98 features)
- source_dropout_selfreport: dBA=-0.0121, dRecall=-0.0152, dBrier=0.0084 (self-report cols neutralized: 178)
- site_stress_CUNY: dBA=-0.0096, dRecall=0.0000, dBrier=0.0169 (site subset n=49)
- missingness_stress_40: dBA=-0.0045, dRecall=0.0000, dBrier=0.0040 (random mask 40% cells)
- missingness_stress_20: dBA=-0.0023, dRecall=0.0000, dBrier=0.0033 (random mask 20% cells)
- drop_scared_p: dBA=0.0000, dRecall=0.0000, dBrier=-0.0030 (dropped 49 features)
- release_stress_11.0: dBA=0.0000, dRecall=0.0000, dBrier=0.0000 (release subset n=286)
- site_stress_CBIC: dBA=0.0023, dRecall=0.0000, dBrier=-0.0035 (site subset n=84)

Conclusion: extreme performance is sensitive to targeted self-report/scared ablations but not necessarily indicative of leakage; keep active monitoring with stress guards.
