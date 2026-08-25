"""Join the three lines the room's August work grew into.

Three heads, one per line the stack grew in parallel: the session line (`_0003`), the
prepared-pericope line (`_0004`) and the device-credential line (`devcred`). Alembic refuses
`upgrade head` with "Multiple head revisions" while they stand apart, so nothing composed
brings a database up at all — it fails before touching anything, which is why this was found
by a graph reading rather than by a broken deploy.

This adds no schema. It is a join and nothing else, so it has no `downgrade` body either:
undoing a join means going back to three heads, which is the state this exists to end.

**The parents are the whole of it.** Drop one and Alembic is content — one head, green
`upgrade head`, and a line silently never applied. `scripts/downgrade_targets.py` derives one
walk-back target per parent, so it needs no edit here; the test beside it is what refuses a
parent going missing.
"""

revision: str = "20260821_join3"
down_revision: tuple[str, str, str] = ("20260820_0003", "20260820_0004", "20260820_devcred")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
