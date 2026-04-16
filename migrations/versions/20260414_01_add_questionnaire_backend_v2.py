"""Add questionnaire backend v2 schema.

Revision ID: 20260414_01
Revises: 20260330_01
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_01"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSON(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "questionnaire_definitions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("slug", name="uq_questionnaire_definitions_slug"),
    )
    op.create_index("ix_questionnaire_definitions_slug", "questionnaire_definitions", ["slug"])

    op.create_table(
        "questionnaire_versions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "definition_id",
            UUID,
            sa.ForeignKey("questionnaire_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("source_folder", sa.String(length=512), nullable=True),
        sa.Column("source_master_csv", sa.String(length=512), nullable=True),
        sa.Column("source_visible_csv", sa.String(length=512), nullable=True),
        sa.Column("source_scales_csv", sa.String(length=512), nullable=True),
        sa.Column("source_preview_md", sa.String(length=512), nullable=True),
        sa.Column("source_pdf", sa.String(length=512), nullable=True),
        sa.Column("source_audit_md", sa.String(length=512), nullable=True),
        sa.Column("questionnaire_version_final", sa.String(length=128), nullable=True),
        sa.Column("scales_version_label", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("definition_id", "version_label", name="uq_questionnaire_definition_version"),
    )

    op.create_table(
        "questionnaire_sections",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "section_key", name="uq_questionnaire_version_section"),
    )

    op.create_table(
        "questionnaire_scales",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scale_id", sa.String(length=120), nullable=False),
        sa.Column("scale_name", sa.String(length=255), nullable=False),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=120), nullable=True),
        sa.Column("scale_guidance", sa.Text(), nullable=True),
        sa.Column("options_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "scale_id", name="uq_questionnaire_version_scale"),
    )

    op.create_table(
        "questionnaire_scale_options",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "scale_ref_id",
            UUID,
            sa.ForeignKey("questionnaire_scales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("option_value", sa.String(length=120), nullable=False),
        sa.Column("option_label", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("scale_ref_id", "option_value", name="uq_questionnaire_scale_option_value"),
    )

    op.create_table(
        "questionnaire_questions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", UUID, sa.ForeignKey("questionnaire_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_code", sa.String(length=120), nullable=False),
        sa.Column("feature_key", sa.String(length=160), nullable=False),
        sa.Column("canonical_question_code", sa.String(length=120), nullable=True),
        sa.Column("question_text_primary", sa.Text(), nullable=True),
        sa.Column("caregiver_question", sa.Text(), nullable=True),
        sa.Column("psychologist_question", sa.Text(), nullable=True),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.Column("layer", sa.String(length=80), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False, server_default="general"),
        sa.Column("domains_final", sa.String(length=255), nullable=True),
        sa.Column("module", sa.String(length=120), nullable=True),
        sa.Column("criterion_ref", sa.String(length=120), nullable=True),
        sa.Column("instrument_or_source", sa.String(length=255), nullable=True),
        sa.Column("feature_type", sa.String(length=120), nullable=True),
        sa.Column("feature_role", sa.String(length=120), nullable=True),
        sa.Column("respondent_expected", sa.String(length=120), nullable=True),
        sa.Column("administered_by", sa.String(length=120), nullable=True),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("scale_id", sa.String(length=120), nullable=True),
        sa.Column("response_options_json", JSONB, nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=80), nullable=True),
        sa.Column("visible_question", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("generated_input", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_internal_input", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_transparent_derived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_internal_scoring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_exact_item_wording", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_clinician_administration", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_child_self_report", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question_audit_status", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "question_code", name="uq_questionnaire_version_question_code"),
    )
    op.create_index("ix_questionnaire_questions_feature_key", "questionnaire_questions", ["feature_key"])

    op.create_table(
        "questionnaire_question_modes",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode_key", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("delivery_mode", sa.String(length=40), nullable=False),
        sa.Column("is_included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority_rank", sa.Float(), nullable=True),
        sa.Column("priority_bucket", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "mode_key", name="uq_question_mode"),
    )

    op.create_table(
        "questionnaire_internal_inputs",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(length=160), nullable=False),
        sa.Column(
            "source_question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("derived_from_features", JSONB, nullable=True),
        sa.Column("internal_scoring_formula_summary", sa.Text(), nullable=True),
        sa.Column("storage_type", sa.String(length=64), nullable=False, server_default="numeric"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_internal_scoring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "feature_key", name="uq_questionnaire_internal_input_feature"),
    )

    op.create_table(
        "questionnaire_repeat_mapping",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repeated_question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canonical_question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reuse_answer", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mapping_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "repeated_question_id", name="uq_questionnaire_repeat_question"),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("model_key", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("mode_key", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("source_line", sa.String(length=120), nullable=True),
        sa.Column("source_campaign", sa.String(length=120), nullable=True),
        sa.Column("model_family", sa.String(length=120), nullable=True),
        sa.Column("feature_set_id", sa.String(length=160), nullable=True),
        sa.Column("config_id", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("model_key", name="uq_model_registry_model_key"),
    )
    op.create_index("ix_model_registry_model_key", "model_registry", ["model_key"])
    op.create_index("ix_model_registry_domain", "model_registry", ["domain"])
    op.create_index("ix_model_registry_mode_key", "model_registry", ["mode_key"])
    op.create_index("ix_model_registry_role", "model_registry", ["role"])

    op.create_table(
        "model_versions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "model_registry_id",
            UUID,
            sa.ForeignKey("model_registry.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version_tag", sa.String(length=128), nullable=False),
        sa.Column("artifact_path", sa.String(length=512), nullable=True),
        sa.Column("fallback_artifact_path", sa.String(length=512), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("calibration", sa.String(length=120), nullable=True),
        sa.Column("threshold_policy", sa.String(length=120), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("seed", sa.String(length=40), nullable=True),
        sa.Column("n_features", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("model_registry_id", "model_version_tag", name="uq_model_registry_version_tag"),
    )
    op.create_index("ix_model_versions_model_registry_id", "model_versions", ["model_registry_id"])

    op.create_table(
        "model_mode_domain_activation",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("mode_key", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("model_registry_id", UUID, sa.ForeignKey("model_registry.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model_version_id", UUID, sa.ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("active_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_campaign", sa.String(length=120), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "domain",
            "mode_key",
            "role",
            "active_flag",
            name="uq_model_mode_domain_active",
        ),
    )
    op.create_index("ix_model_mode_domain_activation_domain", "model_mode_domain_activation", ["domain"])
    op.create_index("ix_model_mode_domain_activation_mode_key", "model_mode_domain_activation", ["mode_key"])
    op.create_index("ix_model_mode_domain_activation_role", "model_mode_domain_activation", ["role"])

    op.create_table(
        "model_metrics_snapshot",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "model_version_id",
            UUID,
            sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("specificity", sa.Float(), nullable=True),
        sa.Column("balanced_accuracy", sa.Float(), nullable=True),
        sa.Column("f1", sa.Float(), nullable=True),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        sa.Column("pr_auc", sa.Float(), nullable=True),
        sa.Column("brier", sa.Float(), nullable=True),
        sa.Column("overfit_flag", sa.String(length=32), nullable=True),
        sa.Column("generalization_flag", sa.String(length=32), nullable=True),
        sa.Column("dataset_ease_flag", sa.String(length=32), nullable=True),
        sa.Column("quality_label", sa.String(length=64), nullable=True),
        sa.Column("metrics_json", JSONB, nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_metrics_snapshot_model_version_id", "model_metrics_snapshot", ["model_version_id"])

    op.create_table(
        "model_artifact_registry",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "model_version_id",
            UUID,
            sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_kind", sa.String(length=64), nullable=False),
        sa.Column("artifact_locator", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("model_version_id", "artifact_kind", name="uq_model_version_artifact_kind"),
    )
    op.create_index("ix_model_artifact_registry_model_version_id", "model_artifact_registry", ["model_version_id"])

    op.create_table(
        "model_confidence_registry",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "activation_id",
            UUID,
            sa.ForeignKey("model_mode_domain_activation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence_pct", sa.Float(), nullable=True),
        sa.Column("confidence_band", sa.String(length=64), nullable=True),
        sa.Column("operational_class", sa.String(length=120), nullable=True),
        sa.Column("recommended_for_default_use", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_confidence_registry_activation_id", "model_confidence_registry", ["activation_id"])

    op.create_table(
        "model_operational_caveats",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "activation_id",
            UUID,
            sa.ForeignKey("model_mode_domain_activation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("caveat", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_operational_caveats_activation_id", "model_operational_caveats", ["activation_id"])

    op.create_table(
        "questionnaire_sessions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("questionnaire_public_id", sa.String(length=40), nullable=False),
        sa.Column(
            "version_id",
            UUID,
            sa.ForeignKey("questionnaire_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("respondent_role", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("mode_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("completion_quality_score", sa.Float(), nullable=True),
        sa.Column("missingness_score", sa.Float(), nullable=True),
        sa.Column("inconsistency_flags_json", JSONB, nullable=True),
        sa.Column("model_pipeline_version", sa.String(length=128), nullable=True),
        sa.Column("questionnaire_version_label", sa.String(length=128), nullable=True),
        sa.Column("scales_version_label", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("questionnaire_public_id", name="uq_questionnaire_sessions_public_id"),
    )
    op.create_index("ix_questionnaire_sessions_questionnaire_public_id", "questionnaire_sessions", ["questionnaire_public_id"])
    op.create_index("ix_questionnaire_sessions_owner_user_id", "questionnaire_sessions", ["owner_user_id"])
    op.create_index("ix_questionnaire_sessions_status", "questionnaire_sessions", ["status"])
    op.create_index("ix_questionnaire_sessions_version_id", "questionnaire_sessions", ["version_id"])

    op.create_table(
        "questionnaire_session_items",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", UUID, sa.ForeignKey("questionnaire_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_id", UUID, sa.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "question_id", name="uq_questionnaire_session_question"),
    )
    op.create_index("ix_questionnaire_session_items_session_id", "questionnaire_session_items", ["session_id"])

    op.create_table(
        "questionnaire_session_answers",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", UUID, sa.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "canonical_question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("answer_raw", JSONB, nullable=False),
        sa.Column("answer_normalized", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="user"),
        sa.Column("answered_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "question_id", name="uq_questionnaire_session_answer"),
    )
    op.create_index("ix_questionnaire_session_answers_session_id", "questionnaire_session_answers", ["session_id"])

    op.create_table(
        "questionnaire_session_internal_features",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(length=160), nullable=False),
        sa.Column("feature_value_numeric", sa.Float(), nullable=True),
        sa.Column("feature_value_text", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="direct"),
        sa.Column(
            "source_question_id",
            UUID,
            sa.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "feature_key", name="uq_session_feature_key"),
    )
    op.create_index(
        "ix_questionnaire_session_internal_features_session_id",
        "questionnaire_session_internal_features",
        ["session_id"],
    )

    op.create_table(
        "questionnaire_session_results",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("operational_recommendation", sa.Text(), nullable=False),
        sa.Column("completion_quality_score", sa.Float(), nullable=True),
        sa.Column("missingness_score", sa.Float(), nullable=True),
        sa.Column("inconsistency_flags_json", JSONB, nullable=True),
        sa.Column("needs_professional_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("runtime_ms", sa.Float(), nullable=True),
        sa.Column("model_bundle_version", sa.String(length=128), nullable=True),
        sa.Column("questionnaire_version_label", sa.String(length=128), nullable=True),
        sa.Column("scales_version_label", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", name="uq_questionnaire_session_results_session"),
    )

    op.create_table(
        "questionnaire_session_result_domains",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "result_id",
            UUID,
            sa.ForeignKey("questionnaire_session_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("alert_level", sa.String(length=40), nullable=False),
        sa.Column("confidence_pct", sa.Float(), nullable=True),
        sa.Column("confidence_band", sa.String(length=64), nullable=True),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("operational_class", sa.String(length=120), nullable=True),
        sa.Column("operational_caveat", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("needs_professional_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("result_id", "domain", name="uq_result_domain"),
    )
    op.create_index(
        "ix_questionnaire_session_result_domains_session_id",
        "questionnaire_session_result_domains",
        ["session_id"],
    )
    op.create_index(
        "ix_questionnaire_session_result_domains_domain",
        "questionnaire_session_result_domains",
        ["domain"],
    )

    op.create_table(
        "questionnaire_session_result_comorbidity",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "result_id",
            UUID,
            sa.ForeignKey("questionnaire_session_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coexistence_key", sa.String(length=120), nullable=False),
        sa.Column("domains_json", JSONB, nullable=False),
        sa.Column("combined_risk_score", sa.Float(), nullable=False),
        sa.Column("coexistence_level", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_questionnaire_session_result_comorbidity_session_id",
        "questionnaire_session_result_comorbidity",
        ["session_id"],
    )

    op.create_table(
        "questionnaire_session_pdf_exports",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="generated"),
        sa.Column("generated_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_questionnaire_session_pdf_exports_session_id",
        "questionnaire_session_pdf_exports",
        ["session_id"],
    )

    op.create_table(
        "questionnaire_tags",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#5B6C7D"),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_questionnaire_tag_owner_name"),
    )
    op.create_index("ix_questionnaire_tags_owner_user_id", "questionnaire_tags", ["owner_user_id"])

    op.create_table(
        "questionnaire_session_tags",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag_id", UUID, sa.ForeignKey("questionnaire_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "tag_id", "assigned_by_user_id", name="uq_questionnaire_session_tag"),
    )

    op.create_table(
        "questionnaire_access_grants",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("grantee_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("grant_type", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_tag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_download_pdf", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "grantee_user_id", name="uq_questionnaire_access_grantee"),
    )
    op.create_index("ix_questionnaire_access_grants_session_id", "questionnaire_access_grants", ["session_id"])
    op.create_index(
        "ix_questionnaire_access_grants_grantee_user_id",
        "questionnaire_access_grants",
        ["grantee_user_id"],
    )

    op.create_table(
        "questionnaire_share_codes",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("code_hint", sa.String(length=16), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_questionnaire_share_codes_session_id", "questionnaire_share_codes", ["session_id"])

    op.create_table(
        "questionnaire_session_access_links",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_type", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column(
            "share_code_id",
            UUID,
            sa.ForeignKey("questionnaire_share_codes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "access_grant_id",
            UUID,
            sa.ForeignKey("questionnaire_access_grants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_questionnaire_session_access_links_session_id",
        "questionnaire_session_access_links",
        ["session_id"],
    )

    op.create_table(
        "dashboard_aggregates",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("aggregate_key", sa.String(length=120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_json", JSONB, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("aggregate_key", "period_start", "period_end", name="uq_dashboard_aggregate_period"),
    )
    op.create_index("ix_dashboard_aggregates_aggregate_key", "dashboard_aggregates", ["aggregate_key"])

    op.create_table(
        "report_jobs",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(length=120), nullable=False),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("params_json", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_report_jobs_job_type", "report_jobs", ["job_type"])

    op.create_table(
        "generated_reports",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("report_job_id", UUID, sa.ForeignKey("report_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_type", sa.String(length=120), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_format", sa.String(length=40), nullable=False, server_default="pdf"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "service_health_snapshots",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("api_uptime_seconds", sa.Float(), nullable=True),
        sa.Column("requests_total", sa.Integer(), nullable=True),
        sa.Column("error_rate", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("db_ready", sa.Boolean(), nullable=True),
        sa.Column("queue_depth", sa.Integer(), nullable=True),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_service_health_snapshots_snapshot_at", "service_health_snapshots", ["snapshot_at"])

    op.create_table(
        "model_monitoring_snapshots",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("mode_key", sa.String(length=64), nullable=False),
        sa.Column("samples_count", sa.Integer(), nullable=True),
        sa.Column("mean_probability", sa.Float(), nullable=True),
        sa.Column("alert_rate", sa.Float(), nullable=True),
        sa.Column("drift_score", sa.Float(), nullable=True),
        sa.Column("calibration_error", sa.Float(), nullable=True),
        sa.Column("equity_gap", sa.Float(), nullable=True),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_monitoring_snapshots_snapshot_at", "model_monitoring_snapshots", ["snapshot_at"])
    op.create_index("ix_model_monitoring_snapshots_domain", "model_monitoring_snapshots", ["domain"])
    op.create_index("ix_model_monitoring_snapshots_mode_key", "model_monitoring_snapshots", ["mode_key"])

    op.create_table(
        "questionnaire_audit_events",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("questionnaire_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_questionnaire_audit_events_event_type", "questionnaire_audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_questionnaire_audit_events_event_type", table_name="questionnaire_audit_events")
    op.drop_table("questionnaire_audit_events")

    op.drop_index("ix_model_monitoring_snapshots_mode_key", table_name="model_monitoring_snapshots")
    op.drop_index("ix_model_monitoring_snapshots_domain", table_name="model_monitoring_snapshots")
    op.drop_index("ix_model_monitoring_snapshots_snapshot_at", table_name="model_monitoring_snapshots")
    op.drop_table("model_monitoring_snapshots")

    op.drop_index("ix_service_health_snapshots_snapshot_at", table_name="service_health_snapshots")
    op.drop_table("service_health_snapshots")

    op.drop_table("generated_reports")

    op.drop_index("ix_report_jobs_job_type", table_name="report_jobs")
    op.drop_table("report_jobs")

    op.drop_index("ix_dashboard_aggregates_aggregate_key", table_name="dashboard_aggregates")
    op.drop_table("dashboard_aggregates")

    op.drop_index("ix_questionnaire_session_access_links_session_id", table_name="questionnaire_session_access_links")
    op.drop_table("questionnaire_session_access_links")

    op.drop_index("ix_questionnaire_share_codes_session_id", table_name="questionnaire_share_codes")
    op.drop_table("questionnaire_share_codes")

    op.drop_index("ix_questionnaire_access_grants_grantee_user_id", table_name="questionnaire_access_grants")
    op.drop_index("ix_questionnaire_access_grants_session_id", table_name="questionnaire_access_grants")
    op.drop_table("questionnaire_access_grants")

    op.drop_table("questionnaire_session_tags")

    op.drop_index("ix_questionnaire_tags_owner_user_id", table_name="questionnaire_tags")
    op.drop_table("questionnaire_tags")

    op.drop_index("ix_questionnaire_session_pdf_exports_session_id", table_name="questionnaire_session_pdf_exports")
    op.drop_table("questionnaire_session_pdf_exports")

    op.drop_index(
        "ix_questionnaire_session_result_comorbidity_session_id",
        table_name="questionnaire_session_result_comorbidity",
    )
    op.drop_table("questionnaire_session_result_comorbidity")

    op.drop_index(
        "ix_questionnaire_session_result_domains_domain",
        table_name="questionnaire_session_result_domains",
    )
    op.drop_index(
        "ix_questionnaire_session_result_domains_session_id",
        table_name="questionnaire_session_result_domains",
    )
    op.drop_table("questionnaire_session_result_domains")

    op.drop_table("questionnaire_session_results")

    op.drop_index(
        "ix_questionnaire_session_internal_features_session_id",
        table_name="questionnaire_session_internal_features",
    )
    op.drop_table("questionnaire_session_internal_features")

    op.drop_index("ix_questionnaire_session_answers_session_id", table_name="questionnaire_session_answers")
    op.drop_table("questionnaire_session_answers")

    op.drop_index("ix_questionnaire_session_items_session_id", table_name="questionnaire_session_items")
    op.drop_table("questionnaire_session_items")

    op.drop_index("ix_questionnaire_sessions_version_id", table_name="questionnaire_sessions")
    op.drop_index("ix_questionnaire_sessions_status", table_name="questionnaire_sessions")
    op.drop_index("ix_questionnaire_sessions_owner_user_id", table_name="questionnaire_sessions")
    op.drop_index(
        "ix_questionnaire_sessions_questionnaire_public_id",
        table_name="questionnaire_sessions",
    )
    op.drop_table("questionnaire_sessions")

    op.drop_index("ix_model_operational_caveats_activation_id", table_name="model_operational_caveats")
    op.drop_table("model_operational_caveats")

    op.drop_index("ix_model_confidence_registry_activation_id", table_name="model_confidence_registry")
    op.drop_table("model_confidence_registry")

    op.drop_index("ix_model_artifact_registry_model_version_id", table_name="model_artifact_registry")
    op.drop_table("model_artifact_registry")

    op.drop_index("ix_model_metrics_snapshot_model_version_id", table_name="model_metrics_snapshot")
    op.drop_table("model_metrics_snapshot")

    op.drop_index("ix_model_mode_domain_activation_role", table_name="model_mode_domain_activation")
    op.drop_index("ix_model_mode_domain_activation_mode_key", table_name="model_mode_domain_activation")
    op.drop_index("ix_model_mode_domain_activation_domain", table_name="model_mode_domain_activation")
    op.drop_table("model_mode_domain_activation")

    op.drop_index("ix_model_versions_model_registry_id", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index("ix_model_registry_role", table_name="model_registry")
    op.drop_index("ix_model_registry_mode_key", table_name="model_registry")
    op.drop_index("ix_model_registry_domain", table_name="model_registry")
    op.drop_index("ix_model_registry_model_key", table_name="model_registry")
    op.drop_table("model_registry")

    op.drop_table("questionnaire_repeat_mapping")
    op.drop_table("questionnaire_internal_inputs")
    op.drop_table("questionnaire_question_modes")

    op.drop_index("ix_questionnaire_questions_feature_key", table_name="questionnaire_questions")
    op.drop_table("questionnaire_questions")

    op.drop_table("questionnaire_scale_options")
    op.drop_table("questionnaire_scales")
    op.drop_table("questionnaire_sections")
    op.drop_table("questionnaire_versions")

    op.drop_index("ix_questionnaire_definitions_slug", table_name="questionnaire_definitions")
    op.drop_table("questionnaire_definitions")
