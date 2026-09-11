"""The notice a drop to critical sends, and every sentence it deliberately does not carry.

**The content is the deliverable here, not the delivery.** An assessment is an affirmation about
four people, not a metric: *critical* means a team in difficulty. So the question this file
answers is not *how do we notify* — ``app/services/notifications/create_notification.py`` has
answered that for four products already — but *what may a notice say about a team that is
struggling, to somebody who is not in the room*.

**What it carries:** that a team's health reading turned critical, which team, on what day, and
where to go. Four facts, and the fourth is the one that does the work — the notice is an
invitation to open the record, which is the surface where being allowed to read is actually
checked.

**What it does not carry, each for its own reason:**

* **Which dimension is critical.** *The relational dimension is critical* is already a statement
  about what is wrong inside a team, delivered to a phone, in a row that outlives the
  conversation. Care is moved by knowing that somebody should call; it is not moved by knowing
  what to brace for.
* **The notes.** The per-dimension note is the most intimate thing this module stores, written by
  a mentor about people who did not consent to it being forwarded. It lives on the record and
  goes no further.
* **The prayer request.** It has its own gate (``_consent.py``) and its own destination; an
  assessment notice is not a second path out of it.
* **The place, the base, the country and the contacts.** ``docs/shema.md`` §6.4 names the
  notification entry among the shapes that *leave coordination*, and a notification row is the
  clearest case of it: it is read by more people than a response body and kept longer.
  :func:`notice_body` takes a language name and a day and has no parameter a place could arrive
  through — which is the same shape ``_scope.py``'s refusal log uses, and a stronger guarantee
  than remembering not to interpolate one.

**The copy is English, and that is a pendency rather than a decision.** Every notification title
and e-mail template in this repository is English, including the password reset the same people
receive, and the bilingual rewrite of the product's client-facing wording belongs to whoever owns
that conversation with the client. Inventing Portuguese here would put unapproved copy about a
team's difficulty in front of a field coordinator on nobody's authority. The sibling
(``app/services/resource_request/_notices.py``) records the same pendency in the same words.

**The trigger is the projection and not the payload**, which is what makes *a drop* mean
something: the overall is read before the write and after it, off the record's four flat fields,
and the notice fires only when it entered critical. A backdated assessment that does not become
the newest reading moves nothing and therefore says nothing — which is correct, because the
current reading of that team is the newer, better one. An assessment that confirms an already
critical team fires nothing either: the second telling is noise, and noise is what makes the
first one stop being read.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey
from app.services import authorization_service
from app.services.notifications.create_notification import create_notification
from app.services.shema._health_audience import recipients
from app.utils.shema_derivations import OverallHealth

logger = logging.getLogger(__name__)

#: The event a consumer filters on. ``shema_health_critical`` rather than a generic
#: ``shema_health``: BE-15 routes by event type, and a type that covers every assessment would
#: make *the ones that need somebody* indistinguishable from the ones that do not.
EVENT_TYPE = "shema_health_critical"

#: Neutral, and it names no team — the title is what shows in a list beside notices from four
#: other products, and a team's difficulty is not a headline.
TITLE = "A health assessment needs attention"

#: What a notice calls a project whose language name is empty. A generic reference rather than an
#: invented name: the four fields required to save include ``languageName``, so this is reachable
#: only through a seed or an import, and naming such a record *"Untitled"* would fabricate a
#: field's value. The sibling's ``FALLBACK_NAME`` is the same call.
FALLBACK_NAME = "A project"


def entered_critical(before: OverallHealth, after: OverallHealth) -> bool:
    """Whether the overall reading **moved into** critical — the one condition that notifies.

    ``na`` to ``critica`` counts, and that is the edge worth stating: nothing *fell*, because
    nobody had read the team before. It is also the case the product exists for — the first time
    anyone hears that a team is in trouble — and the alternative is that the very first critical
    reading of a silent team reaches nobody. ``docs/shema.md`` §7.4's warning is about the same
    asymmetry read from the other side: unassessed is the dominant state, so treating it as a
    baseline that cannot be fallen from would mean most teams can never trigger a notice.

    ``critica`` to ``critica`` does not count — see the module docstring's last paragraph.
    """
    return after is OverallHealth.CRITICA and before is not OverallHealth.CRITICA


def notice_body(language_name: str, *, day: date) -> str:
    """The sentence a recipient reads. No dimension, no note, no place — see the module docstring.

    The parameters are the whole of what a notice may know: a name and a day. A project row is
    deliberately not one of them, so there is nothing for a later edit to reach into.
    """
    name = language_name.strip() or FALLBACK_NAME
    return (
        f"{name} was assessed as critical on {day.isoformat()}. "
        "Open the project record to read the assessment and decide what support to offer."
    )


async def notify_critical(
    db: AsyncSession,
    *,
    app_key: str,
    project_id: str,
    language_name: str,
    region: ShemaRegionKey,
    day: date,
    actor: User,
) -> int:
    """Stage one notice per recipient and answer how many were written.

    **Staged, never committed** — ``commit=False``, so the notices and the assessment land under
    the caller's one commit. ``create_notification``'s own docstring names that contract and the
    property it buys: an assessment that landed always has its notice, and one that rolled back
    leaves none. The signature is called exactly as it stands; nothing here changes it.

    The actor is excluded, for the mentor who is also a regional coordinator: nobody needs to be
    told about their own act.

    **No recipient is not an error.** A region with no coordinator and no OBT Lab holder is a
    gap in the org chart, not a failure of this write — the assessment is filed either way and
    the history carries it. It is logged, because a critical reading that reached nobody is
    exactly the thing somebody should find out about. The recipients are read **before** the app
    registry row, so that path costs one query instead of two.

    The ``RuntimeError`` below is reachable only on an installation with no ``shema`` row in
    ``apps`` — which is an installation nobody could have authenticated into, because
    ``require_app_access`` needs that row to admit the caller who got this far. It is raised
    rather than swallowed all the same: a notice that cannot be addressed is not a notice that
    should be quietly skipped, and the assessment rolls back with it.
    """
    told = await recipients(db, app_key=app_key, region=region, exclude=actor.id)
    if not told:
        logger.warning(
            "shema health assessment turned critical and reached nobody",
            extra={
                "shema_operation": "notify_critical",
                "shema_project_id": project_id,
                "shema_region": region.value,
            },
        )
        return 0

    app = await authorization_service.get_app_by_key(db, app_key)
    if app is None:
        raise RuntimeError(f"App '{app_key}' is not registered; notifications cannot be addressed")

    body = notice_body(language_name, day=day)
    for recipient in told:
        await create_notification(
            db,
            user_id=recipient.id,
            app_id=app.id,
            event_type=EVENT_TYPE,
            title=TITLE,
            body=body,
            actor_id=actor.id,
            commit=False,
        )
    return len(told)
