"""What a client may send about a Shemá project record.

This is the half of the record's optionality the DDL cannot carry.

``app/db/models/shema.py`` holds the other half and its module docstring holds the rule: the
55 columns the Notion export has are NOT NULL with an empty default, the 18 the product added
are nullable, and **the four fields required to save carry no constraint in the database**,
because two of the four are empty across all 127 export records and a ``CHECK`` would refuse
the seed on its first row. This file is where that rule actually lives.

**Exactly four, and nothing more.** ``missingRequired`` in the console's record store is the
only place that decides what is missing, and it names ``languageName``, ``bridgeLanguage``,
``team`` and ``objective`` (FE-44 §5.1.1). Everything else may be saved empty, and the seed
proves it — 27 of the 55 export columns are empty on all 127 records. Validating a fifth
field makes the record uneditable for exactly the field teams whose data is this thin.

**Three keys are refused when they are filled and dropped when they are empty.**
``regionalCoordinator``, ``obtLabPerson`` and ``resourceCirclePerson`` have no column at all:
the region's three role-holders live in ``shema_region_teams`` and are read by reference.
FE-44 §5.3 asks the server to *reject a write that fills them, or drop the columns*, and this
module does both — the table dropped them, and a payload that **fills** one is refused by
name instead of silently discarded, so a client that still believes it owns those fields
learns that it does. BE-02 refused the key itself and BE-06 narrowed that to the value, for
the reason the validator carries: the three are *required* keys of the interface FE-44 §9.3
has ``POST`` take whole, so refusing the key refuses every create the contract describes.

**The health projection is not writable here, and that is the rule rather than an omission.**
``health_emotional`` and its three siblings, ``health_assessment_date``, ``health_assessor``
and ``health_notes`` are a projection of the newest ``shema_health_assessments`` row (FE-44
§5.1, §7.4). ``recordAssessment`` is their only writer — it appends and re-projects in one
step — so accepting them on the record's own write would let a ``PATCH`` report a team as
assessed with no assessment behind it, which is the second truth §5.3 forbids. BE-07 owns the
endpoint that writes them.

Neither are the aggregates the server produces: the progress history entry is **produced by
the server and never accepted from the client** (FE-44 §7.2), ``region_key`` is derived from
``location`` by one owner, and ``source`` and ``approved_units_unverified`` are BE-16's, set
by a seed and not by a payload.

**Absent and empty are different, and that is what every ``| None = None`` here is for.** A
field the payload does not carry is unchanged; a field carrying ``""`` was answered with
nothing. It matters most for the prayer request: FE-44 §8.2 records that an unconditional
write of ``""`` on every save deletes an existing request as a side effect of an unrelated
action, so *not sent* has to be a state this shape can express.

**The wire spelling is camelCase, and BE-06 decided it here** — the question this file asked
and left for whoever wrote the first endpoint. BE-05 answered the read with a *serialisation*
alias over snake_case attributes (``app/models/shema_projects.py``) and this is the mirror: a
*validation* alias, so a client patches in the spelling it reads. ``populate_by_name`` keeps
the house's snake_case accepted for a caller inside this repository — a test, BE-16's seed,
BE-12's import — which is what stops the decision costing anything on this side. The
alternative was a translation table in INT-03's client, read on every save of a
seventy-three-field record. See :data:`_INWARD`.

**And the record's read shape is** ``app/models/shema_record.py``, which is a separate file
for the reason §2.2 gives: this one is what a client *sends*, and the two have different
fields, different optionality and different rules. The sub-shapes the two share — the progress
rows, the phase — live with the read, because the read is the shape that has to be FE-44's
``Project`` key for key.
"""

from datetime import date
from typing import Any

from pydantic import (
    AliasChoices,
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import (
    ShemaPrayerVisibility,
    ShemaProjectStatus,
    ShemaYesNo,
)
from app.models.shema_need import ShemaNeedWrite
from app.models.shema_record import (
    ShemaBookProgressRow,
    ShemaOtherProgressRow,
    ShemaProjectPhase,
    ShemaStoryProgressRow,
)

#: The only fields a save is refused for, per FE-44 §5.1.1.
REQUIRED_TO_SAVE: tuple[str, ...] = ("language_name", "bridge_language", "team", "objective")

#: Keys the contract still carries and this schema deliberately has no column for.
OWNED_BY_THE_ORG_CHART: tuple[str, ...] = (
    "regional_coordinator",
    "regionalCoordinator",
    "obt_lab_person",
    "obtLabPerson",
    "resource_circle_person",
    "resourceCirclePerson",
)

#: Both spellings of the base, which is the same column as :attr:`ShemaProjectUpdate.team`.
THE_BASE: tuple[str, ...] = ("ywam_base", "ywamBase")

#: **The wire is camelCase inward too, and this is where that half is decided** (BE-06).
#:
#: The module docstring left the spelling to whoever wrote the first endpoint — BE-05 for the
#: read, this issue for the write — and BE-05 answered camelCase by a *serialisation* alias.
#: The write is the mirror: a **validation** alias, so a client posts and patches in exactly
#: the spelling it reads, and ``populate_by_name`` keeps the house's snake_case working for a
#: caller inside this repository (a test, a seed, BE-12's import). One shape, two spellings
#: accepted, one emitted — and no translation table in INT-03's client, which for a
#: seventy-three-field record is a second place to be wrong on every save.
_INWARD = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel),
)


