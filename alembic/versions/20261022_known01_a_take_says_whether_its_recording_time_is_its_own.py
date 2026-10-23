"""ir_takes says whether a take's recording time is its own (ENG-1760)

A stored take has its own **Recording time** when the tablet sent one, which is every row whose
`recorded_at` differs from its arrival, and when it is a joined part (its `origin`), whose time
is the server's by ADR 0072. Both are read off the row and need no mark. A spliced part (named as
`take_id` by a sentence laid into its session) has one exactly when the part it was laid into
has one, which the row cannot show: the mark is set for those, read in the order the sentences
were laid. Every other row stays false.

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


def _laid_in_sentences() -> list[tuple[str, str]]:
    laid: list[tuple[str, str]] = []
    for (state,) in op.get_bind().execute(sa.select(SESSIONS.c.back_translation)):
        told = json.loads(state) if isinstance(state, str) else state
        laid += [
            (sentence["previous_take_id"], sentence["take_id"])
            for sentence in (told or {}).get("sentences", [])
        ]
    return laid


def _spliced_into_a_known_part(laid: list[tuple[str, str]]) -> set[str]:
    bases = {previous for previous, _ in laid}
    known = set(
        op.get_bind()
        .execute(
            sa.select(TAKES.c.id).where(
                TAKES.c.id.in_(bases),
                sa.or_(TAKES.c.origin.is_not(None), TAKES.c.recorded_at != TAKES.c.created_at),
            )
        )
        .scalars()
    )
    spliced: set[str] = set()
    for previous, take_id in laid:
        if previous in known or previous in spliced:
            spliced.add(take_id)
    return spliced


def upgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(
            sa.Column("recorded_at_known", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    laid = _laid_in_sentences()
    spliced = _spliced_into_a_known_part(laid) if laid else set()
    if spliced:
        op.execute(
            TAKES.update().where(TAKES.c.id.in_(spliced)).values(recorded_at_known=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.drop_column("recorded_at_known")
