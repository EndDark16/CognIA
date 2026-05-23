"""Add share request workflow, notifications, case label hash, and profile locations.

Revision ID: 20260523_01
Revises: 20260522_01
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260523_01"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("app_user", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column("app_user", sa.Column("location", sa.String(length=255), nullable=True))

    op.add_column("questionnaire_cases", sa.Column("private_label_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_questionnaire_cases_private_label_hash",
        "questionnaire_cases",
        ["private_label_hash"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_cases_owner_hash_status",
        "questionnaire_cases",
        ["owner_user_id", "private_label_hash", "status"],
        unique=False,
    )

    op.add_column(
        "questionnaire_access_grants",
        sa.Column("request_status", sa.String(length=40), server_default="accepted", nullable=False),
    )
    op.add_column(
        "questionnaire_access_grants",
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("questionnaire_access_grants", sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questionnaire_access_grants", sa.Column("response_message", sa.Text(), nullable=True))
    op.add_column(
        "questionnaire_access_grants",
        sa.Column("decision_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "questionnaire_access_grants",
        sa.Column("requested_can_tag", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "questionnaire_access_grants",
        sa.Column("requested_can_download_pdf", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_foreign_key(
        "fk_questionnaire_access_grants_decision_by_user_id",
        "questionnaire_access_grants",
        "app_user",
        ["decision_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_questionnaire_access_grants_request_status",
        "questionnaire_access_grants",
        ["request_status"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_access_grants_requested_at",
        "questionnaire_access_grants",
        ["requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_access_grants_responded_at",
        "questionnaire_access_grants",
        ["responded_at"],
        unique=False,
    )
    op.create_index(
        "ix_questionnaire_access_grants_decision_by_user_id",
        "questionnaire_access_grants",
        ["decision_by_user_id"],
        unique=False,
    )

    op.execute(
        """
        UPDATE questionnaire_access_grants
        SET request_status = 'accepted',
            requested_at = COALESCE(created_at, now()),
            requested_can_tag = COALESCE(can_tag, true),
            requested_can_download_pdf = COALESCE(can_download_pdf, true)
        """
    )

    op.create_table(
        "questionnaire_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notification_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["questionnaire_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["grant_id"], ["questionnaire_access_grants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["questionnaire_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questionnaire_notifications_user_id", "questionnaire_notifications", ["user_id"], unique=False)
    op.create_index(
        "ix_questionnaire_notifications_actor_user_id", "questionnaire_notifications", ["actor_user_id"], unique=False
    )
    op.create_index("ix_questionnaire_notifications_session_id", "questionnaire_notifications", ["session_id"], unique=False)
    op.create_index("ix_questionnaire_notifications_case_id", "questionnaire_notifications", ["case_id"], unique=False)
    op.create_index("ix_questionnaire_notifications_grant_id", "questionnaire_notifications", ["grant_id"], unique=False)
    op.create_index(
        "ix_questionnaire_notifications_notification_type",
        "questionnaire_notifications",
        ["notification_type"],
        unique=False,
    )
    op.create_index("ix_questionnaire_notifications_read_at", "questionnaire_notifications", ["read_at"], unique=False)
    op.create_index(
        "ix_questionnaire_notifications_created_at",
        "questionnaire_notifications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_questionnaire_notifications_created_at", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_read_at", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_notification_type", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_grant_id", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_case_id", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_session_id", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_actor_user_id", table_name="questionnaire_notifications")
    op.drop_index("ix_questionnaire_notifications_user_id", table_name="questionnaire_notifications")
    op.drop_table("questionnaire_notifications")

    op.drop_index("ix_questionnaire_access_grants_decision_by_user_id", table_name="questionnaire_access_grants")
    op.drop_index("ix_questionnaire_access_grants_responded_at", table_name="questionnaire_access_grants")
    op.drop_index("ix_questionnaire_access_grants_requested_at", table_name="questionnaire_access_grants")
    op.drop_index("ix_questionnaire_access_grants_request_status", table_name="questionnaire_access_grants")
    op.drop_constraint(
        "fk_questionnaire_access_grants_decision_by_user_id",
        "questionnaire_access_grants",
        type_="foreignkey",
    )
    op.drop_column("questionnaire_access_grants", "requested_can_download_pdf")
    op.drop_column("questionnaire_access_grants", "requested_can_tag")
    op.drop_column("questionnaire_access_grants", "decision_by_user_id")
    op.drop_column("questionnaire_access_grants", "response_message")
    op.drop_column("questionnaire_access_grants", "responded_at")
    op.drop_column("questionnaire_access_grants", "requested_at")
    op.drop_column("questionnaire_access_grants", "request_status")

    op.drop_index("ix_questionnaire_cases_owner_hash_status", table_name="questionnaire_cases")
    op.drop_index("ix_questionnaire_cases_private_label_hash", table_name="questionnaire_cases")
    op.drop_column("questionnaire_cases", "private_label_hash")

    op.drop_column("app_user", "location")
    op.drop_column("app_user", "department")
    op.drop_column("app_user", "city")
