"""add image_url to projects table

Revision ID: 20260716_0002
Revises: 20260715_0001
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "image_url")
