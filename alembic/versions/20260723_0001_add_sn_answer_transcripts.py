"""add sn_answer_transcripts

One transcription (and English translation) draft per recorded voice answer. Advisory
only: nothing here is merged into an artifact by the API — a human confirms the draft in
the SPA first (PRD v2 §1.1, §12).

The rows double as the async job's state, which is why there is no job table: `pending` is
work to do, `ready` is work never to pay for twice, `failed` carries its own reason and
blocks nothing. No `running` value ships: a claimed-but-unfinished state outlives a crashed
worker as a row nothing will ever move again.

The key is the answer's and the foreign key is composite ON DELETE CASCADE, so deleting or
re-recording an answer takes its draft with it — the draft is a suggestion about a
recording, and it must not outlive the recording it describes.

Creates only the sn_* table and its enum type. This database is shared with every other
Tripod app, so nothing here alters or drops anything it did not create.

Revision ID: 20260723_0001
Revises: 20260717_0003
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0001"
down_revision: str | None = "20260717_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_answer_transcripts",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("resource_path", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "ready", "failed", name="sn_transcript_status_enum"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transcript_source", sa.Text(), nullable=True),
        sa.Column("translation_en", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
        # Composite, straight to the answer rather than to the session: the draft describes
        # one recording, so the recording's deletion is what must take it away.
        sa.ForeignKeyConstraint(
            ["session_id", "resource_path"],
            ["sn_voice_answers.session_id", "sn_voice_answers.resource_path"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", "resource_path"),
    )


def downgrade() -> None:
    op.drop_table("sn_answer_transcripts")

    # drop_table does not drop the TYPE create_table implicitly created, and leaving it
    # behind makes the next upgrade fail on a type that already exists.
    bind = op.get_bind()
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_transcript_status_enum"))
