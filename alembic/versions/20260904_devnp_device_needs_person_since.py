"""record that a tablet needs a person, on the tablet rather than on a session

ENG-624. One nullable column, and the reason it is on `devices` and not on `ir_sessions`
is the case it exists for: a tablet whose session the server has forgotten, or whose build
broke before it opened one. There is nothing session-shaped to hang the halt off, and
`ir_sessions` has no device column — a placeholder session would be a row every consumer of
that table would have to learn to ignore.

Nullable, and NULL on every existing row. No tablet in the field has ever asked for a
person this way, which is true and is what NULL says.

The write that records the halt tests this column for NULL — ``UPDATE ... WHERE
needs_person_since IS NULL``, a row count of zero meaning the halt already stood — so that
a tablet retrying reports one halt rather than a fresh one per attempt. That guard is the
write and not a read for the reason ``20260903_devcoll`` states about its own: the suite
runs on SQLite, where ``SELECT ... FOR UPDATE`` is a no-op.

Downgrading drops the column, and with it any halt standing at that moment. That is
accepted: a room stopped for a person is a thing somebody walks over to, and the tablet
asks again on its next attempt.

Revision ID: 20260904_devnp
Revises: 20260903_devcoll
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_devnp"
down_revision: str | None = "20260903_devcoll"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"
COLUMN_NAME = "needs_person_since"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
