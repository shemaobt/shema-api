"""The Shemá module's frozen vocabularies, as native PostgreSQL enums.

FE-44's Appendix A froze twenty vocabularies against a built, client-reviewed console,
and ``docs/shema.md`` §7.3 sorted them: a vocabulary may be an enum when the client
cannot extend it, and must be text otherwise. This module holds the ten that passed that
test **and that a column actually stores** — everything else the contract lists stays
text on the row it belongs to, with the reason written where the column is.

Four are deliberately absent and the omission is the decision:

``statusGoal`` and ``orgRole`` are not vocabularies at all — free text the Notion export
happened to produce, with no screen editing them and no list defining them. ``formType``
is a free ``string`` on purpose (FE-44 §12.9): the values in the product today are
``full`` and ``field``, neither of them a ``FormKind``, so typing the column as the union
rejects the prototype's own value on the first import. ``NeedCategory`` is the one that
looks enum-safe and is not: §7.3 lists its two siblings ``NeedUrgency`` and
``NeedStatus`` among the enum-safe ten and leaves it out, which reads as deliberate — a
category list is the kind a client adds to, and an enum member costs a migration.

**``ShemaHealthLevel`` is three values and not four, and that is the same decision as
FE-44's own type.** The contract writes ``HealthLevel = boa | atencao | critica`` and
``HealthRating = HealthLevel | ""`` — the empty string is the transport's spelling of
*not assessed*, which a ``<select>`` needs and a column does not. So the column is
``ShemaHealthLevel`` and **NULL is the** ``""``: nullable, no default, no backfill. The
rule §7.4 protects survives exactly — NULL is not ``boa``, and nothing can make it one —
while the database keeps its own word for absence instead of storing an empty enum label
on a dialect this suite cannot exercise.

The trigger pair below is here rather than in one of the two tables that hang it, because
neither owns it: ``shema_progress_history`` and ``shema_role_changes`` are append-only for
different reasons and would otherwise import it from each other.
"""

import enum
from typing import Any

from sqlalchemy import Enum, Table, text
from sqlalchemy.engine import Connection


class ShemaProjectStatus(enum.StrEnum):
    """All eight, including the two the server derives and never writes.

    ``final`` and ``nao-iniciado`` are derived-only (FE-44 §7.1), and the temptation is to
    narrow the column to the three the record's form edits. That makes the 24 records
    stored as ``desconhecido``, ``cancelado`` or ``concluido`` unsaveable — the form can
    express a stored status outside its own three cards by offering the saved one as a
    fourth option. Store all eight, derive the two.
    """

    NAO_INICIADO = "nao-iniciado"
    EM_ANDAMENTO = "em-andamento"
    FINAL = "final"
    CONCLUIDO = "concluido"
    PAUSADO = "pausado"
    CANCELADO = "cancelado"
    PLANEJADO = "planejado"
    DESCONHECIDO = "desconhecido"


class ShemaHealthLevel(enum.StrEnum):
    """A rated dimension. *Not assessed* is NULL and is not a member."""

    BOA = "boa"
    ATENCAO = "atencao"
    CRITICA = "critica"


class ShemaPrayerVisibility(enum.StrEnum):
    """Where a prayer request may travel. **NULL means** ``coordenacao`` and is not a member.

    A visibility level, not a published boolean: ``coordenacao`` is a real destination —
    the people who follow up — and a team that has not consented to being shared still
    reaches them. The absence is the point, so this type never gains a third member for
    it (FE-44 §8.2, ``docs/shema.md`` §7.4).
    """

    COORDENACAO = "coordenacao"
    REDE = "rede"


class ShemaYesNo(enum.StrEnum):
    PT_SIM = "sim"
    PT_NAO = "nao"


class ShemaRegionKey(enum.StrEnum):
    """The seven fixed regions. A project's is derived from the first country of its location.

    ``other`` is not a leftover bin to be cleaned up later: two records have an empty
    ``location`` and land here legitimately, and ``COUNTRY_REGION`` is keyed on the
    export's exact spellings — ``São Tomé e Príncipe`` in Portuguese, ``East Timor`` in
    English — so anything unmapped falls here by design rather than by mistake.
    """

    SOUTH_AMERICA = "south-america"
    NORTH_AMERICA = "north-america"
    AFRICA = "africa"
    ASIA = "asia"
    OCEANIA = "oceania"
    EUROPE = "europe"
    OTHER = "other"


class ShemaRoleKey(enum.StrEnum):
    """The three seats the org chart holds **per region**.

    ``globalStrategist`` is the module's fourth *platform* role key and has no seat here,
    because the chart's three roles are per region (FE-44 §5.3). It is granted through
    ``user_app_roles`` like the other three and is named in ``app/api/shema/_deps.py``;
    this type is the chart's vocabulary, not the app's.
    """

    COORDINATOR = "coordinator"
    OBT_LAB = "obtLab"
    RESOURCE_CIRCLE = "resourceCircle"


