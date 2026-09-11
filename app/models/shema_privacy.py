"""The serialization boundary — what a shape that **leaves coordination** may carry.

``docs/shema.md`` §6.4 asks for the sensitive-country rule to be written once and applied
where the payload is built, and FE-44 §8 says why the payload and not the endpoint: *the
console is one consumer*. An export, a generated Pulse, a webhook, a notification body and a
future mobile client all read the same services, and a rule applied per endpoint is a rule
the next endpoint forgets.

**So the rule lives in a base model, and the boundary is Pydantic's own.** Every shape that
leaves coordination inherits :class:`LeavingShape`, and the withholding happens in a
model validator — after the fields are parsed and before anything serialises them. A later
issue writing ``class PrayerRequestOut(LeavingShape)`` with a ``location`` field gets the
redaction **without knowing this file exists**, which is the DoD line that a per-service call
could not deliver: a call has to be remembered, an inherited validator does not.

**Why a base model and not a service function.** The three candidate homes were a function
every service calls (forgettable), a FastAPI response hook (which would have to read the
database from ``app/api/`` to learn the flag, against
[ADR 0009](../../docs/adr/0009-routers-never-touch-the-database.md), and would work on
already-serialised JSON with the types gone), and this. Only this one is applied by
*declaring a field*, which is the one act a new endpoint's author cannot skip.

**Why here and not in** ``app/services/shema/_redaction.py``, **which** ``docs/shema.md``
**§3.1 names.** A response model may not import ``app/services/`` —
``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids the
inversion that closed an import cycle once — and the rule has to be reachable from the shape
itself for the paragraph above to be true. So the **rule** is here, with the shapes that
apply it, and ``_redaction.py`` stays the module's service-side owner: the one file in
``app/services/shema/`` and ``app/api/shema/`` allowed to read the guarded columns off a row.
That is the same split §3.1 makes for the derivations and for the same stated reason. The PR
records it as a departure from §3.1's table.

**Fail closed, and the closed state is the default.** :attr:`LeavingShape.sensitive_country`
is ``None`` when a shape was built from something that could not answer — a dict assembled by
hand, a partial row, a join that did not select the column. ``None`` withholds. The cost is
visible and cheap (a shape built from a ``ShemaProject`` always answers, because the column is
``NOT NULL``); the alternative fails the other way and fails silently.

**The withholding is visible and says nothing about what was withheld.**
``locationWithheld`` is in every leaving shape's output, always, so a consumer can render
*"location withheld"* and a file can count how many rows it reduced. It is one bit: that
something was reduced. It never carries the country, the place, the base or the reason.

**One seam, named rather than left to be discovered.** FastAPI serialises a returned model by
dumping it to a dict and validating that dict back into the response model
(``fastapi.routing._prepare_response_content``), which drops the excluded inputs below. A
second pass therefore cannot re-read the flag — so a payload that already carries
``locationWithheld`` is taken at its word rather than withheld again. The marker is produced
by this class and by nothing else, every leaving shape is built server-side from a row that
does answer, and re-applying the rule to an already-withheld payload is in any case a no-op;
what the seam buys is that a record the rule cleared does not come back withheld on the
second pass. ``tests/test_shema/test_privacy.py`` pins both halves.
"""

from __future__ import annotations

import enum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.shema_enums import ShemaRegionKey


class ShemaAudience(enum.StrEnum):
    """Who a payload is being built for — FE-44's ``MediaAudience``, verbatim.

    Not in ``app/db/models/shema_enums.py`` with the others because no column holds it: it is
    a **parameter** of a sharing decision, never a stored value, and a native PostgreSQL enum
    for a value that is never written would be a migration bought for nothing.

    ``coordenacao`` is a real destination and not a queue for something unpublished — the
    people who follow up and support (FE-44 §8.2). ``publico`` is anything the product cannot
    take back: an export, the Pulse, a forwarded file.
    """

    COORDENACAO = "coordenacao"
    PUBLICO = "publico"


#: Where a withheld project is placed on a map, longitude first — ``REGION_CENTROIDS`` in
#: FE-44's ``src/constants/geo.ts``, copied rather than re-derived so the server and the
#: console place the same marker in the same square degree.
#:
#: **Reduced precision and not omission**, which is FE-44 §8.1's own choice and worth keeping
#: the reason for: the map must show exactly what the filters return, so a silently
#: incomplete map is its own hazard. The marker moves; it does not disappear.
REGION_CENTROIDS: Final[dict[ShemaRegionKey, tuple[float, float]]] = {
    ShemaRegionKey.SOUTH_AMERICA: (-60.0, -10.0),
    ShemaRegionKey.NORTH_AMERICA: (-100.0, 45.0),
    ShemaRegionKey.AFRICA: (20.0, 5.0),
    ShemaRegionKey.ASIA: (95.0, 35.0),
    ShemaRegionKey.OCEANIA: (140.0, -20.0),
    ShemaRegionKey.EUROPE: (15.0, 50.0),
    ShemaRegionKey.OTHER: (-88.0, 15.0),
}

