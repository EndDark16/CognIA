# Load Testing Policy - CognIA Backend

## Scope
This document defines safe load/stress testing for the backend deployed under `cognia.lat`.

Primary URLs:
- Frontend: `https://www.cognia.lat`
- Backend/API: `https://www.cognia.lat/api`

## Current Infrastructure Context (non-final)
- Home server in constrained environment
- Mac with `8 GB RAM`
- CPU `Intel Core i5-6360U x4`
- Residential internet around `16 Mb`
- External database in Supabase

Important:
- Current results represent present homelab capacity only.
- Do not treat current limits as final platform ceiling.

## Capacity Interpretation Guardrail
When interpreting bottlenecks, separate:
- current homelab limits
- expected future capacity on robust server + fiber

Possible bottleneck sources:
- local CPU/RAM saturation
- home network bandwidth
- latency to Supabase
- DB pool limits
- Gunicorn worker/thread settings
- gateway/reverse proxy behavior
- Supabase concurrency limits
- backend implementation hotspots

## Safety Rules
- Use test users only.
- Use synthetic payloads only.
- Prefer safe mode (`SAFE_MODE=true`) and write-light settings.
- Avoid massive submit/PDF generation in first rounds.
- Run tests in low-traffic window.
- Keep rollback plan ready.

## Stop Criteria
Stop run if any:
- `readyz` fails twice in a row
- error rate above `5%` for more than `60s`
- `p95 > 10s` for more than `2m`
- repeated 5xx bursts
- repeated DB connection failures in logs
- clear user-facing degradation
- sustained host/network saturation

## Execution Recommendation
Prefer running k6 from a separate machine.

If k6 runs on the same server being tested:
- mark the run as `self-load`
- do not interpret as true external capacity

## Versioned Suite
Scenario suite:
- `scripts/load/k6_smoke.js`
- `scripts/load/k6_baseline.js`
- `scripts/load/k6_load.js`
- `scripts/load/k6_stress.js`
- `scripts/load/k6_spike.js`
- `scripts/load/k6_soak.js`
- `scripts/load/k6_questionnaire_v2_flow.js`
- `scripts/load/k6_infra_smoke.js`
- `scripts/load/k6_auth_read.js`
- `scripts/load/k6_qv2_active_read.js`
- `scripts/load/k6_user_journey_read.js`
- `scripts/load/k6_capacity_ladder.js`
- `scripts/load/k6_constant_rps.js`

Usage details:
- `scripts/load/README.md`

## Runtime Configuration Profiles

### Current homelab (recommended)
- `GUNICORN_WORKER_CLASS=gthread`
- `GUNICORN_WORKERS=2`
- `GUNICORN_THREADS=2`
- `GUNICORN_TIMEOUT=60`
- `GUNICORN_GRACEFUL_TIMEOUT=30`
- `GUNICORN_KEEPALIVE=5`
- `GUNICORN_MAX_REQUESTS=1000`
- `GUNICORN_MAX_REQUESTS_JITTER=100`
- `DB_POOL_SIZE=2`
- `DB_MAX_OVERFLOW=1`
- `DB_POOL_TIMEOUT=15`
- `DB_POOL_PRE_PING=true`
- `READINESS_CACHE_TTL_SECONDS=5`
- `READINESS_DB_TIMEOUT_MS=1200`
- `QV2_ACTIVE_PAYLOAD_CACHE_TTL_SECONDS=300`
- `QV2_ACTIVE_VERSION_CACHE_TTL_SECONDS=120`
- `QV2_ACTIVE_ACTIVATION_CACHE_TTL_SECONDS=300`
- `JWT_SECURITY_STATE_CACHE_TTL_SECONDS=60`
- `AUTH_ME_CACHE_TTL_SECONDS=60`
- `CACHE_BACKEND_URI=` (empty => memory)
- `CACHE_KEY_PREFIX=cognia`

Notes:
- Favor stability and predictable latency over max throughput.
- On memory pressure, evaluate `GUNICORN_WORKERS=1` and `GUNICORN_THREADS=4`.

### Future robust server + fiber (to benchmark, not assumed)
- Start from homelab profile and increase gradually with measured evidence.
- Re-benchmark workers/threads and DB pool with external load generator.
- Recalibrate thresholds for p95/p99 and error rate only after baseline is stable.

## Rate Limit Backend Caveat
- `RATE_LIMIT_STORAGE_URI=memory://` is per-worker and not globally shared.
- For global shared rate limits, configure Redis/Valkey:
  - `RATE_LIMIT_STORAGE_URI=redis://<host>:<port>/<db>`
- Keep fallback to `memory://` for compatibility when Redis is unavailable.

Cache backend (A2):
- Local fallback by default: `CACHE_BACKEND_URI=` (memory backend).
- Optional distributed cache:
  - `CACHE_BACKEND_URI=redis://<host>:<port>/<db>`
  - `CACHE_KEY_PREFIX=cognia`
- Backend falls back to memory if Redis is unavailable or not installed.

Warmup (A2):
- Script: `python scripts/warmup_backend.py`
- Performs: `/healthz`, `/readyz`, `/api/auth/login`, `/api/auth/me`, `/api/v2/security/transport-key`, `/api/v2/questionnaires/active` by configured role/mode.
- Safe-only behavior: no create session, no submit, no PDF.

## Evidence Storage
Raw outputs:
- `artifacts/load_tests/<timestamp>_<scenario>/...`

Versioned summaries:
- `reports/load_tests/<timestamp>_<scenario>_summary.md`
