"""add the device credential columns

ENG-443. Spending a claim code buys a long-lived credential, and this is where it is kept.

Only the SHA-256 is stored — the same primitive and the same column width the repository
already uses for refresh and password-reset tokens (``auth.RefreshToken.token_hash``). The
credential itself is returned once, in the response to the claim, and never again; nothing
in the schema can give it back.

Unique, because the hash is what a device is looked up by when it authenticates. Nullable,
because a device exists from installation and only earns a credential when a facilitator
claims it — an unclaimed device with no credential is the normal state, not a broken row.

Adds two columns and one index to the table ENG-437 created. Alters nothing else.

Revision ID: 20260818_0001
Revises: 20260817_0001
Create Date: 2026-08-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_0001"
down_revision: str | None = "20260817_0001"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"
INDEX_NAME = "ix_devices_credential_hash"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column("credential_hash", sa.String(length=64), nullable=True))
    op.add_column(
        TABLE_NAME,
        sa.Column("credential_issued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(INDEX_NAME, TABLE_NAME, ["credential_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.drop_column(TABLE_NAME, "credential_issued_at")
    op.drop_column(TABLE_NAME, "credential_hash")
