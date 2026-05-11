# Deployment Performance Guide

## Purpose
Operational guidance to tune backend performance safely while preserving API contracts.

## Current Production Pattern
- Public site: `https://www.cognia.lat`
- Public API prefix: `/api`
- Health endpoints currently valid at root:
  - `/healthz`
  - `/readyz`

## Homelab Profile (Recommended Now)
Use conservative defaults and override by environment only when measured evidence supports higher values.

### Gunicorn
- `GUNICORN_WORKER_CLASS=gthread`
- `GUNICORN_WORKERS=2`
- `GUNICORN_THREADS=2`
- `GUNICORN_TIMEOUT=60`
- `GUNICORN_GRACEFUL_TIMEOUT=30`
- `GUNICORN_KEEPALIVE=5`
- `GUNICORN_MAX_REQUESTS=1000`
- `GUNICORN_MAX_REQUESTS_JITTER=100`

### Database Pool (Supabase)
- `DB_POOL_SIZE=2`
- `DB_MAX_OVERFLOW=1`
- `DB_POOL_TIMEOUT=15`
- `DB_POOL_PRE_PING=true`
- `DB_POOL_RECYCLE=1800`

### Readiness and runtime cache
- `READINESS_CACHE_TTL_SECONDS=5`
- `READINESS_DB_TIMEOUT_MS=1200`
- `QV2_ACTIVE_PAYLOAD_CACHE_TTL_SECONDS=300`
- `QV2_ACTIVE_VERSION_CACHE_TTL_SECONDS=120`
- `QV2_ACTIVE_ACTIVATION_CACHE_TTL_SECONDS=300`
- `JWT_SECURITY_STATE_CACHE_TTL_SECONDS=60`
- `AUTH_ME_CACHE_TTL_SECONDS=60`

### Cache backend (A2)
- Default (compatible): `CACHE_BACKEND_URI=` (memory backend)
- Optional distributed cache: `CACHE_BACKEND_URI=redis://<host>:<port>/<db>`
- Key namespace: `CACHE_KEY_PREFIX=cognia`
- Fallback behavior: if Redis is unavailable, service falls back to memory cache.

### Cache backend hardening (A3)
- `CACHE_BACKEND_REQUIRED=false` (default): do not break deploy when Redis is unavailable.
- `CACHE_FAIL_OPEN=true` (default): cache backend failures fall back to local memory.
- `CACHE_DEFAULT_TTL_SECONDS=300`
- `CACHE_REDIS_SOCKET_TIMEOUT=0.25`
- `CACHE_REDIS_CONNECT_TIMEOUT=0.25`
- Security note: cache payload serialization is JSON-based; avoid storing secrets/tokens/passwords.

### Metrics detail controls (A2)
- `METRICS_ENDPOINT_SAMPLE_SIZE=512`
- `METRICS_EXCLUDE_ENDPOINT_DETAILS=/healthz,/readyz`
- Totals are always preserved; only endpoint-level detail can be excluded.

### Rate limiting backend
- Default fallback: `RATE_LIMIT_STORAGE_URI=memory://`
- For cross-worker/global limits: `RATE_LIMIT_STORAGE_URI=redis://<host>:<port>/<db>`
- `RATE_LIMIT_FAIL_OPEN=true` keeps API available with local memory fallback if shared storage is unavailable.

### Endpoint backpressure (A3 defaults)
- `QV2_SESSION_CREATE_RATE_LIMIT=60 per minute`
- `QV2_SAVE_ANSWERS_RATE_LIMIT=120 per minute`
- `QV2_SUBMIT_RATE_LIMIT=20 per minute`
- `QV2_CLINICAL_SUMMARY_RATE_LIMIT=30 per minute`
- `QV2_PDF_RATE_LIMIT=8 per minute`
- `QV2_DASHBOARD_RATE_LIMIT=90 per minute`
- `QV2_REPORT_RATE_LIMIT=20 per minute`
- `PROBLEM_REPORT_CREATE_RATE_LIMIT=20 per 10 minutes`

## Future Robust Server + Fiber Profile
Do not hardcode future values without benchmark evidence.

Calibration process:
1. Run smoke + micro-baseline + baseline.
2. Increase workers/threads and DB pool incrementally.
3. Repeat benchmarks from external load generator.
4. Keep the smallest configuration that meets target p95/p99/error-rate.

## Operational Guardrails
- Keep public contracts unchanged when optimizing internals.
- Prefer controlled load ramps with stop criteria.
- Keep rollback SHA ready before production stress runs.
- Treat queue migration (PDF/email/report jobs) as controlled non-breaking future phase.

## Warmup Workflow (A2)
Run warmup after deploy and before k6:

```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
WARMUP_ROLES=guardian,psychologist \
WARMUP_MODES=short,medium \
python scripts/warmup_backend.py
```

If Python warmup is blocked by CDN/WAF, use curl fallback:

```bash
BASE_URL=https://www.cognia.lat \
API_PREFIX=/api \
USERNAME=<test_user> \
PASSWORD=<test_password> \
SAFE_MODE=true \
WARMUP_ROLES=guardian,psychologist \
WARMUP_MODES=short,medium \
bash scripts/warmup_backend.sh
```

For Windows Schannel environments that fail certificate revocation checks, enable:
- `WARMUP_CURL_SSL_NO_REVOKE=true`
