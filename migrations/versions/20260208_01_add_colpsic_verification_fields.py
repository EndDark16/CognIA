"""Add COLPSIC verification fields and questionnaire archive flags."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260208_01"
down_revision = "20260204_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("colpsic_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("app_user", sa.Column("colpsic_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "app_user",
        sa.Column("colpsic_verified_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("app_user", sa.Column("colpsic_rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "app_user",
        sa.Column("colpsic_rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("app_user", sa.Column("colpsic_reject_reason", sa.Text(), nullable=True))
    op.add_column("app_user", sa.Column("sessions_revoked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_app_user_colpsic_verified_by",
        "app_user",
        "app_user",
        ["colpsic_verified_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_app_user_colpsic_rejected_by",
        "app_user",
        "app_user",
        ["colpsic_rejected_by"],
        ["id"],
    )

    op.add_column(
        "questionnaire_template",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "questionnaire_template",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questionnaire_template", "archived_at")
    op.drop_column("questionnaire_template", "is_archived")

    op.drop_constraint("fk_app_user_colpsic_rejected_by", "app_user", type_="foreignkey")
    op.drop_constraint("fk_app_user_colpsic_verified_by", "app_user", type_="foreignkey")
    op.drop_column("app_user", "sessions_revoked_at")
    op.drop_column("app_user", "colpsic_reject_reason")
    op.drop_column("app_user", "colpsic_rejected_by")
    op.drop_column("app_user", "colpsic_rejected_at")
    op.drop_column("app_user", "colpsic_verified_by")
    op.drop_column("app_user", "colpsic_verified_at")
    op.drop_column("app_user", "colpsic_verified")
