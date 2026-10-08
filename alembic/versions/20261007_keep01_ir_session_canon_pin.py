"""the pin of the canon a session opened with, kept until its passage is approved

Every session stored before this keeps the canon the room serves when it lands, read from the
vendored pin at upgrade time rather than written here: it is the canon those sessions read
until now, so nobody hears a change, and a pin written here would go stale under a re-pin
merged first.

Revision ID: 20261007_keep01
Revises: 20261006_opcl01
"""

import re
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "20261007_keep01"
down_revision = "20261006_opcl01"
branch_labels = None
depends_on = None

VENDOR_PIN = (
    Path(__file__).resolve().parents[2]
    / "app/services/internalization_room/canon/vendor/VENDOR_PIN"
)


def upgrade() -> None:
    op.add_column("ir_sessions", sa.Column("canon_pin", sa.String(length=40), nullable=True))
    served = re.findall(r"^pin_commit:\s*(\S+)", VENDOR_PIN.read_text(encoding="utf-8"), re.M)
    op.execute(sa.text("UPDATE ir_sessions SET canon_pin = :pin").bindparams(pin=served[0]))


def downgrade() -> None:
    op.drop_column("ir_sessions", "canon_pin")
