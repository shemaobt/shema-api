"""The project the mesa's approval files, and the Admin who confirms or discards it (OBT-547).

Every case drives the real path: the Admin issues a request link, the holder writes and submits
through it, the base endorses and the mesa assigns the fund, and the mesa approves through
``PUT /requests/{id}/evaluation`` — so the filing is proved at the call site that makes it, in
the decision's own transaction, rather than by calling the service beside it.

The Admin of these tests holds ``admin`` in both apps and is not an installation admin, as in
``admin_surface.py``; the negative cases by role use no installation admin either, because one
passes every guard and would prove nothing. Addresses are ``@fora.example`` and
``@shema.example``: the invitation routes validate with ``EmailStr``, which refuses ``.test``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models.auth import AccessInvite
from app.db.models.resource_request import RREvaluation, RRRequest, RRSnapshot, RRStage
from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import ShemaProjectStatus, ShemaRegionKey
from app.db.models.shema_pending_member import ShemaProjectPendingMember
from app.db.models.shema_project_member import ShemaProjectMember
from app.services.shema import (
    RegionScope,
    count_projects,
    create_pending_project_from_request,
    visible_projects,
    within_scope,
)
from tests.baker import make_user
from tests.test_resource_requests.test_evaluations import endorse, give_fund, put_evaluation
from tests.test_resource_requests.test_requests import REQUESTS, draft
from tests.test_shema.admin_surface import FORM_INVITES, INVITES, give_urls, make_admin
from tests.test_shema.conftest import (
    PREFIX,
    SESSION,
    auth_header,
    grant,
    make_scoped_user,
    make_shema_project,
)

PENDING = f"{PREFIX}/pending-projects"
PROJECTS = f"{PREFIX}/projects"
LINKS = "/api/resource-requests/links"
LINK = "/api/resource-requests/link"

HOLDER = "equipe@fora.example"


def confirm_path(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/confirm"


def reject_path(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/reject"


@asynccontextmanager
async def pending_client(db_session) -> AsyncIterator[httpx.AsyncClient]:
    """The PME's module, the form's module and its invitation routes, and auth — one app."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.api.auth import router as auth_router
    from app.api.resource_requests import router as form_router
    from app.api.resource_requests.access import router as form_access_router
    from app.api.shema import router as module_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.core.rate_limit import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(module_router, prefix=PREFIX)
    app.include_router(form_router, prefix="/api/resource-requests")
    app.include_router(form_access_router, prefix="/api/resource-requests/access")
    app.include_router(auth_router, prefix="/api/auth")
    register_exception_handlers(app)

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def link_draft(**fields: str) -> dict[str, object]:
    """A translation request whose Parte A names a language, a place, a requester and a team."""
    payload = draft()
    answers = dict(payload["fields"])  # type: ignore[call-overload]
    answers.update(
        {
            "reg_name": "Projeto Língua Teste",
            "lang_name": "Língua Teste",
            "lang_iso": "ltt",
            "people_location": "Peru, Vale Teste",
            "tpp_name": "Joana Teste",
        }
    )
    answers.update(fields)
    payload["fields"] = answers
    payload["team"] = [
        {"name": "Ana Teste", "role": "coordenação"},
        {"name": "Bruno Teste", "role": "tradução"},
    ]
    return payload


class Filing:
    """The Admin, the mesa, and a link whose holder can send requests."""

    def __init__(self, client, admin, admin_headers, mesa_headers, link, holder_headers) -> None:
        self.client = client
        self.admin = admin
        self.admin_headers = admin_headers
        self.mesa_headers = mesa_headers
        self.link = link
        self.holder_headers = holder_headers

    async def submitted(self, **fields: str) -> str:
        started = await self.client.post(
            REQUESTS, json=link_draft(**fields), headers=self.holder_headers
        )
        assert started.status_code == 201, started.text
        request_id = started.json()["id"]
        sent = await self.client.post(
            f"{REQUESTS}/{request_id}/submit", headers=self.holder_headers
        )
        assert sent.status_code == 200, sent.text
        return request_id

    async def decided(self, db_session, decision: str = "approved", **fields: str) -> str:
        request_id = await self.submitted(**fields)
        await endorse(db_session, request_id)
        await give_fund(db_session, request_id)
        res = await put_evaluation(self.client, self.mesa_headers, request_id, decision=decision)
        assert res.status_code == 200, res.text
        return request_id


