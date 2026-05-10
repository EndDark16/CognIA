"""Add composite indexes for backend hot paths

Revision ID: 20260510_01
Revises: 20260415_01
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260510_01"
down_revision = "20260415_01"
branch_labels = None
depends_on = None


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _create_index_if_missing(
        "ix_qs_owner_created_at",
        "questionnaire_sessions",
        ["owner_user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_qs_owner_status_created_at",
        "questionnaire_sessions",
        ["owner_user_id", "status", "created_at"],
    )
    _create_index_if_missing(
        "ix_qsi_session_page_order",
        "questionnaire_session_items",
        ["session_id", "page_number", "display_order"],
    )
    _create_index_if_missing(
        "ix_qsrd_session_domain",
        "questionnaire_session_result_domains",
        ["session_id", "domain"],
    )
    _create_index_if_missing(
        "ix_qag_session_grantee_revoked_expires",
        "questionnaire_access_grants",
        ["session_id", "grantee_user_id", "revoked_at", "expires_at"],
    )
    _create_index_if_missing(
        "ix_qsc_session_active_expires",
        "questionnaire_share_codes",
        ["session_id", "is_active", "expires_at"],
    )
    _create_index_if_missing(
        "ix_problem_reports_reporter_created_at",
        "problem_reports",
        ["reporter_user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_problem_reports_status_created_at",
        "problem_reports",
        ["status", "created_at"],
    )


def downgrade() -> None:
    _drop_index_if_exists(
        "ix_problem_reports_status_created_at",
        "problem_reports",
    )
    _drop_index_if_exists(
        "ix_problem_reports_reporter_created_at",
        "problem_reports",
    )
    _drop_index_if_exists(
        "ix_qsc_session_active_expires",
        "questionnaire_share_codes",
    )
    _drop_index_if_exists(
        "ix_qag_session_grantee_revoked_expires",
        "questionnaire_access_grants",
    )
    _drop_index_if_exists(
        "ix_qsrd_session_domain",
        "questionnaire_session_result_domains",
    )
    _drop_index_if_exists(
        "ix_qsi_session_page_order",
        "questionnaire_session_items",
    )
    _drop_index_if_exists(
        "ix_qs_owner_status_created_at",
        "questionnaire_sessions",
    )
    _drop_index_if_exists(
        "ix_qs_owner_created_at",
        "questionnaire_sessions",
    )
