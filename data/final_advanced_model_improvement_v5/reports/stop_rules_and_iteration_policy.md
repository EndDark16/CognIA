# Stop rules and iteration policy

- max_rounds_per_domain_mode = 3
- stop_if_no_material_signal_after_round2 (delta BA < 0.003 and delta PR-AUC < 0.003) except high-priority domains
- stop_if_gain_with_higher_complexity_without_honesty_gain
- stop_if_gain_within_seed_noise

        mode      domain             target_variant  round1_best_ba  round2_best_ba  round1_best_pr_auc  round2_best_pr_auc material_signal_after_round2 round3_executed                               stop_reason
   caregiver        adhd                   baseline        0.881938        0.880385            0.956740            0.950714                           no             yes                           round3_executed
   caregiver     conduct                   baseline        0.932646        0.926396            0.956133            0.943457                           no              no stop_rule_no_material_signal_after_round2
   caregiver elimination   elimination_any_baseline        0.817615        0.793851            0.895841            0.884698                           no             yes                           round3_executed
   caregiver elimination elimination_union_internal        0.817615        0.793851            0.895841            0.884698                           no             yes                           round3_executed
   caregiver elimination elimination_overlap_strict        0.761746        0.737533            0.754712            0.745998                           no             yes                           round3_executed
   caregiver elimination    elimination_clear_cases        0.817615        0.793851            0.895841            0.884698                           no             yes                           round3_executed
   caregiver     anxiety                   baseline        0.969697        0.970833            0.980789            0.981838                           no             yes                           round3_executed
   caregiver  depression                   baseline        0.907043        0.899174            0.968775            0.959208                           no             yes                           round3_executed
psychologist        adhd                   baseline        0.882832        0.874174            0.955248            0.952241                           no             yes                           round3_executed
psychologist     conduct                   baseline        0.945146        0.932130            0.957399            0.956664                           no              no stop_rule_no_material_signal_after_round2
psychologist elimination   elimination_any_baseline        0.821143        0.794298            0.895841            0.878237                           no             yes                           round3_executed
psychologist elimination elimination_union_internal        0.821143        0.794298            0.895841            0.878237                           no             yes                           round3_executed
psychologist elimination elimination_overlap_strict        0.761746        0.754737            0.761475            0.732460                           no             yes                           round3_executed
psychologist elimination    elimination_clear_cases        0.821143        0.794298            0.895841            0.878237                           no             yes                           round3_executed
psychologist     anxiety                   baseline        0.997727        0.997727            1.000000            0.999887                           no             yes                           round3_executed
psychologist  depression                   baseline        0.905619        0.897712            0.968775            0.964603                           no             yes                           round3_executed
