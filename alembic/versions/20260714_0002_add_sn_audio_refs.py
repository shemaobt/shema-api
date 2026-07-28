"""add sn_audio_refs

Binds an audio to a project. Acousteme artifacts are standalone by design (no
project, no recording, a slug for an id), so this table is what a project gate can
stand on when the Sound Necklace lists a bucket.

Creates only the sn_* table. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create — in particular it does not
touch oc_acousteme_artifacts, whose decoupling from OC_Recording was deliberate.

Revision ID: 20260714_0002
Revises: 20260714_0001
Create Date: 2026-07-14 14:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0002"
down_revision: str | None = "20260714_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_audio_refs",
        # Mirrors oc_acousteme_artifacts.audio_id (String(128), widened for long story
        # slugs). Joined by convention, not by constraint: that table has no FKs.
        sa.Column("audio_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("consent_present", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("audio_id"),
    )
    op.create_index(
        op.f("ix_sn_audio_refs_project_id"), "sn_audio_refs", ["project_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sn_audio_refs_project_id"), table_name="sn_audio_refs")
    op.drop_table("sn_audio_refs")