class ShemaNeedUrgency(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ShemaNeedStatus(enum.StrEnum):
    """Four states, not three.

    ``dropped`` is the one the prototype lacked: a request that stopped mattering must
    leave the open list without being deleted, because deleting loses the history a
    region is judged by. *Still outstanding* is ``open`` or ``in-progress`` and has one
    owner; a predicate written as ``status != fulfilled`` is a bug the moment a fifth
    state exists.
    """

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    FULFILLED = "fulfilled"
    DROPPED = "dropped"


class ShemaMaterialKind(enum.StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class ShemaMediaKind(enum.StrEnum):
    """Which of the two frozen media shapes a ``shema_media_items`` row is.

    The only vocabulary here that FE-44 did not freeze, because it is not a product
    vocabulary: ``MediaPhoto`` and ``ProjectVideo`` are two types and ``docs/shema.md``
    §5.5 gives them one table, so the discriminator is a fact about this schema. It is an
    enum rather than text for the reason the others are — the set cannot grow without the
    contract growing a third media type first.
    """

    PHOTO = "photo"
    VIDEO = "video"


class ShemaEtenCreditSource(enum.StrEnum):
    """Where a credit line came from. A stored ``manual`` entry overrides the computed value."""

    MANUAL = "manual"
    CALCULATED = "calculated"


def _enum_type(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """A native PostgreSQL enum that stores the member *values*, not their names.

    ``values_callable`` is not optional: without it the type is written from the member
    names and the contract froze the lowercase, accented, camelCase values.

    ``create_constraint`` has defaulted to ``False`` since SQLAlchemy 1.4, which on a
    dialect without native enums leaves a bare ``VARCHAR`` — and the test suite runs on
    SQLite, so without this every enum in the module would be unenforced in the only
    place a test can watch the database refuse a value. It costs PostgreSQL nothing: a
    native enum is already a closed set and no CHECK is emitted beside it.

    The same three lines stand in ``app/db/models/resource_request.py`` and are not
    imported from there. Reaching across products for a private helper couples two
    modules that share nothing else, and ``docs/shema.md`` §2.6 asks that the first
    person to do it be asked why.
    """
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [m.value for m in cls],
        create_constraint=True,
    )


PROJECT_STATUS = _enum_type(ShemaProjectStatus, "shema_project_status_enum")
HEALTH_LEVEL = _enum_type(ShemaHealthLevel, "shema_health_level_enum")
PRAYER_VISIBILITY = _enum_type(ShemaPrayerVisibility, "shema_prayer_visibility_enum")
YES_NO = _enum_type(ShemaYesNo, "shema_yes_no_enum")
REGION_KEY = _enum_type(ShemaRegionKey, "shema_region_key_enum")
ROLE_KEY = _enum_type(ShemaRoleKey, "shema_role_key_enum")
NEED_URGENCY = _enum_type(ShemaNeedUrgency, "shema_need_urgency_enum")
NEED_STATUS = _enum_type(ShemaNeedStatus, "shema_need_status_enum")
MATERIAL_KIND = _enum_type(ShemaMaterialKind, "shema_material_kind_enum")
MEDIA_KIND = _enum_type(ShemaMediaKind, "shema_media_kind_enum")
ETEN_CREDIT_SOURCE = _enum_type(ShemaEtenCreditSource, "shema_eten_credit_source_enum")

APPEND_ONLY_FUNCTION = "shema_reject_write"


def append_only_ddl(table_name: str, dialect: str) -> tuple[str, ...]:
    """The statements that make ``table_name`` reject every UPDATE and DELETE.

    Two of this module's invariants are database-level rather than service-level, and
    ``docs/shema.md`` §7.2 says why it matters more here than it did for the sibling:
    ``shema_progress_history`` is the record a year-end ETEN report is reconstructed
    from, and ``shema_role_changes`` is the trail that makes a team change a write with
    an audit row instead of a silent update. A rule that lives in the one service that
    writes today is a rule the second writer will not have.

    PostgreSQL needs a trigger function, shared by both tables and written with
    ``CREATE OR REPLACE`` so the second costs nothing. SQLite has no stored functions and
    raises from the trigger body instead, one trigger per verb — and SQLite is what the
    suite runs on, which is the whole reason this is a function of the dialect in hand
    rather than a migration-only concern. ``Base.metadata.create_all`` builds the test
    schema and hangs these on ``after_create``; the migration writes the PostgreSQL half
    literally, because no migration in this repository can run under SQLite at all.
    """
    if dialect == "postgresql":
        return (
            f"CREATE OR REPLACE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql",
            f"CREATE TRIGGER {table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()",
        )
    message = f"{table_name} is append-only"
    return (
        f"CREATE TRIGGER {table_name}_no_update BEFORE UPDATE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
        f"CREATE TRIGGER {table_name}_no_delete BEFORE DELETE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
    )


def guard_append_only(table: Table, connection: Connection, **_: Any) -> None:
    """``after_create`` listener that hangs :func:`append_only_ddl` on the table just made."""
    for statement in append_only_ddl(table.name, connection.dialect.name):
        connection.execute(text(statement))
