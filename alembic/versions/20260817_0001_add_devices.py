"""add the devices table

ENG-437. A device becomes an entity the platform knows about: a row with a project, an
optional label, and the hash of the single-use code it displayed once at installation.

This migration adds one table and does nothing else. It alters no existing table, drops
nothing, and backfills nothing — in particular it does not touch the ``device_id`` values
that ``ir_questions`` and ``ir_takes`` carry, which are self-issued by the room app and
remain meaningless strings until a later slice gives them meaning. Those tables are not
on ``main`` at the time of writing, so nothing here could name them even by accident.

``projects.id`` is referenced ON DELETE SET NULL rather than CASCADE: deleting a project
should orphan its tablets, not delete the rows that say those tablets exist. A device
with no project is a normal state — it is the state every device is in between
installation and being claimed.

The claim code itself is not stored. ``claim_code_hash`` is a SHA-256, unique so that two
concurrent mints cannot land on the same code; the uniqueness is enforced here rather
than left to the service, because a retry loop alone loses the race.

Revision ID: 20260817_0001
Revises: 20260812_0001
Create Date: 2026-08-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_0001"
down_revision: str | None = "20260812_0001"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("claim_code_hash", sa.String(length=64), nullable=False),
        sa.Column("claim_code_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{TABLE_NAME}_project_id", TABLE_NAME, ["project_id"])
    op.create_index(
        f"ix_{TABLE_NAME}_claim_code_hash", TABLE_NAME, ["claim_code_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE_NAME}_claim_code_hash", table_name=TABLE_NAME)
    op.drop_index(f"ix_{TABLE_NAME}_project_id", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
