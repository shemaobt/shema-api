"""the shema module's tables: the project record and the eleven aggregates around it

Revision ID: 20260911_shema01
Revises: 20260830_acc17
Create Date: 2026-09-11

The parent is `20260830_acc17`, read with `uv run alembic heads` in this worktree on
11/sep/2026, immediately before this file was written. It is a measurement and not a value
to remember: `docs/resource_requests.md` §8.3 records a parent that moved **four times**
while a stack sat in review, and the failure is invisible where it is written — a stacked
PR's CI walks its own base, where `tests/test_migration_graph.py` is content, and the graph
forks only when the target branch comes down the stack. Twelve issues in this module author
migrations in waves beside each other, so whoever the user merges second re-points, and the
pull request body is where that is written down so they know.

Written by hand, like the other 97 revisions here. `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a migration
dropping every existing table (`docs/resource_requests.md` §8.1).

The enum objects are shared between the tables that use them. Alembic keeps one impl for the
whole run and the PostgreSQL `ENUM` type memoises against its `_ddl_runner`, so each type is
created once and every later table reuses it rather than failing on a second `CREATE TYPE`.

The append-only trigger is plain plpgsql with no dialect guard, and that is measured rather
than assumed: `alembic upgrade head` cannot run on SQLite at all — `20260226_0001` creates
`users` with `server_default=sa.text("now()")`, which SQLite rejects outright — and nothing
runs alembic anywhere but PostgreSQL. A branch for a dialect this file never meets would be
dead code no test could reach. The SQLite half of the same guard lives in
`app/db/models/shema_enums.py`, where `Base.metadata.create_all` builds the test schema.

The two `CHECK`s on `shema_intercessors` are spelled with `length()`, which both engines
have, because the model's `create_all` writes the same text on SQLite.

**Nothing here backfills.** `prayer_visibility` stays NULL and NULL means `coordenacao`; a
health dimension stays NULL and NULL is not `boa`; media authorization stays NULL and only an
explicit `true` authorizes. The three absences are the module's privacy defaults and a
migration is exactly where they get erased by a well-meaning `server_default`.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema01"
down_revision = "20260830_acc17"
branch_labels = None
depends_on = None

PROJECT_STATUS = sa.Enum(
    "nao-iniciado",
    "em-andamento",
    "final",
    "concluido",
    "pausado",
    "cancelado",
    "planejado",
    "desconhecido",
    name="shema_project_status_enum",
)
HEALTH_LEVEL = sa.Enum("boa", "atencao", "critica", name="shema_health_level_enum")
PRAYER_VISIBILITY = sa.Enum("coordenacao", "rede", name="shema_prayer_visibility_enum")
YES_NO = sa.Enum("sim", "nao", name="shema_yes_no_enum")
REGION_KEY = sa.Enum(
    "south-america",
    "north-america",
    "africa",
    "asia",
    "oceania",
    "europe",
    "other",
    name="shema_region_key_enum",
)
ROLE_KEY = sa.Enum("coordinator", "obtLab", "resourceCircle", name="shema_role_key_enum")
NEED_URGENCY = sa.Enum("low", "medium", "high", name="shema_need_urgency_enum")
NEED_STATUS = sa.Enum("open", "in-progress", "fulfilled", "dropped", name="shema_need_status_enum")
MATERIAL_KIND = sa.Enum("text", "audio", "video", name="shema_material_kind_enum")
MEDIA_KIND = sa.Enum("photo", "video", name="shema_media_kind_enum")
ETEN_CREDIT_SOURCE = sa.Enum("manual", "calculated", name="shema_eten_credit_source_enum")

APPEND_ONLY_TABLES = ("shema_progress_history", "shema_role_changes")

APPEND_ONLY_FUNCTION = (
    "CREATE OR REPLACE FUNCTION shema_reject_write() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
)


def upgrade() -> None:
    op.create_table(
        "shema_projects",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("language_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("language_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("bridge_language", sa.String(200), nullable=False, server_default=""),
        sa.Column("vitality_status", sa.String(120), nullable=False, server_default=""),
        sa.Column("location", sa.String(500), nullable=False, server_default=""),
        sa.Column("location2", sa.String(500), nullable=True),
        sa.Column("speaker_count", sa.String(120), nullable=False, server_default=""),
        sa.Column("longitude", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latitude", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "sensitive_country", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("sensitivity", sa.String(120), nullable=False, server_default=""),
        sa.Column("team", sa.String(300), nullable=False, server_default=""),
        sa.Column("team_leader", sa.String(300), nullable=False, server_default=""),
        sa.Column("mentor", sa.String(300), nullable=False, server_default=""),
        sa.Column("translators", sa.Text(), nullable=False, server_default=""),
        sa.Column("technical_reviewers", sa.Text(), nullable=False, server_default=""),
        sa.Column("partner_org", sa.String(300), nullable=False, server_default=""),
        sa.Column("team_contact", sa.String(300), nullable=False, server_default=""),
        sa.Column("team_leader_contact", sa.String(300), nullable=True),
        sa.Column("mentor_contact", sa.String(300), nullable=True),
        sa.Column("facilitator", sa.String(300), nullable=True),
        sa.Column("objective", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("scope_details", sa.Text(), nullable=False, server_default=""),
        sa.Column("objective_notes", sa.Text(), nullable=True),
        sa.Column("translation_type", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("portion", sa.String(300), nullable=True),
        sa.Column("financial_resources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("financial_notes", sa.Text(), nullable=True),
        sa.Column("financial_other_details", sa.Text(), nullable=True),
        sa.Column("org_role", sa.String(200), nullable=False, server_default=""),
        sa.Column("in_eten", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_units_type", sa.String(60), nullable=False, server_default=""),
        sa.Column("translated_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "community_checked_units", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("approved_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "approved_units_unverified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("book_progress", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("story_progress", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("other_progress", sa.JSON(), nullable=True),
        sa.Column("phases", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("last_updated", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("status", PROJECT_STATUS, nullable=True),
        sa.Column("status_comments", sa.Text(), nullable=False, server_default=""),
        sa.Column("status_goal", sa.String(200), nullable=False, server_default=""),
        sa.Column("stories_translated", sa.String(200), nullable=True),
        sa.Column("ready_vessels_audio_hours", sa.String(200), nullable=True),
        sa.Column("health_emotional", HEALTH_LEVEL, nullable=True),
        sa.Column("health_relational", HEALTH_LEVEL, nullable=True),
        sa.Column("health_spiritual", HEALTH_LEVEL, nullable=True),
        sa.Column("health_physical", HEALTH_LEVEL, nullable=True),
        sa.Column("health_assessment_date", sa.Date(), nullable=True),
        sa.Column("health_assessor", sa.String(200), nullable=False, server_default=""),
        sa.Column("health_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("prayer_requests", sa.Text(), nullable=False, server_default=""),
        sa.Column("prayer_visibility", PRAYER_VISIBILITY, nullable=True),
        sa.Column("prayer_requests_audio", sa.String(500), nullable=True),
        sa.Column(
            "needs_pastoral_intervention",
            YES_NO,
            nullable=False,
            server_default=sa.text("'nao'"),
        ),
        sa.Column("pastoral_intervention_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("pastoral_intervention_when", sa.String(20), nullable=True),
        sa.Column("needs_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("region_key", REGION_KEY, nullable=False, server_default=sa.text("'other'")),
        sa.Column("source", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_projects_region_status", "shema_projects", ["region_key", "status"])
    op.create_index("ix_shema_projects_last_updated", "shema_projects", ["last_updated"])
    op.create_index("ix_shema_projects_language_name", "shema_projects", ["language_name"])

    op.create_table(
        "shema_progress_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("translated_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "community_checked_units", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("approved_units", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("book_progress", sa.JSON(), nullable=True),
        sa.Column("story_progress", sa.JSON(), nullable=True),
        sa.Column("other_progress", sa.JSON(), nullable=True),
        sa.Column("previous_translated", sa.Integer(), nullable=True),
        sa.Column("previous_community", sa.Integer(), nullable=True),
        sa.Column("previous_approved", sa.Integer(), nullable=True),
        sa.Column("initial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("from_field", sa.String(200), nullable=True),
        sa.Column("form_type", sa.String(60), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_progress_history_project_date",
        "shema_progress_history",
        ["project_id", "entry_date"],
    )

    op.create_table(
        "shema_health_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("assessor", sa.String(200), nullable=False, server_default=""),
        sa.Column("emotional", HEALTH_LEVEL, nullable=True),
        sa.Column("relational", HEALTH_LEVEL, nullable=True),
        sa.Column("spiritual", HEALTH_LEVEL, nullable=True),
        sa.Column("physical", HEALTH_LEVEL, nullable=True),
        sa.Column("dimension_notes", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_health_assessments_project_date",
        "shema_health_assessments",
        ["project_id", "assessment_date"],
    )

    op.create_table(
        "shema_needs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("urgency", NEED_URGENCY, nullable=False),
        sa.Column("status", NEED_STATUS, nullable=False, server_default=sa.text("'open'")),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("estimated_value", sa.String(120), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("prayer_shared", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prayer_answered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fulfilled_by", sa.String(200), nullable=True),
        sa.Column("fulfilled_date", sa.Date(), nullable=True),
        sa.Column("dropped_date", sa.Date(), nullable=True),
        sa.Column("submitted_by", sa.String(200), nullable=True),
        sa.Column("submitted_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_needs_project_status", "shema_needs", ["project_id", "status"])
    op.create_index("ix_shema_needs_category_status", "shema_needs", ["category", "status"])

    op.create_table(
        "shema_media_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", MEDIA_KIND, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(300), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("authorization_granted", sa.Boolean(), nullable=True),
        sa.Column("authorized_by", sa.String(200), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_media_items_project_kind", "shema_media_items", ["project_id", "kind"]
    )

    op.create_table(
        "shema_materials",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", MATERIAL_KIND, nullable=False),
        sa.Column("scope", sa.String(300), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(300), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("link", sa.String(1000), nullable=True),
        sa.Column("format", sa.String(60), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("authorization_granted", sa.Boolean(), nullable=True),
        sa.Column("authorized_by", sa.String(200), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_materials_project_kind", "shema_materials", ["project_id", "kind"])

    op.create_table(
        "shema_intercessors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("contact", sa.String(300), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(country) = 2", name="ck_shema_intercessors_country_alpha2"),
        sa.CheckConstraint("length(contact) > 0", name="ck_shema_intercessors_contact_present"),
    )

    op.create_table(
        "shema_region_teams",
        sa.Column("region_key", REGION_KEY, primary_key=True),
        sa.Column("role", ROLE_KEY, primary_key=True),
        sa.Column("holder_name", sa.String(200), nullable=False, server_default=""),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "shema_role_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("region_key", REGION_KEY, nullable=False),
        sa.Column("role", ROLE_KEY, nullable=False),
        sa.Column("from_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("to_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(200), nullable=False, server_default=""),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_role_changes_region_changed", "shema_role_changes", ["region_key", "changed_at"]
    )

    op.create_table(
        "shema_meeting_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(60), nullable=False),
        sa.Column("scope_key", sa.String(30), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "meeting_id", "scope_key", "period", name="uq_shema_meeting_log_meeting_scope_period"
        ),
    )

    op.create_table(
        "shema_eten_credits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=True),
        sa.Column("source", ETEN_CREDIT_SOURCE, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "project_id", "year", "source", name="uq_shema_eten_credits_project_year_source"
        ),
    )

    op.create_table(
        "shema_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("language_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("submitted_by", sa.String(200), nullable=False, server_default=""),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_shema_submissions_project_received",
        "shema_submissions",
        ["project_id", "received_at"],
    )
    op.create_index(
        "uq_shema_submissions_project_content",
        "shema_submissions",
        ["project_id", "content_hash"],
        unique=True,
    )

    op.create_table(
        "shema_intake_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_intake_links_project", "shema_intake_links", ["project_id"])

    op.create_table(
        "shema_notification_prefs",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("channel_email", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("channel_push", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "channel_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("when_key", sa.String(30), nullable=False, server_default=""),
        sa.Column("scope_key", sa.String(30), nullable=False, server_default=""),
        sa.Column("email_addr", sa.String(300), nullable=False, server_default=""),
        sa.Column("phone_addr", sa.String(60), nullable=False, server_default=""),
        sa.Column("custom_project_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "shema_notification_reads",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("entry_id", sa.String(200), primary_key=True),
        sa.Column(
            "read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "shema_user_regions",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("region_key", REGION_KEY, primary_key=True),
        sa.Column("granted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.execute(APPEND_ONLY_FUNCTION)
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS shema_reject_write()")

    op.drop_table("shema_user_regions")
    op.drop_table("shema_notification_reads")
    op.drop_table("shema_notification_prefs")
    op.drop_table("shema_intake_links")
    op.drop_table("shema_submissions")
    op.drop_table("shema_eten_credits")
    op.drop_table("shema_meeting_log")
    op.drop_table("shema_role_changes")
    op.drop_table("shema_region_teams")
    op.drop_table("shema_intercessors")
    op.drop_table("shema_materials")
    op.drop_table("shema_media_items")
    op.drop_table("shema_needs")
    op.drop_table("shema_health_assessments")
    op.drop_table("shema_progress_history")
    op.drop_table("shema_projects")

    bind = op.get_bind()
    for enum_type in (
        ETEN_CREDIT_SOURCE,
        MEDIA_KIND,
        MATERIAL_KIND,
        NEED_STATUS,
        NEED_URGENCY,
        ROLE_KEY,
        REGION_KEY,
        YES_NO,
        PRAYER_VISIBILITY,
        HEALTH_LEVEL,
        PROJECT_STATUS,
    ):
        enum_type.drop(bind, checkfirst=True)
