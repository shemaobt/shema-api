"""The panel: what BE-07, BE-08 and BE-12 already delivered, plus the one kind nobody wrote.

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

**The cap is applied last, over the union, and it is what makes the rule true rather than
stated.** Capping either half first would let one kind evict the other's newest entries for a
recipient with a lot of both; sorting the merged list by ``created_at`` and cutting once is the
only order that does not.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_notification import ShemaNotificationRead
from app.models.shema_notification import ShemaNotificationEntry
from app.models.shema_projects import ShemaProjectCard, ShemaProjectQuery
from app.services.notifications import get_shema_app_id, list_notifications
from app.services.shema._health_audience import reads_assessments
from app.services.shema._scope import RegionScope
from app.services.shema.browse_projects import browse_projects
from app.utils.shema_derivations import StaleStatus

#: FE-44 §5.10's own number: *the cap is 30 per recipient, after routing.*
PANEL_CAP = 30

STALE_TITLE = "A project has gone quiet"


def _kind_of(event_type: str) -> str:
    """The panel's ``kind`` for a delivered notice's ``event_type``.

    Read by substring rather than by an exact table, because the three writers spelled their
    own event names independently (``shema_health_critical``, ``shema.need.urgent``,
    ``shema.submission.received``/``.prayer``) and a fourth writer's spelling should still land
    on a real kind rather than on an exception.
    """
    if "health" in event_type:
        return "health"
    if "need" in event_type:
        return "need"
    if "prayer" in event_type:
        return "prayer"
    if "submission" in event_type:
        return "field"
    return "other"


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
        db, scope, ShemaProjectQuery(stale=StaleStatus.CRITICO), today=today
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
                urgent=True,
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


async def list_notification_panel(
    db: AsyncSession, scope: RegionScope, user: User, *, app_key: str, today: date
) -> list[ShemaNotificationEntry]:
    """The panel, routed and capped — the DoD line ``GET /api/shema/notifications`` answers.

    ``scope`` is positional and has no default, the module's own habit for exactly this reason:
    a scope applied by a permissive keyword is a scope the next caller forgets.
    """
    app_id = await get_shema_app_id(db)
    delivered = [
        ShemaNotificationEntry(
            id=row.id,
            kind=_kind_of(row.event_type),
            title=row.title,
            body=row.body,
            urgent=False,
            project_id=None,
            region=None,
            created_at=row.created_at,
            is_read=row.is_read,
        )
        for row in await list_notifications(db, user.id, app_id, limit=PANEL_CAP)
    ]

    stale: list[ShemaNotificationEntry] = []
    if await reads_assessments(db, user, app_key):
        stale = await _stale_entries(db, scope, today=today)
        seen = await _read_stale_ids(db, user.id, [entry.id for entry in stale])
        stale = [entry.model_copy(update={"is_read": entry.id in seen}) for entry in stale]

    combined = sorted(delivered + stale, key=lambda entry: entry.created_at, reverse=True)
    return combined[:PANEL_CAP]
