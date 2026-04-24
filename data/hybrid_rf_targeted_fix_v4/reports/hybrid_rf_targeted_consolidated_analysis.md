# Hybrid RF Targeted v4 - Consolidated Analysis

## Ranked candidates
| candidate_id | holdout_precision | holdout_recall | holdout_balanced_accuracy | holdout_pr_auc | holdout_brier | ranking_score |
| --- | --- | --- | --- | --- | --- | --- |
| elimination__caregiver_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000147 | 0.912161 |
| elimination__psychologist_2_3 | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 | 0.912102 |
| anxiety__caregiver_2_3 | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 | 0.863641 |
| anxiety__caregiver_full | 0.916667 | 0.895349 | 0.938791 | 0.936379 | 0.030046 | 0.847656 |
| depression__psychologist_2_3 | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 | 0.806237 |
| depression__psychologist_full | 0.825581 | 0.865854 | 0.914083 | 0.947749 | 0.033654 | 0.804100 |
| elimination__caregiver_1_3 | 0.807018 | 0.884615 | 0.929457 | 0.943277 | 0.021935 | 0.802373 |
| depression__caregiver_full | 0.804348 | 0.902439 | 0.928606 | 0.911586 | 0.037988 | 0.795895 |
| depression__caregiver_2_3 | 0.800000 | 0.878049 | 0.916411 | 0.882349 | 0.044623 | 0.782997 |
| elimination__psychologist_1_3 | 0.788462 | 0.788462 | 0.881380 | 0.873756 | 0.031237 | 0.760539 |
| depression__caregiver_1_3 | 0.822785 | 0.792683 | 0.878754 | 0.796155 | 0.054220 | 0.758253 |
| anxiety__caregiver_1_3 | 0.852941 | 0.674419 | 0.824519 | 0.815098 | 0.063315 | 0.748155 |
| adhd__caregiver_2_3 | 0.722222 | 0.968085 | 0.938706 | 0.737523 | 0.059766 | 0.738960 |
| adhd__psychologist_2_3 | 0.718750 | 0.978723 | 0.942730 | 0.729884 | 0.059185 | 0.738272 |
| depression__psychologist_1_3 | 0.767442 | 0.804878 | 0.877313 | 0.801131 | 0.057291 | 0.737640 |
| adhd__caregiver_1_3 | 0.620000 | 0.989362 | 0.920847 | 0.639851 | 0.078998 | 0.676793 |
| adhd__psychologist_1_3 | 0.617450 | 0.978723 | 0.915528 | 0.623836 | 0.078090 | 0.670622 |

## Final champions by domain
| domain | champion_mode | champion_role | champion_decision | champion_source_line | precision | recall | balanced_accuracy | pr_auc | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adhd | psychologist_full | psychologist | CARRY_FORWARD_V3 | v3_carry_forward | 0.948454 | 0.978723 | 0.982885 | 0.980874 | 0.010648 |
| anxiety | caregiver_2_3 | caregiver | PROMOTE_WITH_CAVEAT | v4_targeted | 0.950617 | 0.895349 | 0.942598 | 0.940175 | 0.019952 |
| conduct | psychologist_2_3 | psychologist | CARRY_FORWARD_V3 | v3_carry_forward | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000657 |
| depression | psychologist_2_3 | psychologist | PROMOTE_WITH_CAVEAT | v4_targeted | 0.891892 | 0.804878 | 0.892389 | 0.879506 | 0.043644 |
| elimination | psychologist_2_3 | psychologist | CEILING_CONFIRMED_NO_MATERIAL_GAIN | v4_targeted | 0.981132 | 1.000000 | 0.998832 | 1.000000 | 0.000887 |
