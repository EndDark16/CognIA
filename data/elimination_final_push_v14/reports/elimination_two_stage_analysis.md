# elimination v14 two-stage analysis

        mode                 architecture  threshold  coverage_rate  uncertain_rate  precision_decided  recall_decided  specificity_decided  balanced_accuracy_decided  f1_decided  pr_auc_decided  brier_decided  two_stage_objective
   caregiver       single_stage_reference      0.310       1.000000        0.000000           0.860759        0.844720             0.824000                   0.834360    0.852665        0.911523       0.132678             0.873316
   caregiver           coverage_then_risk      0.310       1.000000        0.000000           0.860759        0.844720             0.824000                   0.834360    0.852665        0.911523       0.132678             0.873316
   caregiver    coverage_plus_uncertainty      0.310       0.825175        0.174825           0.860759        0.918919             0.750000                   0.834459    0.888889        0.930750       0.119575             0.863269
   caregiver   coarse_to_fine_uncertainty      0.310       0.825175        0.174825           0.860759        0.918919             0.750000                   0.834459    0.888889        0.930750       0.119575             0.863269
   caregiver two_stage_with_subtype_blend      0.310       0.825175        0.174825           0.860759        0.918919             0.750000                   0.834459    0.888889        0.927466       0.124433             0.862588
psychologist       single_stage_reference      0.375       1.000000        0.000000           0.847561        0.863354             0.800000                   0.831677    0.855385        0.912164       0.134631             0.874835
psychologist           coverage_then_risk      0.375       1.000000        0.000000           0.847561        0.863354             0.800000                   0.831677    0.855385        0.912164       0.134631             0.874835
psychologist   coarse_to_fine_uncertainty      0.375       0.874126        0.125874           0.856250        0.889610             0.760417                   0.825014    0.872611        0.927367       0.127136             0.859938
psychologist    coverage_plus_uncertainty      0.375       0.713287        0.286713           0.873239        0.946565             0.753425                   0.849995    0.908425        0.944579       0.101847             0.859928
psychologist two_stage_with_subtype_blend      0.375       0.692308        0.307692           0.871429        0.945736             0.739130                   0.842433    0.907063        0.941826       0.106776             0.852875
