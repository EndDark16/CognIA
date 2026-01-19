"""Add MFA fields and tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = "20251211_01"
down_revision = "20251210_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AppUser fields
    op.add_column("app_user", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("app_user", sa.Column("mfa_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("mfa_method", sa.String(), nullable=True, server_default="none"))

    # user_mfa table
    op.create_table(
        "user_mfa",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False, unique=True),
        sa.Column("method", sa.String(), nullable=False, server_default="totp"),
        sa.Column("secret_encrypted", sa.String(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
    )

    # recovery_code table
    op.create_table(
        "recovery_code",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_recovery_code_user", "recovery_code", ["user_id"])
    op.create_index("idx_recovery_code_user_used", "recovery_code", ["user_id", "used_at"])

    # mfa_login_challenge table
    op.create_table(
        "mfa_login_challenge",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String()),
        sa.Column("user_agent", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_mfa_challenge_user", "mfa_login_challenge", ["user_id"])
    op.create_index("idx_mfa_challenge_expires", "mfa_login_challenge", ["expires_at"])
    op.create_index("idx_mfa_challenge_used", "mfa_login_challenge", ["used_at"])


def downgrade() -> None:
    op.drop_index("idx_mfa_challenge_used", table_name="mfa_login_challenge")
    op.drop_index("idx_mfa_challenge_expires", table_name="mfa_login_challenge")
    op.drop_index("idx_mfa_challenge_user", table_name="mfa_login_challenge")
    op.drop_table("mfa_login_challenge")

    op.drop_index("idx_recovery_code_user_used", table_name="recovery_code")
    op.drop_index("idx_recovery_code_user", table_name="recovery_code")
    op.drop_table("recovery_code")

    op.drop_table("user_mfa")

    op.drop_column("app_user", "mfa_method")
    op.drop_column("app_user", "mfa_confirmed_at")
    op.drop_column("app_user", "mfa_enabled")
