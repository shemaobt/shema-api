"""the prepared opening records which passage it was written for

ENG-450. The panorama writes and voices the next passage's first line while the team is
still hearing the panorama, and ``hand_over`` refuses to give that line to a session about
a different passage — because the line is written from one passage's meaning map and would
otherwise be spoken as another passage's own framing, to people who cannot read and have no
way to check.

That guard compared the opening's passage against ``DEFAULT_PERICOPE``, and it worked only
because one constant stood in both places. With the passage resolved per team the constant
is gone, and re-resolving at hand-over time is **not** an equivalent guard: if another
device of the same team closes the passage while the panorama is still playing, the
resolution moves, both sides agree on the new passage, and the line written from the old one
is waved through — the exact case the guard exists for.

So the passage is recorded beside the line it belongs to. Nullable, and null is refused
rather than trusted: every row written before this migration carries no passage, and the
cost of refusing is one session writing its own opening.

Numbered 0004 with 0003 skipped, and that is not a gap to tidy. ENG-451 opened first and
took ``20260820_0003`` on its own branch; two files declaring one revision id is not two
heads but a duplicate, which Alembic reports as a ``UserWarning`` while ``alembic heads``
still exits 0. Renumbering the later one leaves an ordinary two-headed junction for whoever
joins the lines, which is a thing this repository already knows how to close.

``down_revision`` stays at ``20260820_0002`` because ``20260820_0003`` does not exist on this
line — pointing at it here would fail on this branch to tidy a number.

Revision ID: 20260820_0004
Revises: 20260820_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0004"
down_revision: str | None = "20260820_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions", sa.Column("prepared_pericope", sa.String(length=120), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "prepared_pericope")
