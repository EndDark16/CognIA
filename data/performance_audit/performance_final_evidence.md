# CognIA Performance Optimization Evidence (Pre-Deploy)

## Metadata
- date_local: 2026-05-04T22:41:08-05:00
- repository: EndDark16/CognIA
- branch: fix/performance-capacity-hardening-final
- base_commit_before_new_commit: c431af6fe75c35b3db74195de19292b28d65d64d
- environment_scope: local workstation validation only (not production deploy)

## Context
- previous_status: needs_attention
- previous_post_deploy_results:
  - smoke: PASS (`http_req_failed=0.000%`, `p95=2203.82ms`)
  - diagnostic: PASS
  - load: FAIL (`http_req_failed=0.038%`, `p95=5672.67ms > 3000ms`)
  - stress: FAIL (`http_req_failed=6.214% > 5%`, `p95=19997.98ms > 5000ms`)
- probable_degradation_cause_before_iteration_2:
  - backend capacity defaults too aggressive for limited host (`workers`/`threads` behavior)
  - `/readyz` doing DB check on every request without short TTL cache
  - transport-key payload generated per request without response cache

## Changes Applied (Iteration 2)
### 1) Gunicorn / backend capacity
- File: `docker/entrypoint.sh`
- Added env-driven tuning:
  - `GUNICORN_WORKER_CLASS` (default `gthread`)
  - `GUNICORN_WORKERS` (default `3`, conservative fallback to `2` on constrained RAM/1-core)
  - `GUNICORN_THREADS` (default `2`)
  - `GUNICORN_TIMEOUT=60`
  - `GUNICORN_GRACEFUL_TIMEOUT=30`
  - `GUNICORN_KEEPALIVE=5`
  - `GUNICORN_MAX_REQUESTS=1000`
  - `GUNICORN_MAX_REQUESTS_JITTER=100`
- Added gunicorn command options for keepalive/timeouts/max-requests and stdout/stderr logs.

### 2) SQLAlchemy + Supabase pool tuning
- File: `config/settings.py`
- Added env vars:
  - `DB_POOL_SIZE` (default `5`)
  - `DB_MAX_OVERFLOW` (default `10`)
  - `DB_POOL_TIMEOUT` (default `10`)
  - `DB_POOL_RECYCLE` (default `1800`)
  - `DB_POOL_PRE_PING` (default `true`)
- Production engine options now use these envs and include `pool_use_lifo=true`.

### 3) Readiness optimization
- File: `api/routes/health.py`
- `/healthz` remains lightweight.
- `/readyz` now:
  - keeps real DB dependency check (`SELECT 1`),
  - applies short cache TTL (`READINESS_CACHE_TTL_SECONDS`, default `3s`),
  - uses short DB timeout hint on PostgreSQL (`READINESS_DB_TIMEOUT_MS`, default `2000ms`),
  - avoids per-request DB hit storms under concurrent checks.

### 4) Transport key optimization
- File: `api/services/transport_crypto_service.py`
- `transport_key_payload()` now caches public payload and reuses JWK/key metadata inside cache window.
- New env: `QV2_TRANSPORT_KEY_CACHE_TTL_SECONDS` (default `60`; bounded by key TTL).
- Contract preserved:
  - endpoint stays public,
  - no private key exposure,
  - same envelope/version semantics.

### 5) Gateway hardening (documented artifact)
- New file: `docs/gateway/default.conf.production.example`
- Includes:
  - proxy timeout baseline,
  - proxy buffering baseline,
  - gzip for text/json/js/css,
  - forwarded headers,
  - explicit `404` for `/openapi.yaml`, `/api/openapi.yaml`, `/docs`.

### 6) k6 suite updates
- Added `performance/k6/diagnostic-operational-api.js`.
- Added `performance/k6/load-user-public-api.js` (public traffic profile excluding `/readyz`).
- Existing operational scripts keep `/openapi.yaml` excluded.

## Local Validations Executed
- `python -m py_compile config/settings.py` => PASS
- `python -m py_compile api/app.py` => PASS
- `python -m py_compile api/routes/health.py` => PASS
- `python -m py_compile api/services/transport_crypto_service.py` => PASS
- `pytest tests/test_health.py tests/test_docs_metrics.py tests/api/test_questionnaire_v2_api.py tests/api/test_encrypted_payload_transport.py -q` => PASS (`29 passed`)
- `pytest -q` => NOT FULLY GREEN (`1 failed` pre-existing unrelated email header test)
  - failing test: `tests/test_email_service.py::test_build_message_includes_headers`
- `docker compose config` => PASS
- `docker compose config --services` => `backend`
- `docker compose --profile local-db config --services` => `backend`, `postgres`

## Compose/Deploy Notes
- This backend repo compose is backend-only (+ optional local postgres profile).
- Production deployment is done on Ubuntu via GitHub Actions after merge to `main`.
- Local docker-compose output is technical validation only, not production evidence.

## Commands for Ubuntu Post-Merge (exact)
```bash
cd /opt/cognia/backend
git fetch origin --prune
git checkout main
git pull origin main
cd /opt/cognia
docker compose up -d --build backend
docker compose up -d --force-recreate gateway
curl -i http://localhost/healthz
curl -i http://localhost/readyz
curl -i http://localhost/api/v2/security/transport-key
curl -i http://localhost/openapi.yaml
curl -i http://localhost/api/openapi.yaml
curl -i http://localhost/docs
```

## Commands for Real Post-Deploy Validation (public domain)
```bash
curl -i https://www.cognia.lat/healthz
curl -i https://www.cognia.lat/readyz
curl -i https://www.cognia.lat/api/v2/security/transport-key
curl -i https://www.cognia.lat/openapi.yaml
curl -i https://www.cognia.lat/api/openapi.yaml
curl -i https://www.cognia.lat/docs
```

## k6 Post-Deploy Order (required)
```bash
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/smoke-operational-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/diagnostic-operational-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/load-operational-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/load-user-public-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/stress-operational-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/spike-operational-api.js
k6 run -e BASE_URL=https://www.cognia.lat performance/k6/soak-operational-api.js
```

## Approval Criteria Reminder
- smoke: `http_req_failed=0%`, no repeated 5xx, p95 documented
- diagnostic: per-endpoint thresholds pass
- load operational/user-public: `http_req_failed < 1%`, ideal `p95 <= 3000ms`
- stress: `http_req_failed < 5%`, ideal `p95 <= 5000ms`
- spike/soak: no sustained instability, no progressive degradation

## How to Interpret If It Still Fails
- If code-level optimizations are active and failures persist with signs of resource saturation/high external latency, classify likely infra/connectivity bottleneck (`infra_limited`) and attach host metrics/log evidence.

## Pre-Deploy Conclusion
- Local optimization iteration completed and validated technically.
- Real performance closure is pending merge+deploy to `main` and post-deploy k6 execution.
- final_status: pending_post_deploy
