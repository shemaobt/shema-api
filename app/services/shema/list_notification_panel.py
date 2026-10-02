"""The panel: what BE-07, BE-08, BE-12 and the form delivered, plus the one kind nobody wrote.

``docs/shema.md`` §5.10 gives the rule this file follows: **route by role and region before
capping at thirty.** The routing already happened once, at the moment each delivered notice
was staged — ``_health_notice.py``, ``_needs.py`` and ``_submission_notices.py`` each address
one user at a time, off ``list_role_holders`` and this module's own region scope — so listing a
caller's own rows is not a second place that rule could be applied differently. The one
addition here is the stale reading, which has no row because nothing was written when a
project merely stayed quiet; it is filtered by the same audience health and needs already use
(``_health_audience.reads_assessments`` — coordination and the OBT Lab, never the Resource
Circle) and by the caller's own ``RegionScope``, through ``browse_projects``'s stale preset,
which is already scoped and already redacted.

**A project notice is worded by the console, from facts read now** (OBT-559). The five project
kinds — health, need, field, prayer and stale — answer an empty ``title`` and ``body`` and
:class:`~app.models.shema_notification.ShemaProjectNoticeFacts`, which the PME words in its
reader's language. What happened comes off the row's
:class:`~app.db.models.shema_notification.ShemaProjectNotice`; who and where the project is come
off the project, here, through each one's owner, so a notice reads the way its project reads
today and not the way it read when it was written:

* the language's name as every recipient may read it — ``""`` for a withheld project
  (:func:`_language_name`);
* the region key, to every recipient;
* the project's id and, on an urgent need, its place — **only to a reader who reaches the
  project now**, inside the caller's scope or one of its live members, the collection's own rule
  through ``within_scope`` and ``live_membership_ids``. The place is a
  :class:`~app.models.shema_notification.ShemaNoticePlace` built with no reader, so it leaves as
  ``outside`` — a withheld project's place is its region even for the coordination, because a
  notice is an output path (``docs/shema.md`` §6.4).

A project notice written before OBT-559 has no facts and answers its kind and nothing else: its
prose was written once, for whoever read it then, and an urgent need's named the place
(OBT-556, item 1).

**A health notice is read by who the account is now, not by who it was when it was addressed**
(OBT-553). ``_health_notice.py`` addresses the audience at the moment a reading turns critical, and
a grant can be taken back afterwards; an account that left the audience — moved to the Resource
Circle, say — would otherwise keep reading *which team went critical* in its panel. So the same
``reads_assessments`` answer that gates the stale reading leaves the health kind out of the
delivered rows, in the query and therefore before the cap, as §5.10 routes everything else.

**A request notice points at its project only for a reader who reaches it** (OBT-541), by the
same rule. The form's arrival and decision carry their project in ``shema_request_notices`` so
the console can open its record; the Admin and the Gestor who hear of every arrival reach no
region, and the pointer is ``None`` for them, where the record would have answered 404 anyway.
The name and the stage are answered to every recipient: the board already reads both on the
form's card.

**The cap is applied last, over the union, and it is what makes the rule true rather than
stated.** Capping either half first would let one kind evict the other's newest entries for a
recipient with a lot of both; sorting the merged list by ``created_at`` and cutting once is the
only order that does not.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.notification import Notification
from app.db.models.resource_request import RRStage
from app.db.models.shema import ShemaProject
from app.db.models.shema_notification import (
    ShemaNotificationRead,
    ShemaProjectNotice,
    ShemaRequestNotice,
)
from app.models.shema_notification import (
    NotificationKind,
    ShemaNoticePlace,
    ShemaNoticeTotal,
    ShemaNotificationEntry,
    ShemaProjectNoticeFacts,
)
from app.models.shema_projects import ShemaProjectCard, ShemaProjectQuery
from app.services.notifications import get_shema_app_id, list_notifications
from app.services.shema._health_audience import reads_assessments
from app.services.shema._health_notice import EVENT_TYPE as HEALTH_EVENT_TYPE
from app.services.shema._needs import URGENT_NEED_EVENT
from app.services.shema._redaction import is_withheld
from app.services.shema._request_notices import REQUEST_ARRIVAL_EVENT, REQUEST_DECISION_EVENT
from app.services.shema._scope import (
    NO_COORDINATION,
    RegionScope,
    live_membership_ids,
    within_scope,
)
from app.services.shema._submission_notices import ARRIVAL_EVENT, PRAYER_EVENT
from app.services.shema.browse_projects import browse_projects
from app.utils.shema_derivations import StaleStatus

#: FE-44 §5.10's own number: *the cap is 30 per recipient, after routing.*
PANEL_CAP = 30

#: The panel's ``kind`` for a delivered notice's ``event_type`` — off the four writers' own
#: constants, not a substring guess, so a fifth writer's spelling fails loudly here instead of
#: quietly landing on the wrong kind (or matching one it never meant).
_KIND_BY_EVENT_TYPE: dict[str, NotificationKind] = {
    HEALTH_EVENT_TYPE: "health",
    URGENT_NEED_EVENT: "need",
    ARRIVAL_EVENT: "field",
    PRAYER_EVENT: "prayer",
    REQUEST_ARRIVAL_EVENT: "requestArrival",
    REQUEST_DECISION_EVENT: "requestDecision",
}

#: Which kinds page a recipient rather than merely inform them. The event type already says
#: it for two of the four delivered kinds — a critical health reading and an urgent need — so
#: it is derived here rather than answered the same way for every delivered entry.
_URGENT_KINDS = frozenset({"health", "need"})

#: The kinds whose sentence the console words from :class:`ShemaProjectNoticeFacts` (OBT-559):
#: the four the project writers deliver, and the stale reading computed here.
_PROJECT_KINDS = frozenset({"health", "need", "field", "prayer", "stale"})


def _kind_of(event_type: str) -> NotificationKind:
    return _KIND_BY_EVENT_TYPE[event_type]


def _is_urgent(kind: NotificationKind) -> bool:
    return kind in _URGENT_KINDS


def _language_name(project: ShemaProject) -> str:
    """The language's name as every recipient of a notice may read it — ``""`` when withheld.

    A notice is not a shape, and every recipient reads it as somebody outside coordination: a
    project whose place is withheld may carry it in its name too (OBT-560), so its name is not
    answered and the console says *a project*. OBT-560 (shema-api#610) adds the name
    coordination registers for those projects and ``_redaction.language_name_for``, its owner;
    once it lands this is ``language_name_for(project, ShemaReader.OTHER, fallback="")``.
    """
    return "" if is_withheld(project) else project.language_name


def _stale_id(card: ShemaProjectCard) -> str:
    """``stale:{projectId}:{lastProgressDate}`` — FE-44 §5.8's stable-derivation rule."""
    marker = card.derived.last_progress_update if card.derived else None
    return f"stale:{card.id}:{marker.isoformat() if marker else 'never'}"


async def _stale_cards(
    db: AsyncSession, scope: RegionScope, *, today: date
) -> list[ShemaProjectCard]:
    page = await browse_projects(
        db,
        scope,
        ShemaProjectQuery(stale=StaleStatus.CRITICO),
        readership=NO_COORDINATION,
        today=today,
    )
    return list(page.items)


def _stale_language_name(card: ShemaProjectCard) -> str:
    """:func:`_language_name`'s answer, read off the card instead of a second read of the row.

    The card is a leaving shape ``browse_projects`` built for a reader outside coordination, so
    its ``location_withheld`` is the flag, fail-closed, and its ``language_name`` the one the
    record holds — the two :func:`_language_name` reads.
    """
    return "" if card.location_withheld else card.language_name


def _stale_entry(card: ShemaProjectCard, *, today: date) -> ShemaNotificationEntry:
    """A quiet project, worded by the console: its name and how long it has been quiet."""
    return ShemaNotificationEntry(
        id=_stale_id(card),
        kind="stale",
        title="",
        body="",
        urgent=_is_urgent("stale"),
        project_id=card.id,
        region=card.region_key.value if card.region_key else None,
        created_at=datetime.combine(today, time.min, tzinfo=UTC),
        is_read=False,
        facts=ShemaProjectNoticeFacts(
            language_name=_stale_language_name(card),
            days_since_update=card.derived.days_since_update if card.derived else None,
        ),
    )


async def _read_stale_ids(db: AsyncSession, user_id: str, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    stmt = select(ShemaNotificationRead.entry_id).where(
        ShemaNotificationRead.user_id == user_id, ShemaNotificationRead.entry_id.in_(ids)
    )
    return set((await db.execute(stmt)).scalars())


async def _request_notices(
    db: AsyncSession, notification_ids: list[str]
) -> dict[str, ShemaRequestNotice]:
    if not notification_ids:
        return {}
    rows = await db.execute(
        select(ShemaRequestNotice).where(ShemaRequestNotice.notification_id.in_(notification_ids))
    )
    return {detail.notification_id: detail for detail in rows.scalars()}


async def _project_notices(
    db: AsyncSession, notification_ids: list[str]
) -> dict[str, ShemaProjectNotice]:
    if not notification_ids:
        return {}
    rows = await db.execute(
        select(ShemaProjectNotice).where(ShemaProjectNotice.notification_id.in_(notification_ids))
    )
    return {detail.notification_id: detail for detail in rows.scalars()}


async def _projects(db: AsyncSession, project_ids: set[str]) -> dict[str, ShemaProject]:
    if not project_ids:
        return {}
    rows = await db.execute(select(ShemaProject).where(ShemaProject.id.in_(project_ids)))
    return {project.id: project for project in rows.scalars()}


async def _reached(
    db: AsyncSession, scope: RegionScope, user_id: str, project_ids: set[str]
) -> set[str]:
    """Which of these projects this caller reaches now — in scope, or one of its live members."""
    if not project_ids:
        return set()
    reached = await db.execute(
        select(ShemaProject.id).where(
            ShemaProject.id.in_(project_ids),
            or_(within_scope(scope), ShemaProject.id.in_(live_membership_ids(user_id))),
        )
    )
    return set(reached.scalars())


def _facts(
    kind: NotificationKind, detail: ShemaProjectNotice, project: ShemaProject, *, reaches: bool
) -> ShemaProjectNoticeFacts:
    """What a delivered project notice says, with who and where read off the project now."""
    return ShemaProjectNoticeFacts(
        language_name=_language_name(project),
        assessed_on=detail.assessed_on,
        need_count=detail.need_count,
        need_categories=list(detail.need_categories or []),
        need_totals=[ShemaNoticeTotal.model_validate(total) for total in detail.need_totals or []],
        submitted_by=detail.submitted_by,
        place=ShemaNoticePlace.model_validate(project) if reaches and kind == "need" else None,
    )


def _project_entry(
    row: Notification,
    kind: NotificationKind,
    detail: ShemaProjectNotice | None,
    project: ShemaProject | None,
    *,
    reached: set[str],
) -> ShemaNotificationEntry:
    """A delivered project notice — or, written before OBT-559, its kind and nothing else."""
    entry = ShemaNotificationEntry(
        id=row.id,
        kind=kind,
        title="",
        body="",
        urgent=_is_urgent(kind),
        created_at=row.created_at,
        is_read=row.is_read,
    )
    if detail is None or project is None:
        return entry
    reaches = project.id in reached
    return entry.model_copy(
        update={
            "project_id": project.id if reaches else None,
            "region": project.region_key.value,
            "facts": _facts(kind, detail, project, reaches=reaches),
        }
    )


def _request_entry(
    row: Notification,
    kind: NotificationKind,
    detail: ShemaRequestNotice | None,
    *,
    reached: set[str],
) -> ShemaNotificationEntry:
    return ShemaNotificationEntry(
        id=row.id,
        kind=kind,
        title=row.title,
        body=row.body,
        urgent=_is_urgent(kind),
        project_id=detail.project_id if detail and detail.project_id in reached else None,
        region=None,
        created_at=row.created_at,
        is_read=row.is_read,
        request_name=detail.request_name if detail else None,
        request_stage=RRStage(detail.stage) if detail else None,
    )


async def list_notification_panel(
    db: AsyncSession, scope: RegionScope, user: User, *, app_key: str, today: date
) -> list[ShemaNotificationEntry]:
    """The panel, routed and capped — the DoD line ``GET /api/shema/notifications`` answers.

    ``scope`` is positional and has no default, the module's own habit for exactly this reason:
    a scope applied by a permissive keyword is a scope the next caller forgets.
    """
    reads_health = await reads_assessments(db, user, app_key)
    app_id = await get_shema_app_id(db)
    rows = await list_notifications(
        db,
        user.id,
        app_id,
        limit=PANEL_CAP,
        exclude_event_types=() if reads_health else (HEALTH_EVENT_TYPE,),
    )
    row_ids = [row.id for row in rows]
    requests = await _request_notices(db, row_ids)
    notices = await _project_notices(db, row_ids)
    cards = await _stale_cards(db, scope, today=today) if reads_health else []

    projects = await _projects(db, {detail.project_id for detail in notices.values()})
    reached = await _reached(
        db,
        scope,
        user.id,
        {request.project_id for request in requests.values()}
        | {notice.project_id for notice in notices.values()},
    )

    delivered = []
    for row in rows:
        kind = _kind_of(row.event_type)
        if kind in _PROJECT_KINDS:
            detail = notices.get(row.id)
            project = projects.get(detail.project_id) if detail else None
            delivered.append(_project_entry(row, kind, detail, project, reached=reached))
        else:
            delivered.append(_request_entry(row, kind, requests.get(row.id), reached=reached))

    stale = [_stale_entry(card, today=today) for card in cards]
    seen = await _read_stale_ids(db, user.id, [entry.id for entry in stale])
    stale = [entry.model_copy(update={"is_read": entry.id in seen}) for entry in stale]

    combined = sorted(delivered + stale, key=lambda entry: entry.created_at, reverse=True)
    return combined[:PANEL_CAP]
