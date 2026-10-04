"""ir_segments.created_at is NOT NULL, as the model has always said it was

The column was created with a ``server_default`` and no ``NOT NULL`` (``20260828_seg01``),
while the model declares ``Mapped[datetime]``. Nothing writes to this table outside the ORM,
so no row is known to be missing its stamp — but the mismatch is exactly what ``alembic
check`` exists to catch, and a column that says one thing in the schema and another in the
model is a defect waiting for the first insert that goes around the ORM.

The backfill takes each row's own evidence before reaching for the clock: a stretch that was
superseded existed before it was superseded, and a stretch cannot be older than the
conversation it was written in. ``CURRENT_TIMESTAMP`` is the last resort, and it is what
the column's own default would have written anyway.

The downgrade drops the NOT NULL and does not put the nulls back: what it undoes is the
constraint, and a backfilled stamp is a better record than the absence it replaced.

Revision ID: 20260910_seg02
Revises: 20260910_rel01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260910_seg02"
down_revision = "20260910_rel01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE ir_segments SET created_at = COALESCE("
        " superseded_at,"
        " (SELECT s.created_at FROM ir_sessions s WHERE s.id = ir_segments.session_id),"
        " now()"
        ") WHERE created_at IS NULL"
    )
    op.alter_column(
        "ir_segments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.func.now(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "ir_segments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.func.now(),
        nullable=True,
    )
