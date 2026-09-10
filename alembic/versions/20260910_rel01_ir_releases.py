"""a team's approval is a numbered row, under a unique index

The packet was composed on demand and named by nothing, so a comment from Marcia's external
check had no draft to belong to. An approval writes a row here instead: one per approval per
pericope per project, numbered from one and never reused, carrying the packet as approved
beside its hash — the packet is composed from the session's current rows, so after a
re-record nothing else could give version 1 back.

The unique index carries no predicate, unlike the pair on ``ir_segments`` it copies. Those
are partial because a superseded stretch must not collide with the row that replaced it, and
a release is never superseded: there is no row for a predicate to exclude.

No foreign keys, matching every other table of the room.

Revision ID: 20260910_rel01
Revises: 20260910_hard01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260910_rel01"
down_revision = "20260910_hard01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("pericope", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("packet", sa.JSON(), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ir_releases_session_id", "ir_releases", ["session_id"])
    op.create_index(
        "uq_ir_releases_version",
        "ir_releases",
        ["project_id", "pericope", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ir_releases_version", table_name="ir_releases")
    op.drop_index("ix_ir_releases_session_id", table_name="ir_releases")
    op.drop_table("ir_releases")
