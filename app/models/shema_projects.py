"""What ``GET /api/shema/projects`` asks for and what it answers.

**The wire is camelCase, and this is the file that decides it.**
``app/models/shema.py`` deliberately left the project record's spelling to whoever wrote its
first endpoint — *"naming the choice is this file's job, and making it silently is not"* — and
this is that endpoint. The choice is FE-44's own spelling, on both halves:

* **The response** is camelCase by a serialisation alias over snake_case attributes, which is
  ``app/models/shema_session.py``'s mechanism and keeps the Python side in the house's habit.
  The alternative was a translation table in INT-02's client, which is a second place for a
  73-field shape to be wrong, read on every request to the busiest screen in the product.
* **The query string is the screen's own URL**, key for key:
  ``src/utils/filterSerialisation.ts`` already encodes a saved view as ``?status=…&continent=…
  &presets=attention,recent&q=…&sort=…``, and this endpoint accepts exactly that. A shared
  link, a saved view and a request are then the same string, so *the count is by construction
  what the link returns* (FE-44 §9.2) holds across the network too.

**The list item is an allowlist, not the record.** ``redactProjectForExport`` is the precedent
(FE-44 §8.4): a field added to the record later stays out of this shape until somebody puts it
in, which is the property that makes *what leaves* reviewable in a diff. What is in it is what
the Projetos screen reads — the card, the sixteen facets, the five sorts and the Atlas marker.
What is deliberately out: the three contact fields (FE-44 §8.1 rule 5 gates them on every
shape that leaves), the prayer columns (``app/services/shema/_consent.py`` is their only
reader, and the wall is BE-09's), the progress tables and ``source`` (BE-06's record read), and
the org-chart names, which no project row holds at all (``docs/shema.md`` §5.8).

**It is a leaving shape, and that is BE-04's decision inherited rather than this issue's.**
``app/models/shema_privacy.py`` names *the collection read* among the shapes that inherit
:class:`~app.models.shema_privacy.LeavingShape`, and ``COORDINATION_ROUTES`` in
``tests/test_shema/test_privacy_owners.py`` names BE-06's three record routes and
**not this one** — which is why that list is keyed by method and path rather than by path
alone: exempting ``/api/shema/projects`` would have switched the audit off for this shape
in the same line that exempted the create. So a card in a sensitive country carries its region
where its country would be, and the facets built from these cards say the same thing the cards
do — which is how the DoD's fourth line becomes true of the counts and not only of the results.

**The derived block is the parity artifact's row.** ``derived`` carries FE-44 §7's nine
derivations under the keys ``dataJsParity.json`` uses for them, so the acceptance file, the
wire shape and ``app/utils/shema_derivations.py``'s return value are one shape rather than
three that have to be kept in step. The console stops computing them: two implementations of
*is this project stale* diverge, and the divergence shows as a card that says one thing and a
filter that disagrees.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Self

from fastapi import Query
from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaNeedStatus,
    ShemaNeedUrgency,
    ShemaProjectStatus,
    ShemaRegionKey,
)
from app.models.shema_privacy import LeavingShape
from app.utils.shema_derivations import (
    Derivations,
    OverallHealth,
    ProjectPriority,
    StaleStatus,
)
from app.utils.shema_facets import PRESETS

#: Read models speak camelCase outward and snake_case inward. A **serialisation** alias and
#: not a validation one, deliberately: these shapes are validated off ``ShemaProject`` rows by
#: attribute name, and a validation alias would make ``from_attributes`` look for
#: ``languageName`` on a row that has ``language_name``.
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: The five orders the Projetos toolbar offers, and the one it opens on.
SORT_KEYS: tuple[str, ...] = ("deadline", "name", "progress", "team", "health")
DEFAULT_SORT = "deadline"

#: The largest page this endpoint will cut. It is not a performance ceiling at 127 records —
#: it is the number that stops a client from discovering, the day the table is large, that the
#: shape it depends on was *the whole collection*.
MAX_PAGE_SIZE = 500


class ShemaNeedCard(BaseModel):
    """A need, as the three need-shaped facets and two presets read it.

    Not the needs tab's shape: no description, no estimated value, no dates, no fulfiller.
    Those belong to the record (BE-08), and a list endpoint that carried them would be
    shipping the free text of every need on every project to draw four checkboxes.
    """

    model_config = _OUTWARD

    #: Free text, not an enum: FE-44's nine categories are a frontend vocabulary and
    #: ``shema_needs.category`` is a ``String(60)`` on purpose (BE-02).
    category: str = ""
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN
    #: The two prayer flags on a **need** — not the three guarded prayer columns on the
    #: project, which have one reader and it is not this shape.
    prayer_shared: bool = False
    prayer_answered: bool = False


class ShemaProjectDerived(BaseModel):
    """FE-44 §7's nine derivations, under ``dataJsParity.json``'s own keys.

    The server's answer, not a hint: the console reads these instead of recomputing them, which
    is the whole point of the integration. ``progress`` is a percentage and is **not clamped**
    — three real records report more translated units than their scope holds, and the number
    saying 624% is what sends somebody to look at the scope.
    """

    model_config = _OUTWARD

    status: ShemaProjectStatus
    health: OverallHealth
    stale: StaleStatus | None
    progress: float
    priority: ProjectPriority
    health_score: int
    days_since_update: int | None
    last_progress_update: date | None
    region: ShemaRegionKey

    @classmethod
    def of(cls, derivations: Derivations) -> Self:
        """Build from :class:`~app.utils.shema_derivations.Derivations`, field for field."""
        return cls(
            status=derivations.status,
            health=derivations.health,
            stale=derivations.stale,
            progress=derivations.progress,
            priority=derivations.priority,
            health_score=derivations.health_score,
            days_since_update=derivations.days_since_update,
            last_progress_update=derivations.last_progress_update,
            region=derivations.region,
        )


class ShemaProjectCard(LeavingShape):
    """One project, as the Projetos screen reads it — filtered, counted, sorted and drawn.

    Validated straight off a ``ShemaProject`` row, which is what picks up ``sensitive_country``
    and ``region_key`` and applies the redaction without the service naming either column
    (``app/models/shema_privacy.py``). The four things a row cannot answer —
    :attr:`last_progress_date`, :attr:`needs`, :attr:`has_media` and :attr:`search_text` — are
    joined in by ``app/services/shema/browse_projects.py`` and default to the empty answer, so
    a card built from a row alone is honest rather than wrong.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    #: The export's slug, which is the address every screen, URL and saved view carries.
    id: str
    language_name: str = ""
    language_code: str = ""
    bridge_language: str = ""
    vitality_status: str = ""
    #: A string because the field records ranges and notes as typed, never a count.
    speaker_count: str = ""

    #: Withheld to the region name; never to ``""`` — a consumer that receives the region can
    #: still group, count and draw the record (FE-44 §8.1 rule 1).
    location: str = ""
    location2: str | None = None
    #: Excluded from the payload and re-exposed as :attr:`coords`, which is FE-44's frozen
    #: spelling. They are two columns because the database has two, and one pair because
    #: ``[0, 0]`` is *no coordinate* and that is a fact about the pair.
    latitude: float = Field(default=0.0, exclude=True)
    longitude: float = Field(default=0.0, exclude=True)
    #: The base. Withheld to ``""``, because ``YWAM Egypt`` beside a withheld ``Egypt`` has
    #: redacted nothing (FE-44 §8.1 rule 3).
    team: str = ""

    team_leader: str = ""
    mentor: str = ""
    partner_org: str = ""
    org_role: str = ""
    facilitator: str | None = None

    objective: list[str] = Field(default_factory=list)
    translation_type: list[str] = Field(default_factory=list)
    financial_resources: list[str] = Field(default_factory=list)
    portion: str | None = None
    scope_details: str = ""

    total_units: int = 0
    total_units_type: str = ""
    translated_units: int = 0
    community_checked_units: int = 0
    approved_units: int = 0

    #: The **stored** status, NULL when nothing was stored. What the screen shows is
    #: ``derived.status``, which falls back to progress; both are here because the record form
    #: has to be able to offer the saved value as an option (FE-44 §7.1).
    status: ShemaProjectStatus | None = None
    status_goal: str = ""
    status_comments: str = ""

    health_emotional: ShemaHealthLevel | None = None
    health_relational: ShemaHealthLevel | None = None
    health_spiritual: ShemaHealthLevel | None = None
    health_physical: ShemaHealthLevel | None = None
    health_assessment_date: date | None = None
    health_assessor: str = ""
    health_notes: str = ""

    start_date: date | None = None
    deadline: date | None = None
    #: *The Pulse cycle is covered* — a freshness signal and never a received form. The
    #: ``recent`` preset reads this; staleness reads :attr:`last_progress_date`.
    last_updated: date | None = None
    completed_date: date | None = None

    in_eten: bool = False

    needs_notes: str = ""
    #: Internal by default and travelling here because the collection read is a *coordenação*
    #: destination; ``can_export_notes`` refuses them for ``publico`` (FE-44 §8.4), which is
    #: BE-14's path and not this one.
    notes: str = ""

    #: The newest ``shema_progress_history`` entry's date — not a column on the project, and
    #: the field staleness is measured from. ``None`` is *nothing was ever recorded*, which is
    #: 119 of the 127 export records.
    last_progress_date: date | None = None
    needs: list[ShemaNeedCard] = Field(default_factory=list)
    #: Whether any photo or video on the record has content. Content, not authorization: the
    #: facet answers *is there anything here*, and whether it may be **shared** is
    #: ``_media_sharing.py``'s question on a path that shares something.
    has_media: bool = False
    #: The haystack ``app/services/shema/_redaction.py`` allows a search to match this project
    #: on. Excluded from the payload: it is a projection of fields already in it, and shipping
    #: it would invite a second search implementation downstream.
    search_text: str = Field(default="", exclude=True)

    #: FE-44 §7's nine, computed by the server for the day of the request.
    derived: ShemaProjectDerived | None = None

    @computed_field(alias="coords")  # type: ignore[prop-decorator]
    @property
    def coords(self) -> tuple[float, float]:
        """``[longitude, latitude]`` — **longitude first**, as every consumer here expects.

        Read off the already-withheld columns, so a sensitive project plots at its region's
        centroid and no caller has to know that it did. ``[0, 0]`` means *no coordinate* and
        is not the Gulf of Guinea; ``hasPlottableCoords`` is the frontend's owner of that
        reading and the server keeps the number the export gave rather than deciding for it.
        """
        return (self.longitude, self.latitude)

    @field_validator("objective", "translation_type", "financial_resources", mode="before")
    @classmethod
    def _tolerate_a_null_array(cls, value: Any) -> Any:
        """A JSON array column that was written NULL reads as the empty list.

        ``JSON(none_as_null=True)`` lets a row hold SQL NULL where the schema means ``[]``, and
        a card is not the place to discover it: the facet pass iterates these three, and a
        ``None`` there would be a 500 on the busiest screen for one badly written row.
        """
        return [] if value is None else value


