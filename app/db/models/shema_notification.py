"""Notification preferences and read state — the two halves of a panel that is otherwise derived.

``docs/shema.md`` §5.10 decides the shape by deciding what is *not* stored: **the panel's
entries are derived from the projects**, so the platform's ``notifications`` table is the
wrong home for them and this module has no detail table of its own. What a store is needed
for is the two things a derivation cannot hold — what a person asked to be told about, and
what they have already seen.

Entry ids are stable derivations of what a row renders — ``health:{projectId}:{date}``,
``need:{projectId}:{category}:{submittedAt}`` — never of a position, because a removed need
would otherwise hand its read state to its neighbour. That rule is FE-44 §5.8's and it is
what makes ``ShemaNotificationRead`` safe; this table is the reason it has to hold.

**Delivery does not exist and this schema does not pretend otherwise.** There is no e-mail,
no push and no WhatsApp sender anywhere in ``app/services/notifications/`` — ``docs/shema.md``
§4.6 measured it — so the three channel flags default to **off** and the two address fields
ship empty. BE-15 inherits a preference with nothing behind it, and that is the honest state
to ship rather than a half-wired sender.

``app/api/notifications.py`` is not reusable here: every route on it carries
``require_app_access("meaning-map-generator")``. BE-15 writes ``app/api/shema/notifications.py``
and adds ``get_shema_app_id`` beside ``get_mm_app_id`` and ``get_rr_app_id`` — and exports it,
which ``get_oc_app_id`` was not.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaNotificationPrefs(Base):
    """One person's notification settings for this module. One row per account.

    The primary key is the user, which is the whole cardinality: preferences are per person
    and there is nothing to have two of. ``enabled`` defaults **on** and every channel
    defaults **off**, which is the combination that matches what exists — the panel works,
    and nothing is sent anywhere.

    ``when_key`` and ``scope_key`` are text rather than enums: FE-44 §5.8 freezes the
    ``NotificationPrefs`` *shape* and leaves their value sets to the screen, and §7.3's rule
    is that a vocabulary the client can extend is not an enum. ``custom_project_ids`` is a
    JSON array of slugs and not a join table — it is a preference read whole by one person's
    own panel, never queried across accounts.

    **Route by role and region before capping at thirty.** That is §5.10's rule and it is
    BE-15's to apply; capping first lets one region's entries evict another recipient's.
    """

    __tablename__ = "shema_notification_prefs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    channel_email: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    channel_push: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    channel_whatsapp: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    when_key: Mapped[str] = mapped_column(String(30), default="", server_default="")
    scope_key: Mapped[str] = mapped_column(String(30), default="", server_default="")
    #: Ships empty, with the channel's label as the field's placeholder.
    email_addr: Mapped[str] = mapped_column(String(300), default="", server_default="")
    phone_addr: Mapped[str] = mapped_column(String(60), default="", server_default="")
    custom_project_ids: Mapped[list[Any]] = mapped_column(
        JSON(none_as_null=True), default=list, server_default=text("'[]'")
    )

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShemaNotificationRead(Base):
    """That this person has seen this derived entry.

    Keyed by ``(user_id, entry_id)`` where ``entry_id`` is the derived stable id, not a row
    reference — there is no row to reference, which is the point of a derived panel. The id
    is long because it is built from a project slug and a date or a category;
    ``String(200)`` holds every shape the contract produces with room for the occurrence
    suffix an exact duplicate takes.

    Nothing here expires. An entry that stops being derived stops being rendered, and its
    read row becomes a fact about a notice that no longer exists — harmless, small, and
    cheaper than a sweep that has to know what the derivation would have produced.
    """

    __tablename__ = "shema_notification_reads"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    entry_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(UtcDateTime(timezone=True), server_default=func.now())