#: The region a withheld shape names when the row could not say which it is.
#:
#: ``other`` is not a sentinel invented here: it is what this module's own vocabulary already
#: means by *no region could be derived* (``ShemaRegionKey``'s docstring — two records have an
#: empty ``location`` and land here legitimately). Reusing it keeps one vocabulary where a
#: second one would have to be explained to every consumer.
UNKNOWN_REGION: Final = ShemaRegionKey.OTHER

#: The fields whose presence on a response model means the shape can name a place. A shape
#: carrying one of these must leave through :class:`LeavingShape`, and
#: ``tests/test_shema/test_privacy_owners.py`` reads the built application's route table and
#: fails when one does not.
PLACE_FIELDS: Final[tuple[str, ...]] = (
    "location",
    "location2",
    "country",
    "latitude",
    "longitude",
    "coords",
)

#: The name of the place the team works out of. ``team`` is the column BE-02 collapsed
#: ``team`` and ``ywamBase`` into, and both flagged records carry a base that names a place —
#: ``YWAM Egypt``, ``YWAM Morelia`` — so a payload that withholds ``Egypt`` while printing
#: ``YWAM Egypt`` one column over has redacted nothing (FE-44 §8.1 rule 3).
BASE_FIELDS: Final[tuple[str, ...]] = ("base", "team", "ywam_base")

#: Personal contact details belong to a person who may be in a sensitive country, so they are
#: *gated on every output the same way* ``location`` *is* — FE-44 §8.1 rule 5, and the
#: ecosystem's ``CLAUDE.md`` §6.1 in the same words. Shown on the record, never on a shape
#: that leaves it.
CONTACT_FIELDS: Final[tuple[str, ...]] = (
    "team_contact",
    "team_leader_contact",
    "mentor_contact",
)

#: Every field a withheld shape replaces. A subclass that declares none of them is still a
#: leaving shape and still carries ``locationWithheld``; there is nothing on it to reduce.
WITHHELD_FIELDS: Final[tuple[str, ...]] = PLACE_FIELDS + BASE_FIELDS + CONTACT_FIELDS


def withheld_value(field_name: str, region: ShemaRegionKey) -> Any:
    """What ``field_name`` holds once the location is withheld.

    **Never an empty string where the field names the place**, which is FE-44 §8.1 rule 1 and
    the reason the redaction is said to *travel in the shape*: a consumer that receives the
    region can group, count and draw the record, and a consumer that receives ``""`` has to
    decide for itself whether the data is missing or protected — and will guess wrong in a
    file it forwards. The base and the contacts are the other half of the same rule and do go
    empty, because there is no reduced form of a person's phone number.
    """
    if field_name in ("location", "country"):
        return region.value
    longitude, latitude = REGION_CENTROIDS[region]
    if field_name == "latitude":
        return latitude
    if field_name == "longitude":
        return longitude
    if field_name == "coords":
        return (longitude, latitude)
    return ""


class LeavingShape(BaseModel):
    """The base of every payload that leaves coordination.

    Inherit it for the prayer request, the ETEN snapshot, the notification entry, the export
    row, the Pulse entry, a search hit and the collection read. Do **not** inherit it for the
    record read: a project read by somebody allowed to open it is a coordination surface and
    carries the truth, because hiding the country from its own author is data loss rather
    than privacy (FE-44 §8.1 rule 5). That is the whole of the split, and
    ``tests/test_shema/test_privacy_owners.py`` keeps the exceptions to it in one named list
    instead of in reviewers' heads.

    ``from_attributes`` is on so a subclass validates straight off a ``ShemaProject`` row and
    picks up :attr:`sensitive_country` and :attr:`region_key` without the caller passing
    them — which is what makes an endpoint written by somebody who has not read this file
    still emit a protected payload.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    #: Read off the row, excluded from the output, and ``None`` when the shape was built from
    #: something that could not answer. ``None`` withholds — see the module docstring.
    sensitive_country: bool | None = Field(default=None, exclude=True, repr=False)
    #: Read off the row for the region the withheld shape names and the centroid it plots at.
    #: Its absence does not disclose: it falls back to :data:`UNKNOWN_REGION`.
    region_key: ShemaRegionKey | None = Field(default=None, exclude=True, repr=False)

    #: **The withholding, made visible.** One bit, in every leaving shape, saying that the
    #: payload was reduced and nothing about what was reduced. Defaulting to ``True`` is the
    #: fail-closed spelling of the same rule the validator applies.
    location_withheld: bool = Field(default=True, alias="locationWithheld")

    @model_validator(mode="after")
    def _withhold_the_place(self) -> LeavingShape:
        """Replace every guarded field this shape declares, or record that none was.

        Runs on every construction, including the one FastAPI performs when it validates a
        handler's return value into the response model — so a payload cannot be assembled
        past this by returning a model the route did not declare.
        """
        if self.sensitive_country is not None:
            withheld = self.sensitive_country
        elif "location_withheld" in self.__pydantic_fields_set__:
            withheld = self.location_withheld
        else:
            withheld = True

        if withheld:
            region = self.region_key or UNKNOWN_REGION
            for field_name in WITHHELD_FIELDS:
                if field_name in self.model_fields:
                    setattr(self, field_name, withheld_value(field_name, region))

        self.location_withheld = withheld
        return self