async def open_filing(db_session, client, shema_app, form_app, *, holder: str = HOLDER) -> Filing:
    await give_urls(db_session, shema_app, form_app)
    admin, admin_headers = await make_admin(db_session, shema_app, form_app)
    mesa = await make_user(db_session, email="mesa@shema.example")
    await grant(db_session, mesa, form_app, "mesa")
    issued = await client.post(LINKS, json={"email": holder}, headers=admin_headers)
    assert issued.status_code == 201, issued.text
    link = issued.json()
    verified = await client.post(f"{LINK}/{link['token']}/verify", json={"code": link["code"]})
    assert verified.status_code == 200, verified.text
    return Filing(
        client,
        admin,
        admin_headers,
        await auth_header(db_session, mesa),
        link,
        {"Authorization": f"Bearer {verified.json()['session']}"},
    )


async def filed_projects(db_session) -> list[ShemaProject]:
    rows = await db_session.execute(
        select(ShemaProject)
        .where(ShemaProject.source_request_id.is_not(None))
        .order_by(ShemaProject.created_at)
    )
    return list(rows.scalars())


async def request_row(db_session, request_id: str) -> RRRequest:
    row = await db_session.get(RRRequest, request_id)
    await db_session.refresh(row)
    return row


def confirmation(**over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "languageName": "Língua Teste",
        "languageCode": "ltt",
        "location": "Peru",
        "team": "Base Teste",
        "sensitiveCountry": False,
        "members": [],
    }
    body.update(over)
    return body


# --- the approval files it --------------------------------------------------------------------


async def test_approving_a_link_request_files_a_pending_project(
    db_session, shema_app, form_app
) -> None:
    """The DoD's first line: approve a request that came by the link, and a project is pending."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        request_id = await filing.decided(db_session)

    [project] = await filed_projects(db_session)
    assert project.pending_confirmation is True
    assert project.source_request_id == request_id
    assert project.source_link_id == filing.link["id"]
    assert project.language_name == "Língua Teste"
    assert project.language_code == "ltt"
    assert project.status is ShemaProjectStatus.PLANEJADO
    assert project.sensitive_country is False
    assert project.region_key is ShemaRegionKey.SOUTH_AMERICA
    assert (await request_row(db_session, request_id)).shema_project_id is None


async def test_a_pending_project_proposes_the_team_and_the_link_holder(
    db_session, shema_app, form_app
) -> None:
    """The A4 rows with no address, and the link's own address under the requester's name."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)

    [project] = await filed_projects(db_session)
    rows = await db_session.execute(
        select(ShemaProjectPendingMember)
        .where(ShemaProjectPendingMember.project_id == project.id)
        .order_by(ShemaProjectPendingMember.position)
    )
    assert [(row.name, row.role, row.email) for row in rows.scalars()] == [
        ("Ana Teste", "coordenação", ""),
        ("Bruno Teste", "tradução", ""),
        ("Joana Teste", "", HOLDER),
    ]


async def test_the_same_request_never_files_two_projects(db_session, shema_app, form_app) -> None:
    """*Aprovar de novo não cria outro*: the filing asked twice for one request files once."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        request_id = await filing.decided(db_session)
        again = await put_evaluation(
            client, filing.mesa_headers, request_id, decision="approved", comments="outra vez"
        )
    assert again.status_code == 200, again.text

    snapshot = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == request_id))
    ).scalar_one()
    [first] = await filed_projects(db_session)
    answered = await create_pending_project_from_request(
        db_session, snapshot.document, request_id=request_id, link_id=filing.link["id"]
    )
    await db_session.commit()

    assert answered is not None and answered.id == first.id
    assert [project.id for project in await filed_projects(db_session)] == [first.id]


async def test_a_second_request_of_the_link_files_no_second_project(
    db_session, shema_app, form_app
) -> None:
    """One team, one project, however many of its requests the mesa approves while it waits."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        first = await filing.decided(db_session)
        second = await filing.decided(db_session, reg_name="Segundo pedido")
        [project] = await filed_projects(db_session)
        confirmed = await client.post(
            confirm_path(project.id), json=confirmation(), headers=filing.admin_headers
        )

    assert confirmed.status_code == 200, confirmed.text
    assert sorted(confirmed.json()["requestIds"]) == sorted([first, second])
    assert (await request_row(db_session, second)).shema_project_id == project.id


