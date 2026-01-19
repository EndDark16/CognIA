"""Baseline: ensure refresh_token table exists"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20251209_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = inspector.get_table_names()
    if "app_user" not in tables:
        # Esquema base no existe aún; se asume que lo crea otra migración externa.
        return

    if "refresh_token" not in tables:
        op.create_table(
            "refresh_token",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("jti", sa.Text(), nullable=False, unique=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "refresh_token" in inspector.get_table_names():
        op.drop_table("refresh_token")
