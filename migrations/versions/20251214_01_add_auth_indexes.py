"""Add indexes to auth-related tables for performance"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251214_01"
down_revision = "20251211_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # refresh_token indexes
    op.create_index(
        op.f("ix_refresh_token_user_revoked"),
        "refresh_token",
        ["user_id", "revoked", "expires_at"],
        unique=False,
    )

    # mfa_login_challenge indexes
    op.create_index(
        op.f("ix_mfa_login_challenge_user_expires"),
        "mfa_login_challenge",
        ["user_id", "expires_at", "used_at"],
        unique=False,
    )

    # recovery_code indexes
    op.create_index(
        op.f("ix_recovery_code_user_used"),
        "recovery_code",
        ["user_id", "used_at"],
        unique=False,
    )

    # audit_log index
    op.create_index(
        op.f("ix_audit_log_user_created"),
        "audit_log",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_user_created"), table_name="audit_log")
    op.drop_index(op.f("ix_recovery_code_user_used"), table_name="recovery_code")
    op.drop_index(op.f("ix_mfa_login_challenge_user_expires"), table_name="mfa_login_challenge")
    op.drop_index(op.f("ix_refresh_token_user_revoked"), table_name="refresh_token")
