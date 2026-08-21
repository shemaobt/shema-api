"""remember that the team already met the facilitator in the book panorama

Revision ID: 20260812_room02
Revises: 20260812_room01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260812_room02"
down_revision = "20260812_room01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column(
            "after_panorama",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "after_panorama")
