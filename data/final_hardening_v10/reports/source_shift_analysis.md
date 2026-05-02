# Source Shift / Missingness Hardening Analysis (v10)

- trials: 50
## Selected policy by domain/mode
- caregiver/adhd: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- caregiver/anxiety: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- caregiver/conduct: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- caregiver/depression: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- caregiver/elimination: policy=high_gap_conservative, dBA=0.0040, dRecall=0.0000, dBrier=0.0000, dRealism=0.0149
- psychologist/adhd: policy=coverage_sensitive, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0070
- psychologist/anxiety: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- psychologist/conduct: policy=base, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0000
- psychologist/depression: policy=high_gap_conservative, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0166
- psychologist/elimination: policy=missingness_aware, dBA=0.0000, dRecall=0.0000, dBrier=0.0000, dRealism=0.0044

## Notes
- Mixed/coverage-aware policies tend to help recall under low coverage but may slightly increase uncertainty.
