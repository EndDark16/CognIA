# A3 Professional Audit (2026-05-10)

## Scope
- Branch: `perf/a3-professional-reliability-cache-queue`
- Base SHA: `7704e248a096aabaab6d8749a2b49ab2903c93dc`
- API contract policy: no breaking changes in endpoints/inputs/outputs.
- Protected files policy: preserved outside A3 workspace and not touched in this branch.

## Findings

| ID | Category | Severity | Risk of Change | Location | Finding | API Contract Impact | Apply Now | Tests Needed |
|---|---|---|---|---|---|---|---|---|
| A3-01 | cache/performance | high | medium | `api/cache.py` | Redis backend serializes with `pickle`; lacks explicit fail-open/required mode/timeouts and runtime fallback counters. | none (internal) | yes | cache backend unit tests (memory, fallback, ttl, prefix, fail-open) |
| A3-02 | reliability | medium | low | `config/settings.py` | Missing explicit knobs for cache required/fail-open/default ttl/redis timeouts. | none | yes | config + app init sanity |
| A3-03 | observability | medium | low | `api/metrics.py` | Metrics lack cache backend health/fallback telemetry; difficult to correlate Redis/cache failures with latency spikes. | backward-compatible additive only | yes | metrics compatibility tests |
| A3-04 | operational security | medium | low | `api/app.py` + limiter setup | Rate-limit storage is configurable but no explicit documented fail-open strategy and no explicit A3 endpoint backpressure knobs. | none | yes | route functional regression |
| A3-05 | backpressure | high | medium | `api/routes/questionnaire_v2.py` | Heavy endpoints (`submit`, `pdf/generate`, dashboards/reports) are not consistently rate-limited. Risk of homelab saturation. | none (429 standard behavior) | yes | endpoint regression tests |
| A3-06 | backpressure | medium | low | `api/routes/problem_reports.py` | Create report endpoint has no dedicated limiter despite file upload path. | none (429 standard behavior) | yes | problem report tests + limiter behavior smoke |
| A3-07 | warmup operability | medium | low | `scripts/warmup_backend.py` | Warmup script lacks explicit WAF/CDN handling guidance and curl-compatible fallback flags/headers controls. | none | yes | warmup unit tests |
| A3-08 | warmup operability | low | low | `scripts/` | No shell warmup fallback script for environments where Python client gets blocked but curl works. | none | yes | basic shell lint/manual usage |
| A3-09 | queue readiness | medium | medium | `app/models.py` + services | `ReportJob` exists, but no dedicated internal queue service/worker contract for optional future async migration. | none | partial (doc + optional internal service) | service unit tests (if implemented) |
| A3-10 | docs/ops | medium | low | `docs/deployment_performance.md`, `docs/load_testing.md` | A2 docs exist but A3 controls (cache fail-open/required, backpressure envs, warmup curl fallback) are incomplete. | none | yes | documentation consistency check |

## Decision Summary
- Apply now (internal, non-breaking): cache backend hardening, metrics enrichment (additive), optional distributed rate-limit/cache guidance, route-level backpressure for heavy endpoints, warmup improvements (python + curl script), A3 documentation and tests.
- Keep as recommendation (no risky functional shift now): fully asynchronous execution for submit/PDF/report/email as default behavior.

## Regression Guardrails
- Preserve existing endpoint paths, methods, input bodies, query params, and JSON response bodies.
- Keep added behavior internal/optional with fallback (`memory` cache and current sync pathways).
- No changes to frontend code, clinical logic, models, thresholds, or runtime artifacts.
