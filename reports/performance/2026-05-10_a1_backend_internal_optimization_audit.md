# 2026-05-10 A1 Backend Internal Optimization Audit

## Scope
- Repository: `EndDark16/CognIA`
- Branch: `perf/a1-backend-internal-optimization`
- Objective: internal performance/observability/stability optimization without breaking public API contracts.
- API contract policy applied: no path/method/request/response schema changes in existing endpoints.

## Infrastructure Context (Current, Non-Final)
- Homelab server with constrained resources.
- Client machine for tests: Mac 8 GB RAM, Intel Core i5-6360U x4, ~16 Mb internet.
- External DB: Supabase.
- This environment is not representative of future robust server + fiber capacity.

## Baseline Evidence Before A1
- Source report: `reports/load_tests/2026-05-10_backend_perf_final_report.md`
- Smoke (preopt): error rate ~2.74%, p95 ~6377 ms.
- Baseline 10 VUs/5m (preopt): error rate ~32.70%, p95 ~7615 ms.
- Stop criteria was triggered in preopt baseline; no further aggressive scenarios executed.

## Findings (Prioritized)

### F-01 JWT blocklist hot path querying refresh token table for access token path
- Type: performance, stability
- Severity: high
- Change risk: low
- Location: `api/app.py` (`token_in_blocklist_loader`)
- Impact: unnecessary DB round-trips on authenticated hot path.
- Recommendation: query `refresh_token` only when JWT `type=refresh`, and cache user revocation state with short TTL.
- Applied now: yes
- API contract impact: none
- Tests: added access-token hot-path regression test.

### F-02 Limited request-level observability and low endpoint granularity
- Type: observability, operations
- Severity: high
- Change risk: low
- Location: `api/app.py`, `api/metrics.py`
- Impact: difficult correlation of latency/errors by endpoint/status.
- Recommendation: request-id propagation, structured request logs, endpoint metrics and error counters; preserve legacy `/metrics` fields.
- Applied now: yes
- API contract impact: none for existing endpoint schemas; `/metrics` extended backward-compatibly.
- Tests: added observability tests.

### F-03 `/api/v2/questionnaires/active` recomputation on every request
- Type: performance
- Severity: high
- Change risk: medium
- Location: `api/services/questionnaire_v2_service.py`
- Impact: repeated catalog/model confidence queries and payload rebuild.
- Recommendation: in-memory TTL cache keyed by role/mode/page/page_size/include_full + active version + pipeline version; explicit invalidation on loader sync/bootstrap.
- Applied now: yes
- API contract impact: none (same payload shape)
- Tests: added cache+invalidation regression test.

### F-04 Session page endpoint fetching all pages and slicing in memory
- Type: performance
- Severity: medium
- Change risk: low
- Location: `api/services/questionnaire_v2_service.py` (`get_session_page_payload`)
- Impact: higher query/memory cost for paged reads.
- Recommendation: fetch only requested page window via page_number query.
- Applied now: yes
- API contract impact: none
- Tests: covered by existing questionnaire v2 flow tests.

### F-05 N+1 risk in users list and problem reports attachments
- Type: performance
- Severity: medium
- Change risk: low
- Location: `api/routes/users.py`, `api/services/admin_service.py`, `api/services/problem_report_service.py`, `api/routes/problem_reports.py`
- Impact: avoidable per-row lazy-load queries.
- Recommendation: `selectinload` for roles and batch-preload attachments map.
- Applied now: yes
- API contract impact: none
- Tests: existing users/problem_reports tests + full suite.

### F-06 Heavy matplotlib import at worker startup
- Type: performance, stability
- Severity: medium
- Change risk: low
- Location: `api/services/questionnaire_v2_service.py`
- Impact: worker memory/startup cost even when PDF/report endpoints are idle.
- Recommendation: lazy import matplotlib backend only when PDF/report generation is requested.
- Applied now: yes
- API contract impact: none
- Tests: existing PDF/report tests pass.

### F-07 Missing composite indexes on hot read paths
- Type: performance, DB
- Severity: medium
- Change risk: medium
- Location: new Alembic migration `migrations/versions/20260510_01_add_perf_hotpath_indexes.py`
- Impact: lower scan/latency cost for common filters/order patterns.
- Recommendation: add safe composite indexes with idempotent existence checks.
- Applied now: yes
- API contract impact: none
- Tests: full pytest; migration syntax validated by compile/import.

### F-08 Entrypoint did not wire all Gunicorn knobs and had duplicated bind assignment
- Type: deployment, stability
- Severity: medium
- Change risk: low
- Location: `docker/entrypoint.sh`
- Impact: reduced tuning control and startup ambiguity.
- Recommendation: wire `GUNICORN_WORKER_CLASS` and `GUNICORN_GRACEFUL_TIMEOUT`, remove duplicate bind, print effective non-secret settings.
- Applied now: yes
- API contract impact: none
- Tests: compile/test suite unaffected.

### F-09 Homelab defaults too aggressive in compose/config
- Type: stability, deployment
- Severity: medium
- Change risk: medium
- Location: `docker-compose.yml`, `config/settings.py`, `docs/load_testing.md`
- Impact: unnecessary DB/Gunicorn concurrency pressure on constrained host.
- Recommendation: conservative defaults for homelab profile while keeping env override capability.
- Applied now: yes
- API contract impact: none

## Changes Explicitly Deferred (Recommended, Not Applied)
- Durable async queues for submit/PDF/email (Redis/RQ/Celery or DB-backed jobs).
- Deep health endpoint with internal-only diagnostics.
- Contract-level pagination changes (e.g., optional `include_total=false`, keyset pagination).
- Runtime-wide cross-worker shared cache layer (Redis) for active payload and auth state.

## Contract Safety Statement
- No existing endpoint path or HTTP method was changed.
- No existing request body schema was changed.
- No existing response JSON fields were removed/renamed.
- No expected response status codes were intentionally changed.
- Frontend compatibility constraints were preserved.

## Protected/Dirty File Safeguard
- Main workspace protected dirty files were preserved and not modified:
  - `scripts/hardening_second_pass.py`
  - `scripts/rebuild_dsm5_exact_datasets.py`
  - `scripts/run_pipeline.py`
  - `scripts/seed_users.py`
  - `tests/test_health.py`
- This A1 work proceeded in isolated worktree/branch.
