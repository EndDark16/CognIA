"""Add questionnaire runtime v1 schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260330_01"
down_revision = "20260208_01"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "qr_questionnaire_template",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("slug", name="uq_qr_questionnaire_template_slug"),
    )

    op.create_table(
        "qr_questionnaire_version",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("template_id", UUID, sa.ForeignKey("qr_questionnaire_template.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("template_id", "version_label", name="uq_qr_template_version_label"),
    )

    op.create_table(
        "qr_disclosure_version",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("questionnaire_version_id", UUID, sa.ForeignKey("qr_questionnaire_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disclosure_type", sa.String(length=40), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "questionnaire_version_id",
            "disclosure_type",
            "version_label",
            name="uq_qr_disclosure_version",
        ),
    )

    op.create_table(
        "qr_questionnaire_section",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("questionnaire_version_id", UUID, sa.ForeignKey("qr_questionnaire_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("questionnaire_version_id", "key", name="uq_qr_section_key"),
    )

    op.create_table(
        "qr_question",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("section_id", UUID, sa.ForeignKey("qr_questionnaire_section.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=150), nullable=False),
        sa.Column("feature_key", sa.String(length=150), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.Column("response_type", sa.String(length=40), nullable=False),
        sa.Column("requiredness", sa.String(length=20), nullable=False, server_default="required"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("step_value", sa.Float(), nullable=True),
        sa.Column("allowed_values", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("visibility_rule", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("section_id", "key", name="uq_qr_question_key"),
    )

    op.create_table(
        "qr_question_option",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("qr_question.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_value", sa.String(length=120), nullable=False),
        sa.Column("option_label", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "option_value", name="uq_qr_question_option_value"),
    )

    op.create_table(
        "qr_evaluation",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("questionnaire_version_id", UUID, sa.ForeignKey("qr_questionnaire_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("psychologist_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("respondent_type", sa.String(length=40), nullable=False, server_default="caregiver"),
        sa.Column("child_age_years", sa.Integer(), nullable=False),
        sa.Column("child_sex_assigned_at_birth", sa.String(length=32), nullable=False, server_default="Unknown"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("review_tag", sa.String(length=40), nullable=False, server_default="sin_revisar"),
        sa.Column("deleted_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_id", sa.String(length=24), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pin_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_disclosure_id", UUID, sa.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pre_disclaimer_id", UUID, sa.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("result_disclaimer_id", UUID, sa.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pdf_disclaimer_id", UUID, sa.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runtime_scope_version", sa.String(length=64), nullable=False, server_default="questionnaire_runtime_v1"),
        sa.Column("model_runtime_bundle", sa.String(length=120), nullable=False, server_default="qr_runtime_bundle_v1"),
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_waiting_live_result", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_presence_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notify_if_user_offline", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("reference_id", name="uq_qr_evaluation_reference_id"),
    )
    op.create_index("ix_qr_evaluation_requested_by_user_id", "qr_evaluation", ["requested_by_user_id"])
    op.create_index("ix_qr_evaluation_psychologist_user_id", "qr_evaluation", ["psychologist_user_id"])
    op.create_index("ix_qr_evaluation_status", "qr_evaluation", ["status"])
    op.create_index("ix_qr_evaluation_deleted_by_user", "qr_evaluation", ["deleted_by_user"])
    op.create_index("ix_qr_evaluation_reference_id", "qr_evaluation", ["reference_id"])

    op.create_table(
        "qr_evaluation_response",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("evaluation_id", UUID, sa.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("qr_question.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("section_id", UUID, sa.ForeignKey("qr_questionnaire_section.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_raw", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("answer_normalized", sa.Text(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("evaluation_id", "question_id", name="uq_qr_eval_question"),
    )
    op.create_index("ix_qr_evaluation_response_evaluation_id", "qr_evaluation_response", ["evaluation_id"])

    op.create_table(
        "qr_processing_job",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("evaluation_id", UUID, sa.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("evaluation_id", name="uq_qr_processing_job_eval"),
    )

    op.create_table(
        "qr_domain_result",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("evaluation_id", UUID, sa.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("model_status", sa.String(length=120), nullable=False),
        sa.Column("probability", sa.Numeric(8, 6), nullable=False),
        sa.Column("threshold_used", sa.Numeric(8, 6), nullable=False),
        sa.Column("risk_band", sa.String(length=40), nullable=False),
        sa.Column("confidence_level", sa.String(length=40), nullable=False),
        sa.Column("evidence_level", sa.String(length=40), nullable=False),
        sa.Column("uncertainty_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("abstention_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("explanation_short", sa.Text(), nullable=False),
        sa.Column("contributors_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("caveats_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("evaluation_id", "domain", name="uq_qr_eval_domain"),
    )
    op.create_index("ix_qr_domain_result_evaluation_id", "qr_domain_result", ["evaluation_id"])

    op.create_table(
        "qr_notification",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("evaluation_id", UUID, sa.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_qr_notification_user_id", "qr_notification", ["user_id"])
    op.create_index("ix_qr_notification_evaluation_id", "qr_notification", ["evaluation_id"])

    op.create_table(
        "qr_export_log",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("evaluation_id", UUID, sa.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("export_mode", sa.String(length=40), nullable=False),
        sa.Column("export_format", sa.String(length=40), nullable=False, server_default="json"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_qr_export_log_evaluation_id", "qr_export_log", ["evaluation_id"])


def downgrade() -> None:
    op.drop_index("ix_qr_export_log_evaluation_id", table_name="qr_export_log")
    op.drop_table("qr_export_log")

    op.drop_index("ix_qr_notification_evaluation_id", table_name="qr_notification")
    op.drop_index("ix_qr_notification_user_id", table_name="qr_notification")
    op.drop_table("qr_notification")

    op.drop_index("ix_qr_domain_result_evaluation_id", table_name="qr_domain_result")
    op.drop_table("qr_domain_result")

    op.drop_table("qr_processing_job")

    op.drop_index("ix_qr_evaluation_response_evaluation_id", table_name="qr_evaluation_response")
    op.drop_table("qr_evaluation_response")

    op.drop_index("ix_qr_evaluation_reference_id", table_name="qr_evaluation")
    op.drop_index("ix_qr_evaluation_deleted_by_user", table_name="qr_evaluation")
    op.drop_index("ix_qr_evaluation_status", table_name="qr_evaluation")
    op.drop_index("ix_qr_evaluation_psychologist_user_id", table_name="qr_evaluation")
    op.drop_index("ix_qr_evaluation_requested_by_user_id", table_name="qr_evaluation")
    op.drop_table("qr_evaluation")

    op.drop_table("qr_question_option")
    op.drop_table("qr_question")
    op.drop_table("qr_questionnaire_section")
    op.drop_table("qr_disclosure_version")
    op.drop_table("qr_questionnaire_version")
    op.drop_table("qr_questionnaire_template")
