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

    # Logging / Metrics
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG_REQUESTS = os.getenv("LOG_REQUESTS", "true").lower() == "true"
    _exclude = os.getenv("LOG_EXCLUDE_PATHS", "/healthz,/readyz,/metrics")
    LOG_EXCLUDE_PATHS = {p.strip() for p in _exclude.split(",") if p.strip()}

    METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    METRICS_TOKEN = os.getenv("METRICS_TOKEN")


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
