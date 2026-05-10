# Load Test Reports

This directory stores versioned markdown summaries for backend load/stress runs.

Suggested file name:
- `<timestamp>_<scenario>_summary.md`

Minimum fields per summary:
- date/time
- branch and commit SHA
- before/after optimization marker
- environment notes (homelab constraints, Supabase, network)
- target URL, BASE_URL, API_PREFIX
- scenario, VUs, duration
- RPS, error rate, status distribution
- p50/p90/p95/p99/max latency
- readyz behavior
- observed degradation point
- break point (if reached)
- key log observations
- final recommendation (current infra vs future infra)

Note:
- homelab runs are not final capacity reference for production-scale planning.
