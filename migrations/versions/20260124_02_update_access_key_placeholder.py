"""Update access_key_hash placeholder to an explicit reset-required prefix."""

from alembic import op
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = "20260124_02"
down_revision = "20260124_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only adjust legacy placeholders created during the backfill:
    # rows locked to infinity and flagged for reset.
    # Legacy rows have access_key_hash prefixed to avoid confusion with valid hashes.
    op.execute(
        """
        UPDATE evaluation
        SET access_key_hash = 'reset_required:' || md5(id::text)
        WHERE requires_access_key_reset = true
          AND access_key_locked_until = 'infinity'::timestamptz
          AND access_key_hash NOT LIKE 'reset_required:%';
        """
    )


def downgrade() -> None:
    # Restore previous placeholder to keep downgrade deterministic.
    op.execute(
        """
        UPDATE evaluation
        SET access_key_hash = substring(access_key_hash from '^reset_required:(.*)$')
        WHERE requires_access_key_reset = true
          AND access_key_locked_until = 'infinity'::timestamptz
          AND access_key_hash LIKE 'reset_required:%';
        """
    )