class ShemaFacetCounts(BaseModel):
    """The sidebar's numbers, from the same pass that produced the list.

    Three dictionaries rather than sixteen named fields, and that is deliberate: the sixteen
    groups are a vocabulary ``app/utils/shema_facets.py`` owns, and sixteen fields here would
    be a second copy of it that goes stale the first time a group is added. A group whose
    vocabulary is short and closed reports every option including the zeros, so the sidebar can
    grey a checkbox out; every other group is sparse, which for ``continent`` is the same
    privacy property the per-region count already has — a zero beside an unreachable region
    would answer *there is nothing there*.
    """

    model_config = _OUTWARD

    #: ``{group: {option: count}}`` over :data:`~app.utils.shema_facets.FACET_GROUPS`.
    groups: dict[str, dict[str, int]] = Field(default_factory=dict)
    #: One number per preset — each is a single toggle, not a group of options.
    presets: dict[str, int] = Field(default_factory=dict)
    #: What each group's total would be with *that group's* filter cleared: the number the
    #: *All* row of a group shows, and the one that makes clearing a filter predictable.
    group_all: dict[str, int] = Field(default_factory=dict)


class ShemaProjectPage(BaseModel):
    """The list, its counts and where the window sits — one envelope, always together.

    **The counts are not optional and there is no way to ask for the filter without them.**
    FE-44 §9.1 froze this endpoint as the whole scoped collection and named the one shape the
    server may take when that stops being enough: *the filter and the counts together, in one
    endpoint, never the filter alone*. A filtered list with counts computed elsewhere is the
    defect that note exists to prevent, and an envelope that always carries both is that rule
    written as a type instead of as a warning.

    With no query parameters this is still the whole collection the caller's role and region
    allow, unpaged — so §9.1's own default survives and the console's one-pass ``filterProjects``
    keeps working over :attr:`items` unchanged.
    """

    model_config = _OUTWARD

    items: list[ShemaProjectCard]
    counts: ShemaFacetCounts
    #: How many projects matched the filters — what the header reads and what paging divides.
    matched: int
    #: How many the caller reaches at all, before any filter. Both are here because a screen
    #: with only one of them cannot tell an empty region from an over-narrow filter.
    total: int
    limit: int | None = None
    offset: int = 0
    sort: str = DEFAULT_SORT
    #: How many of :attr:`items` had their place reduced, or ``None`` when none were — the
    #: visible overlay FE-44 §8.1 asks the map for. Never ``0``: a file with no sensitive
    #: projects gets no withheld note rather than a line about their absence.
    locations_withheld: int | None = None


