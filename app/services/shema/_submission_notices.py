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
**wrote one** and consent lets it leave coordination — the second is
``app/services/shema/_consent.py``'s question and never this file's, and *an unauthorized
prayer request is absent from all four output paths* with notifications as the fourth.

**The consent read is of the answer and of the record, both** (OBT-554). The notice is staged
before anybody applies the submission, on either door, so at arrival the project's visibility
is still the answer the *last* request was given — read alone, a project that said ``rede``
last month would lend it to a request the team never shared. So the submission has to say
``rede`` itself, and the record has to agree: a leader claiming it through an unauthenticated
link cannot, by itself, make the network hear of anything. A request shared for the first time
is therefore **never announced**: nothing fires on arrival, nothing fires when a coordinator
applies it, and the Resource Circle finds it on the wall without being told.

**No body names a place, and none names the request.** The notice is a pointer: the language,
and that something arrived. The record read is where the truth lives, behind the scope that
decides who may open it, and a notification row is a copy of data in a table with different
readers and no region predicate of its own. The copy is the leak, whatever the body says about
withholding.

**The copy is English, and the bell does not show it** (OBT-559). The row's ``title`` and
``body`` are for the readers of ``notifications`` that are not the PME's bell, like every
notification title and e-mail template in this repository. Each row is staged with its facts
(``_project_notices.py``) — the project, and who signed the Pulse — and the console words them in
its reader's language.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaSubmission
from app.models.shema import ShemaProjectUpdate
from app.models.shema_privacy import ShemaReader
from app.services import authorization_service
from app.services.notifications import get_shema_app_id
from app.services.shema._consent import submission_reaches_prayer_wall
from app.services.shema._project_notices import ProjectNoticeFacts, stage_project_notice
from app.services.shema._redaction import language_name_for
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
    written: ShemaProjectUpdate,
) -> int:
    """Tell the people whose job this is, and answer how many were told.

    Staged with ``commit=False``: the caller owns the transaction and takes the commit, so the
    notices and the archive land together. Returned as a count rather than as rows because the
    number is what a test can assert and what a log line can carry, and the rows belong to the
    people they were addressed to.

    ``written`` is the record write the submission carries, handed to the consent gate unread:
    what the team answered this time is the consent the prayer notice announces.
    """
    app_id = await get_shema_app_id(db)
    # The project's name as the recipients may read it, not the archived copy: OBT Lab is told
    # here and is not coordination, and a sensitive project's name can name the place (OBT-560).
    language = language_name_for(project, ShemaReader.OTHER, fallback="") or "a project"

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
    arrival = ProjectNoticeFacts(
        project_id=project.id, submitted_by=submission.submitted_by.strip() or None
    )
    for user in arrival_recipients:
        await stage_project_notice(
            db,
            user_id=user.id,
            app_id=app_id,
            event_type=ARRIVAL_EVENT,
            title=f"Pulse received — {language}",
            body=(
                f"{submission.submitted_by or 'A team leader'} submitted the monthly Pulse for "
                f"{language}. Open the project to review it."
            ),
            facts=arrival,
        )
        told += 1

    if carries_prayer and submission_reaches_prayer_wall(project, written):
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
            await stage_project_notice(
                db,
                user_id=user.id,
                app_id=app_id,
                event_type=PRAYER_EVENT,
                title=f"Prayer request — {language}",
                body=(
                    f"The Pulse received for {language} carries a prayer request the team has "
                    "shared with the network. Open the project to read it."
                ),
                facts=ProjectNoticeFacts(project_id=project.id),
            )
            told += 1
    return told
