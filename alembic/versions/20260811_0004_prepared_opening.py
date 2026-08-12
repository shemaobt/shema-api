"""hold the passage's first line, written while the team is still hearing the panorama

Revision ID: 20260811_0004
Revises: 20260811_0003

The opening is the one turn whose inputs are known before it is asked for: the team has not
spoken yet, so nothing in it depends on them. Writing it during the panorama spends time the
session was giving away anyway.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260811_0004"
down_revision = "20260811_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_sessions", sa.Column("prepared_speech", sa.Text(), nullable=True))
    op.add_column("ir_sessions", sa.Column("prepared_audio_key", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_sessions", "prepared_audio_key")
    op.drop_column("ir_sessions", "prepared_speech")
