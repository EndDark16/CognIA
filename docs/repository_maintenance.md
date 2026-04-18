# Repository Maintenance Notes

## Goal
Keep CognIA backend maintainable while preserving methodological traceability.

## Maintenance principles

1. Prefer additive and reversible changes.
2. Avoid destructive cleanup on source-of-truth artifacts.
3. Keep runtime-generated files out of Git.
4. Update docs and tests in the same change window.

## Current organization decisions

- API contracts:
  - machine-readable: `docs/openapi.yaml`
  - maintainer overview: `docs/api_full_reference.md`
- Questionnaire architecture:
  - `docs/questionnaire_backend_architecture.md`
  - `docs/questionnaire_api_contract.md`
- Problem-reporting backend:
  - `docs/problem_reporting_backend.md`
- Repository content policy:
  - `docs/repository_artifact_policy.md`
- Traceability map:
  - `docs/traceability_map.md`

## Cleanup actions in this cycle

- Removed deprecated v1 questionnaire activation/clone endpoints and aligned docs/tests to admin equivalents.
- Added explicit policy for runtime uploads and generated exports (`problem_reports` attachments and runtime PDFs).
- Normalized `.gitattributes` and `.gitignore` rules for safer cross-platform behavior and artifact hygiene.
- Consolidated OpenAPI source-of-truth in `docs/openapi.yaml`; moved legacy addendum to `docs/archive/openapi/`.
- Added automated runtime-vs-spec guardrail test: `tests/contracts/test_openapi_runtime_alignment.py`.

## Canonical branch and worktree governance

- Canonical operational branch: `development`.
- For any consolidation/recovery operation:
  1. Use `origin/development` as comparison baseline.
  2. Audit every worktree before edits/removal.
  3. Snapshot dirty state (`status`, `diff`, `untracked`) before cleanup.
  4. Classify differences as:
     - `KEEP_IN_DEVELOPMENT_ALREADY`
     - `CHERRY_PICK_SAFE`
     - `MANUAL_PORT_REQUIRED`
     - `REJECT_AS_NOISY`
     - `REJECT_AS_DANGEROUS`
     - `KEEP_ONLY_AS_BACKUP`
- Do not promote worktree-local state over `development` without explicit validation.
- Keep Swagger/OpenAPI single source of truth in `docs/openapi.yaml`; archival specs stay historical only.

## Pending non-destructive opportunities

- Incremental normalization of legacy docs that still duplicate historical narratives.
- Optional split of very large monolithic docs into indexed sub-documents by domain.
- Optional route inventory automation script to reduce manual drift.
