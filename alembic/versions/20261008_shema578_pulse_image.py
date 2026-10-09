"""the Pulso Mensal carries an image: where it lives before its import, and the trace of its erasure

Revision ID: 20261008_shema578
Revises: 20261007_shema572
Create Date: 2026-10-08

OBT-578 — Karina, via Daniel, 6/oct/2026: *"pulso mensal: acrescentar um campo para adicionar
imagem e uma descrição com um campo de autorização de uso de imagem."* The description and the
box are answers of the form and need no column; the image is bytes in the module's private
bucket, and ``shema_intake_images`` is the row that points at them from the moment a leader
uploads through the link until a coordinator's import mints the ``shema_media_items`` row that
every output path already consults (``app/db/models/shema_form.py``).

``shema_submissions`` gains the pair OBT-561 gave the prayer request, for the image: when the
coordination withdraws the authorization, the Pulse that carried the photo loses its reference,
its description and the leader's answer, and these two columns say who and when — never what.

The parent is `20261007_shema572`, read with `uv run alembic heads` in this worktree on
8/oct/2026, immediately before this file was written. Written by hand and importing nothing from
``app.``, like every revision here.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261008_shema578"
down_revision: str | None = "20261007_shema572"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_intake_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "intake_link_id",
            sa.String(36),
            sa.ForeignKey("shema_intake_links.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(300), nullable=True),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "submission_id",
            sa.String(36),
            sa.ForeignKey("shema_submissions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "media_item_id",
            sa.String(36),
            sa.ForeignKey("shema_media_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_shema_intake_images_link", "shema_intake_images", ["intake_link_id"])
    op.create_index("ix_shema_intake_images_submission", "shema_intake_images", ["submission_id"])
    op.create_index("ix_shema_intake_images_media_item", "shema_intake_images", ["media_item_id"])
    op.add_column(
        "shema_submissions",
        sa.Column("image_erased_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shema_submissions",
        sa.Column(
            "image_erased_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("shema_submissions", "image_erased_by")
    op.drop_column("shema_submissions", "image_erased_at")
    op.drop_index("ix_shema_intake_images_media_item", table_name="shema_intake_images")
    op.drop_index("ix_shema_intake_images_submission", table_name="shema_intake_images")
    op.drop_index("ix_shema_intake_images_link", table_name="shema_intake_images")
    op.drop_table("shema_intake_images")
