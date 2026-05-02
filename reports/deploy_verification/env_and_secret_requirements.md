# Env and Secret Requirements

- Variables criticas deben configurarse via Render/Secrets: SECRET_KEY, DB_*, MFA_ENCRYPTION_KEY, SMTP_* si email habilitado, METRICS_TOKEN si metrics protegidas.
- `.env.example` contiene placeholders seguros; no debe contener valores reales.