async def test_a_request_approved_after_the_confirmation_is_stamped_with_the_project(
    db_session, shema_app, form_app
) -> None:
    """Once the team's project exists, a later approval of the link points at it and files none."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        await client.post(
            confirm_path(project.id), json=confirmation(), headers=filing.admin_headers
        )
        later = await filing.decided(db_session, reg_name="Pedido depois")

    assert [row.id for row in await filed_projects(db_session)] == [project.id]
    assert (await request_row(db_session, later)).shema_project_id == project.id


@pytest.mark.parametrize("decision", ["conditional", "revise", "declined"])
async def test_no_other_decision_files_a_project(
    db_session, shema_app, form_app, decision: str
) -> None:
    """``approved`` and nothing else: *condicional* moves no money and is not an approval here."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session, decision=decision)

    assert await filed_projects(db_session) == []


async def test_the_database_holds_one_project_per_request_and_one_live_per_link(
    db_session,
) -> None:
    """The two unique indexes, as the rows they must refuse — the race the reads cannot close.

    A second live project for one link is refused, and so is a second project for one request,
    discarded or not; a discard frees the link; and the records nobody filed, with neither
    source, never collide on the NULLs.
    """

    def filed(project_id: str, request_id: str, link_id: str) -> ShemaProject:
        return ShemaProject(
            id=project_id,
            language_name=project_id,
            pending_confirmation=True,
            source_request_id=request_id,
            source_link_id=link_id,
        )

    db_session.add(filed("a", "r-1", "l-1"))
    await db_session.commit()

    for duplicate in (filed("b", "r-2", "l-1"), filed("c", "r-1", "l-2")):
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    first = await db_session.get(ShemaProject, "a")
    first.discarded_at = datetime.now(UTC)
    await db_session.commit()
    db_session.add(filed("d", "r-3", "l-1"))
    db_session.add_all(
        [ShemaProject(id="seed-1", language_name="x"), ShemaProject(id="seed-2", language_name="y")]
    )
    await db_session.commit()

    db_session.add(filed("e", "r-1", "l-3"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# --- nobody reads it but the Admin -------------------------------------------------------------


async def _one_of_each(db_session, client, shema_app, form_app) -> tuple[Filing, str]:
    """A pending project in South America and a registered one beside it, same region."""
    filing = await open_filing(db_session, client, shema_app, form_app)
    await filing.decided(db_session)
    await make_shema_project(
        db_session, project_id="registrado", region_key=ShemaRegionKey.SOUTH_AMERICA
    )
    [pending] = await filed_projects(db_session)
    return filing, pending.id


@pytest.mark.parametrize(
    ("role", "regions"),
    [
        ("coordinator", [ShemaRegionKey.SOUTH_AMERICA]),
        ("obtLab", [ShemaRegionKey.SOUTH_AMERICA]),
        ("resourceCircle", [ShemaRegionKey.SOUTH_AMERICA]),
        ("globalStrategist", None),
    ],
)
async def test_a_pending_project_is_absent_for_every_reader_of_the_collection(
    db_session, shema_app, form_app, role: str, regions
) -> None:
    """The DoD's second line, per role: not in the list, not in the counts, not on a direct id.

    Each reader reaches the region the pending project sits in, and the registered project beside
    it proves that — so an empty answer is the exclusion and not a scope that reaches nothing.
    """
    async with pending_client(db_session) as client:
        _filing, pending = await _one_of_each(db_session, client, shema_app, form_app)
        reader = await make_scoped_user(
            db_session, shema_app, email=f"{role}@shema.example", role_key=role, regions=regions
        )
        headers = await auth_header(db_session, reader)
        listed = await client.get(PROJECTS, headers=headers)
        direct = await client.get(f"{PROJECTS}/{pending}", headers=headers)
        roster = await client.get(f"{PROJECTS}/{pending}/members", headers=headers)

    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == ["registrado"]
    assert listed.json()["total"] == 1
    assert direct.status_code == 404
    assert roster.status_code == 404


async def test_the_admin_and_an_installation_admin_do_not_read_it_in_the_collection_either(
    db_session, shema_app, form_app
) -> None:
    """The Atlas shows a project once it is confirmed — for the Admin too, however global."""
    async with pending_client(db_session) as client:
        filing, pending = await _one_of_each(db_session, client, shema_app, form_app)
        await grant(db_session, filing.admin, shema_app, "globalStrategist")
        installation = await make_user(
            db_session, email="root@shema.example", is_platform_admin=True
        )
        seen = []
        for headers in (filing.admin_headers, await auth_header(db_session, installation)):
            listed = await client.get(PROJECTS, headers=headers)
            direct = await client.get(f"{PROJECTS}/{pending}", headers=headers)
            seen.append(([item["id"] for item in listed.json()["items"]], direct.status_code))

    assert seen == [(["registrado"], 404), (["registrado"], 404)]


@pytest.mark.parametrize("seat", ["gestor", "mesa"])
async def test_the_forms_seats_do_not_reach_it_through_the_door(
    db_session, shema_app, form_app, seat: str
) -> None:
    """The mesa and the Gestor pass the PME's door; the roster read behind it answers 404."""
    async with pending_client(db_session) as client:
        _filing, pending = await _one_of_each(db_session, client, shema_app, form_app)
        account = await make_user(db_session, email=f"{seat}-door@shema.example")
        await grant(db_session, account, form_app, seat)
        roster = await client.get(
            f"{PROJECTS}/{pending}/members", headers=await auth_header(db_session, account)
        )

    assert roster.status_code == 404


async def test_the_exclusion_lives_in_the_scope_every_reader_starts_from(
    db_session, shema_app, form_app
) -> None:
    """Not a filter a route applies: ``within_scope`` carries it, for every scope, so the counts,
    the ETEN report, the needs and the export a later issue builds inherit it by starting there.
    """
    async with pending_client(db_session) as client:
        await _one_of_each(db_session, client, shema_app, form_app)

    everywhere = RegionScope(global_=True, regions=frozenset())
    here = RegionScope(global_=False, regions=frozenset({"south-america"}))
    for scope in (everywhere, here):
        assert "pending_confirmation" in str(within_scope(scope))
        ids = (await db_session.execute(visible_projects(scope))).scalars().all()
        assert [project.id for project in ids] == ["registrado"]
        assert await count_projects(db_session, scope) == 1


# --- the Admin reads it ------------------------------------------------------------------------


async def test_the_admin_reads_the_pending_projects(db_session, shema_app, form_app) -> None:
    """The DoD's *visível para admin*: the place as typed, the people, the request's name."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        request_id = await filing.decided(db_session)
        res = await client.get(PENDING, headers=filing.admin_headers)

    assert res.status_code == 200, res.text
    assert res.headers["cache-control"] == "private, no-store"
    [entry] = res.json()
    assert entry["requestId"] == request_id
    assert entry["requestName"] == "Projeto Língua Teste"
    assert entry["languageName"] == "Língua Teste"
    assert entry["location"] == "Peru, Vale Teste"
    assert entry["team"] == ""
    assert entry["locationWithheld"] is False
    assert [member["email"] for member in entry["members"]] == ["", "", HOLDER]


@pytest.mark.parametrize("role", ["coordinator", "obtLab", "resourceCircle", "globalStrategist"])
async def test_only_the_admin_reads_or_decides_a_pending_project(
    db_session, shema_app, form_app, role: str
) -> None:
    """Every Shemá role but ``admin`` is refused the list and both acts — and nothing moves."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        other = await make_scoped_user(
            db_session,
            shema_app,
            email=f"not-admin-{role}@shema.example",
            role_key=role,
            regions=None if role == "globalStrategist" else [ShemaRegionKey.SOUTH_AMERICA],
        )
        headers = await auth_header(db_session, other)
        listed = await client.get(PENDING, headers=headers)
        confirmed = await client.post(
            confirm_path(project.id), json=confirmation(), headers=headers
        )
        discarded = await client.post(
            reject_path(project.id), json={"reason": "não"}, headers=headers
        )

    assert (listed.status_code, confirmed.status_code, discarded.status_code) == (403, 403, 403)
    await db_session.refresh(project)
    assert project.pending_confirmation is True and project.discarded_at is None


@pytest.mark.parametrize("seat", ["gestor", "mesa"])
async def test_the_forms_seats_are_refused_at_the_app_gate(
    db_session, shema_app, form_app, seat: str
) -> None:
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        account = await make_user(db_session, email=f"{seat}-gate@shema.example")
        await grant(db_session, account, form_app, seat)
        listed = await client.get(PENDING, headers=await auth_header(db_session, account))

    assert listed.status_code == 403


# --- confirming --------------------------------------------------------------------------------


async def test_confirming_stamps_the_project_on_the_request_and_opens_it_to_its_region(
    db_session, shema_app, form_app
) -> None:
    """``shema_project_id`` on the request, the project out of pending, and in the Atlas now."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        request_id = await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        res = await client.post(
            confirm_path(project.id), json=confirmation(), headers=filing.admin_headers
        )
        coordinator = await make_scoped_user(
            db_session,
            shema_app,
            email="coord-after@shema.example",
            role_key="coordinator",
            regions=[ShemaRegionKey.SOUTH_AMERICA],
        )
        listed = await client.get(PROJECTS, headers=await auth_header(db_session, coordinator))
        pending = await client.get(PENDING, headers=filing.admin_headers)

    assert res.status_code == 200, res.text
    assert res.json()["requestIds"] == [request_id]
    assert (await request_row(db_session, request_id)).shema_project_id == project.id
    await db_session.refresh(project)
    assert project.pending_confirmation is False
    assert [item["id"] for item in listed.json()["items"]] == [project.id]
    assert pending.json() == []


async def test_confirming_applies_the_adjustments_the_flag_and_the_trail(
    db_session, shema_app, form_app
) -> None:
    """The Admin's corrections land, the region follows the place, and the trail names the Admin."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        res = await client.post(
            confirm_path(project.id),
            json=confirmation(
                languageName="Língua Corrigida",
                location="Mozambique",
                team="Base Corrigida",
                sensitiveCountry=True,
            ),
            headers=filing.admin_headers,
        )
        reader = await make_scoped_user(
            db_session,
            shema_app,
            email="lab-after@shema.example",
            role_key="obtLab",
            regions=[ShemaRegionKey.AFRICA],
        )
        record = await client.get(
            f"{PROJECTS}/{project.id}", headers=await auth_header(db_session, reader)
        )

    assert res.status_code == 200, res.text
    await db_session.refresh(project)
    assert project.language_name == "Língua Corrigida"
    assert project.region_key is ShemaRegionKey.AFRICA
    assert project.sensitive_country is True
    assert record.status_code == 200, record.text
    assert record.json()["locationWithheld"] is True
    assert record.json()["location"] == "africa"
    edits = (
        await db_session.execute(
            select(ShemaRecordEdit.field_key, ShemaRecordEdit.changed_by).where(
                ShemaRecordEdit.project_id == project.id
            )
        )
    ).all()
    assert {key for key, _by in edits} >= {"languageName", "location", "team", "sensitiveCountry"}
    assert {by for _key, by in edits} == {filing.admin.id}


