"""annotation-studio: per-language membership + upload_status indexes

Adds ``as_language_members`` (scopes facilitators to specific languages) and
composite indexes on the recording/clip ``upload_status`` filters used by
readiness and export. Seeds memberships so every existing annotation-studio user
keeps access to every currently-active language (no lockout on deploy).

Revision ID: 20260608_0001
Revises: 20260603_0001
Create Date: 2026-06-08 12:00:00.000000
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0001"
down_revision: str | None = "20260603_0001"
branch_labels = None
depends_on = None

AS_APP_KEY = "annotation-studio"
_ACTIVE_DATA_TABLES = (
    "as_speakers",
    "as_tier_a_words",
    "as_tier_b_pairs",
    "as_tier_c_clips",
    "as_exports",
    "as_analysis_results",
)


def upgrade() -> None:
    op.create_table(
        "as_language_members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("granted_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language_id", "user_id", name="uq_as_language_member"),
    )
    op.create_index(
        op.f("ix_as_language_members_language_id"),
        "as_language_members",
        ["language_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_as_language_members_user_id"),
        "as_language_members",
        ["user_id"],
        unique=False,
    )

    # Composite indexes aligned with readiness/export filters (FK + upload_status).
    op.create_index(
        "ix_as_tier_a_recordings_word_status",
        "as_tier_a_recordings",
        ["word_id", "upload_status"],
        unique=False,
    )
    op.create_index(
        "ix_as_tier_b_recordings_pair_status",
        "as_tier_b_recordings",
        ["pair_id", "upload_status"],
        unique=False,
    )
    op.create_index(
        "ix_as_tier_c_clips_language_status",
        "as_tier_c_clips",
        ["language_id", "upload_status"],
        unique=False,
    )

    _seed_existing_members()


def _seed_existing_members() -> None:
    """Grant every current annotation-studio user access to every active language.

    Prevents a deploy from locking facilitators out of languages they were already
    working on. Admins bypass membership, so seeding them is harmless.
    """
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"),
        {"app_key": AS_APP_KEY},
    ).scalar()
    if app_id is None:
        return

    user_ids = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT DISTINCT user_id FROM user_app_roles "
                "WHERE app_id = :app_id AND revoked_at IS NULL"
            ),
            {"app_id": app_id},
        ).all()
    ]
    if not user_ids:
        return

    language_ids: set[str] = set()
    for table in _ACTIVE_DATA_TABLES:
        for row in bind.execute(sa.text(f"SELECT DISTINCT language_id FROM {table}")).all():
            if row[0] is not None:
                language_ids.add(row[0])
    if not language_ids:
        return

    insert = sa.text(
        "INSERT INTO as_language_members (id, language_id, user_id) "
        "VALUES (:id, :language_id, :user_id)"
    )
    for user_id in user_ids:
        for language_id in language_ids:
            bind.execute(
                insert,
                {"id": str(uuid.uuid4()), "language_id": language_id, "user_id": user_id},
            )


def downgrade() -> None:
    op.drop_index("ix_as_tier_c_clips_language_status", table_name="as_tier_c_clips")
    op.drop_index("ix_as_tier_b_recordings_pair_status", table_name="as_tier_b_recordings")
    op.drop_index("ix_as_tier_a_recordings_word_status", table_name="as_tier_a_recordings")
    op.drop_index(op.f("ix_as_language_members_user_id"), table_name="as_language_members")
    op.drop_index(op.f("ix_as_language_members_language_id"), table_name="as_language_members")
    op.drop_table("as_language_members")
