# Improvement hypotheses

hypothesis_id                      domain      mode                    category                                    rationale expected_gain methodological_risk implementation_cost priority
          H01                         all       all     model_family_challenger                     RF vs boosters vs TabPFN        medium              medium              medium     high
          H02                 elimination      both             target_redesign        clear/strict variants for elimination        medium              medium              medium     high
          H03                         all      both            feature_redesign derived aggregates and missingness summaries         small                 low                 low     high
          H04 adhd,depression,elimination      both        threshold_refinement            precision_guarded operating point         small                 low                 low     high
          H05                     anxiety caregiver        threshold_refinement                balance precision-recall skew         small                 low                 low     high
          H06                         all      both      calibration_refinement             none/platt/isotonic by val brier         small                 low                 low     high
          H07                         all      both      abstention_uncertainty            band optimization for uncertainty         small                 low                 low   medium
          H08                         all      both       missingness_hardening                    compact/hardened features         small                 low              medium   medium
          H09                         all      both regularization_anti_overfit             stability seeds and split checks         small                 low                 low     high
          H10                 elimination      both      two_stage_architecture                coarse->fine precision filter         small              medium              medium   medium
