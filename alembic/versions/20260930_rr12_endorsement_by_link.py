"""the base leader endorses by a link with a code, and has no account

Revision ID: 20260930_rr12
Revises: 20260929_rr11
Create Date: 2026-09-30

BE-23 (OBT-535). The 22/set meeting ended the Líder de Base's account (OBT-522): the team types
the leader's e-mail, and **at submission** the server mails that address a link tied to the
request and a six-digit code. Whoever confirms the code reads the request and endorses it.

1. ``rr_requests.leader_email`` — typed by the team in the draft, required to submit.
2. ``rr_endorsement_links`` — the link, its two digests, attempts, expiry, verification, use and
   revocation. ``uq_rr_endorsement_links_one_live`` keeps one live link per request: the resend
   revokes before it issues.
3. ``rr_requests.endorsed_email`` and ``endorsement_link_id`` — who endorsed, by which link.
   ``endorsed_by`` stays for the endorsements BE-16's accounts gave; nothing new writes it.
4. **Every live ``lider`` grant of this app is revoked** — ``revoked_at`` written, the row kept,
   exactly as ``20260928_rr08`` did to ``equipe``. That revision left ``lider`` standing for one
   reason, *"removing the role first would stop every endorsement"*, and this is the revision
   that makes the endorsement stop needing it. The role row stays: it is a key of the
   capability table the frontend emits, and leaves when FE-49 (OBT-517) re-emits it.

The two tables point at each other (a link belongs to a request; an endorsement names its
link), so the request's FK is added after the table exists. Every existing row gets an empty
``leader_email`` and no link. Written by hand and importing nothing from ``app.``, like every
rr revision.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_rr12"
down_revision: str | None = "20260929_rr11"
branch_labels = None
depends_on = None

LIVE = "used_at IS NULL AND revoked_at IS NULL"
APP_KEY = "resource-request-form"
LEADER_ROLE = "lider"
LINK_FK = "fk_rr_requests_endorsement_link"


def upgrade() -> None:
    op.add_column(
        "rr_requests",
        sa.Column("leader_email", sa.String(320), nullable=False, server_default=""),
    )
    op.create_table(
        "rr_endorsement_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("rr_requests.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("code_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_rr_endorsement_links_request_id", "rr_endorsement_links", ["request_id"]
    )
    op.create_index(
        "uq_rr_endorsement_links_one_live",
        "rr_endorsement_links",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
        sqlite_where=sa.text(LIVE),
    )
    op.add_column("rr_requests", sa.Column("endorsed_email", sa.String(320), nullable=True))
    op.add_column(
        "rr_requests", sa.Column("endorsement_link_id", sa.String(36), nullable=True)
    )
    op.create_foreign_key(
        LINK_FK, "rr_requests", "rr_endorsement_links", ["endorsement_link_id"], ["id"]
    )
    op.execute(
        sa.text(
            "UPDATE user_app_roles SET revoked_at = CURRENT_TIMESTAMP "
            "WHERE revoked_at IS NULL AND role_id IN ("
            "  SELECT roles.id FROM roles JOIN apps ON apps.id = roles.app_id "
            "  WHERE apps.app_key = :app_key AND roles.role_key = :role_key"
            ")"
        ).bindparams(app_key=APP_KEY, role_key=LEADER_ROLE)
    )


def downgrade() -> None:
    endorsed_by_link = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM rr_requests WHERE endorsement_link_id IS NOT NULL")
    ).scalar_one()
    if endorsed_by_link:
        raise RuntimeError(
            f"{endorsed_by_link} requests were endorsed by link; "
            "downgrading would have to erase who endorsed them."
        )
    # The revoked ``lider`` grants stay revoked: a downgrade does not hand an account back an
    # access nobody decided to give it again.
    op.drop_constraint(LINK_FK, "rr_requests", type_="foreignkey")
    op.drop_column("rr_requests", "endorsement_link_id")
    op.drop_column("rr_requests", "endorsed_email")
    op.drop_index("uq_rr_endorsement_links_one_live", table_name="rr_endorsement_links")
    op.drop_index("ix_rr_endorsement_links_request_id", table_name="rr_endorsement_links")
    op.drop_table("rr_endorsement_links")
    op.drop_column("rr_requests", "leader_email")
