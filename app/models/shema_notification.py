"""The panel entry, the preferences and the read-state request — BE-15's own three shapes.

``docs/shema.md`` §5.10 decides what the panel is: **derived, never stored**, so its entries
carry no row of their own. Two kinds feed it. The events with a discrete moment — a health
reading turning critical (BE-07), an urgent need (BE-08), a Pulse arriving (BE-12), and since
OBT-541 a resource request arriving or being decided in the form — are already staged as
ordinary rows in the platform's ``notifications`` table, routed by role and by region at the
moment they were written; this module lists its own slice of that table. The
one kind with **no** discrete moment — a project going quiet — has nothing to write at the
instant it happens, because nothing happens: it is a fact about the calendar, computed fresh
every time the panel is read, off ``app/services/shema/browse_projects.py``'s own stale
preset, which is already scoped and already redacted.

**Why the entry is not a** :class:`~app.models.shema_privacy.LeavingShape`**, and the one shape
here that is.** A leaving shape reduces a place, and :class:`ShemaNotificationEntry` carries none
of its own. ``region`` is the coarse key (``south-america``, ``asia``, …) every ``RegionScope``
already answers in the clear (``docs/shema.md`` §6.1), not a location, a country or a base — the
same distinction FE-44's own ``AppNotification.region`` draws. The project notices' sentence is
the console's since OBT-559: the entry answers :class:`ShemaProjectNoticeFacts` — what happened,
and the language's name as ``_redaction.language_name_for`` lets every recipient read it — and
the platform's English ``title`` and ``body`` stay in the table for the readers that are not the
bell. The one place in those facts is an urgent need's, and it lives in
:class:`ShemaNoticePlace`, a leaving shape the panel builds with no reader — ``outside``, because
a notice is an output path (§6.4) — and only for a reader who reaches the project. A request
notice's ``project_id`` and a project notice's are answered on the same condition, which is
§6.1's rule: whoever a project is out of scope for does not learn where it is.

``ShemaNotificationPrefsOut`` mirrors FE-44's frozen ``NotificationPrefs``: ``enabled``, a
nested ``channels`` triple, ``when``/``scope`` as free text (FE-44 §5.8 leaves their vocabulary
to the screen), and the two address fields, which ship empty because nothing sends anything yet
(``docs/shema.md`` §4.6). ``ShemaNotificationReadRequest`` is the batch of derived or delivered
ids the panel has been shown — FE-44 §5.8's stable-id rule is what makes an id enough to answer
with, with no row to look up first.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.db.models.resource_request import RRStage
from app.db.models.shema_notification import ShemaNotificationPrefs
from app.models.shema_privacy import LeavingShape

#: The five kinds FE-44 §5.8 froze — the delivered health, need, prayer and field notices, plus
#: the one computed kind (``stale``) that has no event at all — and, since OBT-541, the
#: resource-request form's two, its arrival and its decision, rung in the PME's bell. Closed
#: rather than open, so an eighth spelling fails typing instead of landing on the panel unnoticed.
NotificationKind = Literal[
    "health", "need", "prayer", "field", "stale", "requestArrival", "requestDecision"
]

_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

_INWARD = ConfigDict(
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
    extra="forbid",
)


class ShemaNoticePlace(LeavingShape):
    """Where an urgent need's project is — as it leaves, for a reader who reaches it (OBT-559).

    Validated straight off the ``ShemaProject`` row, so the boundary reads the flag and the region
    itself and the panel never names the place: a cleared project's place is its place, and a
    withheld one's is its region key, beside ``locationWithheld``. Built with no reader, so it is
    ``outside`` even for the coordination — the notice is what leaves, not the record.
    """

    model_config = _OUTWARD

    location: str = ""


class ShemaNoticeTotal(BaseModel):
    """One currency's total among an urgent save's needs — never a sum across currencies."""

    model_config = _OUTWARD

    amount: Decimal
    currency: str


class ShemaProjectNoticeFacts(BaseModel):
    """What a project notice says, for the console to word in the reader's language (OBT-559).

    ``language_name`` is the name every recipient may read — ``""`` when the project is withheld
    and has no public name registered (OBT-560), which the console reads as *a project*. The rest
    is each kind's own: ``assessed_on`` the health notice's day; ``need_count``,
    ``need_categories`` and ``need_totals`` the urgent needs of one save; ``submitted_by`` the
    Pulse's signer; ``days_since_update`` how long a quiet project has been quiet (``None`` when
    it never reported). ``place`` is the urgent need's, answered only to a reader who reaches the
    project; everybody else words the sentence with the entry's ``region``.
    """

    model_config = _OUTWARD

    language_name: str = ""
    assessed_on: date | None = None
    need_count: int | None = None
    need_categories: list[str] = []
    need_totals: list[ShemaNoticeTotal] = []
    submitted_by: str | None = None
    days_since_update: int | None = None
    place: ShemaNoticePlace | None = None


class ShemaNotificationEntry(BaseModel):
    """One row of the panel — a delivered notice, or a freshly computed stale reading.

    ``id`` is the notification's own primary key for a delivered kind and a stable derivation
    (``stale:{projectId}:{lastProgressDate}``) for the computed one, per FE-44 §5.8's rule that
    an entry's id names what it renders and never a position.

    **The five project kinds answer** ``facts`` **and an empty** ``title`` **and** ``body``
    (OBT-559): the console writes their sentence in the reader's language. A project notice
    written before that answers ``facts=None`` and nothing else of what it said — its prose was
    written once, for whoever read it then, and could name the place. The two request kinds keep
    their ``title`` and ``body`` and carry ``requestName`` and ``requestStage``.
    """

    model_config = _OUTWARD

    id: str
    kind: NotificationKind
    title: str
    body: str
    urgent: bool
    project_id: str | None = None
    region: str | None = None
    created_at: datetime
    is_read: bool
    #: The two request kinds only (OBT-541): the registered name and the stage, as the notice
    #: told them — GATE-03 D4's whole ceiling. Named as the console's own type names them,
    #: ``requestName`` and ``requestStage``, so the wire is the frozen type verbatim. A request with
    #: no registered name answers ``""`` and the console names it generically in its own language.
    request_name: str | None = None
    request_stage: RRStage | None = None
    #: The five project kinds only: what the notice says, or ``None`` for one written before
    #: OBT-559, whose prose is not answered.
    facts: ShemaProjectNoticeFacts | None = None


class ShemaNotificationChannels(BaseModel):
    """The three delivery channels FE-44 freezes, every one of them unbuilt (§4.6)."""

    model_config = _INWARD

    email: bool = False
    push: bool = False
    whatsapp: bool = False


class ShemaNotificationPrefsOut(BaseModel):
    """``NotificationPrefs``, answered — built from the row rather than validated off it,
    because the nested ``channels`` triple has no single attribute to read.
    """

    model_config = _OUTWARD

    enabled: bool
    channels: ShemaNotificationChannels
    when: str
    scope: str
    email_addr: str
    phone_addr: str
    custom_project_ids: list[str]

    @classmethod
    def default(cls) -> ShemaNotificationPrefsOut:
        """The column defaults, for an account that has never saved a preference."""
        return cls(
            enabled=True,
            channels=ShemaNotificationChannels(),
            when="",
            scope="",
            email_addr="",
            phone_addr="",
            custom_project_ids=[],
        )

    @classmethod
    def of(cls, row: ShemaNotificationPrefs) -> ShemaNotificationPrefsOut:
        """Build from the row, field for field — the nested triple is the whole reason this is
        a classmethod rather than ``from_attributes``.
        """
        return cls(
            enabled=row.enabled,
            channels=ShemaNotificationChannels(
                email=row.channel_email, push=row.channel_push, whatsapp=row.channel_whatsapp
            ),
            when=row.when_key,
            scope=row.scope_key,
            email_addr=row.email_addr,
            phone_addr=row.phone_addr,
            custom_project_ids=list(row.custom_project_ids or []),
        )


class ShemaNotificationPrefsIn(BaseModel):
    """What the preferences screen writes — FE-44's ``NotificationPrefs``, verbatim."""

    model_config = _INWARD

    enabled: bool = True
    channels: ShemaNotificationChannels = ShemaNotificationChannels()
    when: str = ""
    scope: str = ""
    email_addr: str = ""
    phone_addr: str = ""
    custom_project_ids: list[str] = []


class ShemaNotificationReadRequest(BaseModel):
    """The ids the panel has just shown the caller, marked seen in one call."""

    model_config = _INWARD

    ids: list[str]
