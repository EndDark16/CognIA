# Final Validation Diagnosis (v9)

## Macro (v9 recomputed)
- caregiver: BA=0.8976, F1=0.8702, ROC-AUC=0.9496, PR-AUC=0.9423, Brier=0.0729, uncertain_rate=0.0622
- psychologist: BA=0.9120, F1=0.9026, ROC-AUC=0.9549, PR-AUC=0.9535, Brier=0.0639, uncertain_rate=0.0818

## Domains requiring higher caution
- caregiver/elimination: BA=0.8109, uncertain_rate=0.164, flagged_patterns=1, fragile_slices=1
- psychologist/elimination: BA=0.8118, uncertain_rate=0.007, flagged_patterns=1, fragile_slices=1
- psychologist/anxiety: BA=0.9977, uncertain_rate=0.255, flagged_patterns=3, fragile_slices=0
