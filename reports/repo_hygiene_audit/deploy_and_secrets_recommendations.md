# Deploy and Secrets Recommendations

## Archivos requeridos para deploy
- `Dockerfile`
- `docker/entrypoint.sh`
- `requirements.txt`
- `run.py`
- `config/settings.py`
- `artifacts/inference_v4/promotion_scope.json`

## Archivos opcionales
- `docker-compose.yml` (local/dev)

## Secrets / env vars (no versionar)
- `SECRET_KEY`
- `JWT_SECRET_KEY` (si se usa distinto)
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSL_MODE`
- `MFA_ENCRYPTION_KEY`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_PORT__TLS`, `SMTP_PORT__SSL`, `SMTP_USER`, `SMTP_PASSWORD`
- `EMAIL_FROM`, `EMAIL_REPLY_TO`, `EMAIL_UNSUBSCRIBE_*`, `EMAIL_ASSET_BASE_URL`
- `METRICS_TOKEN`

## Recomendacion para Render/Docker
- Definir todas las variables sensibles en el panel de Render (Environment/Secrets).
- Mantener `.env` solo localmente.
- Versionar `.env.example` con placeholders seguros.

## Modelos para runtime
- Si Render no permite binarios grandes en repo: mover `models/` y `artifacts/models/` a storage externo y descargar en build/boot.
- Si se mantienen en repo: reducir a los modelos finales promovidos y documentar tama?o.
