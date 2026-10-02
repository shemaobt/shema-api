"""Notification preferences and read state — the two halves of a panel that is otherwise derived.

``docs/shema.md`` §5.10 decides the shape by deciding what is *not* stored: **the panel's
entries are derived from the projects**, so the platform's ``notifications`` table is the
wrong home for them. What a store is needed for is the two things a derivation cannot hold —
what a person asked to be told about, and what they have already seen.

**Two detail tables, each beside the platform's row and never inside it.** §4.6 said a Shemá
detail table would have no reader until a notice pointed somewhere. The resource-request form's
two notices were the first (OBT-541): each row carries its project, and the registered name and
stage the console renders in its own language, in :class:`ShemaRequestNotice`. The four project
notices are the second (OBT-559): the console writes their sentence in the reader's language, so
each row carries what happened — the day, the needs, who sent the Pulse — in
:class:`ShemaProjectNotice`, and the panel reads who and where the project is off the project
itself, when it is read.

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

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Integer, String, text
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


class ShemaRequestNotice(Base):
    """What a resource-request notice rung in the PME's bell points at and says (OBT-541).

    One row per ``notifications`` row the form's notices write into the ``shema`` app, keyed by
    that row. Three facts and no fourth, which is GATE-03 D4's ceiling written as a schema: the
    **project** the notice leads to, and the request's **registered name** and **stage** as they
    were when it was told — a snapshot, so a later rename or move does not rewrite what a notice
    said. Nothing of the evaluation has a column here to arrive through.

    ``stage`` is text and not the form's native ``rr_stage_enum``: that type is the sibling
    module's to migrate, and a second table holding it would pin its every change to this one.
    The CHECK keeps the value to the five stages a notice can announce — the arrival's ``triagem``
    and the four a decision implies; ``analise`` is absent because a card merely moving there
    tells nobody anything.

    ``project_id`` restricts on delete like the request's own foreign key does — a project with
    requests cannot be deleted, so the notices of those requests cannot be orphaned by it.
    """

    __tablename__ = "shema_request_notices"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('triagem', 'aprovado', 'condicional', 'revisar', 'recusado')",
            name="ck_shema_request_notices_stage",
        ),
    )

    notification_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id"), nullable=False
    )
    request_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    stage: Mapped[str] = mapped_column(String(20))


class ShemaProjectNotice(Base):
    """What a project notice in the bell says, as facts the console words itself (OBT-559).

    One row per ``notifications`` row the four project writers stage — a health reading turned
    critical, urgent needs, a Pulse and the prayer request it carried — keyed by that row, like
    :class:`ShemaRequestNotice`. The platform's ``title`` and ``body`` stay English prose for the
    readers that are not the bell; the bell reads this instead, so the sentence lands in the
    reader's language.

    **What happened, and never who or where.** The project is a pointer; its language's name, its
    region and its place are read off the project when the panel is read, through the owners of
    each (``_redaction.language_name_for``, the region key, ``LeavingShape``). So there is no
    column a name or a place could be stored in and outlive the rule that withholds it: a notice
    written before its project was flagged sensitive reads the way the project reads now, which
    is what a row of prose could not do (OBT-556, item 1). The facts columns are each one kind's:

    * ``assessed_on`` — the health notice: the day the reading turned critical;
    * ``need_count``, ``need_categories``, ``need_totals`` — the urgent needs of one save: how
      many, which categories, and the amounts **per currency, never across them** (``[{"amount":
      "5000.00", "currency": "BRL"}]``, the amount a string so no float ever touches it);
    * ``submitted_by`` — the Pulse: the name the leader signed it with.

    The prayer notice carries none of them: the project is the whole of what it says.

    ``project_id`` restricts on delete like :class:`ShemaRequestNotice`'s — a project is marked,
    never deleted (OBT-547).
    """

    __tablename__ = "shema_project_notices"

    notification_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id"), nullable=False
    )
    assessed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    need_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    need_categories: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    need_totals: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    submitted_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
