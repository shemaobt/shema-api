"""the count of tellings on a stretch, and the table that keeps a hard stretch

The count was one integer per session inside the telling-back state, so three tellings spread
over three different stretches raised the same warning as three tellings of one — and starting the
telling-back over rewrote the state around it. It becomes a column on the stretch, carried onto
the row that supersedes it, so it counts what Marcia's ruling counts.

The crossing gets a table rather than a field beside the halt: the halt is transient and the
fact is not. No foreign keys, matching the room's other tables (ADR 0006).

The column is not nullable and every row that exists was told at least once, so it is
backfilled by its own server default rather than by a statement.

Revision ID: 20260910_hard01
Revises: 20260910_meet01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260910_hard01"
down_revision = "20260910_meet01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_segments",
        sa.Column("tellings", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "ir_hard_stretches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("tellings", sa.Integer(), nullable=False),
        sa.Column(
            "crossed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ir_hard_stretches_session_id", "ir_hard_stretches", ["session_id"])
    op.create_index("ix_ir_hard_stretches_segment_id", "ir_hard_stretches", ["segment_id"])


def downgrade() -> None:
    op.drop_index("ix_ir_hard_stretches_segment_id", table_name="ir_hard_stretches")
    op.drop_index("ix_ir_hard_stretches_session_id", table_name="ir_hard_stretches")
    op.drop_table("ir_hard_stretches")
    op.drop_column("ir_segments", "tellings")
