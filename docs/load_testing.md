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

Usage details:
- `scripts/load/README.md`

## Evidence Storage
Raw outputs:
- `artifacts/load_tests/<timestamp>_<scenario>/...`

Versioned summaries:
- `reports/load_tests/<timestamp>_<scenario>_summary.md`
