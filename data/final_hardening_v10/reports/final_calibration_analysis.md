# Final Calibration and Operating Point Analysis (v10)

- caregiver/adhd: policy=threshold_hardened, threshold 0.605->0.455, BA=0.8713, Recall=0.8385, Precision=0.9184, Brier=0.0871
- caregiver/conduct: policy=base, threshold 0.135->0.135, BA=0.9493, Recall=0.9375, Precision=0.9036, Brier=0.0352
- caregiver/elimination: policy=light_ensemble_blend, threshold 0.505->0.505, BA=0.8171, Recall=0.7143, Precision=0.9200, Brier=0.1463
- caregiver/anxiety: policy=base, threshold 0.100->0.100, BA=0.9439, Recall=0.9697, Precision=0.7805, Brier=0.0321
- caregiver/depression: policy=threshold_hardened, threshold 0.120->0.100, BA=0.9127, Recall=0.9130, Precision=0.8750, Brier=0.0614
- psychologist/adhd: policy=threshold_hardened, threshold 0.605->0.505, BA=0.8721, Recall=0.8323, Precision=0.9241, Brier=0.0825
- psychologist/conduct: policy=base, threshold 0.335->0.335, BA=0.9514, Recall=0.9125, Precision=0.9733, Brier=0.0340
- psychologist/elimination: policy=recall_first_low_thr, threshold 0.505->0.425, BA=0.8149, Recall=0.7019, Precision=0.9262, Brier=0.1446
- psychologist/anxiety: policy=base, threshold 0.100->0.100, BA=0.9977, Recall=1.0000, Precision=0.9851, Brier=0.0028
- psychologist/depression: policy=threshold_hardened, threshold 0.120->0.080, BA=0.9271, Recall=0.9478, Precision=0.8720, Brier=0.0557
