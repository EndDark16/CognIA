# Ceiling status analysis

## Stop rules aplicadas

1. `delta_within_noise`: mejoras recientes en BA/PR-AUC/Brier menores o iguales al ruido bootstrap.
2. penalizacion por robustez: si estabilidad no es aceptable, no se marca `ceiling_reached`.
3. penalizacion operativa: si no entra en runtime fuerte, se evita sobre-claim aunque el delta este en ruido.
4. para Elimination se respeta `KEEP_V12` y `uncertainty_preferred` como limite operativo vigente.

| mode | domain | recent_delta_ba | recent_delta_pr_auc | recent_delta_brier | noise_half_ba | noise_half_pr_auc | noise_half_brier | delta_within_noise | runtime_strong_entry | stability_status | ceiling_classification | decision_rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| caregiver | adhd | 0.009012 | 0.001852 | -0.003023 | 0.010000 | 0.010000 | 0.005000 | True | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| caregiver | anxiety | -0.001326 | -0.013506 | 0.002550 | 0.010000 | 0.010000 | 0.005000 | False | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| caregiver | conduct | -0.024150 | -0.002789 | 0.005161 | 0.010000 | 0.010000 | 0.005000 | False | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| caregiver | depression | -0.004157 | -0.008234 | -0.003193 | 0.010000 | 0.010000 | 0.005000 | True | True | stable | ceiling_reached | recent deltas within bootstrap noise and stability acceptable |
| caregiver | elimination | 0.000000 | 0.000000 | 0.000000 | 0.040217 | 0.047345 | 0.020539 | True | False | fragile_but_bounded | near_ceiling | KEEP_V12 + structural limit + uncertainty_preferred |
| psychologist | adhd | 0.008236 | -0.002845 | 0.001027 | 0.010000 | 0.010000 | 0.005000 | True | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| psychologist | anxiety | -0.007576 | -0.008149 | 0.002199 | 0.010000 | 0.010000 | 0.005000 | True | True | watch | marginal_room_left | only small/mixed deltas after final campaign |
| psychologist | conduct | -0.027943 | -0.009267 | 0.008677 | 0.010000 | 0.010000 | 0.005000 | False | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| psychologist | depression | -0.018605 | -0.016848 | 0.002658 | 0.010000 | 0.010000 | 0.005000 | False | True | stable | near_ceiling | high final BA with mixed/noisy recent deltas; additional gains likely marginal |
| psychologist | elimination | 0.000000 | 0.000000 | 0.000000 | 0.039828 | 0.089316 | 0.011114 | True | False | fragile_but_bounded | near_ceiling | KEEP_V12 + structural limit + uncertainty_preferred |
