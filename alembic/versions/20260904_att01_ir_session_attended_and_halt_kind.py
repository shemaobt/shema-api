"""the facilitator's visit, and which kind of halt it answered

``NEEDS_PERSON`` had one way out and it was the team's — a turn that lands. The halt a
facilitator actually resolves, by walking over, stayed standing until the team spoke.
``attended_at``/``attended_by`` are that visit; ``halt_kind`` is what it answered.

All three are nullable and none is backfilled. A visit nobody made must not be invented, and
a halt raised before this migration has no recorded kind — the read side answers ``blocking``
for a still-halted row with no kind, which is the conservative reading and belongs there
rather than in a write nobody could afterwards tell from a kind somebody recorded.

``halt_kind`` is a ``String(16)`` and not a Postgres enum, for the reason ``bridge_mode`` is
one: a database type is a second place the vocabulary lives, and an ``ALTER TYPE`` on both
sides every time it grows a value.

Revision ID: 20260904_att01
Revises: 20260904_devnp
"""

import sqlalchemy as sa

from alembic import op

revision = "20260904_att01"
down_revision = "20260904_devnp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_sessions", sa.Column("halt_kind", sa.String(length=16), nullable=True))
    op.add_column(
        "ir_sessions", sa.Column("attended_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("ir_sessions", sa.Column("attended_by", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_sessions", "attended_by")
    op.drop_column("ir_sessions", "attended_at")
    op.drop_column("ir_sessions", "halt_kind")
