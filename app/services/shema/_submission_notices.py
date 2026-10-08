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

**Two notices, at two moments.** The arrival reaches coordination when the Pulse is archived
(:func:`notify_submission`). A prayer request inside it reaches the Resource Circle when it
**reaches the wall** — when a coordinator applies the Pulse and the record is written
(:func:`notify_shared_request`, OBT-566) — and only if the Pulse **wrote one** and the wall now
shows a request it did not show before. The second is ``app/services/shema/_consent.py``'s
question and never this file's (``newly_shared_request``), and *an unauthorized prayer request
is absent from all four output paths* with notifications as the fourth.

**Why at the apply and not at arrival.** At arrival nobody has applied anything, so the record
still holds the answer the *last* request was given: OBT-554 had the notice ask both the Pulse
and the record for ``rede``, which kept last month's consent from being lent to a text nobody
shared — and kept the **first** share from ever being announced, because the record only says
``rede`` once that Pulse is applied. After the apply the record is the one truth: the Pulse's
answer has been given to its own text, and the wall shows what the network may read. A request
already on the wall, sent again, is not news; a leader claiming ``rede`` through the link reaches
nobody until a coordinator applies it.

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
from app.models.shema_privacy import ShemaReader
from app.services import authorization_service
from app.services.notifications import get_shema_app_id
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


def _language(project: ShemaProject) -> str:
    """The project's name as the recipients may read it, not the archived copy.

    OBT Lab is told of an arrival and is not coordination, and a sensitive project's name can
    name the place (OBT-560).
    """
    return language_name_for(project, ShemaReader.OTHER, fallback="") or "a project"


async def _tell(
    db: AsyncSession,
    project: ShemaProject,
    *,
    app_key: str,
    roles: tuple[str, ...],
    event_type: str,
    title: str,
    body: str,
    facts: ProjectNoticeFacts,
    operation: str,
    nobody: str,
) -> int:
    """Stage one notice for every holder of ``roles`` who reaches ``project``; answer how many.

    Staged with ``commit=False`` by ``stage_project_notice``: the caller owns the transaction and
    takes the commit, so the notices land with the write they announce. Returned as a count
    rather than as rows because the number is what a test can assert and what a log line can
    carry, and the rows belong to the people they were addressed to. A notice that reaches
    nobody is logged as ``nobody`` says — the region has no holder of the role, which is a
    staffing gap somebody should see.
    """
    app_id = await get_shema_app_id(db)
    recipients = await _recipients(db, app_key, roles, project)
    if not recipients:
        logger.warning(
            nobody,
            extra={
                "shema_operation": operation,
                "shema_project_id": project.id,
                "shema_region": project.region_key.value,
            },
        )
    for user in recipients:
        await stage_project_notice(
            db,
            user_id=user.id,
            app_id=app_id,
            event_type=event_type,
            title=title,
            body=body,
            facts=facts,
        )
    return len(recipients)


async def notify_submission(
    db: AsyncSession, project: ShemaProject, submission: ShemaSubmission, *, app_key: str
) -> int:
    """Tell coordination that a Pulse arrived, and answer how many were told.

    Nothing here is about prayer: what the Pulse asked to share has not reached anybody yet, and
    the Resource Circle hears of it when it does (:func:`notify_shared_request`).
    """
    language = _language(project)
    return await _tell(
        db,
        project,
        app_key=app_key,
        roles=ARRIVAL_ROLES,
        event_type=ARRIVAL_EVENT,
        title=f"Pulse received — {language}",
        body=(
            f"{submission.submitted_by or 'A team leader'} submitted the monthly Pulse for "
            f"{language}. Open the project to review it."
        ),
        facts=ProjectNoticeFacts(
            project_id=project.id, submitted_by=submission.submitted_by.strip() or None
        ),
        operation="notify_submission",
        nobody="shema submission arrived and reached nobody",
    )


async def notify_shared_request(db: AsyncSession, project: ShemaProject, *, app_key: str) -> None:
    """Tell the Resource Circle that an applied Pulse put its prayer request on the wall (OBT-566).

    Called by the apply, after the record write and inside its transaction, once the Pulse wrote
    a request and ``_consent.newly_shared_request`` says the wall gained it: the notice lands
    with the request it announces, or neither does.
    """
    language = _language(project)
    await _tell(
        db,
        project,
        app_key=app_key,
        roles=PRAYER_ROLES,
        event_type=PRAYER_EVENT,
        title=f"Prayer request — {language}",
        body=(
            f"The Pulse received for {language} carries a prayer request the team has "
            "shared with the network. Open the project to read it."
        ),
        facts=ProjectNoticeFacts(project_id=project.id),
        operation="notify_shared_request",
        nobody="shema submission carried a prayer request and reached nobody",
    )