async def test_a_field_the_confirmation_leaves_out_keeps_what_was_filed(
    db_session, shema_app, form_app
) -> None:
    """An omitted ``location``, ``languageCode`` or ``team`` is no adjustment, never a blank.

    Blanking the place would derive the region to ``other`` and hide the project from the
    coordination of the region the team typed; the trail could not give the place back.
    """
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        project.team = "Base Arquivada"
        await db_session.commit()
        body = confirmation()
        for key in ("location", "languageCode", "team"):
            del body[key]
        res = await client.post(confirm_path(project.id), json=body, headers=filing.admin_headers)
        coordinator = await make_scoped_user(
            db_session,
            shema_app,
            email="coord-kept@shema.example",
            role_key="coordinator",
            regions=[ShemaRegionKey.SOUTH_AMERICA],
        )
        listed = await client.get(PROJECTS, headers=await auth_header(db_session, coordinator))

    assert res.status_code == 200, res.text
    await db_session.refresh(project)
    assert (project.location, project.language_code, project.team) == (
        "Peru, Vale Teste",
        "ltt",
        "Base Arquivada",
    )
    assert project.region_key is ShemaRegionKey.SOUTH_AMERICA
    assert [item["id"] for item in listed.json()["items"]] == [project.id]


async def test_the_flag_is_a_decision_the_body_must_state(db_session, shema_app, form_app) -> None:
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        body = confirmation()
        del body["sensitiveCountry"]
        res = await client.post(confirm_path(project.id), json=body, headers=filing.admin_headers)

    assert res.status_code == 422
    await db_session.refresh(project)
    assert project.pending_confirmation is True


