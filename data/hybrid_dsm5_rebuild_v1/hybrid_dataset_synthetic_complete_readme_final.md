Synthetic hybrid dataset final.

Rows generated: 2400
Columns total: 224

Structure:
- participant_id
- 30 clean-base HBN-synthetic defendible features
- 193 explicit DSM-5 quantitative features

Generation principles:
- Started from the final hybrid template structure, not from prior rows.
- Rebuilt the clean-base layer using empirical distributions from the existing synthetic source, after completing it and resampling with small perturbations.
- Generated the DSM-5 layer as internally coherent quantitative features using domain-linked latent severity signals anchored to the clean-base layer.
- Enforced transparent algebra and threshold consistency for totals and DSM-5 derived flags.

Important:
- This file is synthetic and internally coherent.
- It is intended for training/research iteration, not as a claim of exact HBN replication.
