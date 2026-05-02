"""Add question_disorder relation for multi-disorder questions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260124_05"
down_revision = "20260124_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_disorder",
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("question.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "disorder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("disorder.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_question_disorder_question",
        "question_disorder",
        ["question_id"],
    )
    op.create_index(
        "idx_question_disorder_disorder",
        "question_disorder",
        ["disorder_id"],
    )

    # Backfill from legacy question.disorder_id.
    op.execute(
        """
        INSERT INTO question_disorder (question_id, disorder_id)
        SELECT id, disorder_id
        FROM question
        WHERE disorder_id IS NOT NULL
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_question_disorder_disorder", table_name="question_disorder")
    op.drop_index("idx_question_disorder_question", table_name="question_disorder")
    op.drop_table("question_disorder")
