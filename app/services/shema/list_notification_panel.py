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

**A health notice is read by who the account is now, not by who it was when it was addressed**
(OBT-553). ``_health_notice.py`` addresses the audience at the moment a reading turns critical, and
a grant can be taken back afterwards; an account that left the audience — moved to the Resource
Circle, say — would otherwise keep reading *which team went critical* in its panel. So the same
``reads_assessments`` answer that gates the stale reading leaves the health kind out of the
delivered rows, in the query and therefore before the cap, as §5.10 routes everything else.

**A request notice points at its project only for a reader who reaches it** (OBT-541). The
form's arrival and decision carry their project in ``shema_request_notices`` so the console can
open its record; but a project's id is its slug, which names a place, and the Admin and the
Gestor who hear of every arrival reach no region. So the pointer is answered when the project is
inside the caller's scope or the caller is one of its live members — the collection's own rule,
through ``within_scope`` and ``live_membership_ids`` — and is ``None`` otherwise, where the record
would have answered 404 anyway. The name and the stage are answered to every recipient: the
board already reads both on the form's card.

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
from app.db.models.resource_request import RRStage
from app.db.models.shema import ShemaProject
from app.db.models.shema_notification import ShemaNotificationRead, ShemaRequestNotice
from app.models.shema_notification import NotificationKind, ShemaNotificationEntry
from app.models.shema_projects import ShemaProjectCard, ShemaProjectQuery
from app.services.notifications import get_shema_app_id, list_notifications
from app.services.shema._health_audience import reads_assessments
from app.services.shema._health_notice import EVENT_TYPE as HEALTH_EVENT_TYPE
from app.services.shema._needs import URGENT_NEED_EVENT
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

STALE_TITLE = "A project has gone quiet"

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


def _kind_of(event_type: str) -> NotificationKind:
    return _KIND_BY_EVENT_TYPE[event_type]


def _is_urgent(kind: NotificationKind) -> bool:
    return kind in _URGENT_KINDS


def _stale_body(language_name: str, days_since_update: int | None) -> str:
    """What a stale reading says. No place, no team, no contact — see the module docstring."""
    name = language_name.strip() or "A project"
    when = "in a while" if days_since_update is None else f"for {days_since_update} days"
    return f"{name} has had no progress update {when}. Open the project to check in."


def _stale_id(card: ShemaProjectCard) -> str:
    """``stale:{projectId}:{lastProgressDate}`` — FE-44 §5.8's stable-derivation rule."""
    marker = card.derived.last_progress_update if card.derived else None
    return f"stale:{card.id}:{marker.isoformat() if marker else 'never'}"


async def _stale_entries(
    db: AsyncSession, scope: RegionScope, *, today: date
) -> list[ShemaNotificationEntry]:
    page = await browse_projects(
        db,
        scope,
        ShemaProjectQuery(stale=StaleStatus.CRITICO),
        readership=NO_COORDINATION,
        today=today,
    )
    stamp = datetime.combine(today, time.min, tzinfo=UTC)
    entries = []
    for card in page.items:
        days = card.derived.days_since_update if card.derived else None
        entries.append(
            ShemaNotificationEntry(
                id=_stale_id(card),
                kind="stale",
                title=STALE_TITLE,
                body=_stale_body(card.language_name, days),
                urgent=_is_urgent("stale"),
                project_id=card.id,
                region=card.region_key.value if card.region_key else None,
                created_at=stamp,
                is_read=False,
            )
        )
    return entries


async def _read_stale_ids(db: AsyncSession, user_id: str, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    stmt = select(ShemaNotificationRead.entry_id).where(
        ShemaNotificationRead.user_id == user_id, ShemaNotificationRead.entry_id.in_(ids)
    )
    return set((await db.execute(stmt)).scalars())


async def _request_notices(
    db: AsyncSession, scope: RegionScope, user_id: str, notification_ids: list[str]
) -> tuple[dict[str, ShemaRequestNotice], set[str]]:
    """The request details of these rows, and which of their projects this caller reaches."""
    if not notification_ids:
        return {}, set()
    rows = await db.execute(
        select(ShemaRequestNotice).where(ShemaRequestNotice.notification_id.in_(notification_ids))
    )
    details = {detail.notification_id: detail for detail in rows.scalars()}
    project_ids = {detail.project_id for detail in details.values()}
    if not project_ids:
        return details, set()
    reached = await db.execute(
        select(ShemaProject.id).where(
            ShemaProject.id.in_(project_ids),
            or_(within_scope(scope), ShemaProject.id.in_(live_membership_ids(user_id))),
        )
    )
    return details, set(reached.scalars())


async def list_notification_panel(
    db: AsyncSession, scope: RegionScope, user: User, *, app_key: str, today: date
) -> list[ShemaNotificationEntry]:
    """The panel, routed and capped — the DoD line ``GET /api/shema/notifications`` answers.

    ``scope`` is positional and has no default, the module's own habit for exactly this reason:
    a scope applied by a permissive keyword is a scope the next caller forgets.
    """
    app_id = await get_shema_app_id(db)
    reads_health = await reads_assessments(db, user, app_key)
    # Routed by who the account is now, in the query and so before the cap: a health notice
    # addressed while it was in the audience is not read once it has left it (OBT-553).
    rows = await list_notifications(
        db,
        user.id,
        app_id,
        limit=PANEL_CAP,
        exclude_event_types=() if reads_health else (HEALTH_EVENT_TYPE,),
    )
    details, reached = await _request_notices(db, scope, user.id, [row.id for row in rows])
    delivered = []
    for row in rows:
        kind = _kind_of(row.event_type)
        detail = details.get(row.id)
        delivered.append(
            ShemaNotificationEntry(
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
        )

    stale: list[ShemaNotificationEntry] = []
    if reads_health:
        stale = await _stale_entries(db, scope, today=today)
        seen = await _read_stale_ids(db, user.id, [entry.id for entry in stale])
        stale = [entry.model_copy(update={"is_read": entry.id in seen}) for entry in stale]

    combined = sorted(delivered + stale, key=lambda entry: entry.created_at, reverse=True)
    return combined[:PANEL_CAP]
