"""The record — ``GET /api/shema/projects/{id}``, and every sub-shape the ficha is made of.

**This is a coordination surface and it carries the truth.** It is the one read in the module
that deliberately does *not* inherit
:class:`~app.models.shema_privacy.LeavingShape`: FE-44 §9.0 states the split in one line —
*"the project read itself carries the true location — it is a coordination surface"* — and §8.1
rule 5 gives the reason, which is that hiding the country from the record's own author is data
loss rather than privacy. The scope is what decides who may open it (``_scope.py``), and
``tests/test_shema/test_privacy_owners.py`` carries the three routes of this file in
``COORDINATION_PATHS`` so the exemption is a line somebody wrote rather than a shape that
slipped past.

**The shape is FE-44's ``Project``, key for key: 55 required and 18 optional.**
``src/types/__tests__/contract.test.ts`` pins that split in both directions on the other side,
and ``tests/test_shema/test_record_shape.py`` pins it here against the same source — so a
field added to the table stays out of the wire until somebody adds it to this file, and a key
this file drops is a red test rather than a console rendering blanks.

Four notes on where this file and the table do not line up, each of them FE-44's own
instruction rather than a liberty:

* **``team`` and ``ywamBase`` are one column served under two keys.** BE-02 collapsed them
  because all 127 records carry the identical string and two columns that can drift is the
  defect; FE-44 §5.1 asks that the server write both from one input, and serving both from one
  column is the same sentence read on the way out.
* **The three org-chart names are constants.** ``regionalCoordinator``, ``obtLabPerson`` and
  ``resourceCirclePerson`` have no column — BE-02 dropped them — and they are emitted as ``""``
  because the contract still lists them as required keys and ``src/fixtures/__tests__`` asserts
  they stay empty. Emitting them is what keeps a whole ``Project`` round-trippable through
  ``POST``; storing one would be a second owner of a fact ``shema_region_teams`` owns.
* **``completedDate`` is not emitted.** It is a column (GATE-01 item 6) and it is not one of
  FE-44's 73 keys; nothing writes it yet, and a server that invents a 74th key is the reason a
  frozen contract stops being one.
* **``mediaPhotos[].image`` is always ``null``.** The bytes have no serving path: BE-04 built
  the authorization predicate and named *the storage half* as belonging to the issue that
  first serves media (BE-09/BE-14), and a ``src`` invented here would freeze the guess that
  file declined to freeze. The caption and the per-item decision are real and travel.

``derived`` is the ninth thing the console stops computing, exactly as BE-05's card carries it
— one implementation of *is this project stale*, so the ficha's badge and the list's badge
cannot disagree.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Self

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaMaterialKind,
    ShemaNeedStatus,
    ShemaNeedUrgency,
    ShemaPrayerVisibility,
    ShemaProjectStatus,
    ShemaYesNo,
)
from app.models.shema_projects import ShemaProjectDerived
from app.utils.shema_books import chapters_in

#: ``datetime.date`` under a second name. Two shapes below carry a field literally called
#: ``date`` — FE-44's own key for the day a history entry or an assessment belongs to — and a
#: field whose name shadows its own annotation is a model Pydantic cannot build.
Day = date

#: Read models speak camelCase outward and snake_case inward — BE-05's ``_OUTWARD``, and the
#: same mechanism for the same reason (``app/models/shema_projects.py``'s module docstring).
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: The sub-shapes stored inside a JSON column speak camelCase **in both directions**, which is
#: the one place this module's wire spelling reaches the database.
#:
#: They are a *document*, not columns: the export produced them in FE-44's spelling, the Pulse
#: import will carry them in it (BE-12), and the console reads them back in it. Translating a
#: document's keys on the way in and again on the way out is two places to be wrong in
#: exchange for a spelling nothing queries — no index, no predicate and no ``GROUP BY`` reaches
#: inside these arrays (``app/db/models/shema.py``'s class docstring says why they are JSON at
#: all). So one alias generator serves validation and serialisation, and a row round-trips
#: byte for byte.
_DOCUMENT = ConfigDict(
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
    extra="forbid",
)

#: A count on a progress row. Never negative, and the per-row ceiling is :attr:`chapters` —
#: see :class:`ShemaCountedProgressRow`.
Count = Annotated[int, Field(ge=0)]


class ShemaCountedProgressRow(BaseModel):
    """The rows the roll-up can actually add up — a book, or a named *other* scope.

    **The ceiling is per row and never over the aggregates**, and the distinction is the whole
    of this class's reason to exist. FE-44 §5.1 forbids a ``translatedUnits <= totalUnits``
    rule on the record: three real export records carry ``156/25``, ``8/0`` and ``4/0``, the
    scope is what is wrong in them, and ``getProgress`` returning 624% is what sends somebody
    to look. A **row** is a different claim: *28 of Matthew's 28 chapters are translated* is a
    statement about a book, and *30 of 28* is not a scope that needs fixing, it is a typo. So
    the counts are checked against :attr:`chapters` here and nothing is checked against
    ``total_units`` anywhere.

    Every violation in a batch is reported at once, by index, because Pydantic collects the
    errors of a list before it raises — which is what makes *a partial failure applies nothing*
    true of the validation half without a loop that has to remember to keep going.
    """

    model_config = _DOCUMENT

    name: str = ""
    #: The scope this row claims, in chapters. Zero is legitimate: a book a team has listed
    #: and not yet scoped.
    chapters: Count = 0
    translated: Count = 0
    community_checked: Count = 0
    mentor_approved: Count = 0

    @model_validator(mode="after")
    def _no_count_exceeds_the_scope(self) -> Self:
        over = [
            f"{label} {value} of {self.chapters}"
            for label, value in (
                ("translated", self.translated),
                ("communityChecked", self.community_checked),
                ("mentorApproved", self.mentor_approved),
            )
            if value > self.chapters
        ]
        if over:
            raise ValueError(f"more than the row's own scope: {', '.join(over)}")
        return self


class ShemaBookProgressRow(ShemaCountedProgressRow):
    """One Bible book on the progress table, checked against the book that really exists.

    ``id`` is a key of ``app/utils/shema_books.py``'s 66, which is FE-44 §5.2's own table and
    the authority the export agrees with. Two things are refused here and the second is the
    one the issue names: a book that is not a book, and **a scope longer than the book**. A row
    claiming 60 chapters of Matthew is a project counting against a book nobody can finish, and
    it reaches the ETEN report as a denominator.

    ``name`` is **not** checked against the table. It is what the record shows, the table
    carries a Portuguese and an English spelling, and a server that refused ``Mateus`` because
    its own row says ``Matthew`` would be enforcing a display choice as data.
    """

    model_config = _DOCUMENT

    id: str

    @model_validator(mode="after")
    def _the_book_and_its_real_length(self) -> Self:
        real = chapters_in(self.id)
        if real is None:
            raise ValueError(f"{self.id}: not one of the 66 books")
        if self.chapters > real:
            raise ValueError(f"{self.id}: {self.chapters} chapters, and the book has {real}")
        return self


class ShemaOtherProgressRow(ShemaCountedProgressRow):
    """A counted scope that is not a book — FE-44's ``OtherProgressItem``: the same shape
    without the ``id``, and rolled up beside the books for that reason."""


class ShemaStoryProgressRow(BaseModel):
    """One story, and the table the roll-up deliberately ignores.

    A story row has no translated / checked / approved column, so ``rollUpProgress`` leaves the
    aggregates alone rather than zeroing them (FE-44 §7.2) — a divergence from the prototype's
    own roll-up, which would overwrite counts the form has no field to restore.

    ``audio_hours`` is ``number | string`` because the field records ranges as typed
    (``"2 a 3"``). Nothing parses it here; a server that turned it into a float would be
    deciding what a field team meant.
    """

    model_config = _DOCUMENT

    name: str = ""
    audio_hours: float | str | None = None
    record_location: str | None = None
    record_status: str | None = None
    ai_assisted: bool | None = None


class ShemaProjectPhase(BaseModel):
    """``{label, scope, date}``, typed on the record and empty on all 127 export rows.

    ``date`` is a free string and not a ``date``: it is a phase label a coordinator typed
    (*"2º semestre"* is a real answer to *when*), and this repository's date rule is about the
    columns a query compares, which this is not.
    """

    model_config = _DOCUMENT

    label: str = ""
    scope: str = ""
    date: str = ""


class ShemaProgressHistoryEntry(BaseModel):
    """One point in the trail — **produced by the server and never accepted from a client**.

    FE-44 §7.2 is explicit about why: the previous values are the server's own read of the
    record before the write, and a client that could send them could rewrite the history the
    ETEN year-end reconstruction is rebuilt from. The write shapes in ``app/models/shema.py``
    carry no ``progressHistory`` key at all, which is that rule expressed as an absence rather
    than as a check.

    ``date`` is the **actor's local day**, stamped by the write path, not a UTC day — §7.2's
    year-end boundary, where a save at 21:00 in UTC-3 lands in the next year.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    #: ``entry_date`` on the row and ``date`` on the wire — FE-44's key, which the column could
    #: not take because ``date`` is a type name in the model file.
    date: Day = Field(validation_alias="entry_date")
    translated_units: int = 0
    community_checked_units: int = 0
    approved_units: int = 0
    total_units: int | None = None

    book_progress: list[ShemaBookProgressRow] | None = None
    story_progress: list[ShemaStoryProgressRow] | None = None
    other_progress: list[ShemaOtherProgressRow] | None = None

    previous_translated: int | None = None
    previous_community: int | None = None
    previous_approved: int | None = None

    initial: bool = False
    synthetic: bool = False
    #: The submitter's name as a string; together with :attr:`form_type` the entry's
    #: provenance, and what a derived notification needs to exist at all (FE-44 §9.11).
    from_field: str | None = None
    form_type: str | None = None


