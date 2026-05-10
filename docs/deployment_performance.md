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
- `QV2_ACTIVE_PAYLOAD_CACHE_TTL_SECONDS=20`
- `JWT_SECURITY_STATE_CACHE_TTL_SECONDS=45`

### Rate limiting backend
- Default fallback: `RATE_LIMIT_STORAGE_URI=memory://`
- For cross-worker/global limits: `RATE_LIMIT_STORAGE_URI=redis://<host>:<port>/<db>`

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
