"""The org chart on the wire — FE-44 §5.3's frozen shapes, and the one field added beside them.

``Region``, ``RegionTeam``, ``RoleChange`` and ``SaveOutcome`` are frozen
(``src/types/region.ts``, ``src/types/team.ts``) and are reproduced here field for field. The
spelling is camelCase by alias over the house's snake_case attributes, which is
``app/models/shema_session.py``'s mechanism and for its reason: the Python side stays the
repository's, FastAPI serialises by alias, and nothing in this module holds two spellings of
one name.

``from`` is a Python keyword, so :class:`RoleChange` carries ``from_holder`` with
``alias="from"``. That is not a rename — the wire says ``from``, which is what the console
reads, and the attribute is the only thing that had to move.

**What is added, and why it is a second shape rather than a field on the frozen one.**
:class:`RegionWithAccounts` is :class:`Region` plus ``teamAccounts``: the Tripod account of
each seat's holder, where they have one. It is what ``GET /regions/{key}/team`` answers the
editor, and it is **not** what ``GET /regions`` answers its four consumers — that collection
is a directory of offices and carries a name per seat and nothing else, so a user id, which
is an internal identifier, leaves through one surface and never through the one every member
reads. ``team`` stays three strings exactly as frozen on both, so a console written against
the contract keeps working; widening ``team`` into three objects would have been the same
information and a broken client.

**Dates are** ``YYYY-MM-DD`` (FE-44 §9.0), ``changedAt`` included, and the day is the **UTC**
day. ``docs/shema.md`` §6.5's *actor's local day* rule is the progress stamp's and cannot be
applied here without inventing something: no account in this repository stores a timezone, so
a "local" day would be the server's offset wearing the actor's name. The trail says which UTC
day, and says it consistently.

**``labelKey`` is served even though FE-44 §9.0 says an endpoint returns no vocabulary the
frontend already has.** §9.10 freezes ``Region`` as ``{key, labelKey, team}``, so the
exception is the contract's own; the value is derived from the key rather than typed, which
keeps ``REGIONS`` the single list on both sides.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


def label_key_for(region_key: str) -> str:
    """The console's ``REGIONS`` entry for a key: ``south-america`` → ``continent_south_america``.

    Derived rather than tabulated. A seven-row table here would be a second copy of
    ``src/constants/regions.ts``, and the first thing to drift when an eighth region is not
    added to both.
    """
    return f"continent_{region_key.replace('-', '_')}"


class RegionTeam(BaseModel):
    """Three names, one per seat. **Frozen** — ``RegionTeam`` in ``src/types/region.ts``.

    Empty is a real state and not a gap: twenty-one seats ship unassigned on purpose, because
    the prototype's names were real people hardcoded in a file (FE-44 §5.3). Nothing here
    defaults to a name and nothing may.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    coordinator: str = ""
    obt_lab: str = Field(default="", alias="obtLab")
    resource_circle: str = Field(default="", alias="resourceCircle")


class RegionTeamAccounts(BaseModel):
    """The account behind each seat, where the holder has one. ``None`` means *not linked*.

    Not part of :class:`RegionTeam`, because that shape is frozen, and not merged into it,
    because the two answer different questions: ``RegionTeam`` says **who** the product points
    at and this says **which login that is**. ``app/db/models/shema_org_chart.py`` carries the
    argument for why the first never resolves through the second.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    coordinator: str | None = None
    obt_lab: str | None = Field(default=None, alias="obtLab")
    resource_circle: str | None = Field(default=None, alias="resourceCircle")


class Region(BaseModel):
    """One region and its three seats. **Frozen** — ``Region`` in ``src/types/region.ts``."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    label_key: str = Field(alias="labelKey")
    team: RegionTeam


class RegionWithAccounts(Region):
    """The editor's read: the frozen shape, plus the account behind each seat.

    A subclass rather than an optional field on :class:`Region`, so the wide read cannot
    carry an account even by accident: the shape the collection serialises has no field for
    the answer, which is a stronger guarantee than a field left ``None``.
    """

    team_accounts: RegionTeamAccounts = Field(alias="teamAccounts")


class RegionTeamSave(BaseModel):
    """What ``PUT /api/shema/regions/{key}/team`` accepts.

    ``team`` is the frozen shape and is **stated whole**: the screen edits three fields at
    once and a save says what all three now are, so a seat left out of the payload is a seat
    emptied. That is what makes *cleared* a countable outcome rather than a thing a client has
    to spell as ``null``.

    ``accounts`` is optional and **per seat**, and an account sent for a seat whose name is
    changing in the same call belongs to the **new** holder — the link follows the person, so
    a name change with no account beside it clears the old one.
    ``app/services/shema/save_region_team.py`` is the one writer and the rule lives in its
    docstring.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team: RegionTeam
    accounts: RegionTeamAccounts | None = None


class SaveOutcome(BaseModel):
    """What the save actually did. **Frozen** — ``SaveOutcome`` in ``src/types/team.ts``.

    ``filled`` and ``cleared`` are subsets of ``changed`` and a rename is neither: a seat that
    went from *Ana* to *Bruno* changed without being filled or cleared. The screen reports
    the three separately because *nothing changed* is an answer a save owes the person who
    pressed the button (FE-44 §9.10).
    """

    model_config = ConfigDict(populate_by_name=True)

    changed: int = 0
    filled: int = 0
    cleared: int = 0


class RoleChange(BaseModel):
    """One seat's change, as it was recorded. **Frozen** — ``RoleChange`` in ``region.ts``.

    All three names are snapshots and **must not follow a later rename**: this is the record
    of an act, under the name its actor and its subject had at the time. FE-44 §5.3 allows
    exactly two stored copies of a person's name in this product and ``changedBy`` is one of
    them; ``from`` and ``to`` are the same kind of fact about the seat.
    """

    model_config = ConfigDict(populate_by_name=True)

    region_key: str = Field(alias="regionKey")
    role: str
    from_holder: str = Field(alias="from")
    to: str
    changed_by: str = Field(alias="changedBy")
    changed_at: date = Field(alias="changedAt")


class RegionTeamSaved(BaseModel):
    """The save's answer: what it did, and the rows it wrote. **Frozen** — FE-44 §9.10."""

    model_config = ConfigDict(populate_by_name=True)

    outcome: SaveOutcome
    changes: list[RoleChange]
