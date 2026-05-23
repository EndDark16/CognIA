"""Add questionnaire cases, professional reviews, and psychologist location fields.

Revision ID: 20260522_01
Revises: 20260510_01
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260522_01"
down_revision = "20260510_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("professional_city", sa.String(length=120), nullable=True))
    op.add_column("app_user", sa.Column("professional_department", sa.String(length=120), nullable=True))
    op.add_column("app_user", sa.Column("professional_location", sa.String(length=255), nullable=True))

    op.create_table(
        "questionnaire_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_public_id", sa.String(length=40), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("private_label", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_public_id", name="uq_questionnaire_cases_public_id"),
    )
    op.create_index("ix_questionnaire_cases_owner_user_id", "questionnaire_cases", ["owner_user_id"], unique=False)
    op.create_index("ix_questionnaire_cases_status", "questionnaire_cases", ["status"], unique=False)
    op.create_index("ix_questionnaire_cases_case_public_id", "questionnaire_cases", ["case_public_id"], unique=True)

    op.add_column(
        "questionnaire_sessions",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_questionnaire_sessions_case_id", "questionnaire_sessions", ["case_id"], unique=False)
    op.create_foreign_key(
        "fk_questionnaire_sessions_case_id",
        "questionnaire_sessions",
        "questionnaire_cases",
        ["case_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "questionnaire_professional_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("psychologist_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("initial_concept", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("visible_to_guardian", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_diagnostic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["questionnaire_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["psychologist_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["questionnaire_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "psychologist_user_id",
            name="uq_questionnaire_professional_review_session_psychologist",
        ),
    )
    op.create_index(
        "ix_questionnaire_professional_reviews_session_id",
        "questionnaire_professional_reviews",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_professional_reviews_case_id",
        "questionnaire_professional_reviews",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_professional_reviews_owner_user_id",
        "questionnaire_professional_reviews",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_professional_reviews_psychologist_user_id",
        "questionnaire_professional_reviews",
        ["psychologist_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_professional_reviews_review_status",
        "questionnaire_professional_reviews",
        ["review_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_questionnaire_professional_reviews_review_status", table_name="questionnaire_professional_reviews")
    op.drop_index(
        "ix_questionnaire_professional_reviews_psychologist_user_id",
        table_name="questionnaire_professional_reviews",
    )
    op.drop_index("ix_questionnaire_professional_reviews_owner_user_id", table_name="questionnaire_professional_reviews")
    op.drop_index("ix_questionnaire_professional_reviews_case_id", table_name="questionnaire_professional_reviews")
    op.drop_index("ix_questionnaire_professional_reviews_session_id", table_name="questionnaire_professional_reviews")
    op.drop_table("questionnaire_professional_reviews")

    op.drop_constraint("fk_questionnaire_sessions_case_id", "questionnaire_sessions", type_="foreignkey")
    op.drop_index("ix_questionnaire_sessions_case_id", table_name="questionnaire_sessions")
    op.drop_column("questionnaire_sessions", "case_id")

    op.drop_index("ix_questionnaire_cases_case_public_id", table_name="questionnaire_cases")
    op.drop_index("ix_questionnaire_cases_status", table_name="questionnaire_cases")
    op.drop_index("ix_questionnaire_cases_owner_user_id", table_name="questionnaire_cases")
    op.drop_table("questionnaire_cases")

    op.drop_column("app_user", "professional_location")
    op.drop_column("app_user", "professional_department")
    op.drop_column("app_user", "professional_city")
