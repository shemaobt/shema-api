"""ir_takes says whether a take's recording time is its own (ENG-1760)

A stored take has its own **Recording time** when the tablet sent one, which is every row whose
`recorded_at` differs from its arrival, and when it is a joined part (its `origin`) or a spliced
one (named as `take_id` by a sentence laid into its session), whose time is the server's by
ADR 0072. Every other row was stamped with its arrival in place of one — sent with no time, or
stored before ENG-1273 — and stays false, so it keeps the pass order it was read in until now.

Revision ID: 20261022_known01
Revises: 20261021_opfor01
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "20261022_known01"
down_revision = "20261021_opfor01"
branch_labels = None
depends_on = None

TAKES = sa.table(
    "ir_takes",
    sa.column("id", sa.String),
    sa.column("origin", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("recorded_at", sa.DateTime),
    sa.column("recorded_at_known", sa.Boolean),
)
SESSIONS = sa.table("ir_sessions", sa.column("back_translation", sa.JSON))


def _spliced_take_ids() -> set[str]:
    spliced: set[str] = set()
    for (state,) in op.get_bind().execute(sa.select(SESSIONS.c.back_translation)):
        told = json.loads(state) if isinstance(state, str) else state
        spliced |= {sentence["take_id"] for sentence in (told or {}).get("sentences", [])}
    return spliced


def upgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(
            sa.Column("recorded_at_known", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.execute(
        TAKES.update()
        .where(sa.or_(TAKES.c.origin.is_not(None), TAKES.c.recorded_at != TAKES.c.created_at))
        .values(recorded_at_known=sa.true())
    )
    spliced = _spliced_take_ids()
    if spliced:
        op.execute(
            TAKES.update().where(TAKES.c.id.in_(spliced)).values(recorded_at_known=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.drop_column("recorded_at_known")
