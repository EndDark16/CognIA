"""Set defaults on user_session timestamps"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251210_01"
down_revision = "20251209_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure existing rows have values
    op.execute("UPDATE user_session SET started_at = now() WHERE started_at IS NULL;")
    op.execute("UPDATE user_session SET created_at = now() WHERE created_at IS NULL;")
    op.execute("UPDATE user_session SET updated_at = now() WHERE updated_at IS NULL;")

    # Apply server defaults
    op.alter_column(
        "user_session",
        "started_at",
        server_default=sa.text("now()"),
        existing_type=sa.TIMESTAMP(timezone=True),
    )
    op.alter_column(
        "user_session",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.TIMESTAMP(timezone=True),
    )
    op.alter_column(
        "user_session",
        "updated_at",
        server_default=sa.text("now()"),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "user_session",
        "updated_at",
        server_default=None,
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "user_session",
        "created_at",
        server_default=None,
        existing_type=sa.TIMESTAMP(timezone=True),
    )
    op.alter_column(
        "user_session",
        "started_at",
        server_default=None,
        existing_type=sa.TIMESTAMP(timezone=True),
    )
