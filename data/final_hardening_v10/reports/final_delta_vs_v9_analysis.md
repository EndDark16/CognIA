# Final Delta vs V9 Analysis (v10)

## Macro deltas
- caregiver: dBA=0.0012, dRecall=0.0025, dPrecision=0.0003, dF1=0.0017, dPR-AUC=0.0011, dBrier=-0.0004
- psychologist: dBA=0.0006, dRecall=0.0012, dPrecision=0.0001, dF1=0.0009, dPR-AUC=0.0000, dBrier=0.0000

## Domain deltas
- caregiver/adhd: dBA=0.0000, dRecall=0.0000, dPrecision=-0.0000, dBrier=0.0000, fragile_slices 0->0
- caregiver/anxiety: dBA=0.0000, dRecall=0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 0->0
- caregiver/conduct: dBA=-0.0000, dRecall=0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 1->0
- caregiver/depression: dBA=0.0000, dRecall=-0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 1->0
- caregiver/elimination: dBA=0.0062, dRecall=0.0124, dPrecision=0.0013, dBrier=-0.0022, fragile_slices 1->1
- psychologist/adhd: dBA=0.0000, dRecall=0.0000, dPrecision=-0.0000, dBrier=0.0000, fragile_slices 0->0
- psychologist/anxiety: dBA=0.0000, dRecall=0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 0->0
- psychologist/conduct: dBA=0.0000, dRecall=0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 1->0
- psychologist/depression: dBA=0.0000, dRecall=0.0000, dPrecision=0.0000, dBrier=0.0000, fragile_slices 0->0
- psychologist/elimination: dBA=0.0031, dRecall=0.0062, dPrecision=0.0006, dBrier=0.0000, fragile_slices 1->1
