"""The serialization boundary — what a shape that **leaves coordination** may carry, per reader.

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

**Who reads, and not only where it goes (OBT-528).** GATE-04 moved the line BE-04 drew at
the door of the record: the truth of a sensitive place belongs to **coordination**, not to
whoever may open the record. So a shape is built *for a reader* — :class:`ShemaReader`,
three values, one class for all three. ``coordination`` reads the truth; ``other`` (every
other signed-in reader of the console) and ``outside`` (everything that leaves the system)
read the same reduced form. The reader is not data: it arrives only in the validation
context of :meth:`LeavingShape.read_by`, the service's own decision, and a shape built any
other way is ``outside`` — so an endpoint written by somebody who never read this file still
emits the form that leaves.

**A withheld record holds back its text as well as its place (OBT-556).** The notes a team
writes, its health notes, its status comments and its scope are sentences, and a sentence can
say where the team is. So :data:`FREE_TEXT_FIELDS` are reduced like the base — to ``""``,
beside the same marker, for every reader who is not coordination — and are in
:data:`WITHHELD_WRITES` for the base's reason: a reader handed ``""`` may not type over the
truth unseen. Which fields is the client's decision of 2/out/2026 (*recolher tudo* over the
issue's list); the free text the list leaves out is named in ``docs/shema.md`` §6.4.

**Fail closed, and the closed state is the default.** :attr:`LeavingShape.sensitive_country`
is ``None`` when a shape was built from something that could not answer — a dict assembled by
hand, a partial row, a join that did not select the column. ``None`` withholds. The cost is
visible and cheap (a shape built from a ``ShemaProject`` always answers, because the column is
``NOT NULL``); the alternative fails the other way and fails silently.

**The withholding is visible and says nothing about what was withheld.**
``locationWithheld`` is in every leaving shape's output, always: one bit saying that this
record's place is withheld from everything that leaves coordination. It is **the same bit for
every reader** — a coordination reader receives the truth beside it, everybody else the
reduction it announces — which is what keeps a consumer that keys its own redaction on the
bit (the console's map and its client-side export) redacting for a coordinator who now reads
the truth. It never carries the country, the place, the base or the reason.

**One seam, named rather than left to be discovered.** A payload rebuilt from a dump of a
leaving shape — ``model_validate(shape.model_dump())``, which is what a dict round trip
through any transport looks like — carries neither :attr:`LeavingShape.sensitive_country`
nor :attr:`LeavingShape.region_key`, because both are ``exclude=True``, nor its reader. It
arrives with ``locationWithheld`` and without the flag, and the marker is taken as a
**report**: when it says withheld and the reader is not coordination, the payload is reduced
again — idempotently, in the region the payload itself names — because a coordination payload
carries the truth beside the same marker and a round trip must not launder it into one that
leaves. When it says the place is not withheld, the record was cleared and stays cleared.

**Which makes the marker a report and never a request.** A caller that wants a payload
withheld says ``sensitive_country=True``, or says nothing at all, because the default
withholds. What it may not do is set ``locationWithheld`` on a payload that still names a
place and expect this class to finish the job.

**The validator runs again on a shape that is already built, and that is load-bearing.**
FastAPI validates a handler's return value into the response model, and a page validates the
cards handed to it; on Pydantic v2 neither re-validates the fields of an instance of the right
class, but a model validator wraps the schema and runs again — with no context. So the reader
is kept on the instance and only an explicit context sets it, and the reduction is idempotent:
a second pass changes nothing, whether the payload was the truth for coordination or the
region for anybody else. ``tests/test_shema/test_privacy.py`` pins the wire and the round trip
both, and ``tests/test_shema/test_reader.py`` pins the reader through the page and the route.
"""

from __future__ import annotations

import enum
from typing import Any, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationInfo,
    computed_field,
    model_validator,
)

from app.db.models.shema_enums import ShemaRegionKey
from app.utils.shema_derivations import get_region


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


