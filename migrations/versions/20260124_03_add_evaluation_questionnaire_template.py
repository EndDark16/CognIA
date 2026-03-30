"""Link evaluation to questionnaire_template.

SQL (upgrade):
    ALTER TABLE public.evaluation ADD COLUMN questionnaire_template_id uuid;
    UPDATE public.evaluation SET questionnaire_template_id = <active_template_id>;
    ALTER TABLE public.evaluation ALTER COLUMN questionnaire_template_id SET NOT NULL;
    ALTER TABLE public.evaluation ADD CONSTRAINT fk_evaluation_questionnaire_template
        FOREIGN KEY (questionnaire_template_id)
        REFERENCES public.questionnaire_template(id) ON DELETE RESTRICT;
    CREATE INDEX idx_evaluation_questionnaire_template_id
        ON public.evaluation (questionnaire_template_id);

Post-migration checks:
    SELECT COUNT(*) FROM evaluation WHERE questionnaire_template_id IS NULL;
    SELECT id, name, version, updated_at, created_at
      FROM questionnaire_template
     WHERE is_active = true
     ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
     LIMIT 1;
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260124_03"
down_revision = "20260124_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation",
        sa.Column("questionnaire_template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    conn = op.get_bind()
    template_id = conn.execute(
        sa.text(
            """
            SELECT id
            FROM questionnaire_template
            WHERE is_active = true
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        )
    ).scalar()

    if not template_id:
        raise RuntimeError(
            "No active questionnaire_template found; cannot backfill questionnaire_template_id."
        )

    conn.execute(
        sa.text(
            """
            UPDATE evaluation
            SET questionnaire_template_id = :template_id
            WHERE questionnaire_template_id IS NULL
            """
        ),
        {"template_id": template_id},
    )

    op.alter_column("evaluation", "questionnaire_template_id", nullable=False)
    op.create_foreign_key(
        "fk_evaluation_questionnaire_template",
        "evaluation",
        "questionnaire_template",
        ["questionnaire_template_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "idx_evaluation_questionnaire_template_id",
        "evaluation",
        ["questionnaire_template_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_evaluation_questionnaire_template_id", table_name="evaluation")
    op.drop_constraint(
        "fk_evaluation_questionnaire_template", "evaluation", type_="foreignkey"
    )
    op.drop_column("evaluation", "questionnaire_template_id")
