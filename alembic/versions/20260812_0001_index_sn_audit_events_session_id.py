"""index sn_audit_events.session_id

``sn_audit_events.session_id`` is ON DELETE SET NULL. Postgres enforces that with a trigger
that has to find every referencing row when a session goes, and with no index on the
referencing column it does so by sequential scan. This table is append-only and
platform-wide: it only grows, so the scan only gets slower.

That was tolerable while the only thing deleting a session was a rare admin project-delete.
ENG-414 put it behind a Dashboard button a facilitator presses, which is what makes the
index worth a migration on a database six production apps share.

The other index here serves the trail's one read (project, newest first). This one serves
no query at all — it exists for the referential-integrity check, which is why it is on
session_id alone.

Adds one index to one sn_* table. Nothing here alters or drops anything it did not create.

Revision ID: 20260812_0001
Revises: 20260808_0002
Create Date: 2026-08-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "20260812_0001"
down_revision: str | None = "20260808_0002"
branch_labels = None
depends_on = None


TABLE_NAME = "sn_audit_events"
INDEX_NAME = "ix_sn_audit_events_session_id"


def upgrade() -> None:
    op.create_index(INDEX_NAME, TABLE_NAME, ["session_id"])


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
