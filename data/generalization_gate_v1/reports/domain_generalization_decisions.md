# Domain Generalization Decisions

- adhd: model=domain_adhd_research_full | mode=precise | product_ready=False | main_risk=possible_leakage_model
- anxiety: model=retrained_anxiety_anti_overfit_v1 | mode=precise | product_ready=True | main_risk=accepted_but_experimental
- conduct: model=domain_conduct_research_full | mode=precise | product_ready=True | main_risk=accepted_but_experimental
- depression: model=domain_depression_strict_full | mode=precise | product_ready=True | main_risk=accepted_but_experimental
- elimination: model=domain_elimination_strict_full | mode=precise | product_ready=False | main_risk=high_risk_of_overfit
