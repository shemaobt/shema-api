"""bridge-language calibration and the comprehension evidence ledger

The room stops using the quality of a Portuguese retelling as a proxy for
understanding. `bridge_mode` records the working method the team chose orally at the
book panorama (never a proficiency label), and `comprehension` carries the append-only
evidence ledger, the persisted active probe, mother-tongue practice, recovery
bookkeeping, and the recording-consent record — everything the readiness rule reads.

Also registers the non-speaking Comprehension Evidence Assessor prompt key.

Revision ID: 20260819_room08
Revises: 20260812_room07
"""

import sqlalchemy as sa

from alembic import op

revision = "20260819_room08"
down_revision = "20260812_room07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column(
            "bridge_mode",
            sa.String(length=24),
            nullable=False,
            server_default="calibration_pending",
        ),
    )
    op.add_column(
        "ir_sessions",
        sa.Column("comprehension", sa.JSON(), nullable=False, server_default="{}"),
    )
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE ir_prompt_key_enum ADD VALUE IF NOT EXISTS 'comprehension_assessor'"
            )


def downgrade() -> None:
    op.drop_column("ir_sessions", "comprehension")
    op.drop_column("ir_sessions", "bridge_mode")