class ShemaMediaAuthorization(BaseModel):
    """``{granted, by, at}`` — the decision, who made it and when.

    **The default is not authorized.** Only an explicit ``granted = true`` counts, so an item
    with no recorded decision has no authorization object at all rather than one saying
    ``false``: FE-44 §5.2 inverts the prototype's default-checked toggle, and *undecided* and
    *refused* behave identically on every path that shares something.

    ``by`` is the deciding user's name **as it was then**, which FE-44 §5.3 names as one of
    exactly two stored copies of a person's name that are correct.

    ``at`` is a day and not a moment, because FE-44 §9.0 says every date on this wire is —
    including this one by name. The column is a timestamp, so the serialiser below takes its
    date; the extra precision is the database's business and not the contract's.

    **Nothing in this file builds one**, and that absence is the rule rather than an omission:
    the three columns behind it have exactly one reader in the module
    (``app/services/shema/_media_sharing.py``, watched by a glob), so the owner builds this
    shape and hands it over. A model that read the columns itself would be the second reader
    the glob cannot see, because ``app/models/`` is deliberately outside it.
    """

    model_config = _OUTWARD

    granted: bool
    by: str = ""
    at: datetime | None = None

    @field_serializer("at")
    def _as_a_day(self, value: datetime | None) -> str | None:
        return None if value is None else value.date().isoformat()


