# Stop Rule Assessment (v10)

- stop_rule_material: macro dBA >= +0.005 OR elimination dRecall >= +0.03 with non-negative dBA
- stop_rule_marginal: macro dBA >= +0.001 OR elimination dRecall > 0

- caregiver: dBA=0.0012, dRecall=0.0025, dBrier=-0.0004
- psychologist: dBA=0.0006, dRecall=0.0012, dBrier=0.0000
- elimination caregiver: dRecall=0.0124, dBA=0.0062, dBrier=-0.0022
- elimination psychologist: dRecall=0.0062, dBA=0.0031, dBrier=0.0000

- material_improvement_detected: no
- marginal_improvement_detected: yes
