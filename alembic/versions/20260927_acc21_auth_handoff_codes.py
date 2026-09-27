"""handoff codes: a signed-in person carried from one app into another (BE-21)

One table, ``auth_handoff_codes``, for the one-minute, single-use code an app asks for so
another app can open signed in as the same person (OBT-527). It is a table of its own and not
a row in a generic token table, as every token purpose is since BE-20 (``docs/shema.md``
§6.7): the code points at a person and an app through real foreign keys, and the database can
check both.

Only the SHA-256 of the code is stored — the raw value leaves once, in the response that
created the row — so a database read never yields a code that opens anything. ``used_at`` is
the single spend. Both foreign keys cascade: a code is a session in transit, as a
``refresh_tokens`` row is, and a deleted account or app leaves nothing to carry anyone into.

No index on ``expires_at``: nothing reads by it. The two foreign-key indexes serve the
cascades, and the unique one on ``code_hash`` serves the exchange's lookup.

Revision ID: 20260927_acc21
Revises: 20260917_0001
Create Date: 2026-09-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_acc21"
down_revision: str | None = "20260917_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "auth_handoff_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "app_id",
            sa.String(length=36),
            sa.ForeignKey("apps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_handoff_codes_user_id", "auth_handoff_codes", ["user_id"])
    op.create_index("ix_auth_handoff_codes_app_id", "auth_handoff_codes", ["app_id"])
    op.create_index(
        "ix_auth_handoff_codes_code_hash", "auth_handoff_codes", ["code_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_auth_handoff_codes_code_hash", table_name="auth_handoff_codes")
    op.drop_index("ix_auth_handoff_codes_app_id", table_name="auth_handoff_codes")
    op.drop_index("ix_auth_handoff_codes_user_id", table_name="auth_handoff_codes")
    op.drop_table("auth_handoff_codes")
