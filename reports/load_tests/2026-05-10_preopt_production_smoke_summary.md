# 2026-05-10 preopt production smoke summary

- generated_at_utc: `2026-05-10T18:14:06.005968+00:00`
- branch: `perf/safe-backend-optimization-audit`
- commit_sha: `8d62bc94b2b793320ec2a40574450bd74324c85e`
- phase: `pre_optimization_baseline_probe`
- environment_note: `homelab-constrained; probe-only; no stress`
- target_base_url: `https://www.cognia.lat`
- api_prefix: `/api`
- tls_verification: `disabled for probe due local chain verification failure`

## Endpoint probe

| Method | URL | Status | Body sample |
|---|---|---:|---|
| GET | https://www.cognia.lat/healthz | 200 | {"status":"ok"}  |
| GET | https://www.cognia.lat/readyz | 200 | {"cached":false,"latency_ms":1402.85,"status":"ready"}  |
| GET | https://www.cognia.lat/api/healthz | 404 | {"error":"not_found","msg":"The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again."}  |
| GET | https://www.cognia.lat/api/readyz | 404 | {"error":"not_found","msg":"The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again."}  |
| POST | https://www.cognia.lat/api/auth/login | 401 | {"error":"invalid_credentials","msg":"Invalid credentials"}  |
| GET | https://www.cognia.lat/api/v2/questionnaires/active | 401 | {"error":"unauthorized","msg":"Unauthorized"}  |
| GET | https://www.cognia.lat/api/v1/questionnaire-runtime/questionnaire/active | 401 | {"error":"unauthorized","msg":"Unauthorized"}  |

## Notes

- `/healthz` and `/readyz` respond at root path.
- `/api/healthz` and `/api/readyz` returned 404 in this deployment.
- Auth-required endpoints returned expected 401 without valid token.
- This probe is baseline availability evidence only, not load/stress capacity evidence.