"""normalize legacy project_phase status values

Revision ID: 20260715_0002
Revises: 20260715_0001
Create Date: 2026-07-15

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260715_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE project_phases SET status = 'not_started' "
        "WHERE status NOT IN ('not_started', 'in_progress', 'completed', 'blocked')"
    )


def downgrade() -> None:
    pass
