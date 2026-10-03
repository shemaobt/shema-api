"""shema_submissions: when and by whom a withdrawn prayer request left an archived Pulse

Revision ID: 20261002_shema561
Revises: 20261002_shema559
Create Date: 2026-10-02

OBT-561, the residue of the INT-12 privacy pass. Withdrawing the authorization of a prayer
request already erased it from every copy the module keeps but one: the Pulso Mensal archived as
it arrived (``shema_submissions.archived_payload``). Karina, via Daniel, 1/out/2026: *"o pedido
é apagado também do Pulso guardado"*. The service rewrites the archive; these two nullable
columns are the trace the removal leaves — who and when, never the text.

The parent is ``20261002_shema559``, read with ``uv run alembic heads`` in this worktree on
2/out/2026 immediately before this file was written. Written by hand and importing nothing from
``app.``, like the other revisions.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_shema561"
down_revision: str | None = "20261002_shema559"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shema_submissions",
        sa.Column("prayer_request_erased_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shema_submissions",
        sa.Column(
            "prayer_request_erased_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("shema_submissions", "prayer_request_erased_by")
    op.drop_column("shema_submissions", "prayer_request_erased_at")
