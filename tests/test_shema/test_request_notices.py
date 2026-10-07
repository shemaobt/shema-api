"""The resource-request form's notices in the PME's bell — the Shemá side of OBT-541 (BE-21).

``app/services/shema/_request_notices.py`` writes the form's arrival and decision into this app;
``list_notification_panel.py`` answers them as two more kinds. What is proven here: who is told,
role by role and against the negative of each; that a notice can carry nothing but a registered
name and a stage; that the panel answers both kinds without falling over, under the console's
own field names, and points at a project only for a reader who reaches it; that the panel's two
routes open behind the PME's door for the Gestor and the member the notices are addressed to;
and that an installation with no ``shema`` app does not refuse the form. The same notices,
driven through the form's own routes, are ``tests/test_resource_requests/test_pme_notices.py``.
"""

from __future__ import annotations

import inspect
from datetime import date
from importlib import import_module

from sqlalchemy import select

from app.api.shema._deps import APP_KEY
from app.db.models.notification import Notification
from app.db.models.resource_request import RRStage
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_notification import ShemaRequestNotice
from app.db.models.shema_project_member import ShemaProjectMember
from app.services.shema import list_notification_panel, region_scope
from app.services.shema._request_notices import (
    ARRIVAL_TITLE,
    DECISION_TITLES,
    FALLBACK_NAME,
    REQUEST_ARRIVAL_EVENT,
    REQUEST_DECISION_EVENT,
    notice_body,
    ring_arrival,
    ring_decision,
)
from tests.baker import make_user
from tests.test_shema.conftest import (
    auth_header,
    grant,
    make_scoped_user,
    make_shema_project,
)

FORM_APP_KEY = "resource-request-form"
AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA
PANEL = "/api/shema/notifications"


