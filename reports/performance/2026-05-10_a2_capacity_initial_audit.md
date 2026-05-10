# A2 Capacity Initial Audit (2026-05-10)

## Scope
- Intervention: `A2 capacity + reliability optimization`
- Branch target: `perf/a2-capacity-reliability-optimization`
- Base SHA: `0bfcf24fe3adf6bdfb24d7508e0f0a53e6e2cac0` (origin/main at start)
- API contract rule: no breaking changes on existing endpoints/inputs/outputs.

## Protected Files Policy
Protected/sucios files explicitly preserved in primary workspace (`cognia_app`) and never modified in this intervention:
- `scripts/hardening_second_pass.py`
- `scripts/rebuild_dsm5_exact_datasets.py`
- `scripts/run_pipeline.py`
- `scripts/seed_users.py`
- `tests/test_health.py`

## Evidence Snapshot (Primary Workspace)
Command: `git status --short`
- `M scripts/hardening_second_pass.py`
- `M scripts/rebuild_dsm5_exact_datasets.py`
- `M scripts/run_pipeline.py`
- `M scripts/seed_users.py`
- `M tests/test_health.py`
- `?? artifacts/load_tests/`

Command: `git status --short -- scripts/hardening_second_pass.py scripts/rebuild_dsm5_exact_datasets.py scripts/run_pipeline.py scripts/seed_users.py tests/test_health.py`
- same 5 protected files reported modified.

## Working Strategy
- A2 implementation executed on isolated branch/clone to avoid contaminating protected files.
- No stash/reset/restore/checkout performed on protected files.
- Commits limited to backend internals, tests, load suite scripts, and docs/reports for A2.

## Baseline Reference (from prior A1 reports)
- Pre-A1 baseline `10 VUs / 5m`: error `~32.70%`, global p95 `~7615 ms`.
- Post-A1 baseline `10 VUs / 5m`: error `0.0843%`, global p95 `2303.24 ms`.
- Remaining gap motivating A2: reduce p95/outliers and push stable capacity beyond 10 VUs.