async def test_confirming_adds_accounts_and_invites_the_rest(
    db_session, shema_app, form_app
) -> None:
    """An address with an account joins the team; one without is invited to it, naming the
    project and no role; a blank one is left out and named; the same address twice is one."""
    existing = await make_user(db_session, email="ana@fora.example", display_name="Ana Teste")
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        res = await client.post(
            confirm_path(project.id),
            json=confirmation(
                members=[
                    {"name": "Ana Teste", "email": "ANA@fora.example"},
                    {"name": "Bruno Teste", "email": ""},
                    {"name": "Joana Teste", "email": HOLDER},
                    {"name": "Joana de novo", "email": HOLDER},
                ]
            ),
            headers=filing.admin_headers,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["joined"] == [{"email": "ana@fora.example", "userId": existing.id}]
    assert body["withoutEmail"] == ["Bruno Teste"]
    [invited] = body["invited"]
    assert invited["email"] == HOLDER
    assert "/convite?token=" in invited["inviteUrl"]

    members = (
        await db_session.execute(
            select(ShemaProjectMember.user_id, ShemaProjectMember.added_by).where(
                ShemaProjectMember.project_id == project.id,
                ShemaProjectMember.removed_at.is_(None),
            )
        )
    ).all()
    assert members == [(existing.id, filing.admin.id)]
    invite = (
        await db_session.execute(select(AccessInvite).where(AccessInvite.email == HOLDER))
    ).scalar_one()
    assert (invite.project_id, invite.role_id, invite.app_id) == (project.id, None, shema_app.id)


async def test_accepting_a_project_invite_puts_the_person_on_the_team(
    db_session, shema_app, form_app
) -> None:
    """The DoD's third line, last half: signing up with the invited address and accepting makes a
    live membership — the session answers ``equipe`` and ``/me/projects`` lists the project."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        confirmed = await client.post(
            confirm_path(project.id),
            json=confirmation(members=[{"name": "Joana Teste", "email": HOLDER}]),
            headers=filing.admin_headers,
        )
        token = confirmed.json()["invited"][0]["inviteUrl"].split("token=")[1]
        listed = await client.get(INVITES, headers=filing.admin_headers)
        described = await client.get(f"{FORM_INVITES}/{token}")
        signed = await client.post(
            "/api/auth/signup",
            json={"email": HOLDER, "password": "a-long-password", "display_name": "Joana"},
        )
        joiner = {"Authorization": f"Bearer {signed.json()['tokens']['access_token']}"}
        accepted = await client.post(f"{FORM_INVITES}/{token}/accept", headers=joiner)
        session = await client.get(SESSION, headers=joiner)
        mine = await client.get(f"{PREFIX}/me/projects", headers=joiner)

    team_invites = [entry for entry in listed.json() if entry["projectId"] == project.id]
    assert [(entry["roleKey"], entry["status"]) for entry in team_invites] == [
        ("equipe", "pending")
    ]
    assert described.json()["role_key"] == "equipe"
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role_key"] == "equipe"
    assert accepted.json()["granted_by"] == filing.admin.id
    assert session.json()["roles"] == ["equipe"]
    assert [ref["id"] for ref in mine.json()] == [project.id]


async def test_a_team_invite_can_be_recalled_before_it_is_accepted(
    db_session, shema_app, form_app
) -> None:
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        confirmed = await client.post(
            confirm_path(project.id),
            json=confirmation(members=[{"name": "Joana Teste", "email": HOLDER}]),
            headers=filing.admin_headers,
        )
        invite_id = confirmed.json()["invited"][0]["inviteId"]
        recalled = await client.post(
            f"{INVITES}/revoke", json={"inviteId": invite_id}, headers=filing.admin_headers
        )

    assert recalled.status_code == 200, recalled.text
    assert (recalled.json()["status"], recalled.json()["projectId"]) == ("revoked", project.id)


# --- discarding --------------------------------------------------------------------------------


async def test_discarding_keeps_the_request_approved_and_without_a_project(
    db_session, shema_app, form_app
) -> None:
    """The DoD's fourth line: the reason is recorded, the request stays approved with no project,
    and the project stays out of every read — the Admin's list included."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        request_id = await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        res = await client.post(
            reject_path(project.id),
            json={"reason": "  Já existe no PME  "},
            headers=filing.admin_headers,
        )
        pending = await client.get(PENDING, headers=filing.admin_headers)

    assert res.status_code == 200, res.text
    assert res.json()["requestId"] == request_id
    assert res.json()["requestProjectId"] is None
    assert "approved" in res.json()["detail"]
    await db_session.refresh(project)
    assert (project.discard_reason, project.discarded_by) == ("Já existe no PME", filing.admin.id)
    assert project.pending_confirmation is True
    request = await request_row(db_session, request_id)
    assert (request.shema_project_id, request.stage) == (None, RRStage.APROVADO)
    decision = (
        await db_session.execute(
            select(RREvaluation.decision)
            .join(RRSnapshot, RRSnapshot.id == RREvaluation.snapshot_id)
            .where(RRSnapshot.request_id == request_id)
        )
    ).scalar_one()
    assert decision.value == "approved"
    assert pending.json() == []


