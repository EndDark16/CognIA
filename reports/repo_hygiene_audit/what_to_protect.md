# What To Protect

## Must be env vars / secrets (do not commit real values)
- `SECRET_KEY`
- `MFA_ENCRYPTION_KEY`
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSL_MODE`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_PORT__TLS`, `SMTP_PORT__SSL`, `SMTP_USER`, `SMTP_PASSWORD`
- `EMAIL_FROM`, `EMAIL_REPLY_TO`, `EMAIL_UNSUBSCRIBE_SECRET`, `EMAIL_UNSUBSCRIBE_URL`, `EMAIL_ASSET_BASE_URL`
- `METRICS_TOKEN`

## Must be template-only
- `.env.example` (placeholders only)

## Deploy required but protected
- `docker-compose.yml` (uses env vars; no secrets in file)
- `config/settings.py` (reads env vars; no secrets embedded)

## Keep internal / not public
- `models/` (binary models)
- `artifacts/models/`, `artifacts/versioned_models/` (duplicated heavy binaries)
- `data/processed*` (large datasets)

## Safe to commit
- `Dockerfile`
- `docker/entrypoint.sh`
- `requirements.txt`
- `run.py`
- `artifacts/inference_v4/promotion_scope.json`
- `reports/final_closure/`
- `data/final_closure_audit_v1/`