class ShemaReader(enum.StrEnum):
    """Who a leaving shape is built for — OBT-528's second input to the sensitive-country rule.

    * ``coordination`` reads the truth of a sensitive place **and writes the place and the
      flag**: a ``coordinator`` on a project in a region of their scope, the ``admin``
      (confirmed by Daniel on 8/oct/2026) and an installation admin.
      ``app/services/shema/_scope.py`` derives it; nothing else does.
    * ``trusted`` reads the truth and writes none of what coordination writes — the
      ``resourceCircle`` on a project in a region of its scope, since OBT-571 (Karina, via
      Daniel, 6/oct/2026: *"o Resource Circle poderá ver tudo, mesmo os projetos em países
      sensíveis, só não podem editar"*). A third value and not ``coordination`` because the
      console asks ``readAs`` two questions at once — *is this the truth?* and *may I edit the
      place and the flag?* — and this is the first reader for whom the answers differ.
    * ``other`` is every other signed-in reader of the console — ``obtLab`` — and reads the
      region in place of the country, the ficha included. Daniel decided on 7/oct/2026 that the
      OBT Lab stays redacted.
    * ``outside`` is whatever leaves the system: the export, the ETEN report, the Pulse, the
      leader's link, a notice. **The default**, and the fail-closed one.

    ``other`` and ``outside`` reduce the same fields today; they are two values because one is
    decided by the session and the other by the path, and a coordinator's export is ``outside``.
    :attr:`reads_truth` is the one spelling of *this reader is handed the record as it is*, so a
    path that checks ``is COORDINATION`` is asking about **writing**, never about reading.

    **Not** :class:`ShemaAudience`'s ``coordenacao``, which is FE-44's *destination* — every
    role that follows up and supports — and decides notes and media. The two coordinations are
    different memberships on purpose: GATE-04 decided who reads a sensitive place, and nothing
    about who reads a note.
    """

    COORDINATION = "coordination"
    TRUSTED = "trusted"
    OTHER = "other"
    OUTSIDE = "outside"

    @property
    def reads_truth(self) -> bool:
        """Whether a shape built for this reader carries a withheld record as it is."""
        return self in (ShemaReader.COORDINATION, ShemaReader.TRUSTED)


#: The validation-context key a leaving shape reads its reader from — set by
#: :meth:`LeavingShape.read_by` and by nothing else.
READER_KEY: Final = "shema_reader"


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

#: The export's free text about *why* a place is sensitive. BE-02 kept it as provenance beside
#: the flag, and it is a worse thing to emit than the country: since OBT-528 the ficha is a
#: leaving shape, so it goes empty for every reader who is not coordination.
REASON_FIELDS: Final[tuple[str, ...]] = ("sensitivity",)

#: The free text a team writes about itself — the record's notes, the health notes, the status
#: comments and the scope — any of which can say where it is (*a equipe se mudou para …*). Since
#: OBT-556 a withheld shape empties them for every reader who does not read the truth, as it
#: empties the base: there is no reduced form of a sentence. **OBT-573 added five**, Karina's
#: answer to question 8 (via Daniel, 6/out/2026): on a sensitive project the objective's, the
#: finances' and the needs' notes, the partner organisation and the status goal stay with
#: coordination too — and since OBT-571 the reader left without them is the OBT Lab, the
#: Resource Circle reading the truth. The nested free text of a withheld record — a need's
#: description, an assessment's notes, a media caption, a story's recording place — is
#: ``_redaction.py``'s, because a nested list arrives on the shape after it was built.
FREE_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "notes",
    "health_notes",
    "status_comments",
    "scope_details",
    "objective_notes",
    "financial_notes",
    "needs_notes",
    "partner_org",
    "status_goal",
)

#: The language's name, under the two spellings the leaving shapes use (the prayer entry calls
#: it ``language``). A sensitive project's name can name the place — *Sa'di of High Egypt* —
#: so a withheld shape replaces it too (OBT-560): with the name coordination registered for
#: the other readers, or with the region key when none was registered.
NAME_FIELDS: Final[tuple[str, ...]] = ("language_name", "language")

#: Every field a withheld shape replaces. A subclass that declares none of them is still a
#: leaving shape and still carries ``locationWithheld``; there is nothing on it to reduce.
WITHHELD_FIELDS: Final[tuple[str, ...]] = (
    PLACE_FIELDS + BASE_FIELDS + CONTACT_FIELDS + REASON_FIELDS + FREE_TEXT_FIELDS
)

#: What only coordination writes, on **every** record (OBT-528): the place, the flag and the
#: reason beside it. The write shape has no ``country``: the country is the first segment of
#: ``location``, so refusing the location is refusing the country.
COORDINATION_WRITES: Final[frozenset[str]] = frozenset(
    (*PLACE_FIELDS, "sensitive_country", *REASON_FIELDS, "public_language_name")
)

