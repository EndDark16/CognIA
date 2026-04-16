# config/settings.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_bool_env(name: str):
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}

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
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]

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
    REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "10 per 10 minutes")
    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "10 per 15 minutes")
    LOGIN_MFA_RATE_LIMIT = os.getenv("LOGIN_MFA_RATE_LIMIT", "5 per 10 minutes")
    MFA_SETUP_RATE_LIMIT = os.getenv("MFA_SETUP_RATE_LIMIT", "3 per 10 minutes")
    MFA_CONFIRM_RATE_LIMIT = os.getenv("MFA_CONFIRM_RATE_LIMIT", "5 per 10 minutes")
    MFA_DISABLE_RATE_LIMIT = os.getenv("MFA_DISABLE_RATE_LIMIT", "3 per 10 minutes")
    PASSWORD_CHANGE_RATE_LIMIT = os.getenv("PASSWORD_CHANGE_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_FORGOT_RATE_LIMIT = os.getenv("PASSWORD_FORGOT_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_FORGOT_RATE_LIMIT_IP = os.getenv("PASSWORD_FORGOT_RATE_LIMIT_IP", "20 per 10 minutes")
    PASSWORD_FORGOT_RATE_LIMIT_EMAIL = os.getenv(
        "PASSWORD_FORGOT_RATE_LIMIT_EMAIL",
        PASSWORD_FORGOT_RATE_LIMIT,
    )
    PASSWORD_RESET_RATE_LIMIT = os.getenv("PASSWORD_RESET_RATE_LIMIT", "5 per 10 minutes")
    PASSWORD_VERIFY_RATE_LIMIT = os.getenv("PASSWORD_VERIFY_RATE_LIMIT", "20 per 10 minutes")

    # Cookies/session for cross-domain frontend-backend deployments
    AUTH_CROSS_SITE_COOKIES = _bool_env("AUTH_CROSS_SITE_COOKIES", False)
    JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE")
    JWT_COOKIE_SECURE = _optional_bool_env("JWT_COOKIE_SECURE")
    JWT_COOKIE_DOMAIN = os.getenv("JWT_COOKIE_DOMAIN")

    # Admin rate limits
    ADMIN_LIST_RATE_LIMIT = os.getenv("ADMIN_LIST_RATE_LIMIT", "60 per minute")
    ADMIN_MUTATION_RATE_LIMIT = os.getenv("ADMIN_MUTATION_RATE_LIMIT", "20 per minute")
    ADMIN_SECURITY_RATE_LIMIT = os.getenv("ADMIN_SECURITY_RATE_LIMIT", "10 per minute")
    ADMIN_AUDIT_RATE_LIMIT = os.getenv("ADMIN_AUDIT_RATE_LIMIT", "30 per minute")
    ADMIN_IMPERSONATION_TTL_SECONDS = int(os.getenv("ADMIN_IMPERSONATION_TTL_SECONDS", "900"))

    # Evaluations
    EVALUATION_MIN_AGE = int(os.getenv("EVALUATION_MIN_AGE", "6"))
    EVALUATION_MAX_AGE = int(os.getenv("EVALUATION_MAX_AGE", "11"))
    _allowed_status = os.getenv("EVALUATION_ALLOWED_STATUSES", "draft,submitted,completed")
    EVALUATION_ALLOWED_STATUSES = [s.strip() for s in _allowed_status.split(",") if s.strip()]

    # Questionnaire Runtime v1
    QR_PROCESS_ASYNC = _bool_env("QR_PROCESS_ASYNC", True)
    QR_LIVE_HEARTBEAT_GRACE_SECONDS = int(os.getenv("QR_LIVE_HEARTBEAT_GRACE_SECONDS", "45"))
    QR_RETENTION_DRAFT_DAYS = int(os.getenv("QR_RETENTION_DRAFT_DAYS", "30"))
    QR_RETENTION_COMPLETED_DAYS = int(os.getenv("QR_RETENTION_COMPLETED_DAYS", "1095"))
    QR_RETENTION_DELETED_DAYS = int(os.getenv("QR_RETENTION_DELETED_DAYS", "90"))
    QR_RETENTION_NOTIFICATION_DAYS = int(os.getenv("QR_RETENTION_NOTIFICATION_DAYS", "180"))
    QR_PIN_MAX_ATTEMPTS = int(os.getenv("QR_PIN_MAX_ATTEMPTS", "5"))
    QR_PIN_LOCK_MINUTES = int(os.getenv("QR_PIN_LOCK_MINUTES", "10"))

    # Problem reports
    PROBLEM_REPORT_UPLOAD_DIR = os.getenv("PROBLEM_REPORT_UPLOAD_DIR", "artifacts/problem_reports/uploads")
    PROBLEM_REPORT_MAX_ATTACHMENT_BYTES = int(os.getenv("PROBLEM_REPORT_MAX_ATTACHMENT_BYTES", str(5 * 1024 * 1024)))
    _problem_allowed_mime = os.getenv("PROBLEM_REPORT_ALLOWED_MIME_TYPES", "image/png,image/jpeg,image/webp")
    PROBLEM_REPORT_ALLOWED_MIME_TYPES = [x.strip() for x in _problem_allowed_mime.split(",") if x.strip()]

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

    # Proxy and response hardening
    TRUST_PROXY_HEADERS = _bool_env("TRUST_PROXY_HEADERS", False)
    PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "1"))
    PROXY_FIX_X_PROTO = int(os.getenv("PROXY_FIX_X_PROTO", "1"))
    PROXY_FIX_X_HOST = int(os.getenv("PROXY_FIX_X_HOST", "1"))
    PROXY_FIX_X_PORT = int(os.getenv("PROXY_FIX_X_PORT", "1"))
    PROXY_FIX_X_PREFIX = int(os.getenv("PROXY_FIX_X_PREFIX", "1"))
    SECURITY_HEADERS_ENABLED = _bool_env("SECURITY_HEADERS_ENABLED", True)
    SECURITY_HSTS_SECONDS = int(os.getenv("SECURITY_HSTS_SECONDS", "31536000"))
    SECURITY_HSTS_INCLUDE_SUBDOMAINS = _bool_env("SECURITY_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURITY_HSTS_PRELOAD = _bool_env("SECURITY_HSTS_PRELOAD", False)
    SECURITY_FRAME_OPTIONS = os.getenv("SECURITY_FRAME_OPTIONS", "DENY")
    SECURITY_CONTENT_TYPE_OPTIONS = os.getenv("SECURITY_CONTENT_TYPE_OPTIONS", "nosniff")
    SECURITY_REFERRER_POLICY = os.getenv("SECURITY_REFERRER_POLICY", "strict-origin-when-cross-origin")
    SECURITY_CSP = os.getenv("SECURITY_CSP")
    SECURITY_PERMISSIONS_POLICY = os.getenv("SECURITY_PERMISSIONS_POLICY")

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
    SMTP_DEBUG = os.getenv("SMTP_DEBUG", "false").lower() == "true"
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
    AUTH_CROSS_SITE_COOKIES = _bool_env("AUTH_CROSS_SITE_COOKIES", True)
    TRUST_PROXY_HEADERS = _bool_env("TRUST_PROXY_HEADERS", True)
    JWT_COOKIE_SECURE = True if Config.JWT_COOKIE_SECURE is None else Config.JWT_COOKIE_SECURE
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
    SECURITY_HEADERS_ENABLED = False
    QR_PROCESS_ASYNC = False
