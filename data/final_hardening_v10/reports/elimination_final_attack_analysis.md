# Elimination Final Attack Analysis (v10)

- caregiver: best=light_ensemble_blend (thr=0.505, src=prob_blend) | recall 0.7019->0.7143 (d=0.0124), BA 0.8109->0.8171 (d=0.0062), precision=0.9200, material=partial
- psychologist: best=recall_first_low_thr (thr=0.425, src=probability) | recall 0.6957->0.7019 (d=0.0062), BA 0.8118->0.8149 (d=0.0031), precision=0.9262, material=partial

Selection enforces non-negative BA delta to avoid recall gains that destabilize screening performance.