class ShemaProjectUpdate(BaseModel):
    """A partial write of a record: every field optional, absent meaning unchanged.

    ``extra="forbid"`` is what makes the org-chart refusal below reachable at all for a
    misspelling, and what stops a client inventing a column. The three org-chart keys get
    their own message anyway, because *extra field not permitted* is true and useless to
    somebody holding a contract that still lists them.

    **A tab is what a partial write is for.** The ficha has ten of them and each saves the
    fields it owns; a screen that sent the whole record back would have tab 3 writing tab 7's
    values as they stood when tab 3 was opened — which is the silent overwrite the version
    guard catches between *people* and could not catch inside one person's own payload. So
    every field is ``| None`` and absent means unchanged, and ``model_fields_set`` is what the
    write path reads rather than the values themselves.
    """

    model_config = _INWARD

    language_name: str | None = None
    language_code: str | None = None
    bridge_language: str | None = None
    vitality_status: str | None = None
    location: str | None = None
    location2: str | None = None
    speaker_count: str | None = None
    #: ``[longitude, latitude]`` — longitude first, and ``[0, 0]`` is *no coordinate*.
    coords: tuple[float, float] | None = None
    sensitive_country: bool | None = None
    sensitivity: str | None = None

    team: str | None = None
    team_leader: str | None = None
    mentor: str | None = None
    translators: str | None = None
    technical_reviewers: str | None = None
    partner_org: str | None = None
    team_contact: str | None = None
    team_leader_contact: str | None = None
    mentor_contact: str | None = None
    facilitator: str | None = None

    objective: list[str] | None = None
    scope_details: str | None = None
    objective_notes: str | None = None
    translation_type: list[str] | None = None
    portion: str | None = None
    financial_resources: list[str] | None = None
    financial_notes: str | None = None
    financial_other_details: str | None = None
    org_role: str | None = None
    #: ``inETEN`` on the wire, which no camel-caser produces from ``in_eten`` — the one key
    #: of the seventy-three that has to be spelled out.
    in_eten: bool | None = Field(
        default=None, validation_alias=AliasChoices("inETEN", "in_eten", "inEten")
    )

    total_units: int | None = Field(default=None, ge=0)
    total_units_type: str | None = None
    #: No ``translated <= total`` rule, here or in the database: three real records violate
    #: it and 23 have a scope of zero. The scope is what is wrong in those rows.
    translated_units: int | None = Field(default=None, ge=0)
    community_checked_units: int | None = Field(default=None, ge=0)
    approved_units: int | None = Field(default=None, ge=0)

    #: **The batch.** A progress tab saves its whole table, and the rows are typed rather
    #: than free dictionaries so that *every* bad row in a batch is named at once, located by
    #: index — a book that is not a book, a scope longer than the book, a count above its own
    #: row's scope. Pydantic collects a list's errors before it raises, so *a partial failure
    #: applies nothing* is true of the validation half by construction rather than by a loop
    #: remembering to keep going. ``app/models/shema_record.py`` holds the rules.
    book_progress: list[ShemaBookProgressRow] | None = None
    #: The one table the roll-up ignores: a story row has no counts to add (FE-44 §7.2).
    story_progress: list[ShemaStoryProgressRow] | None = None
    other_progress: list[ShemaOtherProgressRow] | None = None
    phases: list[ShemaProjectPhase] | None = None

    start_date: date | None = None
    deadline: date | None = None
    last_updated: date | None = None

    status: ShemaProjectStatus | None = None
    status_comments: str | None = None
    status_goal: str | None = None
    stories_translated: str | None = None
    ready_vessels_audio_hours: str | None = None

    #: Guarded by ``app/services/shema/_consent.py``. Absent is not ``""``.
    prayer_requests: str | None = None
    #: Typed, not free text: the column is the enum and the two members are the whole
    #: vocabulary, so ``"publico"`` is refused by the shape instead of by the database.
    #: NULL means ``coordenacao`` and an explicit ``null`` is how a request is taken back off
    #: the wall — which is a state this shape can express only because *absent* is a third
    #: answer beside it (``model_fields_set``).
    prayer_visibility: ShemaPrayerVisibility | None = None
    prayer_requests_audio: str | None = None

    needs_pastoral_intervention: ShemaYesNo | None = None
    pastoral_intervention_name: str | None = None
    pastoral_intervention_when: str | None = None

    needs_notes: str | None = None
    notes: str | None = None

    #: **The needs tab's batch** (BE-08). Needs travel with the project and are saved by this
    #: ``PATCH`` — there is no needs endpoint in wave 1, and adding one would give
    #: ``needsItems`` a second owner (``docs/shema.md`` §5.4, FE-44 §9.5).
    #:
    #: It is an **upsert batch and not a replacement of the table**: a row with an ``id`` moves
    #: that need, a row without one is a new need, and a need *absent* from the list is
    #: untouched. That is this class's own rule — absent means unchanged, all the way down —
    #: and it is also the aggregate's invariant, because ``dropped`` exists precisely so that a
    #: request that stopped mattering leaves the open list without being deleted.
    #: ``app/services/shema/_needs.py`` carries the argument.
    needs_items: list[ShemaNeedWrite] | None = None

    @model_validator(mode="before")
    @classmethod
    def _the_org_chart_owns_its_own_names(cls, data: Any) -> Any:
        """Refuse a write that **fills** a role-holder; accept and drop one that is empty.

        FE-44 §5.3's requirement is worded on the value — *reject a write that fills them, or
        drop the columns* — and BE-02 did both, refusing the key itself. **BE-06 narrows that
        to the filled case**, because this is the issue that finds out what it costs: FE-44
        §9.3 froze ``POST /api/shema/projects`` as taking a whole ``Project``, the three keys
        are **required** in that interface, and the fixtures assert they are always ``""``. So
        the stricter reading refuses every create the contract describes — a 422 on the one
        payload the client is specified to send, over three empty strings.

        Empty is dropped rather than stored: there is no column, and that is still the whole
        point. A filled one keeps the message that names the chart, because *extra field not
        permitted* is true and useless to somebody holding a contract that still lists them.
        """
        if isinstance(data, dict):
            filled = [key for key in OWNED_BY_THE_ORG_CHART if data.get(key)]
            if filled:
                raise ValueError(
                    f"{', '.join(filled)}: the region's role-holders are read from the org "
                    "chart and are not stored on a project"
                )
            data = {key: value for key, value in data.items() if key not in OWNED_BY_THE_ORG_CHART}
        return data

    @model_validator(mode="before")
    @classmethod
    def _the_base_and_the_team_are_one_input(cls, data: Any) -> Any:
        """``ywamBase`` writes ``team``, because BE-02 collapsed the two columns into one.

        FE-44 §5.1: JOCUM is the Portuguese for YWAM, all 127 records carry the identical
        string in both, the record shows **one** input and *"the server writes both from one
        input"*. With one column that sentence becomes: the key is accepted and folded.

        **Two different values are refused rather than reconciled.** No screen can produce
        them, so a payload that carries both is a client that believes the columns are two
        facts — and picking one silently is how the drift BE-02 removed comes back through a
        door nobody is watching.
        """
        if not isinstance(data, dict):
            return data
        sent = [key for key in THE_BASE if key in data]
        if not sent:
            return data
        values = {data[key] for key in sent}
        team = data.get("team")
        if "team" in data and data["team"] not in values:
            raise ValueError(
                "team and ywamBase are one input on one column: send one, or send both equal"
            )
        if len(values) > 1:
            raise ValueError("ywamBase sent twice with two values")
        data = {key: value for key, value in data.items() if key not in THE_BASE}
        data["team"] = team if "team" in data else values.pop()
        return data

    @field_validator(*REQUIRED_TO_SAVE)
    @classmethod
    def _a_required_field_is_not_blanked(cls, value: Any) -> Any:
        """Sending one of the four empty is a save the console would have refused.

        Not sending it at all is fine — that is an untouched field, and this is a partial
        write. The distinction is the whole reason every field here is ``| None``.
        """
        if value is not None and not value:
            raise ValueError("required to save: send a value or leave the field out")
        return value


class ShemaProjectCreate(ShemaProjectUpdate):
    """A new record. The slug is the id, minted by the client, and the four are mandatory.

    A create is an update with four fields promoted, which is the relation stated once
    instead of a second copy of seventy. What it is **not** is one class with a flag: the
    console refuses a save that is missing any of the four and accepts a patch that touches
    none of them, so *which rules ran* is a fact about which shape arrived and not a runtime
    question.

    ``id`` is the export's slug and stays the address — ``afrikaans-kaaps``,
    ``purepecha-de-capacuaro``. FE-44 §9.3 has the client mint it, and BE-16 must not mint
    new ones for the 127 that already have theirs.
    """

    id: str = Field(min_length=1, max_length=120)
    language_name: str = Field(min_length=1)
    bridge_language: str = Field(min_length=1)
    team: str = Field(min_length=1)
    objective: list[str] = Field(min_length=1)
