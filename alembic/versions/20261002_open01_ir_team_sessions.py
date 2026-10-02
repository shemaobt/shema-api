"""the session a team's open door returns, one per team, pericope and language

Each key is backfilled with the latest session the team entered, and with the latest of any
kind only when it entered none. "Entered" is the rule of
`app/services/internalization_room/entered.py`, carried here in SQL because a migration does
not import the app: a non-empty `messages`, a take, or a halt ever asked for. The old door
minted a session on every relaunch that the tablet then left empty, so the newest row of a key
is often a launch nobody entered.

Revision ID: 20261002_open01
Revises: 20261001_done01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261002_open01"
down_revision = "20261001_done01"
branch_labels = None
depends_on = None

TABLE = "ir_team_sessions"
LATEST_OF_EACH_KEY = """
INSERT INTO ir_team_sessions (project_id, pericope, language, session_id)
SELECT project_id, pericope, language, id FROM (
    SELECT project_id, pericope, language, id, ROW_NUMBER() OVER (
        PARTITION BY project_id, pericope, language
        ORDER BY
            CASE WHEN json_array_length(messages) > 0
                OR EXISTS (SELECT 1 FROM ir_takes WHERE ir_takes.session_id = ir_sessions.id)
                OR halt_kind IS NOT NULL
                OR status = 'needs_person'
            THEN 1 ELSE 0 END DESC,
            updated_at DESC, created_at DESC, id DESC
    ) AS place
    FROM ir_sessions
    WHERE project_id IS NOT NULL
) AS ranked
WHERE place = 1
"""


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("project_id", sa.String(length=36), primary_key=True),
        sa.Column("pericope", sa.String(length=120), primary_key=True),
        sa.Column("language", sa.String(length=8), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
    )
    op.create_index("ix_ir_team_sessions_session_id", TABLE, ["session_id"])
    op.execute(LATEST_OF_EACH_KEY)


def downgrade() -> None:
    op.drop_index("ix_ir_team_sessions_session_id", table_name=TABLE)
    op.drop_table(TABLE)
