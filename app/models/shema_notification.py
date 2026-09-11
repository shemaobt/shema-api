"""The panel entry, the preferences and the read-state request — BE-15's own three shapes.

``docs/shema.md`` §5.10 decides what the panel is: **derived, never stored**, so its entries
carry no row of their own. Two kinds feed it. The events with a discrete moment — a health
reading turning critical (BE-07), an urgent need (BE-08), a Pulse arriving (BE-12) — are
already staged as ordinary rows in the platform's ``notifications`` table, routed by role and
by region at the moment they were written; this module lists its own slice of that table. The
one kind with **no** discrete moment — a project going quiet — has nothing to write at the
instant it happens, because nothing happens: it is a fact about the calendar, computed fresh
every time the panel is read, off ``app/services/shema/browse_projects.py``'s own stale
preset, which is already scoped and already redacted.

**Why this file is not a** :class:`~app.models.shema_privacy.LeavingShape`. A leaving shape
reduces a place; :class:`ShemaNotificationEntry` never carries one. ``region`` is the coarse
key (``south-america``, ``asia``, …) every ``RegionScope`` already answers in the clear
(``docs/shema.md`` §6.1), not a location, a country or a base — the same distinction FE-44's
own ``AppNotification.region`` draws. The body a notice carries is built by
``app/services/shema/_health_notice.py``, ``_needs.py`` and ``_submission_notices.py``, each of
which names no guarded column by design; this file only lists what they already wrote plus the
one computed kind, so there is nothing here left to redact.

``ShemaNotificationPrefsOut`` mirrors FE-44's frozen ``NotificationPrefs``: ``enabled``, a
nested ``channels`` triple, ``when``/``scope`` as free text (FE-44 §5.8 leaves their vocabulary
to the screen), and the two address fields, which ship empty because nothing sends anything yet
(``docs/shema.md`` §4.6). ``ShemaNotificationReadRequest`` is the batch of derived or delivered
ids the panel has been shown — FE-44 §5.8's stable-id rule is what makes an id enough to answer
with, with no row to look up first.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.db.models.shema_notification import ShemaNotificationPrefs

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


class ShemaNotificationEntry(BaseModel):
    """One row of the panel — a delivered notice, or a freshly computed stale reading.

    ``id`` is the notification's own primary key for a delivered kind and a stable derivation
    (``stale:{projectId}:{lastProgressDate}``) for the computed one, per FE-44 §5.8's rule that
    an entry's id names what it renders and never a position.
    """

    model_config = _OUTWARD

    id: str
    kind: str
    title: str
    body: str
    urgent: bool
    project_id: str | None = None
    region: str | None = None
    created_at: datetime
    is_read: bool


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
