# Final Phase Summary (Hybrid DSM5 v2)

- Hybrid line: `data/processed_hybrid_dsm5_v2/`
- Questionnaire layer: `data/questionnaire_dsm5_v1/` + `artifacts/questionnaire_dsm5_v1/`
- Hybrid datasets exported (csv): 78
- Trained models: 15
- Domain models trained: adhd, anxiety, conduct, depression, elimination
- Internal exact models trained: target_adhd_exact

Best domain models (test):
- adhd: domain_adhd_research_full | bal_acc=1.0000 | precision=1.0000 | recall=1.0000 | specificity=1.0000
- anxiety: domain_anxiety_strict_full | bal_acc=0.9879 | precision=0.9701 | recall=0.9848 | specificity=0.9909
- conduct: domain_conduct_research_full | bal_acc=0.9889 | precision=0.9753 | recall=0.9875 | specificity=0.9903
- depression: domain_depression_strict_full | bal_acc=0.9782 | precision=0.9739 | recall=0.9739 | specificity=0.9825
- elimination: domain_elimination_strict_full | bal_acc=1.0000 | precision=1.0000 | recall=1.0000 | specificity=1.0000

Key artifact roots:
- `reports/training_history/`
- `reports/metrics_hybrid_v2/`
- `models/hybrid_dsm5_v2/`
- `artifacts/hybrid_dsm5_v2/models/`
- `artifacts/inference_v2/`