class ShemaProjectQuery(BaseModel):
    """Every filter the Projetos screen offers, read from the query string it already writes.

    The names are ``src/utils/filterSerialisation.ts``'s, key for key — the free-text three,
    the thirteen enums, ``presets`` as a comma list, ``q``, ``sort`` — so a saved view's URL
    and a request to this endpoint are the same string. That is not a convenience: it is what
    makes *the count is by construction what the link returns* survive the trip across the
    network.

    **Nothing here is validated against a vocabulary, and that is a decision.** FE-44's
    Appendix A freezes the lists and the frontend already holds them; a server-side allowlist
    would be a second copy that refuses a value the day the client adds one — and the failure
    mode of an unknown value is a facet that counts nothing, which is the honest answer to
    *show me the projects whose objective is Xyz*. The two places a bad value could do harm
    are paging and ordering, and both are bounded below.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(validation_alias=to_camel),
        extra="forbid",
    )

    #: Free text. Matched against ``_redaction.py``'s haystack, unaccented and case-folded.
    search: str | None = Field(default=None, validation_alias="q")

    team: str | None = None
    country: str | None = None
    vitality: str | None = None

    status: str | None = None
    health: str | None = None
    objective: str | None = None
    financial: str | None = None
    stale: StaleStatus | None = None
    continent: str | None = None
    translation_type: str | None = None
    need_category: str | None = None
    eten: str | None = None
    sensitive: str | None = None
    progress_range: str | None = None
    has_media: str | None = None
    has_open_needs: str | None = None

    #: The four presets as one comma-separated parameter, which is how the screen's URL
    #: carries them. Parsed into the four booleans below.
    presets: str | None = None

    sort: str = DEFAULT_SORT
    #: **Absent means the whole scoped collection**, which is FE-44 §9.1's frozen default kept
    #: as the default rather than as a special case. A window is something a caller asks for.
    limit: int | None = Field(default=None, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(default=0, ge=0)

    attention: bool = False
    prayer: bool = False
    celebrate: bool = False
    recent: bool = False

    @model_validator(mode="after")
    def _read_the_presets_and_the_sort(self) -> Self:
        """Expand ``presets=attention,recent`` and fall back to the default order.

        An unknown preset name is ignored rather than refused — the parameter is a list the
        client owns and a saved view from a newer console must not 422 an older server. An
        unknown ``sort`` falls back to ``deadline``, which is what ``decodeView`` does with
        the same parameter on the other side.
        """
        named = {part.strip() for part in (self.presets or "").split(",") if part.strip()}
        for preset in PRESETS:
            if preset in named:
                setattr(self, preset, True)
        if self.sort not in SORT_KEYS:
            self.sort = DEFAULT_SORT
        return self


#: The whole filter set as **one** query-model dependency (FastAPI 0.115's own feature), and
#: not twenty-three ``Query(...)`` parameters on a handler. Two reasons, and the second is the
#: one that matters: the pass downstream takes the filters as a single object, so a handler
#: that unpacked them would only have to pack them again; and ``extra="forbid"`` on the model
#: makes a misspelled parameter a 422 rather than a filter that silently does not apply —
#: which, on a screen whose whole promise is that the numbers agree with the list, is the
#: difference between a wrong answer and an error message.
ProjectQuery = Annotated[ShemaProjectQuery, Query()]
