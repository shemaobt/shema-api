"""a closed passage the old code left in progress goes back to done

Revision ID: 20261001_done01
Revises: 20260930_idem01
"""

from alembic import op

revision = "20261001_done01"
down_revision = "20260930_idem01"
branch_labels = None
depends_on = None

TABLE = "ir_sessions"
CLOSED_IN_PROGRESS = "status = 'in_progress' AND ended_at IS NOT NULL"


def upgrade() -> None:
    op.execute(
        f"UPDATE {TABLE} SET status = 'done'"  # noqa: S608 - no interpolated input
        f" WHERE {CLOSED_IN_PROGRESS}"
    )


def downgrade() -> None:
    pass
