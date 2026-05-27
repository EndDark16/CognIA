"""Add QV2 application traceability fields.

Revision ID: 20260526_01
Revises: 20260523_01
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260526_01"
down_revision = "20260523_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questionnaire_sessions",
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("questionnaire_sessions", sa.Column("completed_by_display_name", sa.String(length=255), nullable=True))
    op.add_column("questionnaire_sessions", sa.Column("completed_by_role", sa.String(length=80), nullable=True))
    op.add_column(
        "questionnaire_sessions", sa.Column("completed_by_professional_role", sa.String(length=80), nullable=True)
    )
    op.add_column("questionnaire_sessions", sa.Column("respondent_relationship", sa.String(length=80), nullable=True))
    op.add_column("questionnaire_sessions", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questionnaire_sessions", sa.Column("institution_name", sa.String(length=255), nullable=True))
    op.add_column("questionnaire_sessions", sa.Column("source_channel", sa.String(length=80), nullable=True))

    op.create_index(
        "ix_questionnaire_sessions_completed_by_user_id",
        "questionnaire_sessions",
        ["completed_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_questionnaire_sessions_completed_by_user_id",
        "questionnaire_sessions",
        "app_user",
        ["completed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_questionnaire_sessions_applied_at", "questionnaire_sessions", ["applied_at"], unique=False)
    op.create_index("ix_questionnaire_sessions_source_channel", "questionnaire_sessions", ["source_channel"], unique=False)

    op.execute(
        """
        UPDATE questionnaire_sessions
        SET completed_by_user_id = owner_user_id,
            completed_by_role = respondent_role,
            respondent_relationship = COALESCE(respondent_role, 'guardian'),
            applied_at = COALESCE(started_at, created_at)
        WHERE completed_by_user_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_questionnaire_sessions_source_channel", table_name="questionnaire_sessions")
    op.drop_index("ix_questionnaire_sessions_applied_at", table_name="questionnaire_sessions")
    op.drop_constraint(
        "fk_questionnaire_sessions_completed_by_user_id",
        "questionnaire_sessions",
        type_="foreignkey",
    )
    op.drop_index("ix_questionnaire_sessions_completed_by_user_id", table_name="questionnaire_sessions")
    op.drop_column("questionnaire_sessions", "source_channel")
    op.drop_column("questionnaire_sessions", "institution_name")
    op.drop_column("questionnaire_sessions", "applied_at")
    op.drop_column("questionnaire_sessions", "respondent_relationship")
    op.drop_column("questionnaire_sessions", "completed_by_professional_role")
    op.drop_column("questionnaire_sessions", "completed_by_role")
    op.drop_column("questionnaire_sessions", "completed_by_display_name")
    op.drop_column("questionnaire_sessions", "completed_by_user_id")
