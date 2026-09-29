"""a request's edit trail takes a request link as its author

Revision ID: 20260929_rr11
Revises: 20260929_rr10
Create Date: 2026-09-29

BE-26 (OBT-537), third slice. Whoever fills a request by the Admin's link has no account
(GATE-04 D4), and ``rr_request_field_history.changed_by`` is a ``NOT NULL`` FK to ``users``:
writing the issuing Admin's id there would make the trail say the Admin typed what the team
typed. So the request's trail — and only it — takes a link as its author:

1. ``changed_by`` becomes nullable;
2. ``changed_by_link_id``, a nullable FK to ``rr_request_links``;
3. ``ck_rr_request_field_history_one_author``: exactly one of the two.

Every existing row has ``changed_by`` and no link, so the CHECK holds for all of them. The
append-only trigger refuses row updates and deletes, not DDL, so this revision runs under it.
The evaluation's trail is untouched: the mesa is always a person.

The downgrade refuses to run over a row a link wrote, rather than deleting evidence to make the
column ``NOT NULL`` again.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_rr11"
down_revision: str | None = "20260929_rr10"
branch_labels = None
depends_on = None

TABLE = "rr_request_field_history"
CHECK = "ck_rr_request_field_history_one_author"


def upgrade() -> None:
    op.alter_column(TABLE, "changed_by", existing_type=sa.String(36), nullable=True)
    op.add_column(
        TABLE,
        sa.Column(
            "changed_by_link_id",
            sa.String(36),
            sa.ForeignKey("rr_request_links.id"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        CHECK, TABLE, "(changed_by IS NULL) <> (changed_by_link_id IS NULL)"
    )


def downgrade() -> None:
    written_by_links = op.get_bind().execute(
        sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE changed_by_link_id IS NOT NULL")
    ).scalar_one()
    if written_by_links:
        raise RuntimeError(
            f"{written_by_links} trail rows were written by a request link; "
            "downgrading would have to erase them."
        )
    op.drop_constraint(CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "changed_by_link_id")
    op.alter_column(TABLE, "changed_by", existing_type=sa.String(36), nullable=False)
