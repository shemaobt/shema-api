"""remember that the team already met the facilitator in the book panorama

Revision ID: 20260811_0001
Revises: 20260807_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260811_0001"
down_revision = "20260807_0001"
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
