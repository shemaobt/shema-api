"""widen oc_acousteme_artifacts.audio_id to 128

Slugs minted from long story titles exceed 64 chars (the Terena "ruth" pilot
has one at 83), so ingestion failed on insert. Widen the id column; ingestion
also caps ids at 128 with a hash suffix so they always fit.

Revision ID: 20260713_0001
Revises: 20260709_0001
Create Date: 2026-07-13 18:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0001"
down_revision: str | None = "20260709_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "oc_acousteme_artifacts",
        "audio_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "oc_acousteme_artifacts",
        "audio_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
