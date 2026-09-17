"""Who hears that a submission arrived, and what they are told.

*A form that is submitted and never seen is worse than no form, because the sender believes
they have been heard.* That sentence is OBT-401's and it is the whole of this file's brief. It
also says why the notice is staged inside the caller's transaction: a submission that landed
always carries its notice, and one that rolled back leaves none —
``create_notification(..., commit=False)`` is the flag
``app/services/resource_request/_notices.py`` added for exactly this and the rule its docstring
sets holds here too, which is that whoever passes ``False`` owns the commit.

**Routed by role and by region, and the region is not optional.** FE-44 §5.8 gives the audience
table — field, health, need and stale reach ``coordinator`` and ``obtLab``; **prayer reaches**
``resourceCircle`` **alone**, the role whose responsibility it is — and §5.10 adds the rule
that makes it safe: *route by role and region before capping*. A notice that went to every
coordinator would tell a coordinator in Oceania that a project in Africa reported, which is
the collection read leaking one row at a time through a channel nobody audits.

**Two notices, not one, and the second one has two gates.** The arrival reaches
coordination. A prayer request inside it reaches the Resource Circle only if the submission
**wrote one** and the project's own consent lets it leave coordination — the second is
``app/services/shema/_consent.py``'s question about the project and never this file's, and *an
unauthorized prayer request is absent from all four output paths* with notifications as the
fourth.

**The consent read is of the record and not of the answer, and the order that falls out is
deliberate.** A submission that arrives through the link is not applied to the record until a
coordinator applies it, so at arrival the project's visibility is still whatever the project
said before — which means a leader claiming ``rede`` through an unauthenticated link cannot,
by itself, publish anything. The Resource Circle hears about it on the import, once a person
who can be asked has written that consent onto the record.

**No body names a place, and none names the request.** The notice is a pointer: the language,
and that something arrived. The record read is where the truth lives, behind the scope that
decides who may open it, and a notification row is a copy of data in a table with different
readers and no region predicate of its own. The copy is the leak, whatever the body says about
withholding.

**The copy is English**, like every notification title and every e-mail template in this
repository, and that is a pendency rather than a decision — the bilingual rewrite of this
product's client-facing wording is one of GATE-03's own open ends
(``app/services/resource_request/_notices.py`` records the same thing in the same words).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaSubmission
from app.services import authorization_service
from app.services.notifications import create_notification, get_shema_app_id
from app.services.shema._consent import reaches_prayer_wall
from app.services.shema._scope import (
    COORDINATOR_ROLE,
    OBT_LAB_ROLE,
    RESOURCE_CIRCLE_ROLE,
    granted_roles,
    reaches,
    scope_from_roles,
)

logger = logging.getLogger(__name__)

#: Who is told that a Pulse arrived — FE-44 §5.8's ``field`` audience, verbatim.
ARRIVAL_ROLES = (COORDINATOR_ROLE, OBT_LAB_ROLE)

#: Who is told that it carried a prayer request — ``resourceCircle`` **alone**, which is the
#: one row of that table with a single role in it and is not an oversight to be tidied up.
PRAYER_ROLES = (RESOURCE_CIRCLE_ROLE,)

ARRIVAL_EVENT = "shema.submission.received"
PRAYER_EVENT = "shema.submission.prayer"


async def _recipients(
    db: AsyncSession, app_key: str, roles: tuple[str, ...], project: ShemaProject
) -> list[User]:
    """The holders of ``roles`` whose reach includes this project's region.

    **The roles come from the auth spine and the reach comes from** ``_scope.py``, and neither
    is asked here: ``list_role_holders`` is the reverse of the join every guard makes and the
    sibling added it so a module would not reimplement ``require_role`` badly
    (``docs/shema.md`` §2.4), and ``scope_from_roles`` is the module's only reader of
    ``shema_user_regions``. What this function contributes is the ``and`` between them.

    It is two queries per holder, which is honest to state and is the right trade at this size:
    the holders of two roles in one product are a handful of people, and the alternative — a
    join written here over the scope table — would be the second reader of it that ``_scope.py``
    exists to prevent.
    """
    holders = await authorization_service.list_role_holders(db, app_key, roles)
    reached = []
    for holder in holders:
        scope = await scope_from_roles(db, holder, await granted_roles(db, holder.id, app_key))
        if reaches(scope, project.region_key):
            reached.append(holder)
    return reached


async def notify_submission(
    db: AsyncSession,
    project: ShemaProject,
    submission: ShemaSubmission,
    *,
    app_key: str,
    carries_prayer: bool,
) -> int:
    """Tell the people whose job this is, and answer how many were told.

    Staged with ``commit=False``: the caller owns the transaction and takes the commit, so the
    notices and the archive land together. Returned as a count rather than as rows because the
    number is what a test can assert and what a log line can carry, and the rows belong to the
    people they were addressed to.
    """
    app_id = await get_shema_app_id(db)
    language = submission.language_name or project.language_name or project.id

    told = 0
    arrival_recipients = await _recipients(db, app_key, ARRIVAL_ROLES, project)
    if not arrival_recipients:
        logger.warning(
            "shema submission arrived and reached nobody",
            extra={
                "shema_operation": "notify_submission",
                "shema_project_id": project.id,
                "shema_region": project.region_key.value,
            },
        )
    for user in arrival_recipients:
        await create_notification(
            db,
            user_id=user.id,
            app_id=app_id,
            event_type=ARRIVAL_EVENT,
            title=f"Pulse received — {language}",
            body=(
                f"{submission.submitted_by or 'A team leader'} submitted the monthly Pulse for "
                f"{language}. Open the project to review it."
            ),
            commit=False,
        )
        told += 1

    if carries_prayer and reaches_prayer_wall(project):
        prayer_recipients = await _recipients(db, app_key, PRAYER_ROLES, project)
        if not prayer_recipients:
            logger.warning(
                "shema submission carried a prayer request and reached nobody",
                extra={
                    "shema_operation": "notify_submission",
                    "shema_project_id": project.id,
                    "shema_region": project.region_key.value,
                },
            )
        for user in prayer_recipients:
            await create_notification(
                db,
                user_id=user.id,
                app_id=app_id,
                event_type=PRAYER_EVENT,
                title=f"Prayer request — {language}",
                body=(
                    f"The Pulse received for {language} carries a prayer request the team has "
                    "shared with the network. Open the project to read it."
                ),
                commit=False,
            )
            told += 1
    return told