async def test_a_discard_needs_a_reason(db_session, shema_app, form_app) -> None:
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        blank = await client.post(
            reject_path(project.id), json={"reason": "   "}, headers=filing.admin_headers
        )
        missing = await client.post(reject_path(project.id), json={}, headers=filing.admin_headers)

    assert (blank.status_code, missing.status_code) == (422, 422)


async def test_a_discard_frees_the_link_for_a_later_approval(
    db_session, shema_app, form_app
) -> None:
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [discarded] = await filed_projects(db_session)
        await client.post(
            reject_path(discarded.id), json={"reason": "duplicado"}, headers=filing.admin_headers
        )
        later = await filing.decided(db_session, reg_name="Pedido novo")

    projects = await filed_projects(db_session)
    assert [project.id == discarded.id for project in projects] == [True, False]
    assert projects[1].source_request_id == later
    assert projects[1].pending_confirmation is True


async def test_a_decided_project_is_not_decided_again(db_session, shema_app, form_app) -> None:
    """A second act is a 409 that says which decision stands; an id nobody filed is a 404."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        headers = filing.admin_headers
        first = await client.post(confirm_path(project.id), json=confirmation(), headers=headers)
        again = await client.post(confirm_path(project.id), json=confirmation(), headers=headers)
        discard = await client.post(reject_path(project.id), json={"reason": "x"}, headers=headers)
        await make_shema_project(
            db_session, project_id="do-seed", region_key=ShemaRegionKey.SOUTH_AMERICA
        )
        seed = await client.post(confirm_path("do-seed"), json=confirmation(), headers=headers)
        unknown = await client.post(confirm_path("nenhum"), json=confirmation(), headers=headers)

    assert first.status_code == 200, first.text
    assert (again.status_code, discard.status_code) == (409, 409)
    assert "already confirmed" in again.json()["detail"]
    assert (seed.status_code, unknown.status_code) == (404, 404)


async def test_the_admin_writes_no_roster_on_a_pending_project(
    db_session, shema_app, form_app
) -> None:
    """A membership on a project nobody confirmed would reach a project nobody may see."""
    async with pending_client(db_session) as client:
        filing = await open_filing(db_session, client, shema_app, form_app)
        await filing.decided(db_session)
        [project] = await filed_projects(db_session)
        someone = await make_user(db_session, email="someone@fora.example")
        added = await client.post(
            f"{PROJECTS}/{project.id}/members",
            json={"userId": someone.id},
            headers=filing.admin_headers,
        )

    assert added.status_code == 404
    count = await db_session.execute(select(func.count()).select_from(ShemaProjectMember))
    assert count.scalar_one() == 0
