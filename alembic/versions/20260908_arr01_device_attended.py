"""the visit that lifts a tablet's halt

ENG-624 recorded a halt on the device and gave it one exit: the tablet opening a session. So
the queue drained on the room's schedule, and the person who walked over, helped and left had
no way to say so. ``attended_at``/``attended_by`` are that visit.

``attended_lifted_since`` is the halt moment the visit lifted, and it is a column because the
fact cannot be recovered afterwards. ``needs_person_since`` is null once the mark lifts the
halt, so an undo with nothing to read from would have to stamp the halt *now* — and the queue
is ordered by that column, so the tablet would come back announcing a halt that never
happened, ahead of rooms that really did stop after it. It is the device-side twin of
``ir_sessions.lifted_halt``, which exists for the same reason and is argued at ``20260904_att01``.

Three columns and one table. ENG-792's other column lands on ``ir_sessions`` in the revision
after this one rather than here: the device migration tests build every table but ``devices``
from the model's own metadata and then run this chain over it, so a migration that also
touched a metadata-built table would meet its own column and stop the walk.

All three are nullable and none is backfilled. A visit nobody made must not be invented; null
is the true answer for every row that predates this.

Revision ID: 20260908_arr01
Revises: 20260904_att01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260908_arr01"
down_revision = "20260904_att01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("attended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("attended_by", sa.String(length=36), nullable=True))
    op.add_column(
        "devices", sa.Column("attended_lifted_since", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("devices", "attended_lifted_since")
    op.drop_column("devices", "attended_by")
    op.drop_column("devices", "attended_at")
