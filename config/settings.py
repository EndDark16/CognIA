# config/settings.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    DEBUG = False
    TESTING = False
    MODEL_PATH = os.getenv("MODEL_PATH", "model/modelo.pkl")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Database
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password_placeholder")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "cognia_db")
    DB_SSL_MODE = os.getenv("DB_SSL_MODE", "")
    _ssl_suffix = f"?sslmode={DB_SSL_MODE}" if DB_SSL_MODE else ""
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}{_ssl_suffix}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = 900  # 15 minutes in seconds (or use timedelta in app)
    JWT_REFRESH_TOKEN_EXPIRES = 2592000 # 30 days in seconds

    # CORS
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5000"
    ).split(",")

    # MFA
    MFA_CHALLENGE_TTL = int(os.getenv("MFA_CHALLENGE_TTL", "300"))
    MFA_ENROLL_TOKEN_TTL = int(os.getenv("MFA_ENROLL_TOKEN_TTL", "600"))
    RECOVERY_CODE_MAX_AGE_DAYS = int(os.getenv("RECOVERY_CODE_MAX_AGE_DAYS", "90"))
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    PASSWORD_INPUT_MAX = int(os.getenv("PASSWORD_INPUT_MAX", "200"))
    PASSWORD_RESET_TOKEN_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    PASSWORD_RESET_PATH = os.getenv("PASSWORD_RESET_PATH", "/reset-password")

    # Auth hardening
    MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
    REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "5 per 10 minutes")
    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5 per 15 minutes")
    LOGIN_MFA_RATE_LIMIT = os.getenv("LOGIN_MFA_RATE_LIMIT", "5 per 10 minutes")
    MFA_SETUP_RATE_LIMIT = os.getenv("MFA_SETUP_RATE_LIMIT", "3 per 10 minutes")
    MFA_CONFIRM_RATE_LIMIT = os.getenv("MFA_CONFIRM_RATE_LIMIT", "5 per 10 minutes")
    MFA_DISABLE_RATE_LIMIT = os.getenv("MFA_DISABLE_RATE_LIMIT", "3 per 10 minutes")
    PASSWORD_CHANGE_RATE_LIMIT = os.getenv("PASSWORD_CHANGE_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_FORGOT_RATE_LIMIT = os.getenv("PASSWORD_FORGOT_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_RESET_RATE_LIMIT = os.getenv("PASSWORD_RESET_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_VERIFY_RATE_LIMIT = os.getenv("PASSWORD_VERIFY_RATE_LIMIT", "20 per 10 minutes")

    # Evaluations
    EVALUATION_MIN_AGE = int(os.getenv("EVALUATION_MIN_AGE", "6"))
    EVALUATION_MAX_AGE = int(os.getenv("EVALUATION_MAX_AGE", "11"))
    _allowed_status = os.getenv("EVALUATION_ALLOWED_STATUSES", "draft,submitted,completed")
    EVALUATION_ALLOWED_STATUSES = [s.strip() for s in _allowed_status.split(",") if s.strip()]

    # Logging / Metrics
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG_REQUESTS = os.getenv("LOG_REQUESTS", "true").lower() == "true"
    _exclude = os.getenv("LOG_EXCLUDE_PATHS", "/healthz,/readyz,/metrics")
    LOG_EXCLUDE_PATHS = {p.strip() for p in _exclude.split(",") if p.strip()}
    PROPAGATE_EXCEPTIONS = os.getenv("PROPAGATE_EXCEPTIONS", "false").lower() == "true"

    METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    METRICS_TOKEN = os.getenv("METRICS_TOKEN")
    METRICS_TOKEN_REQUIRED = os.getenv("METRICS_TOKEN_REQUIRED", "false").lower() == "true"
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"

    # Email (SMTP)
    EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    EMAIL_SEND_ASYNC = os.getenv("EMAIL_SEND_ASYNC", "true").lower() == "true"
    EMAIL_SANDBOX = os.getenv("EMAIL_SANDBOX", "false").lower() == "true"
    EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@example.com")
    EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO")
    EMAIL_LIST_UNSUBSCRIBE = os.getenv("EMAIL_LIST_UNSUBSCRIBE")
    EMAIL_ASSET_BASE_URL = os.getenv("EMAIL_ASSET_BASE_URL", "")
    EMAIL_UNSUBSCRIBE_URL = os.getenv("EMAIL_UNSUBSCRIBE_URL")
    EMAIL_UNSUBSCRIBE_SECRET = os.getenv("EMAIL_UNSUBSCRIBE_SECRET")
    _email_unsub_ttl = os.getenv("EMAIL_UNSUBSCRIBE_TOKEN_TTL_DAYS")
    try:
        EMAIL_UNSUBSCRIBE_TOKEN_TTL_DAYS = int(_email_unsub_ttl) if _email_unsub_ttl else None
    except ValueError:
        EMAIL_UNSUBSCRIBE_TOKEN_TTL_DAYS = None
    EMAIL_UNSUBSCRIBE_RATE_LIMIT = os.getenv("EMAIL_UNSUBSCRIBE_RATE_LIMIT", "10 per 10 minutes")
    def _int_env(name: str, default: int | None) -> int | None:
        value = os.getenv(name)
        if value is None or value == "":
            return default
        return int(value) if str(value).isdigit() else default

    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = _int_env("SMTP_PORT", 587)
    SMTP_PORT_SSL = _int_env("SMTP_PORT__SSL", None)
    SMTP_PORT_TLS = _int_env("SMTP_PORT__TLS", None)
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "10"))

    SWAGGER_ENABLED = os.getenv("SWAGGER_ENABLED", "true").lower() == "true"

    # Startup behavior
    AUTO_CREATE_REFRESH_TOKEN_TABLE = os.getenv(
        "AUTO_CREATE_REFRESH_TOKEN_TABLE", "false"
    ).lower() == "true"


class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Ajustes de pool para concurrencia
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Ajustado para no competir con poolers externos (ej. pgbouncer en free tier)
        "pool_size": 3,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    # Usa SQLite en memoria para no tocar la base real durante pruebas
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_REQUESTS = False
    RATELIMIT_ENABLED = False
    EMAIL_ENABLED = False
