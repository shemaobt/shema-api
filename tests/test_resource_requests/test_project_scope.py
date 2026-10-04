"""A request belongs to a PME project, and the team is the project's members — BE-19 (OBT-520).

GATE-04 (OBT-519) gave *"uma por equipe"* (Karina, 21/sep/2026) its subject: the team is the
members of a project in the PME (``shema_project_members``, OBT-524), not an account of this
app. These tests hold the server half: the door and the capabilities read a live membership,
a member reads what a teammate started and nothing of another project, the project a request
belongs to is stamped from a checked membership and never from the document, and the count
the one-per-project rule reads.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models.resource_request import (
    RRAttachment,
    RRDecision,
    RRRequest,
    RRRequestFieldHistory,
)
from app.services.oral_collector import gcs_utils
from app.services.resource_request import count_project_translations
from tests.baker import make_user
from tests.resource_request_harness import (
    PDF,
    REQUESTS,
    FakeStore,
    create,
    decide,
    draft,
    put_file,
)
from tests.test_resource_requests.conftest import (
    auth_header,
    grant,
    make_membership,
    make_project,
    own_project_id,
)


async def member_of(db_session, project_id: str, email: str):
    """An account whose **only** tie to the app is a live membership — no grant at all."""
    user = await make_user(db_session, email=email)
    await make_membership(db_session, user, project_id)
    return user, await auth_header(db_session, user)


# ——— the door and the capabilities ——————————————————————————————————————————————


async def test_a_member_with_no_grant_passes_the_door_and_opens_a_request(
    db_session, client, rrf_app
) -> None:
    """The team no longer holds a grant here: ``20260928_rr08`` revokes them. A live
    membership is what holds ``equipe``, for the door and for ``edit_requests`` alike."""
    user, headers = await member_of(db_session, "kadiweu", "membro@rr.test")

    created = await create(client, headers)

    assert created["created_by"] == user.id
    row = await db_session.get(RRRequest, created["id"])
    assert row.shema_project_id == "kadiweu"


async def test_a_removed_member_is_refused_at_the_door(db_session, client, rrf_app) -> None:
    """Leaving the project closes the door: the membership is the grant, and a removed stay is
    not a live one."""
    from datetime import UTC, datetime

    user = await make_user(db_session, email="saiu@rr.test")
    stay = await make_membership(db_session, user, "kadiweu")
    stay.removed_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.get(REQUESTS, headers=await auth_header(db_session, user))

    assert res.status_code == 403


# ——— the project a request belongs to ———————————————————————————————————————————


async def test_the_project_never_rides_in_the_document(db_session, client, rrf_app) -> None:
    """``RequestDraftIn`` forbids extra keys, and the body is the document."""
    _user, headers = await member_of(db_session, "kadiweu", "corpo@rr.test")

    res = await client.post(REQUESTS, json=draft(shema_project_id="outro"), headers=headers)

    assert res.status_code == 422


async def test_a_member_opens_only_in_a_project_they_belong_to(db_session, client, rrf_app) -> None:
    _user, headers = await member_of(db_session, "kadiweu", "dono@rr.test")
    await make_project(db_session, "alheio")

    refused = await client.post(
        REQUESTS, params={"project_id": "alheio"}, json=draft(), headers=headers
    )
    accepted = await client.post(
        REQUESTS, params={"project_id": "kadiweu"}, json=draft(), headers=headers
    )

    assert refused.status_code == 403
    assert accepted.status_code == 201


async def test_a_member_of_several_projects_must_say_which(db_session, client, rrf_app) -> None:
    """Guessing between two of their own projects would file the request under a team that
    never opened it."""
    user, headers = await member_of(db_session, "kadiweu", "dois@rr.test")
    await make_membership(db_session, user, "fataluku")

    unsaid = await client.post(REQUESTS, json=draft(), headers=headers)
    said = await client.post(
        REQUESTS, params={"project_id": "fataluku"}, json=draft(), headers=headers
    )

    assert unsaid.status_code == 422
    assert said.status_code == 201
    row = await db_session.get(RRRequest, said.json()["id"])
    assert row.shema_project_id == "fataluku"


async def test_the_board_opens_with_or_without_a_project(db_session, client, rrf_app) -> None:
    """The mesa and the Gestor reach the whole board and are members of nothing: they may
    open with no project, or name one that exists — and only one that exists."""
    user = await make_user(db_session, email="gestor@rr.test")
    await grant(db_session, user, rrf_app, "gestor")
    headers = await auth_header(db_session, user)
    await make_project(db_session, "kadiweu")

    without = await client.post(REQUESTS, json=draft(), headers=headers)
    named = await client.post(
        REQUESTS, params={"project_id": "kadiweu"}, json=draft(), headers=headers
    )
    unknown = await client.post(
        REQUESTS, params={"project_id": "nao-existe"}, json=draft(), headers=headers
    )

    assert without.status_code == 201
    assert named.status_code == 201
    assert unknown.status_code == 422


async def test_a_revision_stays_in_the_project(db_session, client, rrf_app) -> None:
    """What the mesa evaluated stays that project's, and so does what it asked to revise."""
    team = await make_user(db_session, email="revisa@rr.test")
    await grant(db_session, team, rrf_app, "equipe")
    headers = await auth_header(db_session, team)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    await decide(db_session, created["id"], RRDecision.REVISE)

    opened = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)

    assert opened.status_code == 201, opened.text
    revision = await db_session.get(RRRequest, opened.json()["id"])
    assert revision.shema_project_id == own_project_id(team)


# ——— what a member reads ————————————————————————————————————————————————————————


