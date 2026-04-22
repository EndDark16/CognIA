# Final stability analysis

- estabilidad analizada en seeds/splits (cuando disponible), missingness, coverage drop, source mix y casos borderline.

| mode | domain | seed_std | split_std | missingness_delta | coverage_drop_delta | source_mix_delta | borderline_delta_ba | fragile_slice_status | stability_status | stability_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| caregiver | adhd | 0.001999 | 0.003224 | 0.009602 | 0.003891 | 0.003224 |  | por_confirmar | stable | v4 full_results + v10 slice gap |
| caregiver | anxiety | 0.003726 | 0.003598 | 0.019318 | 0.036458 | -0.003598 |  | por_confirmar | stable | v4 full_results + v10 slice gap |
| caregiver | conduct | 0.003641 | 0.003641 | -0.002640 | 0.017150 | -0.003641 | -0.046555 | no | stable | v4 full_results + v10 slice gap |
| caregiver | depression | 0.001462 | 0.001462 | 0.018555 | 0.010984 | 0.001462 | -0.069266 | partial | stable | v4 full_results + v10 slice gap |
| caregiver | elimination |  |  | -0.064845 | -0.010161 | -0.017789 | -0.240652 | structural_fragility_detected | fragile_but_bounded | baseline_ba=0.829938; stress-scenario matrix |
| psychologist | adhd | 0.001697 | 0.001553 | 0.007143 | 0.005373 | 0.001553 |  | por_confirmar | stable | v4 full_results + v10 slice gap |
| psychologist | anxiety | 0.000000 | 0.000000 | -0.000758 | 0.244697 | 0.000000 |  | por_confirmar | watch | v4 full_results + v10 slice gap |
| psychologist | conduct | 0.002569 | 0.000516 | -0.001608 | 0.014298 | -0.000516 | -0.020840 | no | stable | v4 full_results + v10 slice gap |
| psychologist | depression | 0.004941 | 0.001443 | 0.015745 | 0.015913 | -0.001443 |  | por_confirmar | stable | v4 full_results + v10 slice gap |
| psychologist | elimination |  |  | -0.031106 | -0.005739 | -0.004000 | -0.223303 | structural_fragility_detected | fragile_but_bounded | baseline_ba=0.831677; stress-scenario matrix |
