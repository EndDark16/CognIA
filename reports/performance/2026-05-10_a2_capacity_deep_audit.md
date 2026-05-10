# A2 Capacity Deep Audit (2026-05-10)

## Context
- Host profile under test is constrained (homelab, 8 GB RAM, i5-6360U x4, ~16 Mb, Supabase remote DB).
- Results are interpreted as current infrastructure capacity, not final product ceiling.

## Findings and Actions

1. **Hot path `GET /api/v2/questionnaires/active` still paid avoidable DB work on repeated reads**  
   - Type: performance  
   - Severity: high  
   - Risk to change: medium  
   - Files: `api/services/questionnaire_v2_service.py`, `api/services/questionnaire_v2_loader_service.py`, `config/settings.py`  
   - Root issue: repeated active-version/activation/question bank lookups in read-heavy path.  
   - Applied now: yes  
   - Change: multi-layer cache (active version snapshot, activation confidence snapshot, question bank payload, full active response payload), explicit invalidation on sync/bootstrap, TTLs increased for quasi-static catalog.

2. **`/api/auth/me` read path queried DB every call**  
   - Type: performance  
   - Severity: high  
   - Risk to change: medium  
   - Files: `api/routes/auth.py`, `api/cache.py`, `config/settings.py`  
   - Applied now: yes  
   - Change: short TTL cache for exact response payload with explicit invalidation hooks.

3. **User auth cache invalidation was incomplete across mutation flows**  
   - Type: stability/security-operational  
   - Severity: high  
   - Risk to change: medium  
   - Files: `api/security.py`, `api/services/admin_service.py`, `api/routes/mfa.py`, `api/routes/auth.py`  
   - Applied now: yes  
   - Change: unified invalidation path (`roles + security + auth_me`) after password/MFA/admin/user lifecycle changes.

4. **Metrics lock section was heavier than necessary and detail cardinality on infra endpoints was noisy**  
   - Type: observability/performance  
   - Severity: medium  
   - Risk to change: low  
   - Files: `api/metrics.py`, `api/app.py`, `config/settings.py`  
   - Applied now: yes  
   - Change: configurable sample size, optional endpoint-detail exclusion, lock-time reduction by snapshot-copy then compute.

5. **Cache backend was worker-local only with no distributed option**  
   - Type: reliability/performance  
   - Severity: medium  
   - Risk to change: medium  
   - Files: `api/cache.py`, `api/app.py`, `config/settings.py`, `.env.example`, `docker-compose.yml`  
   - Applied now: yes  
   - Change: backend abstraction (memory default, optional Redis URI, safe fallback to memory).

6. **Cold-start after deploy had no deterministic warmup process**  
   - Type: reliability/operational  
   - Severity: medium  
   - Risk to change: low  
   - Files: `scripts/warmup_backend.py`, `docs/deployment_performance.md`, `docs/load_testing.md`  
   - Applied now: yes  
   - Change: non-destructive warmup script (`healthz/readyz/login/me/transport-key/qv2-active`).

7. **k6 scenarios mixed infra checks with user-journey latency signal**  
   - Type: load-testing methodology  
   - Severity: medium  
   - Risk to change: low  
   - Files: `scripts/load/*.js`, `scripts/load/helpers.js`, `scripts/load/README.md`  
   - Applied now: yes  
   - Change: dedicated A2 scenario set (`infra_smoke`, `auth_read`, `qv2_active_read`, `user_journey_read`, `capacity_ladder`, `constant_rps`) + richer summary breakdown.

8. **Feature contract and field key loading incurred repeated CPU/file work**  
   - Type: performance  
   - Severity: medium  
   - Risk to change: low  
   - Files: `api/services/questionnaire_v2_service.py`, `api/services/crypto_service.py`  
   - Applied now: yes  
   - Change: LRU cache for feature contract loading and field encryption key bytes.

9. **Session item creation path used per-row add in hot create flow**  
   - Type: performance  
   - Severity: low-medium  
   - Risk to change: low  
   - Files: `api/services/questionnaire_v2_service.py`  
   - Applied now: yes  
   - Change: switch to batched `add_all` for session item inserts.

10. **Queue migration for PDF/inference/email remains synchronous risk**  
   - Type: architecture/reliability  
   - Severity: medium-high  
   - Risk to change now: high (contract/flow risk)  
   - Applied now: no (design-only)  
   - Recommendation: async jobs architecture document with backward-compatible migration plan.

## API Contract Impact
- No changes applied to existing endpoint paths, methods, request bodies, query params, response JSON fields, or expected status-code semantics.
- Only internal optimizations, optional config, and additional scripts/docs/tests were introduced.

## Measurement Plan
- Local verification: `ruff`, `compileall`, app import sanity, `pytest`, `k6 inspect`.
- Post-deploy production verification (controlled):
  - warmup script
  - `infra_smoke`
  - `auth_read`
  - `qv2_active_read`
  - `user_journey_read` progressive VUs
  - `capacity_ladder` and `constant_rps` if stop criteria not triggered.
