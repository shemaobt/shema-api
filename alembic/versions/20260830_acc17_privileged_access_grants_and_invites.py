"""privileged access: who revoked a grant, and invites that predate their user

Two changes, one issue (OBT-477). The client's answer of 28/08 is asymmetric on
purpose — Admin and Gestor concede, only Admin revokes — and revocation without a
name is half an audit trail: ``user_app_roles`` already recorded who granted and
when, and when a grant was revoked, but not by whom. ``revoked_by`` closes that.

``access_invites`` is the link-shaped half. It is deliberately **not**
``project_invites``: that table is scoped to a project (``project_id NOT NULL``),
carries no token, no expiry and no revocation, and its service refuses an e-mail
with no active user — which is exactly the person a link invite exists for. This
table holds only the SHA-256 of the token, so a database read never yields a
working link; ``accepted_at`` makes it single-use; ``revoked_at``/``revoked_by``
make a pending invite recallable. The people columns are SET NULL so deleting an
account does not erase the audit line.

This database is shared with every Tripod app: nothing here alters what it did
not create, beyond the one nullable column on ``user_app_roles``.

Revision ID: 20260830_acc17
Revises: 20260828_seg01
Create Date: 2026-08-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_acc17"
down_revision: str | None = "20260828_seg01"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "user_app_roles",
        sa.Column(
            "revoked_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "access_invites",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(length=36),
            sa.ForeignKey("apps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(length=36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "accepted_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_access_invites_app_id", "access_invites", ["app_id"])
    op.create_index("ix_access_invites_role_id", "access_invites", ["role_id"])
    op.create_index("ix_access_invites_email", "access_invites", ["email"])
    op.create_index("ix_access_invites_token_hash", "access_invites", ["token_hash"], unique=True)
    op.create_index("ix_access_invites_expires_at", "access_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_access_invites_expires_at", table_name="access_invites")
    op.drop_index("ix_access_invites_token_hash", table_name="access_invites")
    op.drop_index("ix_access_invites_email", table_name="access_invites")
    op.drop_index("ix_access_invites_role_id", table_name="access_invites")
    op.drop_index("ix_access_invites_app_id", table_name="access_invites")
    op.drop_table("access_invites")
    op.drop_column("user_app_roles", "revoked_by")
