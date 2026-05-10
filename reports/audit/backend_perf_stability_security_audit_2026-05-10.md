# Backend Audit - Performance, Stability, Operational Security (2026-05-10)

## Scope
- Repo: `EndDark16/CognIA`
- Branch: `perf/safe-backend-optimization-audit`
- Goal: audit first, then safe optimization without breaking API contracts or frontend behavior.
- Clinical/methodological guardrail: screening/support in simulated environment only, not automatic diagnosis.

## Protected Dirty Worktree Evidence (preserved, not modified)

### `git status --short`
```
 M scripts/hardening_second_pass.py
 M scripts/rebuild_dsm5_exact_datasets.py
 M scripts/run_pipeline.py
 M scripts/seed_users.py
 M tests/test_health.py
```

### `git diff --numstat -- ...` (protected files)
```
6	6	scripts/hardening_second_pass.py
1666	1666	scripts/rebuild_dsm5_exact_datasets.py
5	5	scripts/run_pipeline.py
62	62	scripts/seed_users.py
54	54	tests/test_health.py
```

Observed warning in all five files:
- `CRLF will be replaced by LF the next time Git touches it`

Interpretation:
- Changes look dominated by line-ending normalization plus whitespace-only churn in sampled hunks.
- These files remain untouched in this audit branch.

## Baseline Deployment Probe (light, non-stress)

Target domain:
- `https://www.cognia.lat`
- expected API base (user-declared): `https://www.cognia.lat/api`

Observed from probe:
- `GET /healthz` -> `200`
- `GET /readyz` -> `200`
- `GET /api/healthz` -> `404`
- `GET /api/readyz` -> `404`
- `POST /api/auth/login` with invalid test creds -> `401`
- `GET /api/v2/questionnaires/active` unauthenticated -> `401`
- `GET /api/v1/questionnaire-runtime/questionnaire/active` unauthenticated -> `401`
- `GET /docs` required access wall in deployment edge (not openly reachable).

Notes:
- TLS validation failed from this local environment due certificate chain verification issue; smoke was repeated with insecure verify for reachability only.
- This is evidence-only probing, not a security recommendation.

## Existing Load/Stress Records Discovery

Found:
- `scripts/k6_smoke.js` (minimal smoke script only).
- `artifacts/api_smoke/endpoint_smoke_report.json` (API endpoint smoke, not a formal k6 load/stress suite).

Initially not found in repo as formal backend load suite artifacts:
- `scripts/load/k6_baseline.js`
- `scripts/load/k6_load.js`
- `scripts/load/k6_stress.js`
- `scripts/load/k6_spike.js`
- `scripts/load/k6_soak.js`
- `reports/load_tests/*` summaries for backend load/stress scenarios.

Status after this audit window:
- formal suite was added under `scripts/load/` with safe-mode controls and URL/prefix normalization guardrails.
- reproducibility docs and report templates were added under `docs/load_testing.md` and `reports/load_tests/`.

## Audit Findings (no code changes applied in this section)

