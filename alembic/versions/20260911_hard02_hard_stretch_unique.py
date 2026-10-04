"""one mark per stretch, promised by the database

The room asked for a person once per hard stretch by reading the table before writing to it.
A read before a write is not a guarantee: two tellings of one stretch landing together both
find no mark and both write one, and the second halt clears ``attended_at``, ``attended_by``
and ``person_arrived_at`` — the record that a facilitator had already walked to the room.

The index carries no predicate, unlike the pair on ``ir_segments``. Those are partial because
a superseded stretch must not collide with the row that replaced it; a mark is never
superseded, so there is no row for a predicate to exclude. The same argument
``uq_ir_releases_version`` makes.

The columns keep the single-column indexes they already had: the queue reads the marks of many
sessions at once by ``session_id``, and this index answers that read only as a prefix.

PRE-DEPLOY AUDIT: run this first — it must return zero rows, or creating the index will fail.
The race this index closes is exactly what can have written such a pair, and the table has been
in production since ``20260910_hard01``:

    SELECT session_id, segment_id, count(*), array_agg(id)
    FROM ir_hard_stretches
    GROUP BY session_id, segment_id
    HAVING count(*) > 1;

A duplicated pair is resolved by keeping the row with the earliest ``crossed_at`` — the moment
the stretch actually crossed — and deleting the rest. Deliberately not done here: deleting rows
of a shared production database is a decision for a person, not a side effect of a deploy.

Revision ID: 20260911_hard02
Revises: 20260910_seg02
"""

from alembic import op

revision = "20260911_hard02"
down_revision = "20260910_seg02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_ir_hard_stretches_session_segment",
        "ir_hard_stretches",
        ["session_id", "segment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ir_hard_stretches_session_segment", table_name="ir_hard_stretches")