class ShemaMediaPhoto(BaseModel):
    """``{image, caption, authorization}`` — three required keys, two of them nullable.

    :attr:`image` is ``None`` **always, for now**, and the module docstring says why: the
    photo's bytes have no serving path in this wave. A caption with no image is a shape the
    contract already has, so the console renders an empty slot rather than a broken one.
    """

    model_config = _OUTWARD

    image: None = None
    caption: str = ""
    authorization: ShemaMediaAuthorization | None = None


class ShemaProjectVideo(BaseModel):
    """``{url}`` plus an optional caption and the same per-item decision a photo carries.

    A video needs no storage adapter: the URL is an address on somebody else's service, which
    is what it already was.
    """

    model_config = _OUTWARD

    url: str = ""
    caption: str | None = None
    authorization: ShemaMediaAuthorization | None = None


class ShemaProjectMaterial(BaseModel):
    """A translated artifact the project produced — text, audio or video.

    ``dataUrl`` is **not** here: it is how the prototype kept a file inside a browser, and the
    server's answer to the same need is a storage key it has no way to serve yet. ``link`` is
    an address somebody typed and travels whole.

    ``format`` and ``durationSeconds`` are read from the file at import and never typed (FE-44
    §5.2), so they arrive here as whatever the import found.
    """

    model_config = _OUTWARD

    id: str
    kind: ShemaMaterialKind
    scope: str = ""
    file_name: str | None = None
    file_size: int | None = None
    link: str | None = None
    format: str | None = None
    duration_seconds: float | None = None
    authorization: ShemaMediaAuthorization | None = None