| ID | Type | Severity | Change Risk | Finding | Location | Recommendation | Apply now |
|---|---|---|---|---|---|---|---|
| F01 | performance | high | low | Experimental `/api/predict` loads joblib model on every request, creating avoidable I/O and latency spikes. | `core/models/predictor.py`, `api/services/model_service.py`, `api/routes/predict.py` | Cache model object per worker process (lazy load + reuse). | yes |
| F02 | performance | medium | low | `list_history` in v2 does a per-session result lookup (`N+1` pattern). | `api/services/questionnaire_v2_service.py` (`list_history`) | Batch-load `QuestionnaireSessionResult` for current page ids. | yes |
| F03 | performance | medium | medium | `save_answers` in v2 performs repeated per-answer queries (`question`, `answer`, `repeat mapping`, session item mark). | `api/services/questionnaire_v2_service.py` (`save_answers`) | Prefetch needed rows and update in-memory maps before commit. | yes |
| F04 | stability | medium | low | Runtime v1 history and notifications are unpaginated and can return large payloads under growth. | `api/routes/questionnaire_runtime.py`, `api/services/questionnaire_runtime_service.py` | Add optional pagination contract (backward-compatible) or guarded max page size in service. | no (document first) |
| F05 | performance | medium | low | Dashboard helpers rely on multiple `count()` queries per request and month buckets. | `api/services/questionnaire_v2_service.py` (`_monthly_series`, `dashboard_*`) | Keep current contract, but optimize query strategy and/or short cache for dashboard reads. | partial |
| F06 | observability | medium | low | `/metrics` is in-memory per process and not aggregated across Gunicorn workers. | `api/metrics.py` | Document worker-local nature; for production-grade aggregation use centralized metrics backend. | doc |
| F07 | stability | medium | low | Rate limit storage defaults to in-memory; multi-worker/multi-instance consistency is limited without shared storage. | `api/extensions.py` | Configure shared rate-limit backend (`RATE_LIMIT_STORAGE_URI`) in production. | doc |
| F08 | operational_security | medium | low | PDF/report generation is synchronous inside request path and can block worker time under concurrent use. | `api/services/questionnaire_v2_service.py` (`generate_pdf`, `build_report`) | Keep behavior, add safe-mode skips for load tests and recommend async/offline generation in future. | doc |
| F09 | deployment | medium | low | Gunicorn runtime flags for timeout/keepalive/max-requests are not explicitly tunable in entrypoint command. | `docker/entrypoint.sh` | Accept optional env-based Gunicorn runtime flags with safe defaults. | yes |
| F10 | deployment | medium | low | DB pool settings are hardcoded in production config and not tunable via env for constrained hardware tuning. | `config/settings.py` | Allow env overrides (`DB_POOL_*`) while preserving defaults. | yes |
| F11 | observability | low | low | `/readyz` in code returns `{status, latency_ms}`, but deployed response observed extra `cached` field. | `api/routes/health.py` vs deployed runtime | Mark as deployment/runtime divergence to confirm before contract edits. | no (`por confirmar`) |
| F12 | tests | medium | low | No formal backend load/stress regression suite versioned in `scripts/load` and `reports/load_tests`. | repo-level | Add k6 scenario suite with safe-mode controls and reproducible reporting templates. | yes |

## Current Infrastructure Constraint (explicit)

This audit treats current deployment capacity as constrained and non-final:
- small home server
- Mac 8GB RAM
- Intel i5-6360U x4
- ~16 Mb internet
- Supabase remote DB

Interpretation guardrail:
- measured limits in this phase represent current homelab envelope, not final product capacity.
- bottlenecks may be from host CPU/RAM, residential network, Supabase latency/limits, proxy/gateway, worker/pool configuration, or backend implementation.

## Applied Changes (safe optimization pass)

- `core/models/predictor.py`
  - Added `lru_cache` for model loading to avoid repeated `joblib.load` per request (`F01`).
- `api/services/questionnaire_v2_service.py`
  - Removed per-item repeated queries in `save_answers` via prefetch maps (`F03`).
  - Reworked progress recompute to a single aggregate query (`F03`).
  - Removed `N+1` result summary lookups in `list_history` by page-batch query (`F02`).
- `config/settings.py`
  - Added env-overridable DB pool settings in `ProductionConfig` (`F10`).
  - Added `RATELIMIT_STORAGE_URI` config entry for operational tuning (`F07`).
- `docker/entrypoint.sh`
  - Added optional Gunicorn runtime env flags (`timeout`, `keep-alive`, `max-requests`, `max-requests-jitter`) (`F09`).
- Load/stress suite and docs
  - Added `scripts/load/*.js`, `scripts/load/helpers.js`, `scripts/load/README.md` (`F12`).
  - Added `docs/load_testing.md`, `reports/load_tests/README.md`, `reports/load_tests/summary_template.md`.
  - Updated `scripts/k6_smoke.js` compatibility path to helper-based URL-safe behavior.

## Verification Evidence (post-change)

- `ruff check --select F api tests` -> passed
- `python -m compileall -q api app config core scripts run.py` -> passed
- `python -c "from api.app import create_app; app = create_app(); print(app.name)"` -> `api.app`
- `pytest -q` -> `148 passed, 3 skipped`
- `k6 inspect` executed for all new scripts in `scripts/load/` and compatibility `scripts/k6_smoke.js` -> parse/options OK
- Docker build attempt:
  - `docker build -t cognia-backend:perf-audit .` failed locally due missing Docker daemon (`dockerDesktopLinuxEngine` pipe not found).

## Production Smoke Evidence Artifact

- `reports/load_tests/2026-05-10_preopt_production_smoke_summary.md`
  - includes timestamp, branch, commit, endpoint statuses, and TLS verification caveat for probe environment.

## Pending / Por Confirmar
- Exact production runtime SHA currently serving `cognia.lat`.
- Whether deployment edge rewrites `/metrics` and `/docs` paths (observed behavior suggests edge-layer mediation).
- Availability of test credentials dedicated for safe load testing.
- Host-level observability access during stress tests (CPU/RAM/network live capture).
