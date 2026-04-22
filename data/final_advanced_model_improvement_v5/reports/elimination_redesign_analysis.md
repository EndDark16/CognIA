# Elimination redesign analysis

            target_variant                                                              definition  positives    n  ambiguous_removed
  elimination_any_baseline                                               target_domain_elimination       1074 1905                  0
elimination_union_internal                        target_enuresis_exact OR target_encopresis_exact       1074 1905                  0
elimination_overlap_strict                       target_enuresis_exact AND target_encopresis_exact        732 1905                  0
   elimination_clear_cases baseline with ambiguous cases removed by direct/absent criteria support       1074 1905                  0

        mode feature_set  feature_count                                                                                                                                                                                                                                                                    features_preview
   caregiver        base             16           age_years|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|has_cbcl|release|sdq_conduct_problems|sdq_emotional_symptoms|sdq_hyperactivity_inattention
   caregiver  engineered             27  age_years|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|der_cbcl_mean|der_cbcl_missing_ratio|der_cbcl_std|der_global_missing_ratio|der_global_nonzero_ratio
   caregiver     compact             20 age_years|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|der_cbcl_missing_ratio|der_global_missing_ratio|der_has_missing_ratio|der_sdq_missing_ratio|has_cbcl
psychologist        base             17                                                  age_years|sex_assigned_at_birth|site|release|has_cbcl|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|has_sdq
psychologist  engineered             28  age_years|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|der_cbcl_mean|der_cbcl_missing_ratio|der_cbcl_std|der_global_missing_ratio|der_global_nonzero_ratio
psychologist     compact             21 age_years|cbcl_aggressive_behavior_proxy|cbcl_anxious_depressed_proxy|cbcl_attention_problems_proxy|cbcl_externalizing_proxy|cbcl_internalizing_proxy|cbcl_rule_breaking_proxy|der_cbcl_missing_ratio|der_global_missing_ratio|der_has_missing_ratio|der_sdq_missing_ratio|has_cbcl

           architecture_id                                      description            expected_benefit
              single_stage  single classifier + threshold + abstention band                    baseline
two_stage_precision_filter stage1 detect + stage2 stricter precision filter reduce FP at cost of recall
