"""dedupe oc_recordings duplicate (project_id, title) pairs before the unique index

ENG-735: a database restored from the production dump does not reach `alembic upgrade
head`. `20260601_0001` creates `uq_oc_recordings_project_title` assuming only
whitespace/case variants of a duplicate title could exist (the app-level check already
blocked exact repeats) — production held an exact duplicate anyway, and
`docker compose up` on a fresh restore fails with a `UniqueViolationError` at that
migration.

Same partial scope as the index: only rows where `split_from_id IS NULL AND
splitting_status <> 'archived_after_split'` collide, and a NULL title never collides
with anything. Within each colliding (project_id, title) group, the row with the
earliest `created_at` (ties broken by `id`) keeps its title; every other row is
renamed to `"{title} (dup {id})"`, which cannot collide with anything else because
`id` is a primary key.

Revision ID: 20260916_0001
Revises: 20260724_0002
Create Date: 2026-09-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_0001"
down_revision: str | None = "20260724_0002"
branch_labels: str | None = None
depends_on: str | None = None

_DEDUPE_SQL = """
    UPDATE oc_recordings
    SET title = title || ' (dup ' || id || ')'
    WHERE id IN (
        SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY project_id, title
                ORDER BY created_at, id
            ) AS rn
            FROM oc_recordings
            WHERE title IS NOT NULL
              AND split_from_id IS NULL
              AND splitting_status <> 'archived_after_split'
        ) ranked
        WHERE rn > 1
    )
"""


def upgrade() -> None:
    op.execute(sa.text(_DEDUPE_SQL))


def downgrade() -> None:
    # Irreversible: the original duplicate titles are not recoverable. No-op.
    pass
