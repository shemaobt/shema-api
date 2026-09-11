"""a forced release says who forced it, when, and what was open; an approval says which tablet

A release is refused while the telling-back carries an open finding or a part of the
rehearsal is unheard, and only a facilitator forces one past those two. A force that left no
trace would be the failure Marcia named of the old one: an approval forced over a disputed
finding appeared only in the server log, so the draft reached Refine looking exactly like a
draft nobody had to force. The record belongs on the row the approval writes.

``forced_open_findings`` keeps the findings as the packet dumped them at that moment and not
a count or a pointer: the session goes on changing after the force, and a reader asking what
the facilitator overrode has to see what was on the table then.

``device_id`` is the other half, and it is about the team's approval rather than the force.
Every other write a tablet makes carries the device that made it; the approval was the one
that did not, so the only team act with a number on it was the one nobody could attribute.

All four are nullable, and on purpose: every release written before this deploy was a team
approval from a build that sent no device, and backfilling a device id or a forcing
facilitator onto them would be inventing the record this column exists to keep.

Revision ID: 20260911_rel02
Revises: 20260911_hard02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_rel02"
down_revision = "20260911_hard02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_releases", sa.Column("device_id", sa.String(length=64), nullable=True))
    op.add_column("ir_releases", sa.Column("forced_by", sa.String(length=36), nullable=True))
    op.add_column("ir_releases", sa.Column("forced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ir_releases", sa.Column("forced_open_findings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_releases", "forced_open_findings")
    op.drop_column("ir_releases", "forced_at")
    op.drop_column("ir_releases", "forced_by")
    op.drop_column("ir_releases", "device_id")
