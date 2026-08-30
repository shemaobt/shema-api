"""The mesa and the Gestores are told a request arrived, when the team submits it."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequest
from app.services.notifications.create_notification import create_notification
from app.services.notifications.get_rr_app_id import get_rr_app_id
from app.services.resource_request._notices import (
    Letter,
    board_watchers,
    letter,
    product_name,
    request_name,
)

EVENT_TYPE = "rr_request_submitted"

TITLE = "A new request arrived"


async def notify_arrival(
    db: AsyncSession, *, request: RRRequest, actor_id: str, app_key: str
) -> list[Letter]:
    """Write everyone's in-app notice; hand back their letters for after the commit.

    The other half of GATE-03's loop, and the half that has no single recipient: the team
    is one account, the mesa and the Gestores are a list, read through
    ``board_watchers`` — whoever holds the Painel's entry gate. **The Gestor is here as a
    recipient and as nothing else**: no capability was added, and none was moved.

    Called from ``submit_request``, which is the one place a request becomes visible to
    the mesa. A draft still being typed announces nothing, and a card the mesa later drags
    announces nothing either — the arrival happens once, when the snapshot is frozen.

    The submitter is excluded, for the account that holds both a team role and a board
    one: nobody needs to be told about their own act.
    """
    watchers = await board_watchers(db, app_key, exclude=actor_id)
    if not watchers:
        return []

    app_id = await get_rr_app_id(db)
    name = request_name(request)
    body = f"{name} was submitted and is waiting in triagem."
    chrome = await product_name(db, app_id)

    letters: list[Letter] = []
    for watcher in watchers:
        await create_notification(
            db,
            user_id=watcher.id,
            app_id=app_id,
            event_type=EVENT_TYPE,
            title=TITLE,
            body=body,
            actor_id=actor_id,
            commit=False,
        )
        letters.append(
            letter(
                to=watcher.email,
                subject=TITLE,
                template="rr_arrival.html.jinja",
                app_name=chrome,
                greeting=watcher.display_name or watcher.email,
                headline=TITLE,
                request_name=name,
                request_type=request.request_type.value,
            )
        )
    return letters
