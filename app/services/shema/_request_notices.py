"""The resource-request form's two notices, rung in the PME's bell (OBT-541, BE-21).

The form tells its own people twice — a row in its own app and an e-mail after the commit
(BE-13, ``app/services/resource_request/_notices.py``). Since GATE-04 the team, the Admin and
the Gestor sign in to the PME too, and the PME's bell reads only the ``shema`` app's rows, so
somebody who works only in the PME never heard either. This file is the third half: the same
two events, written into the ``shema`` app, for the people the PME knows. The form's two
halves go out exactly as before; the notifiers call in here beside them.

**Who.** The decision reaches whoever **started** the request (``rr_requests.started_by``,
BE-25) — the person who holds the pen: a member of the project, or the Admin, the mesa or the
Gestor who started it for the team. The arrival reaches the **Admin and the Gestor**, read the
way the PME's door reads them (``_scope.SHEMA_APP_ROLES`` and ``FORM_DOOR_ROLES``): ``admin``
off the ``shema`` grant, which is the one every guard below the door reads, and ``gestor`` off
the form's. The mesa is told in the form, where it works. Nobody is told about their own act.
There is **no region** in either: the Admin and the Gestor reach none (OBT-523) and read every
request (BE-24), and a decision is addressed to one person.

**What.** The registered name and the stage — GATE-03 D4's ceiling, the line BE-24's card
draws too. The two functions below take a name, a stage, a project and whom to tell, and
nothing else: no request row, no evaluation, no ``team_note``, so there is no parameter an
evaluation field could arrive through (``_health_notice.notice_body``'s shape, and
``test_request_notices.py`` pins the signatures). The row's ``actor_id`` stays empty — on a
decision the actor is the evaluator. The titles are constants and the name goes only in the
body, because ``notifications.title`` is 200 characters and a registered name may be 255.

**Where it points.** A notice in the PME is a way into the project's record, so every row
written here carries a :class:`~app.db.models.shema_notification.ShemaRequestNotice`: the
project, and the name and stage the console renders in its own language — the detail table
``docs/shema.md`` §4.6 said would come the day something deep-linked.
``list_notification_panel.py`` hands the pointer only to a reader who reaches that project.

**When it stays silent.** A request with no project has no record to point at — a card the
mesa, the Gestor or the Admin opened without one, or a seeded card — and one with nobody who
started it came by the Admin's link (OBT-537): *quem entrou por link continua recebendo por
e-mail*. And an installation with no ``shema`` app has no bell: the form's own halves go out
regardless, and this half never costs the form its decision.

**The event types are the form's own** (``notify_arrival.EVENT_TYPE``,
``notify_decision.EVENT_TYPE``), written here a second time because importing them would load
the form's service package from inside this one's; a test pins the pair, the way the
``*_APP_KEY`` constants are pinned. **This file imports nothing from**
``app.services.resource_request`` for the same reason — the form imports it.

**The copy is English**, the pendency every notice in this repository records.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.db.models.resource_request import RRStage
from app.db.models.shema_notification import ShemaRequestNotice
from app.services import authorization_service
from app.services.notifications.create_notification import create_notification
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema._scope import ADMIN_ROLE, GESTOR_ROLE

logger = logging.getLogger(__name__)

REQUEST_ARRIVAL_EVENT = "rr_request_submitted"
REQUEST_DECISION_EVENT = "rr_decision"

ARRIVAL_TITLE = "A resource request arrived"

#: One title per stage a decision implies — ``_decision_stage.DECISION_STAGE``'s four values.
DECISION_TITLES: dict[RRStage, str] = {
    RRStage.APROVADO: "A resource request was approved",
    RRStage.CONDICIONAL: "A resource request was approved with conditions",
    RRStage.REVISAR: "A resource request needs a revision",
    RRStage.RECUSADO: "A resource request was not approved",
}

_SENTENCES: dict[RRStage, str] = {
    RRStage.TRIAGEM: "was submitted and is waiting in triagem.",
    RRStage.APROVADO: "was approved by the Resource Circle.",
    RRStage.CONDICIONAL: "was approved with conditions by the Resource Circle.",
    RRStage.REVISAR: "was reviewed by the Resource Circle, which asks for a revision.",
    RRStage.RECUSADO: "was reviewed by the Resource Circle and was not approved.",
}

#: What the body calls a request with no registered name. A generic reference and not an
#: invented title, like the form's own; worded for a reader who is not necessarily its team.
FALLBACK_NAME = "A resource request"


def notice_body(name: str, stage: RRStage) -> str:
    """The sentence a recipient reads: the registered name and the stage, and nothing else."""
    return f"{name.strip() or FALLBACK_NAME} {_SENTENCES[stage]}"


async def _pme(db: AsyncSession) -> App | None:
    app = await authorization_service.get_app_by_key(db, SHEMA_APP_KEY)
    if app is None:
        logger.debug("no shema app on this installation; the PME's bell is not rung")
    return app


async def _arrival_recipients(
    db: AsyncSession, form_app_key: str, exclude: str | None
) -> list[str]:
    """The Admin off the ``shema`` grant and the Gestor off the form's, once each, by e-mail."""
    admins = await authorization_service.list_role_holders(db, SHEMA_APP_KEY, (ADMIN_ROLE,))
    gestores = await authorization_service.list_role_holders(db, form_app_key, (GESTOR_ROLE,))
    people = {user.id: user for user in (*admins, *gestores) if user.id != exclude}
    return [user.id for user in sorted(people.values(), key=lambda user: user.email)]


