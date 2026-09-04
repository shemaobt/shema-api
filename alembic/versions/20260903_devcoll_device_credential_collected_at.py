"""record the moment a tablet collected its credential, so it can only do it once

ENG-622. One nullable column, and it is not decoration beside ``credential_issued_at``:
issuing is something the server did, collecting is something a device came and took, and
only the second one has to be refused a second time.

The guard that makes the route exactly-once is a write, not a read — ``UPDATE ... WHERE
credential_collected_at IS NULL``, a row count of zero meaning another call won — for the
reason ``claim_device`` states about its own guard: the suite runs on SQLite, where
``SELECT ... FOR UPDATE`` is a no-op, so a lock would leave the race untested exactly
where the defect lives. That shape needs a column with a NULL to guard on, which is this
one.

Nullable, and NULL on every existing row. A tablet claimed before this migration has never
collected anything, which is true and is what NULL says. It keeps whatever credential the
Desk was handed until it collects, and collecting replaces it.

Revision ID: 20260903_devcoll
Revises: 20260902_room09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_devcoll"
down_revision: str | None = "20260902_room09"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"
COLUMN_NAME = "credential_collected_at"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