#: What only coordination writes on a record whose place is **withheld**: the rest of what the
#: read withholds from everybody else. *Não dá para editar o que não se vê* — a base read as
#: ``""`` is not a base a reader may type over, and neither are the notes (OBT-556).
#: ``language_name`` joined them with OBT-560: a withheld record hands everyone else the public
#: name in its place, and a value typed over it would overwrite the real one unseen.
WITHHELD_WRITES: Final[frozenset[str]] = frozenset(
    (*BASE_FIELDS, *CONTACT_FIELDS, *FREE_TEXT_FIELDS, "language_name")
)


def withheld_value(field_name: str, region: ShemaRegionKey) -> Any:
    """What ``field_name`` holds once the location is withheld.

    **Never an empty string where the field names the place**, which is FE-44 §8.1 rule 1 and
    the reason the redaction is said to *travel in the shape*: a consumer that receives the
    region can group, count and draw the record, and a consumer that receives ``""`` has to
    decide for itself whether the data is missing or protected — and will guess wrong in a
    file it forwards. The base and the contacts are the other half of the same rule and do go
    empty, because there is no reduced form of a person's phone number.

    ``location2`` goes empty for the same reason rather than against it: it is a **second**
    address line, so the reduced form the rule asks for is already in ``location`` beside it,
    and repeating the region under it would say the region twice and the place never.
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


#: The values a reduced ``location`` or ``country`` can hold.
_REGION_VALUES: Final = frozenset(region.value for region in ShemaRegionKey)


def _region_named_by(shape: BaseModel) -> ShemaRegionKey:
    """The region a payload rebuilt from a dump names, for the seam the module docstring names.

    A payload that was already reduced carries the region key in ``location`` (or
    ``country``); one built for coordination carries the place itself, and the region is
    derived from it by the owner of that map. A shape that declares neither falls back to
    :data:`UNKNOWN_REGION`, which withholds.
    """
    for field_name in ("location", "country"):
        value = getattr(shape, field_name, None)
        if not isinstance(value, str) or not value:
            continue
        if value in _REGION_VALUES:
            return ShemaRegionKey(value)
        return get_region(value)
    return UNKNOWN_REGION


class LeavingShape(BaseModel):
    """The base of every payload that leaves coordination — built for a reader.

    Inherit it for the prayer request, the ETEN snapshot, the notification entry, the export
    row, the Pulse entry, a search hit, the collection read and — since OBT-528 — the record
    read. Only a ``coordination`` reader gets the truth of a sensitive place, and a shape
    learns its reader from :meth:`read_by` and from nowhere else.
    ``tests/test_shema/test_privacy_owners.py`` keeps the routes that take the caller's reader
    in one named list instead of in reviewers' heads.

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

    #: **The withholding, made visible.** One bit, in every leaving shape: this record's place
    #: is withheld from everything that leaves coordination. The same bit for every reader —
    #: coordination reads the truth beside it. Defaulting to ``True`` is the fail-closed
    #: spelling of the same rule the validator applies.
    location_withheld: bool = Field(default=True, alias="locationWithheld")

    #: Read off the row like :attr:`sensitive_country`, and excluded likewise: the name
    #: coordination registered for every other reader of a sensitive project (OBT-560).
    public_language_name: str | None = Field(default=None, exclude=True, repr=False)

    #: **The name is not the language's own.** ``True`` on a withheld shape that declares a
    #: name field and was read by anybody but coordination — whether the name it carries is
    #: the one coordination registered or, when none was, the region key. ``False`` for
    #: coordination, who reads the real name — unlike ``locationWithheld`` — and the marker that
    #: keeps a payload rebuilt from a dump (the seam) from being reduced twice.
    language_name_withheld: bool = Field(default=False, alias="languageNameWithheld")

    #: Who this payload was built for. Private, so no input can set it; kept on the instance,
    #: so the validator's second pass (FastAPI's response validation, a page taking its cards)
    #: does not reset it.
    _reader: ShemaReader = PrivateAttr(default=ShemaReader.OUTSIDE)

    @property
    def reader(self) -> ShemaReader:
        """The reader this payload was built for — ``outside`` unless a service said otherwise."""
        return self._reader

    @classmethod
    def read_by(cls, source: Any, reader: ShemaReader) -> Self:
        """Build this shape from a row or a mapping, **for** ``reader``.

        The one way a reader reaches a shape. Another shape is refused as a source: validating
        an instance hands the same object back, so reading a coordination payload *for*
        somebody else would reduce it in place under whoever else holds it.
        """
        if isinstance(source, BaseModel):
            raise TypeError(
                f"{cls.__name__} is read from a row or a mapping, never from another shape"
            )
        return cls.model_validate(source, context={READER_KEY: ShemaReader(reader)})

    def _withhold(self, region: ShemaRegionKey) -> None:
        for field_name in WITHHELD_FIELDS:
            if field_name in self.model_fields:
                setattr(self, field_name, withheld_value(field_name, region))
        self._withhold_name(region)

    def _withhold_name(self, region: ShemaRegionKey) -> None:
        """Give the other readers the name coordination registered, or the region key.

        Karina, via Daniel, 1/out/2026, chose *"um nome alternativo, cadastrado pela
        coordenação"* for the language of a sensitive project (OBT-560). That much is hers.
        **Ours:** while none is registered the name is the region key, the convention
        ``location`` already follows here (*the region shown in place of*) — fail closed,
        because the alternative is the name that named the place.
        """
        declared = [name for name in NAME_FIELDS if name in self.model_fields]
        if not declared or self.language_name_withheld:
            return
        public = (self.public_language_name or "").strip()
        for field_name in declared:
            setattr(self, field_name, public or region.value)
        self.language_name_withheld = True

    def spoken_name(self, fallback: str) -> str:
        """The name for a sentence a person reads — a notice body, never a field (OBT-562).

        A withheld name with no public one registered is the region key, which is a value for a
        screen to translate and not a word for a sentence: *africa raised an urgent need* reads
        as a defect. So prose says ``fallback`` instead. An empty name says it too.
        """
        name = next((getattr(self, f) for f in NAME_FIELDS if f in self.model_fields), "")
        if not isinstance(name, str) or not name.strip():
            return fallback
        if self.language_name_withheld and name in _REGION_VALUES:
            return fallback
        return name

    @model_validator(mode="after")
    def _withhold_the_place(self, info: ValidationInfo) -> Self:
        """Replace every guarded field this shape declares, unless coordination is reading.

        Runs on every construction, including the one FastAPI performs when it validates a
        handler's return value into the response model — so a payload cannot be assembled
        past this by returning a model the route did not declare — and again on an instance
        that is already built, which is why the reader is only ever *set* here from an
        explicit context and every reduction is idempotent.
        """
        context = info.context if isinstance(info.context, dict) else {}
        if READER_KEY in context:
            self._reader = ShemaReader(context[READER_KEY])
        reads_the_truth = self._reader.reads_truth

        if self.sensitive_country is None and "location_withheld" in self.__pydantic_fields_set__:
            # The seam. The marker arrived and the flag did not, so this payload has been
            # through here once: a cleared record stays cleared, and a withheld one is reduced
            # again for anybody but coordination, in the region it names itself.
            if self.location_withheld and not reads_the_truth:
                self._withhold(self.region_key or _region_named_by(self))
            return self

        withheld = True if self.sensitive_country is None else self.sensitive_country

        if withheld and not reads_the_truth:
            self._withhold(self.region_key or UNKNOWN_REGION)

        self.location_withheld = withheld
        return self


class SessionShape(LeavingShape):
    """A leaving shape the console reads — the card and the record — which says who read it.

    ``readAs`` is additive, and it is the server's own answer to the question the console
    would otherwise answer with a second copy of the rule: whether the payload in hand is the
    truth or the reduction (``locationWithheld`` and ``readAs == "other"``), and whether its
    place and flag are this reader's to edit (``readAs == "coordination"``). Since OBT-571 the
    two answers can differ: ``readAs == "trusted"`` is the truth in hand and nothing of
    coordination's to edit — the Resource Circle's read of a sensitive project. Shapes that
    leave the system do not carry it: a file does not say who it was not written for.
    """

    @computed_field(alias="readAs")  # type: ignore[prop-decorator]
    @property
    def read_as(self) -> ShemaReader:
        """Who this payload was read as — ``coordination``, ``trusted`` or ``other`` on the
        console's reads."""
        return self._reader
