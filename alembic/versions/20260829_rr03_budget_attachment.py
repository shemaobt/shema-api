"""rr_attachments: the budget file, private-bucket keys with a superseded history

Revision ID: 20260829_rr03
Revises: 20260828_rr02
Create Date: 2026-08-29

BE-14 (OBT-474). GATE-03 D3 made the budget attachment a real file; this table records
which file a request currently carries and every file it ever carried. A replacement
stamps ``superseded_at`` on the current row and inserts a new one — never a DELETE — and
the partial unique index is what turns *one file per request* into a rule about current
rows only. ``storage_key`` points into a private bucket and is content-addressed (the
sha256 is in the path); no URL is ever stored.

The parent is ``20260828_rr02``, the head this branch's base (BE-04) carries — re-read at
every merge of ``main``, not once at creation, as 20260825_rr01's own header records
having paid for twice. BE-16 creates a migration on this same line from this same parent;
whichever merges second re-parents or writes the merge revision (`uv run alembic heads`
before opening the PR is the check).

Written by hand like the other revisions: ``alembic/env.py`` has empty metadata and
``--autogenerate`` would drop every existing table (docs/resource_requests.md §8.1).
``postgresql_where`` alone carries the partial index here because migrations only ever
run on PostgreSQL (20260825_rr01 measured it: the graph cannot upgrade on SQLite at all);
the SQLite half of the same index lives on the model, where ``create_all`` builds the
test suite's schema.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260829_rr03"
down_revision = "20260828_rr02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rr_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(36),
            sa.ForeignKey("rr_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_rr_attachments_request_created", "rr_attachments", ["request_id", "created_at"]
    )
    op.create_index(
        "uq_rr_attachments_request_current",
        "rr_attachments",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_rr_attachments_request_current", table_name="rr_attachments")
    op.drop_index("ix_rr_attachments_request_created", table_name="rr_attachments")
    op.drop_table("rr_attachments")
