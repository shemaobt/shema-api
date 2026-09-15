"""``/api/shema/notifications`` — the panel, the preferences and the read state (FE-44 §9.11).

Four routes, and each declares its dependencies, calls one service and returns what it
answers — no query here, no filter, no role check of its own, per
[ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md). The panel's own
audience gate (coordination and the OBT Lab, never the Resource Circle, for the one computed
kind) lives in ``_health_audience.py`` and is applied by
``app/services/shema/list_notification_panel.py``, not here — the same split
``health_assessments.py`` draws and for the same reason: a rule that lives in the operation
survives whoever calls it next.

**No role guard on any of these four routes**, and that is deliberate rather than an omission.
Every account with a Shemá grant may hold preferences and may have delivered notices of its
own; the routing that decides *whose* notices those are already happened once, at the moment
each was staged. A role check here would refuse nothing a caller could not already see.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.api.shema._deps import APP_KEY, CurrentUser, Db, Scope
from app.models.shema_notification import (
    ShemaNotificationEntry,
    ShemaNotificationPrefsIn,
    ShemaNotificationPrefsOut,
    ShemaNotificationReadRequest,
)
from app.services.shema import (
    get_notification_prefs,
    list_notification_panel,
    mark_notifications_read,
    save_notification_prefs,
)

router = APIRouter(prefix="/notifications")


@router.get("", response_model=list[ShemaNotificationEntry])
async def read_notifications(
    db: Db, scope: Scope, user: CurrentUser
) -> list[ShemaNotificationEntry]:
    """The panel: this account's delivered notices plus its own stale readings, capped at 30."""
    today = datetime.now(UTC).date()
    return await list_notification_panel(db, scope, user, app_key=APP_KEY, today=today)


@router.get("/prefs", response_model=ShemaNotificationPrefsOut)
async def read_notification_prefs(db: Db, user: CurrentUser) -> ShemaNotificationPrefsOut:
    """This account's preferences, or the honest default if none were ever saved."""
    return await get_notification_prefs(db, user.id)


@router.put("/prefs", response_model=ShemaNotificationPrefsOut)
async def write_notification_prefs(
    payload: ShemaNotificationPrefsIn, db: Db, user: CurrentUser
) -> ShemaNotificationPrefsOut:
    """Save this account's preferences whole — FE-38's screen calls this and nothing else."""
    return await save_notification_prefs(db, user.id, payload)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def read_notifications_mark(
    payload: ShemaNotificationReadRequest, db: Db, user: CurrentUser
) -> None:
    """Mark every id the panel just showed as seen — delivered and derived alike.

    ``response_model=None`` is stated rather than left to inference: this file carries
    ``from __future__ import annotations``, so a bare ``-> None`` is a string FastAPI's own
    forward-ref evaluation normalises to ``NoneType`` — a truthy class — which trips the
    framework's own assertion that a 204 may not declare a response body.
    """
    await mark_notifications_read(db, user.id, payload.ids)
