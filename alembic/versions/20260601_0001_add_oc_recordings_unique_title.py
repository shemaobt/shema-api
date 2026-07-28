"""add partial unique index on oc_recordings (project_id, title)

Revision ID: 20260601_0001
Revises: 20260724_0002
Create Date: 2026-06-01 00:00:00.000000

Enforces per-project title uniqueness for user-created recordings (ENG-71),
matching the service-layer check in recording_service. Split-derived rows
(split_from_id IS NOT NULL) and archived split parents
(splitting_status = 'archived_after_split') are exempt; NULL titles may repeat
(Postgres treats NULLs as distinct in a unique index).

PRE-DEPLOY AUDIT: run this first — it must return zero rows, or creating the
index will fail. The previous silent dedup prevented exact duplicates, so only
whitespace/case variants can exist:

    SELECT project_id, btrim(title) AS norm, count(*), array_agg(id)
    FROM oc_recordings
    WHERE title IS NOT NULL AND btrim(title) <> ''
      AND split_from_id IS NULL
      AND splitting_status <> 'archived_after_split'
    GROUP BY project_id, btrim(title)
    HAVING count(*) > 1;
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_0001"
down_revision: str | None = "20260724_0002"
branch_labels: str | None = None
depends_on: str | None = None

_INDEX_NAME = "uq_oc_recordings_project_title"
_WHERE = "split_from_id IS NULL AND splitting_status <> 'archived_after_split'"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "oc_recordings",
        ["project_id", "title"],
        unique=True,
        postgresql_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="oc_recordings")
