# Stop rule assessment

        mode      domain  delta_ba  delta_recall  delta_brier improvement_level                                 stop_rule                              decision
   caregiver  depression  0.025533      0.173922     0.004538          material stop_if_no_material_signal_after_2_rounds allow_micro_refinement_only_if_needed
   caregiver        adhd -0.000751      0.014498     0.000884              none stop_if_no_material_signal_after_2_rounds                                  stop
   caregiver elimination  0.000015      0.000030    -0.000498              none stop_if_no_material_signal_after_2_rounds                                  stop
psychologist  depression -0.000767      0.060822     0.001738          material stop_if_no_material_signal_after_2_rounds allow_micro_refinement_only_if_needed
psychologist        adhd  0.006243      0.012387     0.000534          marginal stop_if_no_material_signal_after_2_rounds                                  stop
psychologist elimination  0.009332      0.018663    -0.001431          marginal stop_if_no_material_signal_after_2_rounds                                  stop
