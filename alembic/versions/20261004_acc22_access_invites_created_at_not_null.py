"""access_invites.created_at is NOT NULL, as the model has always said it was

The column was created with a ``server_default`` and no ``NOT NULL`` (``20260830_acc17``),
while the model declares ``Mapped[datetime]``. Nothing writes to this table outside the ORM,
so no row is known to be missing its stamp — but the mismatch is exactly what ``alembic
check`` exists to catch, and it is the one item the check reports once ``main`` is merged
into ``dev``: ``main``'s migrations job runs the check, ``dev``'s never did.

The backfill takes each row's own evidence before reaching for the clock: an invite existed
before it was accepted and before it was revoked, so the earlier of the two is a stamp no
later than the truth. ``now()`` is the last resort, and it is what the column's own default
would have written anyway. The same reasoning, in the same order, as ``20260910_seg02``.

The downgrade drops the NOT NULL and does not put the nulls back: what it undoes is the
constraint, and a backfilled stamp is a better record than the absence it replaced.

Revision ID: 20261004_acc22
Revises: 20261002_shema561
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_acc22"
down_revision = "20261002_shema561"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE access_invites SET created_at = COALESCE("
        " LEAST(accepted_at, revoked_at),"
        " now()"
        ") WHERE created_at IS NULL"
    )
    op.alter_column(
        "access_invites",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.func.now(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "access_invites",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.func.now(),
        nullable=True,
    )
