"""replace apps.platform string with platforms JSON array

Revision ID: 20260704_0001
Revises: 20260609_0001
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_0001"
down_revision: str | None = "20260609_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("apps", sa.Column("platforms", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE apps SET platforms = CAST(
            CASE
                WHEN platform = 'web' THEN '["web"]'
                WHEN platform = 'mobile' THEN '["android", "ios"]'
                WHEN platform = 'both' THEN '["web", "android", "ios"]'
                ELSE '["web"]'
            END AS json
        )
        """
    )
    op.alter_column("apps", "platforms", nullable=False)
    op.drop_column("apps", "platform")


def downgrade() -> None:
    op.add_column("apps", sa.Column("platform", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE apps SET platform = CASE
            WHEN platforms::jsonb = '["web"]'::jsonb THEN 'web'
            WHEN platforms::jsonb = '["android", "ios"]'::jsonb THEN 'mobile'
            WHEN platforms::jsonb = '["web", "android", "ios"]'::jsonb THEN 'both'
            ELSE 'web'
        END
        """
    )
    op.alter_column("apps", "platform", nullable=False, server_default="web")
    op.drop_column("apps", "platforms")
