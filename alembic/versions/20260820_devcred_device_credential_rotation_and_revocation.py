"""add the columns rotation and legible revocation need

ENG-448. Two columns, and they exist for opposite reasons — one holds a hash that still
authenticates, the other holds a hash that never will again.

``previous_credential_hash`` is the overlap a rotation needs. The room has no reliable
network, which is why ``credential.py`` gives the credential no expiry at all; under the
same argument a rotation cannot retire the old credential the moment the new one is
issued, because the response carrying the new one is exactly what a bad network loses. So
both authenticate until the new one is *used*, and that first use clears this column. The
window closes on evidence that the tablet received the answer, never on a clock.

``revoked_credential_hash`` is the opposite, and it is deliberately never consulted by
the lookup that authenticates. ENG-444 revokes by setting ``credential_hash`` to NULL —
NULL equals nothing, so no string anyone presents can match, not even one recovered from
a backup — and that property is worth keeping exactly as it is. What it costs is that a
revoked credential becomes indistinguishable from one that was never issued, and those are
two different things for a tablet to do about it: forget yourself and show a claim code,
versus you have a bug. So the hash is copied here on the way out, read only after
authentication has already failed, and only to choose which refusal to answer with.

Both are nullable, both start NULL on every existing row, and neither has a unique index:
two devices can hold no previous credential at once, and ``credential_hash`` remains the
only column uniqueness is asserted on.

**The id is a word rather than the next number, for the reason
``20260820_qcomp`` states.** This revision was ``20260820_0003`` and so was
``20260820_0003_ir_session_ended_at`` on another branch — the same collision one level
down, and the same silent outcome: git merges two files with one id cleanly, Alembic picks
one, and the other never runs.

Revision ID: 20260820_devcred
Revises: 20260820_0002
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_devcred"
down_revision: str | None = "20260820_qcomp"
branch_labels = None
depends_on = None


TABLE_NAME = "devices"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME, sa.Column("previous_credential_hash", sa.String(length=64), nullable=True)
    )
    op.add_column(
        TABLE_NAME, sa.Column("revoked_credential_hash", sa.String(length=64), nullable=True)
    )
    op.create_index(
        "ix_devices_previous_credential_hash", TABLE_NAME, ["previous_credential_hash"]
    )
    op.create_index("ix_devices_revoked_credential_hash", TABLE_NAME, ["revoked_credential_hash"])


def downgrade() -> None:
    op.drop_index("ix_devices_revoked_credential_hash", table_name=TABLE_NAME)
    op.drop_index("ix_devices_previous_credential_hash", table_name=TABLE_NAME)
    op.drop_column(TABLE_NAME, "revoked_credential_hash")
    op.drop_column(TABLE_NAME, "previous_credential_hash")
