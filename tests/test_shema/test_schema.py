"""What the Shemá schema promises, each promise proved by trying to break it.

These run on SQLite, which is what the suite has, and that is the reason
``app/db/models/shema_enums.py`` turns ``create_constraint`` back on and writes the
append-only guard for the dialect in hand: PostgreSQL enforces the same rules with a native
enum and one plpgsql trigger, and without those two decisions none of this would be visible
where a test can watch it happen.

Where the ORM would refuse first, the test writes through the connection instead —
SQLAlchemy's ``Enum`` rejects an unknown member in Python, and a test that stopped there
would have proved nothing about the database.

The migration was separately walked up, loaded with a copy of the real 127-record export,
walked down and walked back up on PostgreSQL 14, and its schema diffed column for column
against ``Base.metadata``. That is in the pull request, not here: nothing in this repository
can run alembic under SQLite.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaHealthLevel, append_only_ddl
from app.db.models.shema_health import ShemaHealthAssessment
from app.db.models.shema_media import ShemaMediaItem
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_org_chart import ShemaRoleChange
from app.db.models.shema_progress import ShemaProgressEntry
from app.db.types import UtcDateTime

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260911_shema01_shema_module.py"
)

#: The keys the Notion export has. They have an empty state and never an absent one, so the
#: column is NOT NULL with an empty default — except nine, each named in one of the three
#: lists below with its reason. Eight of them break the NOT NULL half; ``id`` breaks only the
#: default half, being a primary key that is supplied and never defaulted.
EXPORT_BACKED_NOT_NULL = (
    "language_name",
    "language_code",
    "bridge_language",
    "vitality_status",
    "location",
    "speaker_count",
    "longitude",
    "latitude",
    "sensitive_country",
    "sensitivity",
    "team",
    "team_leader",
    "mentor",
    "translators",
    "technical_reviewers",
    "partner_org",
    "team_contact",
    "objective",
    "scope_details",
    "translation_type",
    "financial_resources",
    "org_role",
    "in_eten",
    "total_units",
    "total_units_type",
    "translated_units",
    "community_checked_units",
    "approved_units",
    "book_progress",
    "story_progress",
    "phases",
    "status_comments",
    "status_goal",
    "health_assessor",
    "health_notes",
    "prayer_requests",
    "needs_pastoral_intervention",
    "pastoral_intervention_name",
    "needs_notes",
    "notes",
)

#: Fifteen of the eighteen the product added; the other three are collections and live in a
#: child table, not in a column here. Absent means absent, so every one of these is nullable
#: with no default of any kind.
PRODUCT_ADDED_NULLABLE = (
    "location2",
    "team_leader_contact",
    "mentor_contact",
    "facilitator",
    "objective_notes",
    "portion",
    "financial_notes",
    "financial_other_details",
    "other_progress",
    "stories_translated",
    "ready_vessels_audio_hours",
    "health_physical",
    "prayer_visibility",
    "prayer_requests_audio",
    "pastoral_intervention_when",
)

#: Export keys that carry a date. Rule one cannot hold for them: a ``Date`` has no ``""``.
EXPORT_BACKED_DATES = ("start_date", "deadline", "last_updated", "health_assessment_date")

#: Export keys nullable for the other reason: NULL is a state the value itself has, so an
#: empty default would be the server answering on the record's behalf. ``getProjectStatus``
#: (FE-44 §7.1) already derives from progress when the stored value is not one of the six,
#: which is exactly what NULL is; and an unrated dimension is the contract's ``""``, which
#: §7.4 forbids anything from reading as ``boa``.
EXPORT_BACKED_NULL_IS_A_STATE = (
    "status",
    "health_emotional",
    "health_relational",
    "health_spiritual",
)

#: The export's slug, frozen as the primary key (FE-44 §5.1). NOT NULL like the other 48 and
#: with no default, because a primary key is supplied and never defaulted — BE-16 does not
#: mint new ids for the 127 that already have theirs.
EXPORT_BACKED_PRIMARY_KEY = ("id",)

#: Neither side of FE-44's cut: six columns this schema added. Two answer a gate before it
#: can ask (``approved_units_unverified`` for §10 item 7, ``completed_date`` for GATE-01
#: item 6), two are the module's own (``region_key`` derived, ``source`` the export row kept
#: verbatim), and two are the platform's housekeeping.
ADDED_BY_THE_SCHEMA = (
    "approved_units_unverified",
    "completed_date",
    "region_key",
    "source",
    "created_at",
    "updated_at",
)

#: FE-44 §5.1's own two numbers. The table's column count is derived from them, not equal to
#: them, and ``test_the_cut_is_the_contract_s_two_numbers`` writes every step of the
#: derivation down.
EXPORT_KEYS = 55
PRODUCT_ADDED_KEYS = 18
#: Keys that are collections: they live in a child table, not in a column on the record.
EXPORT_KEYS_IN_A_CHILD_TABLE = ("progressHistory", "needsItems", "materials")
PRODUCT_KEYS_IN_A_CHILD_TABLE = ("healthHistory", "mediaPhotos", "mediaVideos")
#: Export keys with no column anywhere: the org chart owns the three (FE-44 §5.3).
EXPORT_KEYS_DROPPED = ("regionalCoordinator", "obtLabPerson", "resourceCirclePerson")
#: One key that shares a column with another: ``ywamBase`` is ``team``.
EXPORT_KEYS_COLLAPSED = ("ywamBase",)
#: One key that is two columns: ``coords`` is ``longitude`` and ``latitude``.
EXPORT_KEYS_SPLIT_IN_TWO = ("coords",)


@pytest.fixture()
async def project(db_session: AsyncSession) -> ShemaProject:
    row = ShemaProject(id="afrikaans-kaaps", language_name="Afrikaans: Kaaps")
    db_session.add(row)
    await db_session.commit()
    return row


def test_the_export_backed_columns_have_an_empty_state_and_not_an_absent_one() -> None:
    columns = ShemaProject.__table__.columns
    not_null = [name for name in EXPORT_BACKED_NOT_NULL if columns[name].nullable]
    assert not_null == []
    without_default = [
        name for name in EXPORT_BACKED_NOT_NULL if columns[name].server_default is None
    ]
    assert without_default == []


def test_the_product_added_columns_are_absent_rather_than_empty() -> None:
    columns = ShemaProject.__table__.columns
    assert [name for name in PRODUCT_ADDED_NULLABLE if not columns[name].nullable] == []
    assert [
        name for name in PRODUCT_ADDED_NULLABLE if columns[name].server_default is not None
    ] == []


def test_every_column_is_on_one_side_of_the_cut_and_exactly_one() -> None:
    """The DoD's *column by column, in both directions*, made total.

    Lists that watch part of a table are the defect they were written to prevent: a column
    added later on either side of the cut is watched by none of them, and nothing says so.
    This is the test that fails the moment a column is added and not classified — which is
    the moment somebody still knows which side it belongs to. Failing here is not a bug to
    route around: put the new column in the list whose rule it keeps, or in
    ``ADDED_BY_THE_SCHEMA`` with the reason written beside it.
    """
    census = (
        EXPORT_BACKED_NOT_NULL
        + EXPORT_BACKED_DATES
        + EXPORT_BACKED_NULL_IS_A_STATE
        + EXPORT_BACKED_PRIMARY_KEY
        + PRODUCT_ADDED_NULLABLE
        + ADDED_BY_THE_SCHEMA
    )
    twice = sorted({name for name in census if census.count(name) > 1})
    assert twice == [], "a column classified on two sides of the cut"

    columns = set(ShemaProject.__table__.columns.keys())
    assert sorted(columns - set(census)) == [], "column on the table that no list watches"
    assert sorted(set(census) - columns) == [], "watched name that is not a column"


def test_the_cut_is_the_contract_s_two_numbers() -> None:
    """55 + 18 keys become 49 + 15 columns, and every step of the difference is a decision.

    The keys are FE-44 §5.1's; the columns are this table's. They differ by six choices and
    each one is written down above, so a count that drifts points at the choice that moved
    rather than at an arbitrary number nobody can check.
    """
    export_backed = (
        EXPORT_BACKED_NOT_NULL
        + EXPORT_BACKED_DATES
        + EXPORT_BACKED_NULL_IS_A_STATE
        + EXPORT_BACKED_PRIMARY_KEY
    )
    expected = (
        EXPORT_KEYS
        - len(EXPORT_KEYS_IN_A_CHILD_TABLE)
        - len(EXPORT_KEYS_DROPPED)
        - len(EXPORT_KEYS_COLLAPSED)
        + len(EXPORT_KEYS_SPLIT_IN_TWO)
    )
    assert len(export_backed) == expected == 49
    assert (
        len(PRODUCT_ADDED_NULLABLE) == PRODUCT_ADDED_KEYS - len(PRODUCT_KEYS_IN_A_CHILD_TABLE) == 15
    )


def test_a_dropped_org_chart_key_and_a_collapsed_one_have_no_column_to_drift_in() -> None:
    """The three differences the census counts, asserted rather than only counted.

    FE-44 §5.3 offers *reject the write or drop the columns* and this took the second;
    ``ywamBase`` is ``team`` under another name; and ``coords`` is one key over two columns.
    """
    columns = set(ShemaProject.__table__.columns.keys())
    assert columns.isdisjoint({"regional_coordinator", "obt_lab_person", "resource_circle_person"})
    assert "ywam_base" not in columns
    assert "team" in columns
    assert {"longitude", "latitude"} <= columns
    assert "coords" not in columns


def test_the_primary_key_is_the_export_slug_and_nothing_defaults_it() -> None:
    """A supplied address, not a minted one — so the one export-backed column with no default."""
    column = ShemaProject.__table__.columns["id"]
    assert column.primary_key
    assert not column.nullable
    assert column.default is None
    assert column.server_default is None


def test_an_export_key_whose_value_has_a_null_state_keeps_it() -> None:
    """NULL is not ``desconhecido`` and it is not ``boa``; a default here would invent both."""
    columns = ShemaProject.__table__.columns
    for name in EXPORT_BACKED_NULL_IS_A_STATE:
        column = columns[name]
        assert column.nullable, name
        assert column.default is None, name
        assert column.server_default is None, name


def test_an_export_date_is_nullable_because_a_date_has_no_empty_string() -> None:
    columns = ShemaProject.__table__.columns
    assert [name for name in EXPORT_BACKED_DATES if not columns[name].nullable] == []


def test_nothing_defaults_prayer_visibility() -> None:
    """NULL means ``coordenacao``. A default here would publish every request in the table."""
    column = ShemaProject.__table__.columns["prayer_visibility"]
    assert column.nullable
    assert column.default is None
    assert column.server_default is None


def test_nothing_defaults_a_health_dimension() -> None:
    """An unassessed dimension is NULL and NULL is not ``boa``.

    All 127 seed records arrive with every dimension empty, so a default here would report
    every silent team as healthy — the exact failure the product exists to prevent.
    """
    for table, names in (
        (ShemaProject, ("health_emotional", "health_relational", "health_spiritual")),
        (ShemaHealthAssessment, ("emotional", "relational", "spiritual", "physical")),
    ):
        for name in names:
            column = table.__table__.columns[name]
            assert column.nullable, name
            assert column.default is None, name
            assert column.server_default is None, name


def test_media_authorization_starts_undecided_and_undecided_refuses() -> None:
    """Only an explicit ``True`` authorizes; NULL is the state a replaced artifact returns to."""
    column = ShemaMediaItem.__table__.columns["authorization_granted"]
    assert column.nullable
    assert column.default is None
    assert column.server_default is None


async def test_a_record_with_more_translated_than_total_is_accepted(
    db_session: AsyncSession,
) -> None:
    """Three real records violate it — ``156/25``, ``8/0``, ``4/0``. The scope is what is wrong."""
    db_session.add(
        ShemaProject(id="over", language_name="Over", total_units=25, translated_units=156)
    )
    db_session.add(ShemaProject(id="zero", language_name="Zero", total_units=0, translated_units=8))
    await db_session.commit()


async def test_the_database_refuses_a_region_that_is_not_one_of_the_seven(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO shema_projects (id, region_key, needs_pastoral_intervention) "
                "VALUES ('bad', 'antarctica', 'nao')"
            )
        )
        await db_session.commit()


async def test_the_database_refuses_an_unrated_health_dimension_spelled_as_empty(
    db_session: AsyncSession,
) -> None:
    """``""`` is the transport's word for *not assessed*; the column's word is NULL."""
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO shema_projects "
                "(id, region_key, needs_pastoral_intervention, health_emotional) "
                "VALUES ('blank', 'other', 'nao', '')"
            )
        )
        await db_session.commit()


async def test_a_rated_dimension_round_trips(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    db_session.add(
        ShemaHealthAssessment(
            project_id=project.id,
            assessment_date=date(2026, 5, 14),
            emotional=ShemaHealthLevel.ATENCAO,
        )
    )
    await db_session.commit()
    row = (await db_session.execute(ShemaHealthAssessment.__table__.select())).one()
    assert row.emotional == ShemaHealthLevel.ATENCAO
    assert row.relational is None


async def test_the_progress_history_refuses_an_update(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    entry = ShemaProgressEntry(project_id=project.id, entry_date=date(2026, 5, 14))
    db_session.add(entry)
    await db_session.commit()

    with pytest.raises(DatabaseError):
        await db_session.execute(text("UPDATE shema_progress_history SET approved_units = 99"))
        await db_session.commit()


async def test_the_progress_history_refuses_a_delete(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    db_session.add(ShemaProgressEntry(project_id=project.id, entry_date=date(2026, 5, 14)))
    await db_session.commit()

    with pytest.raises(DatabaseError):
        await db_session.execute(text("DELETE FROM shema_progress_history"))
        await db_session.commit()


async def test_the_role_change_trail_refuses_an_update(db_session: AsyncSession) -> None:
    db_session.add(ShemaRoleChange(region_key="africa", role="coordinator", to_name="Joana"))
    await db_session.commit()

    with pytest.raises(DatabaseError):
        await db_session.execute(text("UPDATE shema_role_changes SET to_name = 'outra'"))
        await db_session.commit()


async def test_a_project_with_history_cannot_be_deleted(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    """RESTRICT rather than CASCADE, so the error names the project and not a trigger."""
    db_session.add(ShemaProgressEntry(project_id=project.id, entry_date=date(2026, 5, 14)))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM shema_projects WHERE id = :id"), {"id": project.id}
        )
        await db_session.commit()


async def test_a_need_travels_with_its_project_and_goes_with_it(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    """Needs cascade, unlike the history: there is no trail here to strand."""
    db_session.add(
        ShemaNeed(project_id=project.id, category="equipment", urgency="high", status="open")
    )
    await db_session.commit()
    await db_session.execute(text("DELETE FROM shema_projects WHERE id = :id"), {"id": project.id})
    await db_session.commit()
    remaining = await db_session.execute(text("SELECT count(*) FROM shema_needs"))
    assert remaining.scalar_one() == 0


async def test_an_intercessor_country_is_a_code_and_a_contact_is_required(
    db_session: AsyncSession,
) -> None:
    for country, contact in (("B", "a@b.test"), ("BR", "")):
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO shema_intercessors (id, name, country, contact) "
                    "VALUES ('i', 'Alguém', :country, :contact)"
                ),
                {"country": country, "contact": contact},
            )
            await db_session.commit()
        await db_session.rollback()


def test_every_moment_this_module_stores_reads_back_knowing_its_clock() -> None:
    """The DoD's timezone line, asserted over the schema rather than per column.

    ``UtcDateTime`` is stricter than ``DateTime(timezone=True)`` and that is the point: the
    driver hands back a naive value on SQLite and an aware one on Postgres off one schema,
    so a column declared only ``timezone=True`` measures a different contract under test
    than the one production keeps.
    """
    offenders: list[str] = []
    for name, table in Base.metadata.tables.items():
        if not name.startswith("shema"):
            continue
        for column in table.columns:
            if isinstance(column.type, DateTime) and not isinstance(column.type, UtcDateTime):
                offenders.append(f"{name}.{column.name}")
    assert offenders == []


def test_every_shema_table_is_in_the_migration_both_ways() -> None:
    """The defect this catches is adding a model and forgetting the revision.

    Read off the revision's source rather than by running it: no migration in this
    repository can run under SQLite, so the suite cannot walk the graph at all.
    """
    source = _REVISION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    bodies = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    tables = sorted(name for name in Base.metadata.tables if name.startswith("shema"))
    assert tables, "the metadata knows of no shema table"
    assert [t for t in tables if f'"{t}"' not in bodies["upgrade"]] == []
    assert [t for t in tables if f'"{t}"' not in bodies["downgrade"]] == []


def test_the_scoped_collection_read_has_an_index_and_region_key_has_no_second_one() -> None:
    """A B-tree serves its leading column alone; a second index would cost every write."""
    names = {
        index.name: [c.name for c in index.columns] for index in ShemaProject.__table__.indexes
    }
    assert names["ix_shema_projects_region_status"] == ["region_key", "status"]
    assert "ix_shema_projects_region_key" not in names


def test_the_child_tables_are_reachable_by_the_project_the_screen_asks_for() -> None:
    """Assembling one record is a read per collection, and each one leads on ``project_id``."""
    expected = {
        "shema_progress_history": "ix_shema_progress_history_project_date",
        "shema_health_assessments": "ix_shema_health_assessments_project_date",
        "shema_needs": "ix_shema_needs_project_status",
        "shema_media_items": "ix_shema_media_items_project_kind",
        "shema_materials": "ix_shema_materials_project_kind",
        "shema_submissions": "ix_shema_submissions_project_received",
        "shema_intake_links": "ix_shema_intake_links_project",
    }
    for table_name, index_name in expected.items():
        table = Base.metadata.tables[table_name]
        index = next(i for i in table.indexes if i.name == index_name)
        assert next(c.name for c in index.columns) == "project_id", table_name


def test_the_append_only_guard_is_written_for_the_dialect_in_hand() -> None:
    postgres = append_only_ddl("shema_progress_history", "postgresql")
    sqlite = append_only_ddl("shema_progress_history", "sqlite")
    assert any("plpgsql" in statement for statement in postgres)
    assert all("plpgsql" not in statement for statement in sqlite)
    assert len(sqlite) == 2


async def test_the_schema_the_suite_builds_carries_every_table(db_session: AsyncSession) -> None:
    bind = db_session.get_bind()
    names = await db_session.run_sync(lambda session: inspect(session.get_bind()).get_table_names())
    assert len([n for n in names if n.startswith("shema")]) == 16
    assert bind is not None


async def test_a_stored_moment_reads_back_aware(
    db_session: AsyncSession, project: ShemaProject
) -> None:
    row = (await db_session.execute(ShemaProject.__table__.select())).one()
    assert row.created_at.tzinfo is not None
    assert row.created_at <= datetime.now(UTC)
