# Worktree Cleanup Report

- scope: limpieza de worktrees, respaldo de cambios no commiteados, verificacion de commits no pusheados y aislamiento de ruido local.
- cleanup_execution_date_utc: 2026-05-03

## Classification

| worktree | branch | classification | rationale |
|---|---|---|---|
| cognia_app | main | keep_required; preserve_uncommitted_changes | worktree principal con rama main; ruido respaldado en patches/stash. |
| cognia_app_audit_v13 | audit/v13-real-prediction-anti-clone | remove_clean_merged | worktree limpio sin cambios ni commits no pusheados. |
| cognia_app_ci_close | fix/sonar-main-gate-alignment-v1 | remove_noise_only | tenia cambios locales de ruido/mezcla; respaldado en patch antes de remover. |
| cognia_app_elimination_rescue | fix/elimination-structural-audit-rescue-v1 | remove_noise_only | worktree con ruido local en reportes; respaldado y removido. |
| cognia_app_elimination_v14_fix | fix/elimination-v14-real-anti-clone-rescue | remove_noise_only | worktree con ruido local en reportes; respaldado y removido. |
| cognia_app_final_rf_plus_maximize | fix/global-compatible-rf-champion-selection-v13 | remove_clean_merged | worktree limpio sin pendientes; removido. |
| cognia_app_final_structural_compliance | fix/final-model-structural-compliance-v1 | remove_clean_merged | worktree limpio sin pendientes; removido. |
| cognia_app_mode_rebuild | fix/structural-mode-model-rescue-v1 | remove_clean_merged | worktree limpio sin pendientes; removido. |
| cognia_app_rf_max_real_metrics | train/rf-max-real-metrics-v1 | remove_noise_only | ruido local masivo en reportes/training; respaldado y removido. |
| cognia_app_v15_caregiver_full_fix | fix/v15-elimination-caregiver-full-metric-rescue | remove_noise_only | ruido local en reportes de auditoria; respaldado y removido. |
| cognia_app_v16_final_clean | fix/v16-final-clean-champion-resolution | remove_clean_merged | worktree limpio sin pendientes; removido. |
| cognia_app_v17_runtime_security | fix/v17-runtime-diagnostic-security-final | remove_clean_merged | worktree limpio sin pendientes; removido. |
| cognia_sonar_fix_clean | fix/final-sonar-quality-gate-cleanup | temporary_sonar_worktree; keep_required | worktree limpio creado para cierre Sonar y release flow. |

## Actions Applied

- backup de cambios no commiteados por worktree en `data/worktree_cleanup_audit/patches/*_uncommitted.patch`.
- backup de estado por worktree en `*_status.txt` y `*_diff_stat.txt`.
- verificacion de commits no pusheados: `*_unpushed_commits.txt` (todos en 0).
- limpieza de worktrees no requeridos via `git worktree remove` (`--force` solo en worktrees con ruido local respaldado).
- `git worktree prune` ejecutado para eliminar referencias stale.
- creacion de worktree limpio temporal: `cognia_sonar_fix_clean`.

## Key Results

- worktrees_before: 12
- worktrees_after: 2 (main + temporary sonar worktree)
- removed_worktrees: 11
- uncommitted_changes_preserved_with_patches: true
- unpushed_commits_detected: 0
- functionality_loss_detected: false
- reports_training_noise_committed: false