async def _rows(db_session, shema_app, user_id: str | None = None) -> list[Notification]:
    stmt = select(Notification).where(Notification.app_id == shema_app.id)
    if user_id is not None:
        stmt = stmt.where(Notification.user_id == user_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def _panel(db_session, user) -> list[dict]:
    scope = await region_scope(db_session, user, APP_KEY)
    entries = await list_notification_panel(
        db_session, scope, user, app_key=APP_KEY, today=date(2026, 9, 29)
    )
    return [entry.model_dump(mode="json", by_alias=True) for entry in entries]


async def _member(db_session, user, project_id: str) -> None:
    db_session.add(ShemaProjectMember(project_id=project_id, user_id=user.id, role="equipe"))
    await db_session.commit()


async def _arrive(db_session, project_id: str | None, actor_id: str, name: str = "Kadiwéu") -> int:
    told = await ring_arrival(
        db_session,
        form_app_key=FORM_APP_KEY,
        project_id=project_id,
        name=name,
        actor_id=actor_id,
    )
    await db_session.commit()
    return told


# --- the event types and the copy ------------------------------------------------------------


def test_the_event_types_are_the_forms_own() -> None:
    """*Mesmo event_type do formulário* — spelled here a second time, and held to the first."""
    arrival = import_module("app.services.resource_request.notify_arrival")
    decision = import_module("app.services.resource_request.notify_decision")
    assert REQUEST_ARRIVAL_EVENT == arrival.EVENT_TYPE
    assert REQUEST_DECISION_EVENT == decision.EVENT_TYPE


def test_a_request_notice_can_carry_nothing_but_a_name_and_a_stage() -> None:
    """GATE-03 D4's ceiling as a signature: no request row, no evaluation, no ``team_note`` —
    there is no parameter an evaluation field could arrive through."""
    assert list(inspect.signature(ring_decision).parameters) == [
        "db",
        "starter_id",
        "project_id",
        "name",
        "stage",
        "actor_id",
    ]
    assert list(inspect.signature(ring_arrival).parameters) == [
        "db",
        "form_app_key",
        "project_id",
        "name",
        "actor_id",
    ]
    assert list(inspect.signature(notice_body).parameters) == ["name", "stage"]


def test_the_copy_names_the_request_and_the_stage_and_nothing_else() -> None:
    assert notice_body("Kadiwéu", RRStage.TRIAGEM) == (
        "Kadiwéu was submitted and is waiting in triagem."
    )
    assert notice_body("  ", RRStage.RECUSADO).startswith(FALLBACK_NAME)
    assert set(DECISION_TITLES) == {
        RRStage.APROVADO,
        RRStage.CONDICIONAL,
        RRStage.REVISAR,
        RRStage.RECUSADO,
    }
    for title in (ARRIVAL_TITLE, *DECISION_TITLES.values()):
        assert len(title) <= 200


# --- who hears an arrival --------------------------------------------------------------------


async def test_the_arrival_rings_the_admin_and_the_gestor(db_session, shema_app, form_app) -> None:
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    admin = await make_user(db_session, email="admin@notices.test")
    await grant(db_session, admin, shema_app, "admin")
    gestor = await make_user(db_session, email="gestor@notices.test")
    await grant(db_session, gestor, form_app, "gestor")
    starter = await make_user(db_session, email="starter@notices.test")

    assert await _arrive(db_session, project.id, starter.id) == 2

    for person in (admin, gestor):
        [row] = await _rows(db_session, shema_app, person.id)
        assert (row.event_type, row.title, row.actor_id) == (
            REQUEST_ARRIVAL_EVENT,
            ARRIVAL_TITLE,
            None,
        )
        detail = await db_session.get(ShemaRequestNotice, row.id)
        assert detail is not None
        assert (detail.project_id, detail.request_name, detail.stage) == (
            project.id,
            "Kadiwéu",
            "triagem",
        )


async def test_the_arrival_rings_no_mesa_no_coordination_and_no_admin_held_only_in_the_form(
    db_session, shema_app, form_app
) -> None:
    """The mesa is told in the form; the coordination is not this notice's audience; and the
    form's own ``admin`` row is not the Admin the PME's door counts (``FORM_DOOR_ROLES``)."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    mesa = await make_user(db_session, email="mesa@notices.test")
    await grant(db_session, mesa, form_app, "mesa")
    form_admin = await make_user(db_session, email="form-admin@notices.test")
    await grant(db_session, form_admin, form_app, "admin")
    coordinator = await make_scoped_user(
        db_session, shema_app, email="coord@notices.test", role_key="coordinator", regions=[AFRICA]
    )
    starter = await make_user(db_session, email="starter@notices.test")

    assert await _arrive(db_session, project.id, starter.id) == 0

    assert await _rows(db_session, shema_app) == []
    for nobody in (mesa, form_admin, coordinator, starter):
        assert await _panel(db_session, nobody) == []


async def test_whoever_submits_is_not_told_of_their_own_arrival(
    db_session, shema_app, form_app
) -> None:
    """And an account holding both ``admin`` and ``gestor`` is told once, not twice."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    submitter = await make_user(db_session, email="admin-starter@notices.test")
    await grant(db_session, submitter, shema_app, "admin")
    both = await make_user(db_session, email="both@notices.test")
    await grant(db_session, both, shema_app, "admin")
    await grant(db_session, both, form_app, "gestor")

    assert await _arrive(db_session, project.id, submitter.id) == 1

    assert await _rows(db_session, shema_app, submitter.id) == []
    assert len(await _rows(db_session, shema_app, both.id)) == 1


# --- who hears a decision --------------------------------------------------------------------


async def test_whoever_started_and_then_decided_is_not_told_of_their_own_decision(
    db_session, shema_app, form_app
) -> None:
    """The mesa, the Gestor and the Admin may start a request for a team; deciding it after
    is their own act."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    mesa = await make_user(db_session, email="mesa-starter@notices.test")

    told = await ring_decision(
        db_session,
        starter_id=mesa.id,
        project_id=project.id,
        name="Kadiwéu",
        stage=RRStage.APROVADO,
        actor_id=mesa.id,
    )
    await db_session.commit()

    assert told == 0
    assert await _rows(db_session, shema_app, mesa.id) == []


async def test_the_decision_rings_only_whoever_started_the_request(
    db_session, shema_app, form_app
) -> None:
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    starter = await make_user(db_session, email="starter@notices.test")
    admin = await make_user(db_session, email="admin@notices.test")
    await grant(db_session, admin, shema_app, "admin")

    told = await ring_decision(
        db_session,
        starter_id=starter.id,
        project_id=project.id,
        name="Kadiwéu",
        stage=RRStage.REVISAR,
        actor_id=None,
    )
    await db_session.commit()

    assert told == 1
    [row] = await _rows(db_session, shema_app)
    assert (row.user_id, row.event_type, row.title, row.actor_id) == (
        starter.id,
        REQUEST_DECISION_EVENT,
        DECISION_TITLES[RRStage.REVISAR],
        None,
    )


async def test_a_request_with_no_project_or_no_starter_rings_nothing(
    db_session, shema_app, form_app
) -> None:
    """The Admin's link (OBT-537) has no starter; a card the board opened has no project. No
    record to point at, and *quem entrou por link continua recebendo por e-mail*."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    admin = await make_user(db_session, email="admin@notices.test")
    await grant(db_session, admin, shema_app, "admin")
    starter = await make_user(db_session, email="starter@notices.test")

    assert await _arrive(db_session, None, starter.id) == 0
    for starter_id, project_id in ((None, project.id), (starter.id, None)):
        told = await ring_decision(
            db_session,
            starter_id=starter_id,
            project_id=project_id,
            name="Kadiwéu",
            stage=RRStage.APROVADO,
            actor_id=None,
        )
        assert told == 0
    await db_session.commit()

    assert await _rows(db_session, shema_app) == []


async def test_without_the_pme_installed_the_form_is_not_refused(db_session, form_app) -> None:
    """No ``shema`` app, no bell: the PME's half answers 0 and never raises, so a form-only
    installation — and every form test that seeds no ``shema`` app — decides as before."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    gestor = await make_user(db_session, email="gestor@notices.test")
    await grant(db_session, gestor, form_app, "gestor")
    starter = await make_user(db_session, email="starter@notices.test")

    assert await _arrive(db_session, project.id, starter.id) == 0
    assert (
        await ring_decision(
            db_session,
            starter_id=starter.id,
            project_id=project.id,
            name="Kadiwéu",
            stage=RRStage.APROVADO,
            actor_id=None,
        )
        == 0
    )
    rows = await db_session.execute(select(Notification))
    assert rows.scalars().all() == []


# --- the panel -------------------------------------------------------------------------------


async def test_the_panel_lists_both_request_kinds_with_their_project(
    db_session, shema_app, form_app
) -> None:
    """``_KIND_BY_EVENT_TYPE`` knows both, so the panel answers them instead of a 500, and a
    member reaches the project of their own request."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    strategist = await make_scoped_user(
        db_session,
        shema_app,
        email="global@notices.test",
        role_key="coordinator",
        regions=list(ShemaRegionKey),
    )
    await grant(db_session, strategist, shema_app, "admin")
    starter = await make_user(db_session, email="starter@notices.test")
    await _member(db_session, starter, project.id)

    await _arrive(db_session, project.id, starter.id, name="Kadiwéu 2026")
    await ring_decision(
        db_session,
        starter_id=starter.id,
        project_id=project.id,
        name="Kadiwéu 2026",
        stage=RRStage.CONDICIONAL,
        actor_id=None,
    )
    await db_session.commit()

    [arrival] = await _panel(db_session, strategist)
    assert (arrival["kind"], arrival["projectId"], arrival["requestStage"]) == (
        "requestArrival",
        project.id,
        "triagem",
    )
    [decision] = await _panel(db_session, starter)
    assert (decision["kind"], decision["projectId"], decision["requestStage"]) == (
        "requestDecision",
        project.id,
        "condicional",
    )
    assert decision["requestName"] == "Kadiwéu 2026"
    assert decision["urgent"] is False


