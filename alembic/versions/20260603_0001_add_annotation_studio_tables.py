"""add annotation-studio tables and seed app/roles

Revision ID: 20260603_0001
Revises: 20260519_0001
Create Date: 2026-06-03 12:00:00.000000
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "20260603_0001"
down_revision: str | None = "20260519_0001"
branch_labels = None
depends_on = None


AS_APP_KEY = "annotation-studio"
AS_APP_NAME = "Annotation Studio"
AS_APP_URL = "https://annotationstudio.shemaywam.com"
AS_APP_DESCRIPTION = (
    "Multi-language, gamified Tier A/B/C audio collection studio for the "
    "XEUS layer-wise experiment: repeated words, minimal pairs and free-sort "
    "clips, exported as the analysis-notebook CSV contract."
)
AS_ROLES = [
    ("admin", "Admin", "Full access: manage collection and exports."),
    ("facilitator", "Facilitator", "Default access role: collect audio and build exports."),
]


def upgrade() -> None:
    op.create_table(
        "as_speakers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language_id", "label", name="uq_as_speaker_lang_label"),
    )
    op.create_index(
        op.f("ix_as_speakers_language_id"), "as_speakers", ["language_id"], unique=False
    )

    op.create_table(
        "as_tier_a_words",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("gloss", sa.String(length=120), nullable=True),
        sa.Column("emblem", sa.String(length=40), nullable=True),
        sa.Column("reference_storage_key", sa.String(length=500), nullable=True),
        sa.Column("reference_status", sa.String(length=12), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language_id", "label", name="uq_as_tier_a_word"),
    )
    op.create_index(
        op.f("ix_as_tier_a_words_language_id"), "as_tier_a_words", ["language_id"], unique=False
    )

    op.create_table(
        "as_tier_a_recordings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("word_id", sa.String(length=36), nullable=False),
        sa.Column("speaker_id", sa.String(length=36), nullable=False),
        sa.Column("rep_index", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("export_filename", sa.String(length=200), nullable=False),
        sa.Column("upload_format", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("upload_status", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["word_id"], ["as_tier_a_words.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["as_speakers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word_id", "speaker_id", "rep_index", name="uq_as_tier_a_recording"),
    )
    op.create_index(
        op.f("ix_as_tier_a_recordings_word_id"), "as_tier_a_recordings", ["word_id"], unique=False
    )
    op.create_index(
        op.f("ix_as_tier_a_recordings_speaker_id"),
        "as_tier_a_recordings",
        ["speaker_id"],
        unique=False,
    )

    op.create_table(
        "as_tier_b_pairs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("pair_number", sa.Integer(), nullable=False),
        sa.Column("word_a_text", sa.String(length=120), nullable=True),
        sa.Column("word_b_text", sa.String(length=120), nullable=True),
        sa.Column("speaker_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["as_speakers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language_id", "pair_number", name="uq_as_tier_b_pair"),
    )
    op.create_index(
        op.f("ix_as_tier_b_pairs_language_id"), "as_tier_b_pairs", ["language_id"], unique=False
    )

    op.create_table(
        "as_tier_b_recordings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pair_id", sa.String(length=36), nullable=False),
        sa.Column("side", sa.String(length=1), nullable=False),
        sa.Column("rep_index", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("export_filename", sa.String(length=200), nullable=False),
        sa.Column("upload_format", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("upload_status", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["pair_id"], ["as_tier_b_pairs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair_id", "side", "rep_index", name="uq_as_tier_b_recording"),
    )
    op.create_index(
        op.f("ix_as_tier_b_recordings_pair_id"), "as_tier_b_recordings", ["pair_id"], unique=False
    )

    op.create_table(
        "as_tier_c_clips",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("clip_number", sa.Integer(), nullable=False),
        sa.Column("source_recording_id", sa.String(length=36), nullable=True),
        sa.Column("source_word_text", sa.String(length=120), nullable=True),
        sa.Column("position", sa.String(length=12), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("export_clip_id", sa.String(length=80), nullable=False),
        sa.Column("export_filename", sa.String(length=200), nullable=False),
        sa.Column("upload_format", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("upload_status", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language_id", "clip_number", name="uq_as_tier_c_clip"),
    )
    op.create_index(
        op.f("ix_as_tier_c_clips_language_id"), "as_tier_c_clips", ["language_id"], unique=False
    )

    op.create_table(
        "as_tier_c_sort_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clip_id", sa.String(length=36), nullable=False),
        sa.Column("dimension", sa.String(length=8), nullable=False),
        sa.Column("round", sa.String(length=12), nullable=False),
        sa.Column("group_label", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clip_id"], ["as_tier_c_clips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clip_id", "dimension", "round", name="uq_as_tier_c_sort"),
    )
    op.create_index(
        op.f("ix_as_tier_c_sort_assignments_clip_id"),
        "as_tier_c_sort_assignments",
        ["clip_id"],
        unique=False,
    )

    op.create_table(
        "as_exports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("bundle_key", sa.String(length=500), nullable=True),
        sa.Column("manifest_json", sa.Text(), nullable=True),
        sa.Column("tiers_included", sa.String(length=40), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_as_exports_language_id"), "as_exports", ["language_id"], unique=False
    )

    op.create_table(
        "as_analysis_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("export_id", sa.String(length=36), nullable=True),
        sa.Column("recommended_layer", sa.Integer(), nullable=True),
        sa.Column("tiers", sa.String(length=80), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("plot_keys_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_as_analysis_results_language_id"),
        "as_analysis_results",
        ["language_id"],
        unique=False,
    )

    # ── Seed the app registry row + its roles (idempotent) ──
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"),
        {"app_key": AS_APP_KEY},
    ).scalar()
    if app_id is None:
        app_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO apps (id, app_key, name, description, app_url, platform, is_active) "
                "VALUES (:id, :app_key, :name, :description, :app_url, :platform, TRUE)"
            ),
            {
                "id": app_id,
                "app_key": AS_APP_KEY,
                "name": AS_APP_NAME,
                "description": AS_APP_DESCRIPTION,
                "app_url": AS_APP_URL,
                "platform": "web",
            },
        )

    for role_key, label, description in AS_ROLES:
        role_exists = bind.execute(
            sa.text("SELECT id FROM roles WHERE app_id = :app_id AND role_key = :role_key"),
            {"app_id": app_id, "role_key": role_key},
        ).scalar()
        if role_exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO roles (id, app_id, role_key, label, description, is_system) "
                    "VALUES (:id, :app_id, :role_key, :label, :description, TRUE)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "app_id": app_id,
                    "role_key": role_key,
                    "label": label,
                    "description": description,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"),
        {"app_key": AS_APP_KEY},
    ).scalar()
    if app_id is not None:
        bind.execute(sa.text("DELETE FROM roles WHERE app_id = :app_id"), {"app_id": app_id})
        bind.execute(sa.text("DELETE FROM apps WHERE id = :id"), {"id": app_id})

    op.drop_index(op.f("ix_as_analysis_results_language_id"), table_name="as_analysis_results")
    op.drop_table("as_analysis_results")

    op.drop_index(op.f("ix_as_exports_language_id"), table_name="as_exports")
    op.drop_table("as_exports")

    op.drop_index(
        op.f("ix_as_tier_c_sort_assignments_clip_id"), table_name="as_tier_c_sort_assignments"
    )
    op.drop_table("as_tier_c_sort_assignments")

    op.drop_index(op.f("ix_as_tier_c_clips_language_id"), table_name="as_tier_c_clips")
    op.drop_table("as_tier_c_clips")

    op.drop_index(op.f("ix_as_tier_b_recordings_pair_id"), table_name="as_tier_b_recordings")
    op.drop_table("as_tier_b_recordings")

    op.drop_index(op.f("ix_as_tier_b_pairs_language_id"), table_name="as_tier_b_pairs")
    op.drop_table("as_tier_b_pairs")

    op.drop_index(op.f("ix_as_tier_a_recordings_speaker_id"), table_name="as_tier_a_recordings")
    op.drop_index(op.f("ix_as_tier_a_recordings_word_id"), table_name="as_tier_a_recordings")
    op.drop_table("as_tier_a_recordings")

    op.drop_index(op.f("ix_as_tier_a_words_language_id"), table_name="as_tier_a_words")
    op.drop_table("as_tier_a_words")

    op.drop_index(op.f("ix_as_speakers_language_id"), table_name="as_speakers")
    op.drop_table("as_speakers")
