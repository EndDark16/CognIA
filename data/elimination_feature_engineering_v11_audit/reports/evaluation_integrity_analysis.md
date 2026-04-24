# evaluation integrity

                                       check_name    status                                                                                                                                                      detail
                               split_disjointness      pass                                                                                                                                                   (0, 0, 0)
                    v11_manifest_split_path_match      pass manifest_split_dir=C:\Users\andre\Documents\Workspace Academic\Backend Tesis\cognia_app\data\processed_hybrid_dsm5_v2\splits\domain_elimination_strict_full
                      same_holdout_hash_reference      pass              ordered=9529927227be7db57bfc27568de0e2cc43b9195a635c2f47559f15068fa0fe4a; set=be5c57d800b8da9a394599b21e324eeb07813cac1e2898e7f1e8e1edb5ab7b38
                 recomputed_vs_manifest_caregiver      pass                                                                                                                                   max_abs_diff=0.0000000000
              recomputed_vs_manifest_psychologist      pass                                                                                                                                   max_abs_diff=0.0000000000
                   prediction_hash_distinct_modes      pass                                                                                                                                   caregiver_vs_psychologist
              shortcut_rule_equivalence_caregiver      warn                                                                                                                                       max_diff=0.0080000000
           shortcut_rule_equivalence_psychologist      fail                                                                                                                                       max_diff=0.0000000000
                      extreme_performance_trigger triggered                                                                                                                             rule: BA>=0.995 or P/R/Spec=1.0
     extreme_audit_ablation_cbcl108_112_caregiver      pass                                                                                                                      delta_ba_without_cbcl108_112=-0.004000
   extreme_audit_probability_saturation_caregiver      warn                                                                                                                                saturation_rate_raw=0.541958
  extreme_audit_ablation_cbcl108_112_psychologist      fail                                                                                                                      delta_ba_without_cbcl108_112=-0.010211
extreme_audit_probability_saturation_psychologist      warn                                                                                                                                saturation_rate_raw=0.524476

- Confidence visible policy: user[1%,99%], professional[0.5%,99.5%], internal raw unchanged.
