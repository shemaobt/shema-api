"""the Admin's external request link, and a request that entered by one

Revision ID: 20260929_rr10
Revises: 20260929_rr09
Create Date: 2026-09-29

BE-26 (OBT-537), first slice: the schema the rest of the issue — and OBT-547's approval hook —
stand on. GATE-04 D1 and D4 (OBT-519): someone outside the PME asks through a link the Admin
issues, with no account until the mesa's approval registers the project.

1. ``rr_request_links`` — the link, its two digests (token and code), attempts, expiry,
   verification, revocation, the Admin who issued it and a free-text hint.
2. ``rr_requests.request_link_id`` and ``started_by_link_id``, nullable FKs to it.
3. ``uq_rr_requests_one_open_per_link`` — BE-25's one-open rule, with the link as the team.

Every existing row has neither column, so the index cannot collide. Written by hand and
importing nothing from ``app.``, like every rr revision.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_rr10"
down_revision: str | None = "20260929_rr09"
branch_labels = None
depends_on = None

OPEN = "submitted_at IS NULL AND cancelled_at IS NULL"


def upgrade() -> None:
    op.create_table(
        "rr_request_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("code_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("project_hint", sa.String(500), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_rr_request_links_email", "rr_request_links", ["email"])

    op.add_column(
        "rr_requests",
        sa.Column(
            "request_link_id",
            sa.String(36),
            sa.ForeignKey("rr_request_links.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "rr_requests",
        sa.Column(
            "started_by_link_id",
            sa.String(36),
            sa.ForeignKey("rr_request_links.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_rr_requests_request_link_id", "rr_requests", ["request_link_id"])
    op.create_index(
        "uq_rr_requests_one_open_per_link",
        "rr_requests",
        ["request_link_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
        sqlite_where=sa.text(OPEN),
    )


def downgrade() -> None:
    op.drop_index("uq_rr_requests_one_open_per_link", table_name="rr_requests")
    op.drop_index("ix_rr_requests_request_link_id", table_name="rr_requests")
    op.drop_column("rr_requests", "started_by_link_id")
    op.drop_column("rr_requests", "request_link_id")
    op.drop_index("ix_rr_request_links_email", table_name="rr_request_links")
    op.drop_table("rr_request_links")
