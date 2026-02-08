"""Add email unsubscribe table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260204_01"
down_revision = "20260130_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_unsubscribe",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("request_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_unsubscribe_email", "email_unsubscribe", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_email_unsubscribe_email", table_name="email_unsubscribe")
    op.drop_table("email_unsubscribe")