async def test_a_member_reads_a_teammates_draft_and_submission_and_nothing_of_another_project(
    db_session, client, rrf_app
) -> None:
    """GATE-04 D2: every member sees the instance, drafts included. The other project's team
    is invisible — the 404 that hides a foreign request's existence, not a 403."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@rr.test")
    _caio, caio = await member_of(db_session, "fataluku", "caio@rr.test")

    teammate_sent = await create(client, ana)
    await client.post(f"{REQUESTS}/{teammate_sent['id']}/submit", headers=ana)
    teammate_draft = await create(client, ana)
    foreign = await create(client, caio)

    listed = {row["id"] for row in (await client.get(REQUESTS, headers=bia)).json()}

    assert teammate_draft["id"] in listed
    assert teammate_sent["id"] in listed
    assert foreign["id"] not in listed
    assert (await client.get(f"{REQUESTS}/{teammate_draft['id']}", headers=bia)).status_code == 200
    assert (await client.get(f"{REQUESTS}/{foreign['id']}", headers=bia)).status_code == 404


# ——— what a member writes: reading a teammate's request is not editing it ——————————————


@pytest.fixture()
def storage(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    return fake


async def _count(db_session, model, request_id: str) -> int:
    stmt = select(func.count()).select_from(model).where(model.request_id == request_id)
    return (await db_session.execute(stmt)).scalar_one()


async def test_a_teammate_reads_a_draft_but_does_not_edit_it(db_session, client, rrf_app) -> None:
    """OBT-520: the draft is *só leitura para quem não o iniciou*. Who edits a project's
    instance is OBT-534's to decide, so until then the scope that opens the read does not
    open the write — and no trail is written in the teammate's name."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@rr.test")
    started = await create(client, ana)

    res = await client.patch(
        f"{REQUESTS}/{started['id']}",
        json=draft(team=[{"name": "Bia", "role": "coordenação"}]),
        headers=bia,
    )

    assert res.status_code == 403, res.text
    assert await _count(db_session, RRRequestFieldHistory, started["id"]) == 0


async def test_the_board_reads_a_teams_draft_and_does_not_edit_it(
    db_session, client, rrf_app
) -> None:
    """BE-25 (OBT-534) closed what BE-19 left open: the mesa reaches the whole board and
    reads the draft there, and writing it is the starter's — GATE-02 D4, revised by Daniel
    on 23/sep/2026."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    mesa = await make_user(db_session, email="mesa@rr.test")
    await grant(db_session, mesa, rrf_app, "mesa")
    mesa_headers = await auth_header(db_session, mesa)
    started = await create(client, ana)

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=mesa_headers)
    res = await client.patch(
        f"{REQUESTS}/{started['id']}",
        json=draft(team=[{"name": "Mesa", "role": "coordenação"}]),
        headers=mesa_headers,
    )

    assert read.status_code == 200
    assert read.json()["can_edit"] is False
    assert res.status_code == 403, res.text


async def test_a_teammate_does_not_replace_the_budget_file(
    db_session, client, rrf_app, storage
) -> None:
    """Refused before a byte reaches the bucket, so no object is left behind either."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@rr.test")
    started = await create(client, ana)

    res = await put_file(client, started["id"], bia, PDF, "application/pdf", filename="b.pdf")

    assert res.status_code == 403, res.text
    assert storage.objects == {}
    assert await _count(db_session, RRAttachment, started["id"]) == 0


async def test_a_teammate_does_not_open_a_revision_of_anothers_request(
    db_session, client, rrf_app
) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@rr.test")
    started = await create(client, ana)
    await client.post(f"{REQUESTS}/{started['id']}/submit", headers=ana)
    await decide(db_session, started["id"], RRDecision.REVISE)

    res = await client.post(f"{REQUESTS}/{started['id']}/revise", headers=bia)

    assert res.status_code == 403, res.text
    revisions = (
        select(func.count()).select_from(RRRequest).where(RRRequest.revision_of_id.is_not(None))
    )
    assert (await db_session.execute(revisions)).scalar_one() == 0


async def test_a_teammate_does_not_sign_anothers_draft(db_session, client, rrf_app) -> None:
    """Submitting was already the author's alone — it is the electronic acceptance; held here
    beside the three writes the project scope opened, so the list is whole."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@rr.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@rr.test")
    started = await create(client, ana)

    res = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=bia)

    assert res.status_code == 403, res.text
    row = await db_session.get(RRRequest, started["id"])
    assert row.submitted_at is None


# ——— the count the one-per-project rule reads ——————————————————————————————————


async def test_the_count_is_submitted_translations_of_the_project_and_nothing_else(
    db_session, client, rrf_app
) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "conta@rr.test")
    _caio, caio = await member_of(db_session, "fataluku", "outro@rr.test")

    sent = await create(client, ana)
    await client.post(f"{REQUESTS}/{sent['id']}/submit", headers=ana)
    training = await create(
        client,
        ana,
        request_type="treinamento",
        team=[{"name": "Ana", "role": "coordenação"}],
        checks={"teamtype": ["tradutores"], "trainformat": ["cursos"]},
    )
    assert (
        await client.post(f"{REQUESTS}/{training['id']}/submit", headers=ana)
    ).status_code == 200
    await create(client, ana)
    elsewhere = await create(client, caio)
    await client.post(f"{REQUESTS}/{elsewhere['id']}/submit", headers=caio)

    submitted = (
        await db_session.execute(
            select(RRRequest.id).where(
                RRRequest.id == sent["id"], RRRequest.submitted_at.is_not(None)
            )
        )
    ).scalar_one_or_none()
    assert submitted is not None

    assert await count_project_translations(db_session, "kadiweu") == 1
    assert await count_project_translations(db_session, "fataluku") == 1
    assert await count_project_translations(db_session, "sem-pedido") == 0
