"""add the advisory editor lease to sn_sessions

Two people in one session must not overwrite each other. The lease lives on the session
row rather than in a table of its own because null already means unheld: a separate lock
row would have to be upserted into existence on every acquire, and there is no upsert
that spells the same on Postgres and on the SQLite the tests run against. Nothing
backfills, and nothing sweeps lapsed leases — expiry is decided on read.

Alters only the sn_* table. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create.

Revision ID: 20260717_0001
Revises: 20260715_0001
Create Date: 2026-07-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_0001"
down_revision: str | None = "20260715_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sn_sessions",
        sa.Column("locked_by", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "sn_sessions",
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # SET NULL, never CASCADE: the holder is not the owner, and nothing clears a lapsed
    # lease, so this column goes on naming whoever last opened the session. Under CASCADE,
    # deleting that user would delete the session itself along with its state and
    # artifacts. Null is what a deleted holder should leave behind: unheld.
    op.create_foreign_key(
        "fk_sn_sessions_locked_by_users",
        "sn_sessions",
        "users",
        ["locked_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sn_sessions_locked_by_users", "sn_sessions", type_="foreignkey")
    op.drop_column("sn_sessions", "lock_expires_at")
    op.drop_column("sn_sessions", "locked_by")
