"""a request's budget attachment takes a request link as its author

Revision ID: 20260930_rr13
Revises: 20260930_shema403
Create Date: 2026-09-30

FE-55 (OBT-542). Whoever fills a request by the Admin's link has no account (GATE-04 D4), and
``rr_attachments.uploaded_by`` is a ``NOT NULL`` FK to ``users``: the link's holder could not
attach the budget detail at all, and writing the issuing Admin's id would make the record say the
Admin sent a file the team sent. So the attachment takes a link as its author, the pair ``rr11``
gave the request's trail:

1. ``uploaded_by`` becomes nullable;
2. ``uploaded_by_link_id``, a nullable FK to ``rr_request_links``;
3. ``ck_rr_attachments_one_author``: exactly one of the two.

Every existing row has ``uploaded_by`` and no link, so the CHECK holds for all of them.

The downgrade refuses to run over a row a link uploaded, rather than deleting evidence to make the
column ``NOT NULL`` again.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_rr13"
down_revision: str | None = "20260930_shema403"
branch_labels = None
depends_on = None

TABLE = "rr_attachments"
CHECK = "ck_rr_attachments_one_author"


def upgrade() -> None:
    op.alter_column(TABLE, "uploaded_by", existing_type=sa.String(36), nullable=True)
    op.add_column(
        TABLE,
        sa.Column(
            "uploaded_by_link_id",
            sa.String(36),
            sa.ForeignKey("rr_request_links.id"),
            nullable=True,
        ),
    )
    op.create_check_constraint(CHECK, TABLE, "(uploaded_by IS NULL) <> (uploaded_by_link_id IS NULL)")


def downgrade() -> None:
    uploaded_by_links = (
        op.get_bind()
        .execute(sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE uploaded_by_link_id IS NOT NULL"))
        .scalar_one()
    )
    if uploaded_by_links:
        raise RuntimeError(
            f"{uploaded_by_links} attachments were uploaded by a request link; "
            "downgrading would have to erase them."
        )
    op.drop_constraint(CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "uploaded_by_link_id")
    op.alter_column(TABLE, "uploaded_by", existing_type=sa.String(36), nullable=False)
