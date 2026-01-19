import importlib
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, MetaData

# Make project root importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load Flask app and metadata
from api.app import create_app  # noqa
from app.models import db  # noqa


def get_config_class():
    """Load config class from APP_CONFIG_CLASS env var or default to DevelopmentConfig."""
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


flask_app = create_app(get_config_class())
with flask_app.app_context():
    # Permite usar credenciales/URI distintas para migraciones (p. ej. rol db_migrator).
    migration_uri = os.getenv("MIGRATION_DATABASE_URI")
    if not migration_uri:
        mig_user = os.getenv("MIGRATION_DB_USER")
        mig_pass = os.getenv("MIGRATION_DB_PASSWORD")
        if mig_user and mig_pass:
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "5432")
            name = os.getenv("DB_NAME", "cognia_db")
            sslmode = os.getenv("DB_SSL_MODE", "")
            suffix = f"?sslmode={sslmode}" if sslmode else ""
            migration_uri = f"postgresql+psycopg://{mig_user}:{mig_pass}@{host}:{port}/{name}{suffix}"
    config.set_main_option("sqlalchemy.url", migration_uri or flask_app.config["SQLALCHEMY_DATABASE_URI"])
    target_metadata = db.metadata
    REFLECT_FROM_DB = os.getenv("ALEMBIC_REFLECT_FROM_DB", "0") == "1"


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if REFLECT_FROM_DB:
            # Opción para crear una baseline reflejando el esquema actual de la BD.
            metadata = MetaData()
            metadata.reflect(bind=connection)
            metadata_to_use = metadata
        else:
            metadata_to_use = target_metadata

        context.configure(
            connection=connection,
            target_metadata=metadata_to_use,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
