"""the dev line and the main line meet again

Revision ID: 20261022_meet03
Revises: 20261009_shema575, 20261022_swap01
Create Date: 2026-10-22 12:00:00.000000

Two heads, for the reason `20261004_meet02` had two: after it, `dev` and `main` grew apart
again. `dev` went on through five revisions of the PME and the Shemá module (the app URL,
the strategist's retirement, the Pulse image, the change log, the prayer release) to
`20261009_shema575`; `main` went through twenty-six, the room's (earlier passages, archives,
the canon pin, the demo team, scene rehearsals, retellings, takes, forced releases, the external
check and its outside listeners, grain switches) and two of the oral collector's, to
`20261022_swap01`. Bringing `main` into `dev` puts both at the end
of the graph with nothing after them, and Alembic refuses `upgrade head` while they stand
apart.

It is a merge revision and not a re-point for `meet02`'s reason: both lines have already run
against a shared database, `dev`'s on staging and `main`'s on production. A database standing
at the tip of a re-pointed line would count the other line among its ancestors and never run
it.

This adds no schema, so there is no `downgrade` body: undoing it means going back to two
heads, which is the state it exists to end.

**The parents are the whole of it**, and `tests/test_migration_graph.py` is what refuses one
going missing. `scripts/downgrade_targets.py` derives one walk-back target per parent, so the
migrations job walks the newest migration of each line down and back up with no edit there.
"""

revision: str = "20261022_meet03"
down_revision: tuple[str, str] = ("20261009_shema575", "20261022_swap01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
