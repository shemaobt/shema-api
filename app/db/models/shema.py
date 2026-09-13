"""The Shemá project record — the module's spine, and the table the other twelve hang from.

``docs/shema.md`` §4.3 decided the hard question before this issue started: **a Shemá
project is not a** ``projects`` **row, there is no foreign key, and there is no**
``language_id``. Four measurements, not a boundary preference: ``projects.language_id`` is
``NOT NULL`` with ``ondelete="RESTRICT"`` while ``languages.code`` is ``String(3)``
**unique**, and the export carries ``jaa-b``, ``not iso language``, three empty strings and
``pah`` on five different projects — the one mandatory column of that row is the one this
data cannot fill. Eleven foreign keys across six model files already point at
``projects.id``; the overlap is four fields of seventy-three; and the two primary keys are
different kinds of thing. The nullable ``tripod_project_id`` that would let the two products
point at each other is **not here**: §4.3 asks the issue that needs it to add it then.

**The primary key is the export's slug**, frozen by FE-44 §5.1 as the address every screen,
URL and saved view already carries. BE-16 does not mint new ids.

Three rules decide every column's nullability, and together they are the DoD's *optionality
reflecting the real export*.

**One — the 55 export keys are NOT NULL with an empty default; the 18 the product added are
nullable.** FE-44 §5.1 pins that split in both directions with a test: the 55 required fields
of ``Project`` are exactly the keys the Notion export has, and the 18 optional ones are
exactly the keys it does not. So an export-backed column has no *absent* state — it has an
empty one, which 27 of the 55 carry on all 127 records — while a product-added column means
absent when it is NULL, and *absent is not an empty default*.

**Two — a date has no empty string, so every date the export carries is nullable.** It is the
one place rule one cannot hold: FE-44 §6.1 requires real ``date`` columns rather than
``13/04/2024`` in text, where a parsing bug costs a migration instead of a function, and a
date column's word for *the export wrote nothing here* is NULL. Eight records have a
``start_date`` and none has a ``deadline``.

**Three — the four fields required to save carry no constraint in the database.**
``missingRequired`` names ``language_name``, ``bridge_language``, ``team`` and ``objective``
(FE-44 §5.1.1), and two of those four are empty across the whole export: ``bridge_language``
on all 127, ``objective`` on 23. A ``CHECK (bridge_language <> '')`` would refuse the seed on
its first row. The rule is real and it belongs to the write path, where
``app/models/shema.py`` holds it — a schema that marks ``location``, ``deadline`` or
``speaker_count`` NOT NULL makes 127 existing records unsaveable and makes the record
uneditable for exactly the field teams whose data is this thin.

**And no** ``translated_units <= total_units`` **constraint.** Three real records violate it
— ``156/25``, ``8/0``, ``4/0`` — and 23 records have a scope of zero. The scope is what is
wrong in those rows, not the count.

**Three columns the export has are dropped rather than stored.**
``regionalCoordinator``, ``obtLabPerson`` and ``resourceCirclePerson`` are empty on all 127
records and stay empty on purpose: the region's three role-holders are read from the org
chart (``shema_region_teams``) and never copied onto a project. FE-44 §5.3 asks the server to
*reject a write that fills them, or drop the columns*, and dropping is the stronger of the
two — a column that does not exist cannot become a second owner of a fact the chart owns,
and no later issue has to remember the rejection. ``app/models/shema.py`` refuses the three
keys on the way in so a client that sends them learns why.

**Two columns that hold one fact, and which one is authoritative.** ``docs/shema.md`` §10's
first open question is this table's, and it is answered in opposite directions for the two
pairs, because the pairs are not the same shape.

``team`` and ``ywamBase`` are **collapsed into one column**. JOCUM is the Portuguese for
YWAM, all 127 records carry the identical string in both, the record shows one input, and two
columns that can drift *is* the defect the question names. Collapsing removes the drift
instead of policing it; the response model serves the one value under both keys, which is one
line in the shape that leaves and no rule for anybody to forget. Nothing is lost either way:
``source`` below holds the export's own two columns verbatim.

``sensitivity`` and ``sensitive_country`` **stay two columns, and the boolean is
authoritative**. They are not one fact in two spellings — the boolean is the safety flag the
redaction reads and the text is a free-text export column with nine values, which agrees with
the flag today by accident of the data rather than by construction. The text is provenance:
no screen edits it, nothing reads it for a safety decision. Collapsing here would delete
evidence; keeping the flag the only reader is what stops them drifting.

**The flag is not derived from that text, and BE-16 amended this paragraph to say so**
(``docs/shema.md`` §9.5, §10 item 1). This issue expected the import to read the boolean off
``sensitivity``; OBT-405's own requirement is the opposite — *do not infer them from the CSV,
from country names, or from anything in the prototype* — so the flag comes from the client's
written list of countries, and the export's text and boolean may only **raise** it, never
clear it. One of the two records the export marks ``Confidential`` is why: it sits in
**Mexico**, where seven other records are ``Unrestricted``, which a list keyed by country
cannot express. The columns below are unchanged; what changed is that nothing reads the
export as permission.

**The three prayer columns are guarded, not private.** ``prayer_requests``,
``prayer_visibility`` and ``prayer_requests_audio`` have exactly one reader —
``app/services/shema/_consent.py``, which BE-04 writes together with the glob test that fails
the build when a second file references them (``docs/shema.md`` §6.4). They are named here in
the spelling that test will look for. ``prayer_visibility`` is **nullable with no default and
no server default**, and NULL means ``coordenacao``: nothing has to be written for a request
to stay private, and something has to be written for it to travel. A migration that backfills
it to ``rede`` publishes every request in the database.

The guard has a fourth place to look, and it is ``source`` below. ``prayerRequests`` is one
of the export's 55 keys, so the row kept verbatim carries that key too, under the export's
own camelCase spelling — empty in today's export, and exactly where the next one's text
lands. ``prayerVisibility`` and ``prayerRequestsAudio`` are not in it at all, being two of
the 18 the product added. So a glob written on the three column names alone walks straight
past ``source["prayerRequests"]``.

**``region_key`` is stored and maintained, which is §10's second open question and this
issue's answer.** It is derived — ``location.split(",")[0]`` through ``COUNTRY_REGION``,
falling back to ``other`` — and computing it per query would make the one predicate every
list query carries (``docs/shema.md`` §6.1's ``RegionScope``) unsargable over a growing table.
So it is a column, written by the same service that writes ``location``, from the single
owner in ``app/utils/shema_derivations.py``. It is deliberately **not** a generated column:
the derivation is a lookup over 25 country strings kept in Python, and expressing it in DDL
would be a second copy of a map whose whole value is that there is one. Never a hand-typed
field.

**``source`` is BE-16's, and it is here so BE-16 does not need a migration.** The seed
interprets: ``DD/MM/YYYY`` becomes a real date, ``team`` and ``ywamBase`` become one column,
and ``sensitive_country`` is decided by a list the export does not contain. Where a column is
an interpretation, the uninterpreted row has to survive somewhere or the interpretation
cannot be audited or redone.
One JSON column holding the export row as it arrived answers that for every field at once,
which per-field ``*_source`` columns would not — and it is NULL for records born in the
product, which is the honest difference between *migrated* and *typed*.

``approved_units_unverified`` is the same courtesy for the same issue's other open question
(§10, item 7). The export's ``approvedUnits`` is a copy of ``translatedUnits`` on all 127
records, so migrating it as-is credits approvals nobody made, and BE-16 chooses between
importing it as-is, as zero, or flagged as unverified. Two of those three answers need no
column and the third needs this one; giving it now is what keeps BE-16 out of the migration
graph while BE-11 waits on the same fact.

``completed_date`` is not an export column and nothing writes it yet. It is here because
GATE-01's item 6 cannot close without it: ``status`` records *that* a project finished and
never *when*, and the ETEN report is per year. It is the one open item on that gate that is a
schema change, and a schema change is the thing a stacked wave cannot afford to discover late.

**Coordinates are two floats and the pair is longitude first.** ``[0, 0]`` is *no
coordinate*, not the Gulf of Guinea — two records carry it and both have an empty
``location``. Storing the reading rather than the value would be the mistake:
``hasPlottableCoords`` is the single owner of it and lives with the derivations, so the
columns keep the number the export gave and nothing here decides what it means.

**``status`` is nullable, and NULL means nothing was stored.** ``getProjectStatus`` (FE-44
§7.1) returns the stored value when it is one of the six explicit ones and otherwise derives
from progress, so the function is already total over *not one of the six* — which is what
NULL is. All 127 export records carry one of the six, so this is not a state the seed
produces; it is the state of a record nobody has said anything about, and defaulting it to
``desconhecido`` would be the server asserting an answer on the record's behalf.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import (
    HEALTH_LEVEL,
    PRAYER_VISIBILITY,
    PROJECT_STATUS,
    REGION_KEY,
    YES_NO,
    ShemaHealthLevel,
    ShemaPrayerVisibility,
    ShemaProjectStatus,
    ShemaRegionKey,
    ShemaYesNo,
)
from app.db.types import UtcDateTime


class ShemaProject(Base):
    """One language project, addressed by the slug the export minted for it.

    The indexes are the module docstring's last subject and the DoD's fifth line, and what
    they serve is deliberately narrower than the screen's filter list. FE-44 §9.1 froze
    ``GET /api/shema/projects`` as *the whole collection the caller's role and region allow*
    — **no pagination, no filter parameters, no facet counts** — because sixteen facet
    groups and four presets are computed client-side in one pass, under a rule whose whole
    value is that the sidebar's numbers and the list agree because one function produces
    both. So the query this screen actually makes, server-side, is one: the collection
    within a ``RegionScope``.

    ``ix_shema_projects_region_status`` is that query, with the status filter that could
    move server-side first riding on it. ``region_key`` gets no index of its own: a B-tree
    serves its leading column alone, and a second one would cost every write and buy no
    read. ``last_updated`` carries the ``recent`` preset and the freshness signal Rhythm and
    the Forms hub both read; ``language_name`` is the collection's default order and the
    dominant field of its text search.

    **Three of the filters the issue lists are not indexable here, and saying which is the
    point.** Overall health is the worst of four nullable dimensions, staleness is a
    function of the newest progress entry *and* a clock, and the text search spans several
    columns — the first two are derivations no B-tree can answer and the third wants a
    ``tsvector`` that SQLite, which is what the suite runs on, cannot carry. Indexing a
    column that stands in for a derivation is worse than not indexing it: it promises an
    answer the query cannot use and invites a second owner of the rule. ``objective`` and
    ``translation_type`` are JSON arrays for the same reason — this repository has no
    JSONB anywhere and no precedent for a GIN index, and a child table per array to serve a
    filter that runs in the browser is schema built for a query nobody issues. FE-44 §9.1
    names when that stops being true — past roughly 2,000 projects — and asks that the
    server take the filter *and* the counts together when it does.
    """

    __tablename__ = "shema_projects"
    __table_args__ = (
        Index("ix_shema_projects_region_status", "region_key", "status"),
        Index("ix_shema_projects_last_updated", "last_updated"),
        Index("ix_shema_projects_language_name", "language_name"),
    )

    #: The export's slug (``afrikaans-kaaps``), never a minted uuid — FE-44 §5.1.
    id: Mapped[str] = mapped_column(String(120), primary_key=True)

    #: Never normalised: not trimmed, not title-cased, not transliterated. ``Embera Dobida``
    #: carries a non-breaking space and three names legitimately begin lowercase.
    language_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: Checked and never refused. The export holds ``?``, ``N/A``, ``not iso language``,
    #: ``LLL``, ``jaa-b`` and ``pah`` five times — which is why it is text and not a FK.
    language_code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    #: Required to save and empty on all 127 records, which is why no ``CHECK`` guards it.
    bridge_language: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: Free text offered as the six-step UNESCO scale. The stored value is ``""``, never the
    #: form's ``"na"`` sentinel, which exists only because Radix reads ``value=""`` as
    #: nothing-selected.
    vitality_status: Mapped[str] = mapped_column(String(120), default="", server_default="")
    #: Free text that may name several countries — ``China, Laos, Vietnam``. The region is
    #: derived from the first; two records are empty and land in ``other``.
    location: Mapped[str] = mapped_column(String(500), default="", server_default="")
    location2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: A string because the field records ranges and notes as typed, not a count.
    speaker_count: Mapped[str] = mapped_column(String(120), default="", server_default="")
    longitude: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    latitude: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))

    #: The safety flag, and the only one anything reads. ``sensitivity`` beside it is the
    #: export's free text and is provenance only.
    sensitive_country: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    sensitivity: Mapped[str] = mapped_column(String(120), default="", server_default="")

    #: ``team`` and ``ywamBase`` collapsed: one concept, one column, no drift.
    team: Mapped[str] = mapped_column(String(300), default="", server_default="")
    #: Several people legitimately live in one string — ``Pati & Marcos``, ``Rodolfo /
    #: Debora``. Splitting on ``&`` or ``/`` invents people; display splits on ``,`` and
    #: ``;`` only.
    team_leader: Mapped[str] = mapped_column(String(300), default="", server_default="")
    mentor: Mapped[str] = mapped_column(String(300), default="", server_default="")
    translators: Mapped[str] = mapped_column(Text, default="", server_default="")
    technical_reviewers: Mapped[str] = mapped_column(Text, default="", server_default="")
    partner_org: Mapped[str] = mapped_column(String(300), default="", server_default="")
    team_contact: Mapped[str] = mapped_column(String(300), default="", server_default="")
    team_leader_contact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mentor_contact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facilitator: Mapped[str | None] = mapped_column(String(300), nullable=True)

    objective: Mapped[list[str]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )
    scope_details: Mapped[str] = mapped_column(Text, default="", server_default="")
    objective_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_type: Mapped[list[str]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )
    portion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    financial_resources: Mapped[list[str]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )
    financial_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_other_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Free text the export produced, one distinct value over 24 records. No screen edits it
    #: and no list defines it, so it is not a vocabulary and never an enum.
    org_role: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: False on all 127. The entire ETEN report is empty by honest accident, and that is not
    #: a bug for a seed to hide.
    in_eten: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    total_units: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: Six unit types are offered and the export uses one (``Capítulos``). Not in §7.3's
    #: enum-safe list, so text.
    total_units_type: Mapped[str] = mapped_column(String(60), default="", server_default="")
    translated_units: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    community_checked_units: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    approved_units: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: BE-16's third answer to §10's item 7, given a column now so it needs no migration.
    approved_units_unverified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    book_progress: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )
    story_progress: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )
    other_progress: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    #: ``{label, scope, date}`` typed on the record, empty on all 127. Not this repository's
    #: ``phases`` table, which is a translation project's workflow — same word, different
    #: concept (``docs/shema.md`` §4.7).
    phases: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Read as *the Pulse cycle is covered* by Rhythm and Forms. A freshness signal, never a
    #: received form — relabelling it as one lies to a coordinator about whether a team was
    #: heard.
    last_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: GATE-01 item 6: ``status`` records *that* a project finished, never *when*, and the
    #: ETEN report is per year. Nothing writes it yet.
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[ShemaProjectStatus | None] = mapped_column(PROJECT_STATUS, nullable=True)
    status_comments: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: Five values in the export, one of them ``N/A``. Free text, never an enum.
    status_goal: Mapped[str] = mapped_column(String(200), default="", server_default="")
    stories_translated: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ready_vessels_audio_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: The four dimensions are a **projection of the newest** ``shema_health_assessments``
    #: **entry**, never a second truth: BE-07 appends and re-projects in one step. NULL is
    #: *not assessed* and is not ``boa`` — all 127 records arrive with every dimension
    #: empty, so unassessed is the dominant state and a default here would report every
    #: silent team as healthy.
    health_emotional: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    health_relational: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    health_spiritual: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    #: The fourth dimension the product added; the export has no column for it, so a migrated
    #: record is three-quarters assessed at most.
    health_physical: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    health_assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    health_assessor: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: The running blob, derived from the assessment's per-dimension notes at write time. The
    #: per-dimension note is the data; a server that stores only this has lost it.
    health_notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: Guarded: ``app/services/shema/_consent.py`` is the only reader of these three.
    prayer_requests: Mapped[str] = mapped_column(Text, default="", server_default="")
    prayer_visibility: Mapped[ShemaPrayerVisibility | None] = mapped_column(
        PRAYER_VISIBILITY, nullable=True
    )
    #: A storage key in the module's private bucket, never a URL — the signed GET is minted
    #: per call and stored nowhere (``docs/shema.md`` §4.6). BE-04 owns the adapter.
    prayer_requests_audio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    needs_pastoral_intervention: Mapped[ShemaYesNo] = mapped_column(
        YES_NO, default=ShemaYesNo.PT_NAO, server_default=text("'nao'")
    )
    pastoral_intervention_name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    #: ``now`` or ``30d``. Text and not an enum: §7.3 blessed ten vocabularies as enum-safe
    #: and this two-value union is not among them, and an urgency window is the kind of list
    #: a client extends.
    pastoral_intervention_when: Mapped[str | None] = mapped_column(String(20), nullable=True)

    needs_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: Round-trips unchanged. Nothing trims or normalises it, in any script.
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: Derived from ``location`` and maintained by the service that writes it. The one
    #: predicate every scoped list query carries.
    region_key: Mapped[ShemaRegionKey] = mapped_column(
        REGION_KEY, default=ShemaRegionKey.OTHER, server_default=text("'other'")
    )
    #: The export row as it arrived, for every column this schema interpreted. NULL for a
    #: record born in the product.
    #:
    #: **One of the three guarded columns has a second address in here.**
    #: ``prayerRequests`` is one of the 55 keys the export has (FE-44 §5.1), so a seeded row
    #: carries it as ``source["prayerRequests"]`` beside ``prayer_requests`` above — empty in
    #: today's export, and the place the next one's text lands. ``prayerVisibility`` and
    #: ``prayerRequestsAudio`` are not here at all: they are two of the 18 the product added
    #: and the export has no column for either. So BE-04's glob (``docs/shema.md`` §6.4) has
    #: to fail on this spelling too, not only on the three snake_case names.
    source: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
