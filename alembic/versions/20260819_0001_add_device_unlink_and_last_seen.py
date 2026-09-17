"""add the device unlink and last-seen columns

ENG-444. Unlinking a device takes it out of the Desk and revokes its credential, and this
is where both facts are kept.

``unlinked_at`` is the record, not the revocation. What stops an unlinked device
authenticating is that ``credential_hash`` is set to NULL in the same write: the lookup
that authenticates a device compares a hash for equality, and NULL never equals anything,
so a revoked row cannot match no matter what is presented. The timestamp exists so a
facilitator's list can leave the device out and an operator can still see the row.

The device keeps its ``project_id`` after unlinking, deliberately. The row is the only
place that records where a tablet was, there is no audit trail in this line of work yet,
and nulling the column would answer "which team was this?" with silence. Every read path
filters on ``unlinked_at IS NULL`` instead.

``last_seen_at`` is null until the device asks the API something. Nothing but
``GET /api/devices/me`` moves it, because that is the only request a device makes.

Adds two columns to the table ENG-437 created. Alters nothing else.

Revision ID: 20260819_0001
Revises: 20260818_0001
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0001"
down_revision: str | None = "20260818_0001"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE_NAME, sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE_NAME, "last_seen_at")
    op.drop_column(TABLE_NAME, "unlinked_at")
