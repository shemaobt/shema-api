"""ENG-2089 — a reader lists a passage's archives, newest first, each with its Zerar snapshot."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRArchive, IRSession
from app.main import app as the_app
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.opening_harness import the_tablet_opens
from tests.release_harness import PREFIX, P, a_claimed_device, at_the_desk, team_headers
from tests.room_harness import room_client, the_room_speaks

ABSENT_TEAM = "nao-existe-em-lugar-nenhum"


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    await make_role(db_session, app.id, role_key="consultant", label="Consultant", is_system=True)
    return app


@pytest.fixture()
async def consultant(db_session: AsyncSession, room_app) -> dict[str, str]:
    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


def archive_url(team_id: str, pericope: str, door: str = "archive") -> str:
    return f"{PREFIX}/facilitator/projects/{team_id}/passages/{pericope}/{door}"


async def zerar(
    client: httpx.AsyncClient, desk: dict[str, str], team_id: str, pericope: str
) -> dict[str, Any]:
    answered = await client.post(archive_url(team_id, pericope), headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    body = answered.json()
    assert body["archived"] is True
    return body["archive"]


async def listed(
    client: httpx.AsyncClient, headers: dict[str, str], team_id: str, pericope: str
) -> httpx.Response:
    return await client.get(archive_url(team_id, pericope, "archives"), headers=headers)


async def test_two_zerars_on_one_passage_are_listed_the_later_first_each_as_its_zerar_answered(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    first_session = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    first = await zerar(client, desk, team.id, P)
    second_session = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    second = await zerar(client, desk, team.id, P)

    answered = await listed(client, desk, team.id, P)

    assert answered.status_code == 200
    assert answered.json() == {"archives": [second, first]}
    assert first_session["session_id"] != second_session["session_id"]
    newest, oldest = answered.json()["archives"]
    assert [s["session_id"] for s in newest["sessions"]] == [second_session["session_id"]]
    assert [s["session_id"] for s in oldest["sessions"]] == [first_session["session_id"]]


async def test_a_passage_never_zeroed_lists_no_archive_never_404(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    answered = await listed(client, desk, team.id, P)

    assert answered.status_code == 200
    assert answered.json() == {"archives": []}


async def test_a_passages_list_holds_only_this_teams_archives(client, db_session, room_app) -> None:
    team_a, tablet_a = await a_claimed_device(db_session)
    team_b, tablet_b = await a_claimed_device(db_session, email="outra@example.com")
    desk_a, _ = await at_the_desk(db_session, room_app, team_a)
    desk_b, _ = await at_the_desk(db_session, room_app, team_b)
    await the_tablet_opens(client, tablet_a, {"pericope": P, "language": "pt"})
    await the_tablet_opens(client, tablet_b, {"pericope": P, "language": "pt"})
    zeroed_a = await zerar(client, desk_a, team_a.id, P)
    zeroed_b = await zerar(client, desk_b, team_b.id, P)

    assert (await listed(client, desk_a, team_a.id, P)).json() == {"archives": [zeroed_a]}
    assert (await listed(client, desk_b, team_b.id, P)).json() == {"archives": [zeroed_b]}


async def test_a_zeroed_panorama_is_listed_under_ov_book_and_the_books_passages_list_nothing(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    panorama = await the_tablet_opens(client, tablet, {"pericope": "OV"})
    assert panorama["pericope"] == f"OV-{ROOM_BOOK}"
    zeroed = await zerar(client, desk, team.id, f"OV-{ROOM_BOOK}")

    under_panorama = await listed(client, desk, team.id, f"OV-{ROOM_BOOK}")

    assert under_panorama.json() == {"archives": [zeroed]}
    for passage in load_book(ROOM_BOOK):
        under_passage = await listed(client, desk, team.id, passage.pericope_num)
        assert under_passage.json() == {"archives": []}, passage.pericope_num


async def test_the_teams_tablet_credential_cannot_list_the_archives(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)

    refused = await listed(client, team_headers(tablet), team.id, P)

    assert refused.status_code == 401


async def test_a_facilitator_of_another_team_is_answered_as_a_team_that_does_not_exist(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    other, _ = await a_claimed_device(db_session, email="outra@example.com")
    desk, _ = await at_the_desk(db_session, room_app, team)
    stranger, _ = await at_the_desk(db_session, room_app, other)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)

    theirs = await listed(client, stranger, team.id, P)
    nothing = await listed(client, stranger, ABSENT_TEAM, P)

    assert theirs.status_code == nothing.status_code == 404
    assert theirs.json() == nothing.json() == {"detail": "Team not found", "code": "NOT_FOUND"}


async def test_the_consultant_lists_the_archives_the_teams_facilitator_lists(
    client, db_session, room_app, consultant
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)

    by_facilitator = await listed(client, desk, team.id, P)
    by_consultant = await listed(client, consultant, team.id, P)
    absent = await listed(client, consultant, ABSENT_TEAM, P)

    assert by_consultant.status_code == 200
    assert len(by_consultant.json()["archives"]) == 2
    assert by_consultant.json() == by_facilitator.json()
    assert absent.status_code == 404
    assert absent.json() == {"detail": "Team not found", "code": "NOT_FOUND"}


async def test_listing_the_archives_writes_nothing(
    client, db_session, per_request, room_app, consultant
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)
    live = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    async def what_is_stored() -> tuple[int, list[tuple[Any, ...]]]:
        async with per_request() as fresh:
            archives = await fresh.scalar(select(func.count()).select_from(IRArchive))
            sessions = await fresh.execute(
                select(
                    IRSession.id, IRSession.archive_id, IRSession.version, IRSession.updated_at
                ).order_by(IRSession.id)
            )
            return archives, [tuple(row) for row in sessions.all()]

    before = await what_is_stored()

    for headers in (desk, consultant, desk, consultant):
        assert (await listed(client, headers, team.id, P)).status_code == 200

    assert await what_is_stored() == before
    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    assert reopened["session_id"] == live["session_id"]


def test_the_api_reference_documents_the_archives_door_with_archive_view() -> None:
    spec = the_app.openapi()
    door = spec["paths"][archive_url("{project_id}", "{pericope}", "archives")]["get"]
    schema = door["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]

    assert schema["type"] == "object"
    assert schema["properties"]["archives"]["type"] == "array"
    assert schema["properties"]["archives"]["items"] == {"$ref": "#/components/schemas/ArchiveView"}
