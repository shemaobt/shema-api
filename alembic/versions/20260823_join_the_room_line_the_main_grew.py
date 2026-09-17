"""Join the line the room grew on `main` to the line the integration branch grew.

Two heads, and they are two because `20260812_room07` has two children. The room's August
work on `main` went on to `20260819_room08` — bridge calibration and comprehension — while
the integration branch went the other way, through `20260820_merge` and on to
`20260821_join3`. Neither line knows the other exists, so bringing `main` into the branch
puts both at the end of the graph with nothing after them.

Alembic refuses `upgrade head` while they stand apart, and the development container was
already changed to `upgrade heads` for exactly this window (ENG-563). That makes the boot
tolerant; it does not make the graph joined, and a graph left forked is a deploy that fails
at the first `alembic upgrade head` against the shared production database.

This adds no schema — a join and nothing else — so there is no `downgrade` body: undoing it
means going back to two heads, which is the state it exists to end.

**The parents are the whole of it**, and the test beside this file is what refuses one going
missing. Drop either and Alembic is content: one head, a green `upgrade head`, and a whole
line silently never applied. That failure is invisible to the suite, which builds its tables
directly and never walks the graph.
"""

revision: str = "20260823_join4"
down_revision: tuple[str, str] = ("20260821_join3", "20260819_room08")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
