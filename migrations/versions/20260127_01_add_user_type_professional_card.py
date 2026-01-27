"""Add user_type and professional_card_number to app_user."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260127_01"
down_revision = "20260125_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("user_type", sa.String(), nullable=False, server_default="guardian"),
    )
    op.add_column(
        "app_user",
        sa.Column("professional_card_number", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_app_user_professional_card_number",
        "app_user",
        ["professional_card_number"],
    )
    op.create_index("ix_app_user_user_type", "app_user", ["user_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_app_user_user_type", table_name="app_user")
    op.drop_constraint(
        "uq_app_user_professional_card_number",
        "app_user",
        type_="unique",
    )
    op.drop_column("app_user", "professional_card_number")
    op.drop_column("app_user", "user_type")
