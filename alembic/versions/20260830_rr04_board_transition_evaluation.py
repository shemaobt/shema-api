"""a decision's move names its evaluation: evaluation_id on rr_board_transitions

Revision ID: 20260830_rr04
Revises: 20260830_rr03
Create Date: 2026-08-30

The design's §4.4 named this column and handed BE-08 (OBT-457) the decision to add or to
refuse it. Added: GATE-02 D6 insists that a decision's move and a hand's drag are
different events, and once the two converge on the same transition path they land in the
same table — indistinguishable whenever no money moved, unless the decision-driven row
names the evaluation that caused it. A manual move carries NULL, which is the asymmetry
itself.

No ON DELETE action, like ``movement_id`` beside it: an evaluation that moved a card is
not unwound by disappearing, and a delete that would orphan the trail fails naming the
row that holds on. The downgrade drops the column — an installation rolling back loses
which transitions were decisions, and only that.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_rr04"
down_revision: str | None = "20260830_rr03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rr_board_transitions", sa.Column("evaluation_id", sa.String(36), nullable=True)
    )
    op.create_foreign_key(
        "fk_rr_board_transitions_evaluation_id",
        "rr_board_transitions",
        "rr_evaluations",
        ["evaluation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_rr_board_transitions_evaluation_id", "rr_board_transitions", type_="foreignkey"
    )
    op.drop_column("rr_board_transitions", "evaluation_id")