async def test_the_entry_answers_under_the_pme_s_own_field_names(
    db_session, shema_app, form_app
) -> None:
    """The console's type is ``projectId``, ``requestName`` and ``requestStage``; the wire is the
    frozen type verbatim (the PME's ``CLAUDE.md`` §8), and the other kinds carry them empty."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    starter = await make_user(db_session, email="starter@notices.test")
    await _member(db_session, starter, project.id)
    await ring_decision(
        db_session,
        starter_id=starter.id,
        project_id=project.id,
        name="",
        stage=RRStage.APROVADO,
        actor_id=None,
    )
    await db_session.commit()

    [entry] = await _panel(db_session, starter)
    assert {"kind", "projectId", "requestName", "requestStage"} <= set(entry)
    assert "request_name" not in entry
    assert entry["requestName"] == ""


async def test_the_pointer_goes_only_to_a_reader_who_reaches_the_project(
    db_session, shema_app, form_app
) -> None:
    """A project's id is its slug, ``<language>-<place>``: whoever the project is out of scope
    for does not learn it exists (§6.1). The Gestor and a coordinator of another region are told
    the name and the stage and not where it points; the coordination in scope would be."""
    project = await make_shema_project(
        db_session, project_id="sa-di-of-high-egypt", region_key=AFRICA
    )
    gestor = await make_user(db_session, email="gestor@notices.test")
    await grant(db_session, gestor, form_app, "gestor")
    elsewhere = await make_scoped_user(
        db_session, shema_app, email="asia@notices.test", role_key="coordinator", regions=[ASIA]
    )
    await grant(db_session, elsewhere, shema_app, "admin")
    starter = await make_user(db_session, email="starter@notices.test")

    await _arrive(db_session, project.id, starter.id)

    for reader in (gestor, elsewhere):
        [entry] = await _panel(db_session, reader)
        assert entry["projectId"] is None
        assert entry["requestStage"] == "triagem"
        assert "egypt" not in str(entry).lower()


# --- the panel's routes, behind the door -----------------------------------------------------


async def test_the_gestor_and_the_member_read_their_notices_behind_the_door(
    db_session, client, shema_app, form_app
) -> None:
    """Neither holds a Shemá grant — the app gate would have refused both — and both are who
    the form's notices are addressed to. Each reads its own rows and marks them read."""
    project = await make_shema_project(db_session, project_id="kadiweu", region_key=AFRICA)
    gestor = await make_user(db_session, email="gestor@notices.test")
    await grant(db_session, gestor, form_app, "gestor")
    starter = await make_user(db_session, email="starter@notices.test")
    await _member(db_session, starter, project.id)
    await _arrive(db_session, project.id, starter.id)
    await ring_decision(
        db_session,
        starter_id=starter.id,
        project_id=project.id,
        name="K",
        stage=RRStage.APROVADO,
        actor_id=None,
    )
    await db_session.commit()

    gestor_h = await auth_header(db_session, gestor)
    res = await client.get(PANEL, headers=gestor_h)
    assert res.status_code == 200, res.text
    assert [entry["kind"] for entry in res.json()] == ["requestArrival"]
    marked = await client.post(
        f"{PANEL}/read", json={"ids": [res.json()[0]["id"]]}, headers=gestor_h
    )
    assert marked.status_code == 204
    assert (await client.get(PANEL, headers=gestor_h)).json()[0]["isRead"] is True

    res = await client.get(PANEL, headers=await auth_header(db_session, starter))
    assert res.status_code == 200, res.text
    assert [(entry["kind"], entry["projectId"]) for entry in res.json()] == [
        ("requestDecision", project.id)
    ]


async def test_an_account_at_no_door_is_still_refused_the_panel(
    db_session, client, shema_app, form_app
) -> None:
    """The door opens for a role of the session's vocabulary, not for any account: the form's
    ``equipe`` floor and no role at all are refused, and the preferences stay behind the app
    gate even for a Gestor."""
    nobody = await make_user(db_session, email="nobody@notices.test")
    floor = await make_user(db_session, email="floor@notices.test")
    await grant(db_session, floor, form_app, "equipe")
    for account in (nobody, floor):
        headers = await auth_header(db_session, account)
        assert (await client.get(PANEL, headers=headers)).status_code == 403
        assert (
            await client.post(f"{PANEL}/read", json={"ids": []}, headers=headers)
        ).status_code == 403

    gestor = await make_user(db_session, email="gestor@notices.test")
    await grant(db_session, gestor, form_app, "gestor")
    prefs = await client.get(f"{PANEL}/prefs", headers=await auth_header(db_session, gestor))
    assert prefs.status_code == 403
