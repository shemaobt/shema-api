"""a warning stands in a column of its own, and needs_person means a blocking halt only

Revision ID: 20260929_warn01
Revises: 20260925_halt01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260929_warn01"
down_revision = "20260925_halt01"
branch_labels = None
depends_on = None

TABLE = "ir_sessions"
STANDING_WARNING = "status = 'needs_person' AND halt_kind = 'warning'"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("warned_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        f"UPDATE {TABLE} SET warned_at = updated_at, status = 'done'"  # noqa: S608 - no interpolated input
        f" WHERE {STANDING_WARNING} AND ended_at IS NOT NULL"
    )
    op.execute(
        f"UPDATE {TABLE} SET warned_at = updated_at, status = 'in_progress'"  # noqa: S608 - no interpolated input
        f" WHERE {STANDING_WARNING}"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE {TABLE} SET status = 'needs_person'"  # noqa: S608 - no interpolated input
        " WHERE warned_at IS NOT NULL AND attended_at IS NULL"
    )
    op.drop_column(TABLE, "warned_at")