class ShemaNeedItem(BaseModel):
    """One need on the record — read here, written by BE-08's own tab.

    The lifecycle is **four** states: ``dropped`` is what lets a request that stopped mattering
    leave the open list without deleting the history a region is judged by. A predicate written
    as ``status != "fulfilled"`` is a bug the moment a fifth state exists, which is why
    ``is_open_need`` has one owner and no caller writes the comparison out.

    ``id`` is the row's and is emitted, which is a small departure from the frozen shape where
    a ``NeedItem`` carries none: ``docs/shema.md`` §10 item 6 hands the question to BE-08, the
    column exists either way, and a record whose items cannot be addressed cannot have one
    edited. It costs a key the console may ignore.
    """

    model_config = _OUTWARD

    id: str
    category: str = ""
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN
    description: str = ""
    estimated_value: str | None = None
    deadline: date | None = None
    prayer_shared: bool = False
    prayer_answered: bool = False
    fulfilled_by: str | None = None
    fulfilled_date: date | None = None
    dropped_date: date | None = None
    submitted_by: str | None = None
    submitted_at: date | None = None


class ShemaHealthAssessmentEntry(BaseModel):
    """One reading of a team's health — read here, appended by BE-07.

    **The per-dimension note is the data and ``notes`` is a reading of it** (FE-44 §5.2): the
    blob is derived from ``dimensionNotes`` at write time so the older display keeps working,
    and a server that stored only the blob has lost the data and cannot get it back. Both
    travel, and BE-07 owns the derivation.
    """

    model_config = _OUTWARD

    date: Day = Field(validation_alias="assessment_date")
    assessor: str = ""
    emotional: ShemaHealthLevel | None = None
    relational: ShemaHealthLevel | None = None
    spiritual: ShemaHealthLevel | None = None
    physical: ShemaHealthLevel | None = None
    notes: str = ""
    dimension_notes: dict[str, str] | None = None


