"""the language the room speaks to a team, carried on the session

The room's language was a deploy constant, so every team heard the language the server was
built with. It is now the tablet's, named once when the session opens and fixed for its
lifetime — a per-request choice would move the language under a team mid-passage.

``server_default`` is the floor, English, and not the Portuguese every existing row was
actually spoken in. Writing the old constant into old rows would make the floor depend on
when a row was written, which is the defect this whole change exists to remove; and a
session's language only decides turns it has not taken yet, while the app re-opens its
sessions on restart anyway.

Revision ID: 20260831_lang01
Revises: 20260828_seg01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_lang01"
down_revision = "20260828_seg01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "language")
