# Worktree Recovery Audit (2026-04-17)

## Canonical baseline
- Baseline branch for consolidation: `origin/development` (`985a890` at audit time).
- Policy decision: `development` remains the canonical operational branch.

## Non-destructive protection applied before cleanup
- Backup root (local, outside repo): `C:/Users/andre/Documents/Workspace Academic/Backend Tesis/cognia_worktree_backups/20260417_190150/`
- Snapshot artifacts per worktree:
  - `status.txt`
  - `head.txt`
  - `branch.txt`
  - `ahead_behind_vs_origin_development.txt`
  - `tracked_changes.patch`
  - `tracked_changes_ignore_cr.patch`
  - `untracked_files.txt`
- Safety tags created:
  - `safety/worktree_20260417_190150_feat_openapi-spanish-endpoint-descriptions`
  - `safety/worktree_20260417_190150_feat_openapi-contract-audit-v3`
  - `safety/worktree_20260417_190150_feat_openapi-runtime-contract-v6`
  - `safety/worktree_20260417_190150_hotfix_render-startup`
  - `safety/worktree_20260417_190150_feat_openapi-runtime-hardening-v2`
  - `safety/worktree_20260417_190150_promote_questionnaire-full`

## Classification against `origin/development`

| Worktree path | Branch | Classification | Rationale |
| --- | --- | --- | --- |
| `cognia_app` | `feat/openapi-spanish-endpoint-descriptions` | `KEEP_ONLY_AS_BACKUP` | Contains substantive local uncommitted changes and large untracked research/artifact payloads; not promoted in this recovery window. |
| `.worktrees/openapi_full_intervention` | `feat/openapi-contract-audit-v3` | `REJECT_AS_NOISY` | No substantive diff after `--ignore-cr-at-eol`; only line-ending noise. |
| `.worktrees/openapi_rework` | `feat/openapi-runtime-contract-v6` | `KEEP_IN_DEVELOPMENT_ALREADY` | Clean worktree, no local changes, branch state already represented in `origin/development` history. |
| `cognia_app_deployfix` | `hotfix/render-startup` | `REJECT_AS_NOISY` | Only line-ending churn in scripts/tests, no functional delta. |
| `cognia_app_openapi_intervention` | `feat/openapi-runtime-hardening-v2` | `REJECT_AS_NOISY` | Tracked changes are line-ending churn in reports/scripts/tests; no substantive code/contract delta. |
| `cognia_app_promote_qv2` | `promote/questionnaire-full` | `REJECT_AS_NOISY` | Only line-ending churn in scripts/tests; no functional delta. |

## OpenAPI/Swagger source-of-truth validation scope
- Runtime docs route already serves `docs/openapi.yaml` through `/openapi.yaml`.
- Swagger UI (`/docs`) points to `/openapi.yaml`.
- Added explicit test guardrail to assert endpoint bytes match `docs/openapi.yaml`.

## Worktree cleanup outcome
- Removed obsolete worktrees after backup/tagging:
  - `.worktrees/openapi_full_intervention`
  - `.worktrees/openapi_rework`
  - `cognia_app_deployfix`
  - `cognia_app_openapi_intervention`
  - `cognia_app_promote_qv2`
- Preserved active worktrees:
  - `cognia_app` (primary user workspace, kept as backup-bearing tree)
  - `cognia_app_recovery` (canonical consolidation tree)
