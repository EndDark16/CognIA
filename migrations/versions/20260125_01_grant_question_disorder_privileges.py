"""Grant runtime role privileges on question_disorder."""

import os

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260125_01"
down_revision = "20260124_05"
branch_labels = None
depends_on = None


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    runtime_role = os.getenv("DB_USER", "api_backend")
    runtime_role_quoted = _quote_ident(runtime_role)
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.question_disorder TO {runtime_role_quoted};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {runtime_role_quoted};"
    )


def downgrade() -> None:
    runtime_role = os.getenv("DB_USER", "api_backend")
    runtime_role_quoted = _quote_ident(runtime_role)
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.question_disorder FROM {runtime_role_quoted};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {runtime_role_quoted};"
    )
