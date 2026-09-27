"""shema network: the one-year review and the exit link

Revision ID: 20260927_shema531
Revises: 20260917_0001
Create Date: 2026-09-27

The parent is `20260917_0001`, read with `uv run alembic heads` in this worktree on
27/sep/2026, immediately before this file was written — the measurement `docs/shema.md` §7.1
asks for. **This revision is numbered by its issue (OBT-531) and not by the next counter.**
Five migrations of the access batch are written on the same parent at the same time, and the
counter is exactly what collided once already (`shema02` → `shema07`); an issue number does
not repeat. The sibling on the same base (OBT-527) is merged first by the declared order, so
whoever merges second re-points `down_revision` at the head of the day — the pull request says
so where the person merging reads it.

Two changes, both answers of the client on 22/sep to `docs/shema.md` §10 item 8:

`shema_intercessors.reviewed_at` and `.last_sent_at` — a contact nobody has used in a year is
**reviewed**, and the year counts from the latest of `added_at`, `reviewed_at` and
`last_sent_at`. **Nothing backfills either.** An existing contact counts from `added_at`, which
is the truth: nobody has reviewed it and nothing was ever sent to it.

`shema_intercessor_exit_links` — how a person who cannot log in leaves the network. One row per
link minted, the digest and never the token, `ON DELETE CASCADE` from the person so leaving
takes every link with it. The shapes are `shema_intake_links`'s in `20260911_shema01`: a
column-level `unique=True` on `token_hash` and a named index on the foreign key, the same name
the model declares.

Written by hand like every revision in this directory (`docs/resource_requests.md` §8.1).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260927_shema531"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shema_intercessors",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shema_intercessors",
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "shema_intercessor_exit_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "intercessor_id",
            sa.String(36),
            sa.ForeignKey("shema_intercessors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_intercessor_exit_links_intercessor",
        "shema_intercessor_exit_links",
        ["intercessor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shema_intercessor_exit_links_intercessor", table_name="shema_intercessor_exit_links"
    )
    op.drop_table("shema_intercessor_exit_links")
    op.drop_column("shema_intercessors", "last_sent_at")
    op.drop_column("shema_intercessors", "reviewed_at")
