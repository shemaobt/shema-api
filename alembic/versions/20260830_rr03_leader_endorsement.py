"""the endorsement enters the system: who vouched for a request, and when

Revision ID: 20260830_rr03
Revises: 20260828_rr02
Create Date: 2026-08-30

GATE-02 D2 named the fourth role — the Líder de Base, who *"só assina/verifica o
projeto"* — and GATE-03 D2 made his signature an act in the system instead of a line
typed on paper. The act needs exactly two columns on ``rr_requests``: ``endorsed_by``
says who and ``endorsed_at`` says when, both stamped by the server in
``endorse_request.py`` (BE-16, OBT-476) — the same shape ``created_by``/``submitted_at``
already give the team's electronic acceptance (OBT-483). ``leader_name`` and
``leader_date`` already exist and become this act's display pair; no new column for them.

Both are nullable because unendorsed is the legitimate state of every request that ever
existed before this revision ran, and of every new one until its base's leader signs.
The FK carries no ``ondelete`` and therefore restricts, like ``created_by`` and the
ledger's author: a record of who vouched is worth nothing if the who can be forgotten
(GATE-02 D7). No index — nothing queries by endorser, and the blocking rule (a request
without ``endorsed_at`` leaves ``triagem`` only for ``recusado``, BE-08's to enforce)
reads the row it already holds.

Written by hand like the other revisions here, and importing nothing from ``app.``:
importing a model module executes ``app.core.database``, which builds an engine at import
time — the reasoning 20260731_0001 recorded and every rr revision repeats.

⚠️ One-head discipline (§9.3 of the branch notes): BE-14 creates a migration on this same
line. Whichever merges second re-parents its ``down_revision`` or writes the merge
revision — ``uv run alembic heads`` before opening the PR is the check.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260830_rr03"
down_revision = "20260828_rr02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rr_requests",
        sa.Column("endorsed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "rr_requests",
        sa.Column("endorsed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rr_requests", "endorsed_at")
    op.drop_column("rr_requests", "endorsed_by")
