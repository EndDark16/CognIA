"""Add evaluation access keys and subject guardian relations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260124_01"
down_revision = "20251215_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Evaluation access key fields (safe: add nullable first, then backfill, then NOT NULL).
    op.add_column("evaluation", sa.Column("registration_number", sa.Text(), nullable=True))
    op.add_column("evaluation", sa.Column("access_key_hash", sa.Text(), nullable=True))
    op.add_column(
        "evaluation",
        sa.Column(
            "access_key_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "evaluation",
        sa.Column("access_key_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evaluation",
        sa.Column(
            "access_key_failed_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "evaluation",
        sa.Column("access_key_locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evaluation",
        sa.Column(
            "requires_access_key_reset",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.execute(
        """
        UPDATE evaluation
        SET registration_number =
            'EV-' || to_char(COALESCE(created_at, now()), 'YYYYMMDD') || '-' ||
            substr(md5(id::text), 1, 8)
        WHERE registration_number IS NULL;
        """
    )

    # Existing rows cannot recover the plain access key. We mark them as locked
    # and requiring reset, and set a non-usable placeholder hash for NOT NULL.
    op.execute(
        """
        UPDATE evaluation
        SET access_key_hash = md5(id::text),
            access_key_locked_until = 'infinity'::timestamptz,
            requires_access_key_reset = true
        WHERE access_key_hash IS NULL;
        """
    )

    op.execute(
        """
        UPDATE evaluation
        SET access_key_created_at = COALESCE(access_key_created_at, now())
        WHERE access_key_created_at IS NULL;
        """
    )

    op.alter_column("evaluation", "registration_number", nullable=False)
    op.alter_column("evaluation", "access_key_hash", nullable=False)

    op.create_unique_constraint(
        "uq_evaluation_registration_number", "evaluation", ["registration_number"]
    )
    op.create_index(
        "idx_evaluation_requested_by_created_at",
        "evaluation",
        ["requested_by_user_id", "created_at"],
    )
    op.create_index(
        "idx_evaluation_subject_created_at",
        "evaluation",
        ["subject_id", "created_at"],
    )

    # subject_guardian table (updated_at managed by application, no trigger).
    op.create_table(
        "subject_guardian",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subject.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "relationship IN ('father','mother','guardian','tutor','other')",
            name="ck_subject_guardian_relationship",
        ),
    )

    op.create_index(
        "uq_subject_guardian_active",
        "subject_guardian",
        ["subject_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index("idx_subject_guardian_user", "subject_guardian", ["user_id"])
    op.create_index("idx_subject_guardian_subject", "subject_guardian", ["subject_id"])

    op.execute(
        "COMMENT ON COLUMN subject_guardian.updated_at IS "
        "'Managed by application (no trigger)'"
    )


def downgrade() -> None:
    op.drop_index("idx_subject_guardian_subject", table_name="subject_guardian")
    op.drop_index("idx_subject_guardian_user", table_name="subject_guardian")
    op.drop_index("uq_subject_guardian_active", table_name="subject_guardian")
    op.drop_table("subject_guardian")

    op.drop_index("idx_evaluation_subject_created_at", table_name="evaluation")
    op.drop_index("idx_evaluation_requested_by_created_at", table_name="evaluation")
    op.drop_constraint(
        "uq_evaluation_registration_number", "evaluation", type_="unique"
    )
    op.drop_column("evaluation", "requires_access_key_reset")
    op.drop_column("evaluation", "access_key_locked_until")
    op.drop_column("evaluation", "access_key_failed_attempts")
    op.drop_column("evaluation", "access_key_rotated_at")
    op.drop_column("evaluation", "access_key_created_at")
    op.drop_column("evaluation", "access_key_hash")
    op.drop_column("evaluation", "registration_number")
