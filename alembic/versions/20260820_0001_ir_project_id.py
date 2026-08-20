"""carry project_id on ir_sessions, ir_questions and ir_takes

ENG-440. The room's tables learn whose conversation it was. Until now a session was
anonymous: nothing in the data said which team held it, which is why the Desk cannot
filter by team and why five issues wait on this one.

**``ir_takes.team_id`` is renamed, not replaced.** It was nullable, indexed and never
written, and the rest of the schema says "project" for the same entity. Carrying two
vocabularies in one schema is how the next person loses an afternoon. "Team" stays the
Desk's word, in the UI and in the backlog. The downgrade renames it back rather than
dropping it, so nothing that was in the column can be lost by going backwards.

**Nothing is backfilled, and that is a finding rather than an omission.** The only
device-to-project link that exists is the credential ENG-443 issues. ``ir_questions.
device_id`` and ``ir_takes.device_id`` hold a string the room app mints for itself, which
matches no row in ``devices`` and never did, and ``ir_takes.team_id`` was never populated
by anything. So there is nothing to derive a project from for any existing row, and every
one of them stays null. Guessing would have been worse than null: a wrong owner on a
recording is harder to notice than a missing one.

**These columns will read null for a while, and that is expected.** The room app does not
send its device credential yet — that is ENG-454 — so sessions opened today are accepted
with no project, deliberately and consistently across all three tables. The issue itself
warns that indexed columns nothing writes are how a null column gets read as meaningful;
this is that risk, taken knowingly, because the alternative is refusing every session in
every room until the app side ships.

Not a foreign key, matching the column being renamed. The room tables carry ids across an
app boundary and have never constrained them; adding a constraint to rows that are all
null would be a separate decision with a separate migration.

Revision ID: 20260820_0001
Revises: 20260812_room07
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0001"
down_revision: str | None = "20260812_room07"
branch_labels = None
depends_on = None


ADDING = ("ir_sessions", "ir_questions")
RENAMING = "ir_takes"


def upgrade() -> None:
    for table in ADDING:
        op.add_column(table, sa.Column("project_id", sa.String(length=36), nullable=True))
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])

    op.drop_index("ix_ir_takes_team_id", table_name=RENAMING)
    op.alter_column(RENAMING, "team_id", new_column_name="project_id")
    op.create_index("ix_ir_takes_project_id", RENAMING, ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_ir_takes_project_id", table_name=RENAMING)
    op.alter_column(RENAMING, "project_id", new_column_name="team_id")
    op.create_index("ix_ir_takes_team_id", RENAMING, ["team_id"])

    for table in ADDING:
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "project_id")
