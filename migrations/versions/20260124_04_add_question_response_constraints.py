"""Add response constraint metadata to question."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260124_04"
down_revision = "20260124_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("question", sa.Column("response_min", sa.Numeric(), nullable=True))
    op.add_column("question", sa.Column("response_max", sa.Numeric(), nullable=True))
    op.add_column("question", sa.Column("response_step", sa.Numeric(), nullable=True))
    op.add_column("question", sa.Column("response_options", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("question", "response_options")
    op.drop_column("question", "response_step")
    op.drop_column("question", "response_max")
    op.drop_column("question", "response_min")
