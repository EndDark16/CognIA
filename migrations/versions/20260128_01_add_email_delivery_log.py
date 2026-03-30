"""Add email_delivery_log table."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260128_01"
down_revision = "20260127_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_delivery_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("recipient_email", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("email_delivery_log")