async def _ring(
    db: AsyncSession,
    app_id: str,
    recipients: list[str],
    *,
    event_type: str,
    title: str,
    project_id: str,
    name: str,
    stage: RRStage,
) -> int:
    """Stage one row and its detail per recipient, inside the caller's transaction."""
    body = notice_body(name, stage)
    for user_id in recipients:
        row = await create_notification(
            db,
            user_id=user_id,
            app_id=app_id,
            event_type=event_type,
            title=title,
            body=body,
            commit=False,
        )
        db.add(
            ShemaRequestNotice(
                notification_id=row.id,
                project_id=project_id,
                request_name=name.strip(),
                stage=stage.value,
            )
        )
    return len(recipients)


async def ring_arrival(
    db: AsyncSession,
    *,
    form_app_key: str,
    project_id: str | None,
    name: str,
    actor_id: str | None,
) -> int:
    """Tell the Admin and the Gestor, in the PME, that a request arrived; answer how many.

    Staged with ``commit=False`` — the caller, ``submit_request``, owns the commit. An arrival
    is always in ``triagem``: a revision is a new request, and it starts there too.
    ``actor_id`` is ``None`` when a link submitted (OBT-537) — which also has no project, so it
    never gets as far as the recipients.
    """
    if project_id is None:
        logger.info(
            "resource request arrived with no project; the PME's bell stays silent",
            extra={"shema_operation": "ring_arrival"},
        )
        return 0
    app = await _pme(db)
    if app is None:
        return 0
    recipients = await _arrival_recipients(db, form_app_key, actor_id)
    if not recipients:
        logger.warning(
            "resource request arrived and reached nobody in the PME",
            extra={"shema_operation": "ring_arrival", "shema_project_id": project_id},
        )
        return 0
    return await _ring(
        db,
        app.id,
        recipients,
        event_type=REQUEST_ARRIVAL_EVENT,
        title=ARRIVAL_TITLE,
        project_id=project_id,
        name=name,
        stage=RRStage.TRIAGEM,
    )


async def ring_decision(
    db: AsyncSession,
    *,
    starter_id: str | None,
    project_id: str | None,
    name: str,
    stage: RRStage,
    actor_id: str | None,
) -> int:
    """Tell whoever started the request, in the PME, the stage its decision put it in.

    ``stage`` is the column the decision implies, never the decision's own vocabulary: the
    notice names a stage, as the team's status does (GATE-03 D4). Staged with
    ``commit=False`` — the caller, ``save_evaluation``, owns the commit. ``actor_id`` is who
    decided, compared and never written: the mesa, the Gestor or the Admin who started a
    request for the team and then decided it is not told of their own act.
    """
    if starter_id is None or project_id is None:
        logger.info(
            "resource request decided with no starter or no project; the PME's bell stays silent",
            extra={"shema_operation": "ring_decision"},
        )
        return 0
    if starter_id == actor_id:
        return 0
    app = await _pme(db)
    if app is None:
        return 0
    return await _ring(
        db,
        app.id,
        [starter_id],
        event_type=REQUEST_DECISION_EVENT,
        title=DECISION_TITLES[stage],
        project_id=project_id,
        name=name,
        stage=stage,
    )
