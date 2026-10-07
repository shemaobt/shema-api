"""the pending object: the object name an unconfirmed upload of a recording was handed

No backfill: a recording stored before has no upload awaiting confirm-upload under a new
name, which is what a null says; confirm-upload falls back to the name it checked before.

Revision ID: 20261007_pend01
Revises: 20261007_keep01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_pend01"
down_revision = "20261007_keep01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oc_recordings", sa.Column("pending_blob_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("oc_recordings", "pending_blob_name")
