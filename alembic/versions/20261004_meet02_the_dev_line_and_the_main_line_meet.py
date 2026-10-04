"""the dev line and the main line meet

Revision ID: 20261004_meet02
Revises: 20261004_acc22, 20261002_open01
Create Date: 2026-10-04 18:15:15.039998

Two heads, and they are two because `dev` and `main` both grew from `20260908_arr02`, the last
head they shared. `dev` went on through resource requests, access grants and invites, journeys
and the Shemá module to `20261002_shema561` — and one step more, `20261004_acc22`, the
NOT NULL `main`'s `alembic check` asks of it; `main` went the other way, through the room's
releases, hard stretches, turns and idempotency keys to `20261002_open01`. Bringing `main` into
`dev` puts both at the end of the graph with nothing after them, and Alembic refuses
`upgrade head` while they stand apart.

It is a merge revision and not a re-point because both lines have already run against a shared
database: `dev`'s on staging at every push, `main`'s on production at every deploy. A database
standing at the tip of a re-pointed line would count the other line among its ancestors and
never run it. That is the day `docs/resource_requests.md` §8.3 reserved a merge revision for.

This adds no schema — a join and nothing else — so there is no `downgrade` body: undoing it
means going back to two heads, which is the state it exists to end.

**The parents are the whole of it**, and `tests/test_migration_graph.py` is what refuses one
going missing. Drop either and Alembic is content: one head, a green `upgrade head`, and a whole
line silently never applied. `scripts/downgrade_targets.py` derives one walk-back target per
parent, so the migrations job walks the newest migration of each line down and back up with no
edit there.
"""

revision: str = "20261004_meet02"
down_revision: tuple[str, str] = ("20261004_acc22", "20261002_open01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision joins lines, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo, for the same reason."""
