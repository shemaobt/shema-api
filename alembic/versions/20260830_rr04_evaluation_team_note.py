"""the mesa's message to the team: team_note on rr_evaluations

Revision ID: 20260830_rr04
Revises: 20260829_rr03
Create Date: 2026-08-30

The client's answer of 28/aug/2026 — *"caso tenha a necessidade de revisão a equipe recebe
um aviso"* — is a message from the mesa addressed to the team, written in Parte C under
``edit_evaluation``. It lands on the evaluation and not on the request because the team
does not start reading the evaluation; it starts reading a note addressed to it, served
through the status projection (BE-06, OBT-455) beside stage, submitted_at and the decision,
and through nothing else.

Nullable, with no server default: *no note was written* and *an empty note was written* are
different facts, the same distinction that keeps a score nullable one table down. The
downgrade drops the column — it carries mesa prose, and an installation rolling this back
is choosing to lose exactly that and nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_rr04"
down_revision: str | None = "20260829_rr03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rr_evaluations", sa.Column("team_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rr_evaluations", "team_note")
