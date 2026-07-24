"""sn_sessions.audio_ref becomes a real foreign key

audio_ref is the only link from a bucket audio to the artifacts cut from it. It was a
bare String(255) that create_session copied from the request without checking, so a
session could name an audio nobody has: the row survives, the export happens, and the
one field saying where it came from is wrong. Nothing could trace those artifacts back,
and nothing would report the loss.

Three changes, in the order Postgres needs them:

1. Narrow to 128, matching sn_audio_refs.audio_id. A foreign key cannot point a wider
   column at a narrower one and mean it — 255 could hold a value the referenced column
   is unable to store. Guarded: the migration fails loudly if any existing value is
   longer, rather than truncating a reference into a different audio.
2. Index it. It is what a future "everything cut from this audio" query filters on, and
   the column had no index at all.
3. The foreign key itself, with NO ACTION on delete — not CASCADE. Removing an audio
   must FAIL while a session points at it; the alternative is destroying somebody's
   finished work to satisfy a delete they did not ask for. Deleting a PROJECT still
   works: projects cascades to sn_sessions and sn_audio_refs in the same statement, and
   NO ACTION is checked at statement end, so both rows go together. Verified against
   PostgreSQL 14, not assumed.

No backfill and no cleanup: nothing today writes a dangling audio_ref (the SPA only
offers ids from GET /projects/{id}/audios), so this migration makes an invariant explicit
rather than repairing one. If it fails on the widening or the constraint, that failure is
the finding — a session whose audio cannot be identified is not something a migration
should guess its way past.

Revision ID: 20260724_0002
Revises: 20260723_0001
Create Date: 2026-07-24 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260724_0002"
down_revision: str | None = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        too_long = bind.execute(
            sa.text("SELECT count(*) FROM sn_sessions WHERE length(audio_ref) > 128")
        ).scalar_one()
        if too_long:
            raise RuntimeError(
                f"{too_long} session(s) carry an audio_ref longer than 128 chars; "
                "narrowing would truncate a reference into a different audio. "
                "Resolve those rows before running this migration."
            )
        orphans = bind.execute(
            sa.text(
                "SELECT count(*) FROM sn_sessions s "
                "LEFT JOIN sn_audio_refs a ON a.audio_id = s.audio_ref "
                "WHERE a.audio_id IS NULL"
            )
        ).scalar_one()
        if orphans:
            raise RuntimeError(
                f"{orphans} session(s) reference an audio that does not exist. "
                "Each one is an export that cannot be traced to its audio — decide what "
                "they belong to before the foreign key is added."
            )

    op.alter_column(
        "sn_sessions",
        "audio_ref",
        existing_type=sa.String(length=255),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    op.create_index("ix_sn_sessions_audio_ref", "sn_sessions", ["audio_ref"])
    op.create_foreign_key(
        "sn_sessions_audio_ref_fkey",
        "sn_sessions",
        "sn_audio_refs",
        ["audio_ref"],
        ["audio_id"],
    )


def downgrade() -> None:
    op.drop_constraint("sn_sessions_audio_ref_fkey", "sn_sessions", type_="foreignkey")
    op.drop_index("ix_sn_sessions_audio_ref", table_name="sn_sessions")
    op.alter_column(
        "sn_sessions",
        "audio_ref",
        existing_type=sa.String(length=128),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
