"""Add problem reports backend tables.

Revision ID: 20260415_01
Revises: 20260414_01
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260415_01"
down_revision = "20260414_01"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSON(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "problem_reports",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("report_code", sa.String(length=24), nullable=False),
        sa.Column("reporter_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("reporter_role", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_module", sa.String(length=120), nullable=True),
        sa.Column("source_path", sa.String(length=255), nullable=True),
        sa.Column(
            "related_questionnaire_session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("related_questionnaire_history_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("report_code", name="uq_problem_reports_report_code"),
    )
    op.create_index("ix_problem_reports_report_code", "problem_reports", ["report_code"])
    op.create_index("ix_problem_reports_reporter_user_id", "problem_reports", ["reporter_user_id"])
    op.create_index("ix_problem_reports_reporter_role", "problem_reports", ["reporter_role"])
    op.create_index("ix_problem_reports_issue_type", "problem_reports", ["issue_type"])
    op.create_index("ix_problem_reports_status", "problem_reports", ["status"])
    op.create_index("ix_problem_reports_created_at", "problem_reports", ["created_at"])

    op.create_table(
        "problem_report_attachments",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "report_id",
            UUID,
            sa.ForeignKey("problem_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_kind", sa.String(length=40), nullable=False, server_default="local"),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_problem_report_attachments_report_id",
        "problem_report_attachments",
        ["report_id"],
    )

    op.create_table(
        "problem_report_audit_events",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "report_id",
            UUID,
            sa.ForeignKey("problem_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_problem_report_audit_events_report_id",
        "problem_report_audit_events",
        ["report_id"],
    )
    op.create_index(
        "ix_problem_report_audit_events_event_type",
        "problem_report_audit_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_problem_report_audit_events_event_type", table_name="problem_report_audit_events")
    op.drop_index("ix_problem_report_audit_events_report_id", table_name="problem_report_audit_events")
    op.drop_table("problem_report_audit_events")

    op.drop_index("ix_problem_report_attachments_report_id", table_name="problem_report_attachments")
    op.drop_table("problem_report_attachments")

    op.drop_index("ix_problem_reports_created_at", table_name="problem_reports")
    op.drop_index("ix_problem_reports_status", table_name="problem_reports")
    op.drop_index("ix_problem_reports_issue_type", table_name="problem_reports")
    op.drop_index("ix_problem_reports_reporter_role", table_name="problem_reports")
    op.drop_index("ix_problem_reports_reporter_user_id", table_name="problem_reports")
    op.drop_index("ix_problem_reports_report_code", table_name="problem_reports")
    op.drop_table("problem_reports")
