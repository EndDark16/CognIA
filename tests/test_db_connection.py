import os

import pytest
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def _build_url(prefix: str) -> str | None:
    """Arma la URL a partir de env vars. prefix='' para runtime, 'MIGRATION_' para migraciones."""
    direct = os.getenv(f"{prefix}DATABASE_URI")
    if direct:
        return direct

    user = os.getenv(f"{prefix}DB_USER")
    password = os.getenv(f"{prefix}DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    sslmode = os.getenv("DB_SSL_MODE", "")
    if not all([user, password, host, name]):
        return None
    suffix = f"?sslmode={sslmode}" if sslmode else ""
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}{suffix}"


def _maybe_test_connection(url: str):
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


@pytest.mark.skipif(os.getenv("DB_CONNECTION_TEST") != "1", reason="DB_CONNECTION_TEST not enabled")
def test_runtime_db_connection():
    """Prueba runtime (DB_USER/DB_PASSWORD)."""
    url = _build_url("")
    if not url:
        pytest.skip("Runtime DB env vars not set")
    _maybe_test_connection(url)


@pytest.mark.skipif(os.getenv("DB_CONNECTION_TEST") != "1", reason="DB_CONNECTION_TEST not enabled")
def test_migration_db_connection():
    """Prueba migraciones (MIGRATION_DB_USER/MIGRATION_DB_PASSWORD o MIGRATION_DATABASE_URI)."""
    url = _build_url("MIGRATION_")
    if not url:
        pytest.skip("Migration DB env vars not set")
    _maybe_test_connection(url)
