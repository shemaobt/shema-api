"""add sn_artifacts

The exported triple, held as opaque objects in GCS. This row is the pointer plus the
checksums that prove custody — the bytes are never in Postgres, because jsonb discards
key order and whitespace and the downstream pipeline diffs these files byte for byte.

Creates only the sn_* table and its enum type. This database is shared with every other
Tripod app, so nothing here alters or drops anything it did not create.

Revision ID: 20260714_0003
Revises: 20260714_0002
Create Date: 2026-07-14 15:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0003"
down_revision: str | None = "20260714_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_artifacts",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("manifest", "anchoring", "report", name="sn_artifact_kind_enum"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("crc32c", sa.String(length=16), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        # One artifact of each kind per session: re-completing a reopened session
        # replaces it rather than leaving the pipeline two manifests to choose between.
        sa.PrimaryKeyConstraint("session_id", "kind"),
    )


def downgrade() -> None:
    op.drop_table("sn_artifacts")

    bind = op.get_bind()
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_artifact_kind_enum"))
