"""Add password reset tokens and password_changed_at."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260130_01"
down_revision = "20260128_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_reset_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_password_reset_token_user_id", "password_reset_token", ["user_id"], unique=False)
    op.create_index("ix_password_reset_token_hash", "password_reset_token", ["token_hash"], unique=False)
    op.create_index("ix_password_reset_token_expires", "password_reset_token", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_password_reset_token_expires", table_name="password_reset_token")
    op.drop_index("ix_password_reset_token_hash", table_name="password_reset_token")
    op.drop_index("ix_password_reset_token_user_id", table_name="password_reset_token")
    op.drop_table("password_reset_token")
    op.drop_column("app_user", "password_changed_at")
