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

**Three keys are refused rather than ignored.** ``regionalCoordinator``, ``obtLabPerson`` and
``resourceCirclePerson`` have no column at all: the region's three role-holders live in
``shema_region_teams`` and are read by reference. FE-44 §5.3 asks the server to *reject a
write that fills them, or drop the columns*, and this module does both — the table dropped
them, and a payload that carries one is refused by name instead of silently discarded, so a
client that still believes it owns those fields learns that it does not.

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

**The wire spelling is not decided here.** These fields are the house's snake_case, which is
what ``app/models/resource_request.py`` sends and receives, while FE-44's frozen types are
camelCase. Whoever writes the first endpoint (BE-05 for the read, BE-06 for the write) decides
whether the mapping is a Pydantic alias generator on this side or INT-02's client on the
other; naming the choice is this file's job, and making it silently is not.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.shema_enums import (
    ShemaProjectStatus,
    ShemaYesNo,
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


class ShemaProjectUpdate(BaseModel):
    """A partial write of a record: every field optional, absent meaning unchanged.

    ``extra="forbid"`` is what makes the org-chart refusal below reachable at all for a
    misspelling, and what stops a client inventing a column. The three org-chart keys get
    their own message anyway, because *extra field not permitted* is true and useless to
    somebody holding a contract that still lists them.
    """

    model_config = ConfigDict(extra="forbid")

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
    in_eten: bool | None = None

    total_units: int | None = Field(default=None, ge=0)
    total_units_type: str | None = None
    #: No ``translated <= total`` rule, here or in the database: three real records violate
    #: it and 23 have a scope of zero. The scope is what is wrong in those rows.
    translated_units: int | None = Field(default=None, ge=0)
    community_checked_units: int | None = Field(default=None, ge=0)
    approved_units: int | None = Field(default=None, ge=0)

    book_progress: list[dict[str, Any]] | None = None
    story_progress: list[dict[str, Any]] | None = None
    other_progress: list[dict[str, Any]] | None = None
    phases: list[dict[str, Any]] | None = None

    start_date: date | None = None
    deadline: date | None = None
    last_updated: date | None = None

    status: ShemaProjectStatus | None = None
    status_comments: str | None = None
    status_goal: str | None = None
    stories_translated: str | None = None
    ready_vessels_audio_hours: str | None = None

    #: Guarded by ``app/services/shema/_consent.py`` once it exists. Absent is not ``""``.
    prayer_requests: str | None = None
    prayer_visibility: str | None = None
    prayer_requests_audio: str | None = None

    needs_pastoral_intervention: ShemaYesNo | None = None
    pastoral_intervention_name: str | None = None
    pastoral_intervention_when: str | None = None

    needs_notes: str | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _the_org_chart_owns_its_own_names(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sent = [key for key in OWNED_BY_THE_ORG_CHART if key in data]
            if sent:
                raise ValueError(
                    f"{', '.join(sent)}: the region's role-holders are read from the org "
                    "chart and are not stored on a project"
                )
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