class ShemaProjectRecord(BaseModel):
    """The whole record, in FE-44's frozen spelling — what the ficha's ten tabs read.

    Validated straight off a ``ShemaProject`` row; the six collections a row cannot answer
    (:attr:`needs_items`, :attr:`materials`, :attr:`media_photos`, :attr:`media_videos`,
    :attr:`progress_history`, :attr:`health_history`) are joined in by
    ``app/services/shema/read_record.py`` and default to empty, so a record built from a row
    alone is honest rather than wrong.

    **It is not a** :class:`~app.models.shema_privacy.LeavingShape`, deliberately and by
    exemption — the module docstring carries the argument and
    ``tests/test_shema/test_privacy_owners.py`` carries the three routes.
    """

    model_config = _OUTWARD

    id: str
    language_name: str = ""
    language_code: str = ""
    bridge_language: str = ""
    vitality_status: str = ""
    location: str = ""
    speaker_count: str = ""

    #: Excluded and re-exposed as :attr:`coords`, which is FE-44's frozen spelling — BE-05's
    #: card does the same and for the same reason: the database has two columns and ``[0, 0]``
    #: is a fact about the pair.
    latitude: float = Field(default=0.0, exclude=True)
    longitude: float = Field(default=0.0, exclude=True)

    translation_type: list[str] = Field(default_factory=list)
    financial_resources: list[str] = Field(default_factory=list)

    team: str = ""
    team_leader: str = ""
    mentor: str = ""
    translators: str = ""
    technical_reviewers: str = ""
    partner_org: str = ""
    team_contact: str = ""

    objective: list[str] = Field(default_factory=list)
    scope_details: str = ""

    total_units: int = 0
    total_units_type: str = ""
    translated_units: int = 0
    community_checked_units: int = 0
    approved_units: int = 0

    start_date: date | None = None
    deadline: date | None = None
    #: The **stored** status, ``None`` when nothing was stored. ``derived.status`` is what the
    #: screen shows; both travel because the record form offers the saved value as a fourth
    #: option beside its three editable ones (FE-44 §7.1).
    status: ShemaProjectStatus | None = None
    sensitivity: str = ""
    sensitive_country: bool = False
    status_comments: str = ""
    status_goal: str = ""
    org_role: str = ""

    phases: list[ShemaProjectPhase] = Field(default_factory=list)
    story_progress: list[ShemaStoryProgressRow] = Field(default_factory=list)
    book_progress: list[ShemaBookProgressRow] = Field(default_factory=list)

    health_emotional: ShemaHealthLevel | None = None
    health_relational: ShemaHealthLevel | None = None
    health_spiritual: ShemaHealthLevel | None = None
    health_assessment_date: date | None = None
    health_assessor: str = ""
    health_notes: str = ""

    prayer_requests: str = ""
    needs_pastoral_intervention: ShemaYesNo = ShemaYesNo.PT_NAO
    pastoral_intervention_name: str = ""
    needs_notes: str = ""
    notes: str = ""
    in_eten: bool = Field(default=False, serialization_alias="inETEN")
    last_updated: date | None = None

    # --- the eighteen the product added; absent means absent, never an empty default -----
    health_physical: ShemaHealthLevel | None = None
    prayer_visibility: ShemaPrayerVisibility | None = None
    prayer_requests_audio: str | None = None
    pastoral_intervention_when: str | None = None
    location2: str | None = None
    portion: str | None = None
    facilitator: str | None = None
    team_leader_contact: str | None = None
    mentor_contact: str | None = None
    objective_notes: str | None = None
    financial_notes: str | None = None
    financial_other_details: str | None = None
    other_progress: list[ShemaOtherProgressRow] | None = None
    stories_translated: str | None = None
    ready_vessels_audio_hours: str | None = None

    # --- joined in by the service; a row alone answers none of them ---------------------
    needs_items: list[ShemaNeedItem] = Field(default_factory=list)
    materials: list[ShemaProjectMaterial] = Field(default_factory=list)
    progress_history: list[ShemaProgressHistoryEntry] = Field(default_factory=list)
    health_history: list[ShemaHealthAssessmentEntry] | None = None
    media_photos: list[ShemaMediaPhoto] | None = None
    media_videos: list[ShemaProjectVideo] | None = None

    #: **The concurrency token**, excluded from the payload and handed to the client as the
    #: response's ``ETag``. It is not one of FE-44's 73 keys and adding a 74th to a frozen
    #: shape is how a contract stops being one; a header is where HTTP already keeps the
    #: version of a thing you are about to conditionally write.
    version: int = Field(default=1, exclude=True)

    #: The newest ``shema_progress_history`` entry's date, joined in by the service — the field
    #: staleness is measured from, and deliberately not ``last_updated``, which is the Pulse
    #: freshness signal the ``recent`` preset reads (FE-44 §7.3).
    #:
    #: **Excluded from the payload**: FE-44's ``Project`` has no such key, and :attr:`derived`
    #: already carries the same day as ``lastProgressUpdate``. It is a field rather than an
    #: argument because ``app/utils/shema_derivations.py``'s ``Derivable`` protocol reads it off
    #: the record, which is what keeps that file from having an opinion about how the row is
    #: found.
    last_progress_date: date | None = Field(default=None, exclude=True)

    #: FE-44 §7's nine, computed by the server for the day of the request — BE-05's shape,
    #: reused rather than restated, so the ficha's badge and the card's badge are one answer.
    derived: ShemaProjectDerived | None = None

    @computed_field(alias="coords")  # type: ignore[prop-decorator]
    @property
    def coords(self) -> tuple[float, float]:
        """``[longitude, latitude]`` — longitude first, and ``[0, 0]`` is *no coordinate*."""
        return (self.longitude, self.latitude)

    @computed_field(alias="ywamBase")  # type: ignore[prop-decorator]
    @property
    def ywam_base(self) -> str:
        """The base, served from :attr:`team` — one column under the contract's two keys.

        JOCUM is the Portuguese for YWAM and all 127 records carry the identical string in
        both, so BE-02 collapsed the columns. FE-44 §5.1 asks the server to write both from one
        input; this is that sentence on the way out, and it is one line rather than a rule
        somebody has to remember when they add a field beside it.
        """
        return self.team

    @computed_field(alias="regionalCoordinator")  # type: ignore[prop-decorator]
    @property
    def regional_coordinator(self) -> str:
        """Always ``""`` — the region's roles are read from the org chart. Module docstring."""
        return ""

    @computed_field(alias="obtLabPerson")  # type: ignore[prop-decorator]
    @property
    def obt_lab_person(self) -> str:
        """Always ``""`` — see :attr:`regional_coordinator`."""
        return ""

    @computed_field(alias="resourceCirclePerson")  # type: ignore[prop-decorator]
    @property
    def resource_circle_person(self) -> str:
        """Always ``""`` — see :attr:`regional_coordinator`."""
        return ""
