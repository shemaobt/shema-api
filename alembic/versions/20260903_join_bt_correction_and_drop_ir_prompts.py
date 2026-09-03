"""Join the branch's `BT_CORRECTION` prompt key line to `main`'s drop of `ir_prompts`.

Two heads, and they are two because `20260831_lang01` has two children. The branch went on
to `20260901_room09` — a new `IRPromptKey` member for the correction prompt — while `main`
went the other way, to `20260902_room09`, which drops the `ir_prompts` table and its seeding
path outright. Neither line knows the other exists, so bringing `main` in puts both at the
end of the graph with nothing after them.

This is the first branch, walking the reconciliation bottom-up, where both lines are
present — every branch above it inherits this join through the merge, rather than growing
a second copy of its own. A second copy in a branch further up would still leave Alembic
content (same revision id, same parents, so a clean merge either way), but it would mean
the join no longer *originates* at the one place both lines first met.

This adds no schema — a join and nothing else — so there is no `downgrade` body: undoing it
means going back to two heads, which is the state it exists to end.

**The parents are the whole of it**, and `tests/test_migration_graph.py` is what refuses one
going missing. Drop either and Alembic is content: one head, a green `upgrade head`, and a
whole line silently never applied.
"""

revision: str = "20260903_join5"
down_revision: tuple[str, str] = ("20260901_room09", "20260902_room09")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
