"""backfill project_phases so every phase belongs to every project

Revision ID: 20260715_0011
Revises: 20260713_0001
Create Date: 2026-07-15

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0011"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    missing = conn.execute(
        sa.text(
            """
            SELECT p.id AS project_id, ph.id AS phase_id
            FROM projects p
            CROSS JOIN phases ph
            WHERE NOT EXISTS (
                SELECT 1 FROM project_phases pp
                WHERE pp.project_id = p.id AND pp.phase_id = ph.id
            )
            """
        )
    ).fetchall()

    if not missing:
        return

    conn.execute(
        sa.text(
            "INSERT INTO project_phases (id, project_id, phase_id, status) "
            "VALUES (:id, :project_id, :phase_id, 'not_started')"
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "project_id": row.project_id,
                "phase_id": row.phase_id,
            }
            for row in missing
        ],
    )


def downgrade() -> None:
    pass
