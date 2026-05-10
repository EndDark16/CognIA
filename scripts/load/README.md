# Backend Load Testing Suite (k6)

## Goal
Reusable load/stress suite for CognIA backend with safe defaults for limited homelab infrastructure.

## Infrastructure Context (current)
- Home server + residential network (~16 Mb)
- Mac 8 GB RAM, Intel i5-6360U x4
- Supabase external DB
- Results from this environment are not final product capacity.

## Safety Defaults
- `SAFE_MODE=true` by default in helper config.
- `SKIP_WRITE_HEAVY=true` by default.
- `SKIP_SUBMIT=true` by default.
- `SKIP_PDF=true` by default.
- Use dedicated test users only.

## Scenarios
- `k6_smoke.js`: basic availability and auth.
- `k6_baseline.js`: normal baseline profile.
- `k6_load.js`: moderate load.
- `k6_stress.js`: progressive stress ramp.
- `k6_spike.js`: spike and recovery.
- `k6_soak.js`: sustained stability run.
- `k6_questionnaire_v2_flow.js`: realistic v2 flow with safe-mode controls.
- `k6_infra_smoke.js`: health/readiness only (infrastructure check).
- `k6_auth_read.js`: read-only auth path (`/api/auth/me`).
- `k6_qv2_active_read.js`: read-only hot path (`/api/v2/questionnaires/active`).
- `k6_user_journey_read.js`: read-only combined user flow (`auth/me + qv2_active`).
- `k6_capacity_ladder.js`: controlled VU ladder (`10 -> 30`) with abort thresholds.
- `k6_constant_rps.js`: controlled throughput ladder (`5/10/15/20 RPS`) with abort thresholds.

## Environment Variables
- `BASE_URL`
- `API_PREFIX`
- `USERNAME`
- `PASSWORD`
- `ADMIN_USERNAME` (optional)
- `ADMIN_PASSWORD` (optional)
- `K6_DURATION`
- `K6_VUS`
- `K6_RAMP_TARGET`
- `K6_OUTPUT_DIR` (optional path for `handleSummary` files)
- `TEST_RUN_ID`
- `SAFE_MODE`
- `SKIP_WRITE_HEAVY`
- `SKIP_PDF`
- `SKIP_SUBMIT`
- `THINK_TIME_SECONDS`

## BASE_URL and API_PREFIX rules
The helper prevents duplicate `/api/api`.

Example A:
- `BASE_URL=https://www.cognia.lat`
- `API_PREFIX=/api`

Example B:
- `BASE_URL=https://www.cognia.lat/api`
- `API_PREFIX=`

Health/readiness detection is auto-resolved from:
- prefixed path (`{API_PREFIX}/healthz`, `{API_PREFIX}/readyz`)
- root path (`/healthz`, `/readyz`)

For current production (`https://www.cognia.lat`) the valid health endpoints are at root:
- `/healthz`
- `/readyz`

## Recommended Profiles for Current Hardware
- Smoke: `5-10 VUs`, `30s`
- Baseline: `5-10 VUs`, `3-5m`
- Load: `10-25 VUs`, `5-10m`
- Stress: progressive up to `60 VUs` first round
- Spike: base `5`, spike `40-75`, short duration
- Soak: `10-15 VUs`, `20-30m` first run

## Stop Criteria (manual guardrail)
Stop test if any:
- `readyz` fails twice consecutively
- error rate `>5%` for more than `60s`
- `p95 > 10s` for more than `2m`
- repeated 5xx bursts
- DB connection failures repeated in logs
- clear service degradation for real users
- host CPU/RAM/network saturation sustained

## Example Commands
Smoke:
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
k6 run scripts/load/k6_smoke.js
```

Baseline:
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
k6 run --summary-export artifacts/load_tests/baseline/summary.json scripts/load/k6_baseline.js
```

Load:
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
SKIP_WRITE_HEAVY=true \
SKIP_SUBMIT=true \
SKIP_PDF=true \
k6 run --summary-export artifacts/load_tests/load/summary.json scripts/load/k6_load.js
```

Stress:
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
K6_RAMP_TARGET=60 \
k6 run --summary-export artifacts/load_tests/stress/summary.json scripts/load/k6_stress.js
```

Questionnaire v2 flow (safe):
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
TEST_RUN_ID=k6_20260510 \
SAFE_MODE=true \
SKIP_WRITE_HEAVY=true \
SKIP_SUBMIT=true \
SKIP_PDF=true \
k6 run --summary-export artifacts/load_tests/qv2_flow/summary.json scripts/load/k6_questionnaire_v2_flow.js
```

User journey read (10 VUs):
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
K6_VUS=10 \
K6_DURATION=5m \
k6 run --summary-export artifacts/load_tests/user_journey_read/summary.json scripts/load/k6_user_journey_read.js
```

Capacity ladder (10 -> 30 VUs):
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
k6 run --summary-export artifacts/load_tests/capacity_ladder/summary.json scripts/load/k6_capacity_ladder.js
```

Constant RPS ladder:
```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
k6 run --summary-export artifacts/load_tests/constant_rps/summary.json scripts/load/k6_constant_rps.js
```

## Evidence Output Convention
Raw artifacts (if not ignored):
- `artifacts/load_tests/<timestamp>_<scenario>/summary.json`
- `artifacts/load_tests/<timestamp>_<scenario>/raw-output.json` (optional)

Automatic per-run outputs from `handleSummary`:
- `<K6_OUTPUT_DIR>/<timestamp>_<scenario>_<test_run_id>_summary.json`
- `<K6_OUTPUT_DIR>/<timestamp>_<scenario>_<test_run_id>_summary.md`

Versioned summary:
- `reports/load_tests/<timestamp>_<scenario>_summary.md`

Recommended metadata in each summary:
- date/time
- commit SHA
- branch
- before/after optimization marker
- environment and host notes
- URL target, BASE_URL, API_PREFIX
- VUs, duration, RPS
- error rate and status code mix
- p50/p90/p95/p99/max
- readyz behavior and degradation point
- caveats and recommendations
