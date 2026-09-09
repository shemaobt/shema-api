"""Join the line the `resource_requests` module grew to the line `dev` grew.

Two heads, and they are two because the two lines never met. The module's own chain runs from
BE-02's tables out to `20260830_acc17`, BE-17's grants and invites; `dev` went the other way,
through the Internalization Room's August and September work out to `20260908_arr02`. Neither
line knows the other exists, so bringing `dev` into this branch puts both at the end of the
graph with nothing after them.

Alembic refuses `upgrade head` while they stand apart. That is the whole cost and it is
enough: a graph left forked is a deploy that fails at the first `alembic upgrade head`
against the shared database, and `docs/ci.md` says so in advance — red on the Migrations job
of an integration branch means a merge revision is owed. This is that revision.

This adds no schema — a join and nothing else — so there is no `downgrade` body: undoing it
means going back to two heads, which is the state it exists to end.

**The parents are the whole of it**, and `tests/test_migration_graph.py` is what refuses one
going missing. Drop either and Alembic is content: one head, a green `upgrade head`, and a
whole line silently never applied. That failure is invisible to the suite, which builds its
tables directly and never walks the graph.
"""

revision: str = "20260909_join5"
down_revision: tuple[str, str] = ("20260830_acc17", "20260908_arr02")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
