# Warmup Usage (A3)

## Purpose
Warm up safe read paths after deploy to reduce cold-cache latency without creating sessions, submitting answers, or generating PDFs.

## Python warmup
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

Optional A3 flags:
- `WARMUP_USER_AGENT=CognIA-Warmup/1.0`
- `WARMUP_EXTRA_HEADERS="X-Trace=warmup;X-Env=prod"`
- `WARMUP_CURL_COMPATIBLE_MODE=true`
- `WARMUP_INSECURE=false`

## Curl fallback (for WAF/CDN restrictions)
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

## Safety guarantees
- requires `SAFE_MODE=true`
- does not create questionnaire sessions
- does not submit inference
- does not generate PDFs
- does not print token/password in output
