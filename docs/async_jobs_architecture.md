# Async Jobs Architecture (Non-Breaking Plan)

## Objective
Introduce durable async execution for heavy operations (PDF, reporting, email, optional inference submit) without breaking existing API contracts or frontend compatibility.

## Current Constraint
- Existing endpoints are synchronous and must remain backward-compatible.
- Homelab infrastructure is constrained; queue runtime must be optional and safe by default.

## Candidate Targets
- `POST /api/v2/questionnaires/history/{session_id}/pdf/generate`
- `POST /api/v2/reports/jobs`
- SMTP email dispatch paths
- Optional future async mode for questionnaire submit/inference (only if backward-compatible)

## Option A: DB-backed jobs (no Redis required)
- Pros:
  - no extra infra dependency
  - easy bootstrap in constrained environments
- Cons:
  - adds load to Supabase
  - queue polling can compete with API traffic
  - weaker scalability at higher throughput

## Option B: Redis/Valkey + Worker (recommended for robust server)
- Pros:
  - low-latency queue operations
  - clean separation API vs workers
  - supports retries/backoff/dead-letter
- Cons:
  - extra component to deploy/monitor
  - requires secrets and network hardening

## Option C: Hybrid
- Default sync behavior preserved for compatibility.
- Optional async mode enabled by env flags and worker presence.
- Existing endpoints keep current response shape and semantics.

## Backward-Compatible Migration Strategy
1. Keep current synchronous endpoint behavior as default.
2. Add internal enqueue layer behind feature flags.
3. If async enabled:
   - endpoints may still return the existing payload for current clients, while persisting job state.
   - optionally expose additional non-breaking metadata fields where safe.
4. Reuse `report_jobs` and related tables for traceability.
5. Add observability:
   - queue depth
   - retry counts
   - job age
   - failure classes

## Operational Safety
- No mandatory queue dependency in current homelab deploy.
- Fail-safe fallback: if queue unavailable, keep sync path (or controlled 503 for explicitly async-only operations in future opt-in endpoints).
- Rollback path: disable async flags and continue sync execution.

## Security and Data Handling
- No PHI/token/password logging in workers.
- Same encryption/authorization policies as API layer.
- Restrict worker access to minimum required secrets.

## Recommended Phased Rollout
1. Phase 1: Async email only (lowest contract risk).
2. Phase 2: Async report generation with durable `report_jobs`.
3. Phase 3: Async PDF generation with download polling semantics compatible with existing metadata endpoint.
4. Phase 4: Evaluate async inference submit as optional mode with strict comparability tests.
