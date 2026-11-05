"""ENG-2188 — the team's pericope listing answers any served book the reader names.

Each passage is placed for this team as the Current book's are, and only the Current book has a
current passage. Every case reads the route as a client does.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import load_book, served_maps
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import apply_coverage
from tests.baker import (
    grant_room_app_role,
    having_finished_the_passage,
    make_app,
    make_role,
    make_user,
    open_ir_session,
)
from tests.opening_harness import desk_routes
from tests.release_harness import (
    APP_KEY,
    P,
    a_claimed_device,
    at_the_desk,
    desk_release,
    ready_session,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import room_client, the_bucket_is_in_memory, upload_a_part

ESTHER = [meaning_map.pericope_num for meaning_map in load_book("Esther")]
JONAH = [meaning_map.pericope_num for meaning_map in load_book("Jonah")]
RUTH = [meaning_map.pericope_num for meaning_map in load_book("Ruth")]
TEAM_NOT_FOUND = {"detail": "Team not found", "code": "NOT_FOUND"}


@pytest.fixture()
async def room(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
    async with desk_routes(db_session) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def team_at_the_desk(db_session: AsyncSession, room_app):
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    return team, tablet, desk


@pytest.fixture()
async def stranger(db_session: AsyncSession, room_app) -> dict[str, str]:
    other_team, _tablet = await a_claimed_device(db_session)
    headers, _ = await at_the_desk(db_session, room_app, other_team)
    return headers


async def the_answer(
    desk_client: httpx.AsyncClient, headers: dict[str, str], team_id: str, book: str | None = None
) -> httpx.Response:
    return await desk_client.get(
        f"/api/facilitator/teams/{team_id}/pericopes",
        headers=headers,
        params={} if book is None else {"book": book},
    )


async def the_listing(
    desk_client: httpx.AsyncClient, headers: dict[str, str], team_id: str, book: str | None = None
) -> list[dict]:
    answered = await the_answer(desk_client, headers, team_id, book)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def having_closed(db: AsyncSession, team_id: str, *passages: str) -> None:
    for passage in passages:
        session = await open_ir_session(db, pericope=passage, project_id=team_id)
        await having_finished_the_passage(db, session)


async def approved_by_the_team(
    db: AsyncSession, room: httpx.AsyncClient, tablet: str, team_id: str, passage: str
) -> IRSession:
    session = await ready_session(db, pericope=passage, project_id=team_id)
    approved = await room.post(team_release(session.id), headers=team_headers(tablet))
    assert approved.status_code == 200, approved.text[:300]
    await apply_coverage(
        db, session.id, dict.fromkeys(element_keys(passage), CoverageStatus.ENGAGED.value)
    )
    return session


def positions(body: list[dict]) -> dict[str, str]:
    return {entry["pericope"]: entry["position"] for entry in body}


def every_passage(passages: list[str], position: str) -> dict[str, str]:
    return dict.fromkeys(passages, position)


async def row_counts(db: AsyncSession) -> dict[str, int]:
    from app.core.database import Base

    return {
        table.name: (await db.execute(select(func.count()).select_from(table))).scalar_one()
        for table in Base.metadata.sorted_tables
    }


async def test_with_no_book_the_listing_answers_the_current_book_as_it_does_today(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, RUTH[0])

    no_book = await the_listing(desk_client, desk, team.id)

    assert positions(no_book)[RUTH[1]] == "current"
    assert no_book == await the_listing(desk_client, desk, team.id, "ruth")


async def test_a_team_standing_in_ruth_asking_for_esther_reads_every_passage_future_in_the_canons_order_none_current_and_none_with_a_release(  # noqa: E501
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, RUTH[0])

    listing = await the_listing(desk_client, desk, team.id, "esther")

    assert [(e["pericope"], e["reference"], e["title"]) for e in listing] == [
        (meaning_map.pericope_num, meaning_map.reference, meaning_map.title)
        for meaning_map in load_book("Esther")
    ]
    assert {e["position"] for e in listing} == {"future"}
    assert [e["release"] for e in listing] == [None] * len(ESTHER)
    assert not any(e["approved"] or e["open_findings"] or e["session_id"] for e in listing)


async def test_a_team_that_closed_ruth_and_stands_in_esther_asking_for_ruth_reads_every_passage_closed_each_with_its_latest_release_approval_and_open_findings(  # noqa: E501
    room, desk_client, db_session, team_at_the_desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, tablet, desk = team_at_the_desk
    first = RUTH[0]
    await approved_by_the_team(db_session, room, tablet, team.id, first)
    forced_again = await approved_by_the_team(db_session, room, tablet, team.id, P)
    the_bucket_is_in_memory(monkeypatch)
    again = await upload_a_part(
        room, forced_again.id, part=None, audio=b"recorded again", headers=team_headers(tablet)
    )
    assert again.status_code == 200, again.text[:300]
    await reported_playback(
        db_session,
        forced_again,
        await told_back_with_an_open_finding(db_session, forced_again),
    )
    forced = await room.post(desk_release(forced_again.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text[:300]
    unreleased = [passage for passage in RUTH if passage not in (first, P)]
    await having_closed(db_session, team.id, *unreleased)

    listing = await the_listing(desk_client, desk, team.id, "ruth")
    by_passage = {entry["pericope"]: entry for entry in listing}

    assert positions(listing) == every_passage(RUTH, "closed")
    assert by_passage[first]["release"]["version"] == 1
    assert by_passage[first]["release"]["forced_at"] is None
    assert by_passage[first]["approved"] is True
    assert by_passage[first]["open_findings"] == 0
    assert by_passage[P]["release"]["version"] == 2
    assert by_passage[P]["release"]["forced_at"] is not None
    assert by_passage[P]["approved"] is True
    assert by_passage[P]["open_findings"] == 1
    assert by_passage[unreleased[0]]["release"] is None
    assert by_passage[unreleased[0]]["approved"] is False


async def test_a_team_that_closed_ruth_asking_for_esther_reads_the_answer_it_reads_with_no_book(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)

    named = await the_listing(desk_client, desk, team.id, "esther")

    assert positions(named)[ESTHER[0]] == "current"
    assert named == await the_listing(desk_client, desk, team.id)


async def test_a_book_the_room_does_not_serve_is_refused_with_422_naming_no_passage_and_no_team(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await open_ir_session(db_session, pericope=RUTH[1], project_id=team.id)

    answered = await the_answer(desk_client, desk, team.id, "genesis")

    assert answered.status_code == 422
    assert answered.json()["code"] == "BOOK_NOT_SERVED"
    named_nowhere = [
        team.id,
        team.name,
        "genesis",
        *(meaning_map.pericope_num for meaning_map in served_maps()),
    ]
    assert [word for word in named_nowhere if word in answered.text] == []


@pytest.mark.parametrize("not_a_key", ["Esther", "", "RUTH", " ruth"])
async def test_the_servers_spelling_and_an_empty_book_are_not_keys_and_are_refused_the_same(
    desk_client, db_session, team_at_the_desk, not_a_key: str
) -> None:
    team, _tablet, desk = team_at_the_desk

    refused = await the_answer(desk_client, desk, team.id, "genesis")
    answered = await the_answer(desk_client, desk, team.id, not_a_key)

    assert answered.status_code == 422
    assert answered.json() == refused.json()


async def test_a_reader_with_no_link_to_the_team_gets_the_same_404_with_a_served_book_as_with_none(
    desk_client, team_at_the_desk, stranger
) -> None:
    team, _tablet, _desk = team_at_the_desk

    with_none = await the_answer(desk_client, stranger, team.id)
    with_book = await the_answer(desk_client, stranger, team.id, "esther")

    assert with_none.status_code == with_book.status_code == 404
    assert with_none.json() == with_book.json() == TEAM_NOT_FOUND


async def test_a_reader_with_no_link_to_the_team_gets_404_not_422_with_a_book_the_room_does_not_serve(  # noqa: E501
    desk_client, team_at_the_desk, stranger
) -> None:
    team, _tablet, _desk = team_at_the_desk

    answered = await the_answer(desk_client, stranger, team.id, "genesis")

    assert answered.status_code == 404
    assert answered.json() == TEAM_NOT_FOUND


async def test_a_consultant_reads_a_named_book_of_a_team_they_have_no_link_to(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, _desk = team_at_the_desk
    consultant = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, consultant.id, "consultant")
    access, _refresh = await issue_tokens(db_session, consultant)

    listing = await the_listing(
        desk_client, {"Authorization": f"Bearer {access}"}, team.id, "esther"
    )

    assert positions(listing) == every_passage(ESTHER, "future")


async def test_a_passage_closed_out_of_order_in_a_book_the_team_never_stood_in_reads_closed_and_the_rest_future(  # noqa: E501
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    out_of_order = ESTHER[2]
    await having_closed(db_session, team.id, out_of_order)
    in_ruth = await open_ir_session(db_session, pericope=RUTH[0], project_id=team.id)
    await db_session.execute(
        update(IRSession)
        .where(IRSession.id == in_ruth.id)
        .values(
            messages=[{"role": "guide", "content": "Vamos ouvir."}],
            updated_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await db_session.commit()
    assert positions(await the_listing(desk_client, desk, team.id))[RUTH[0]] == "current"

    listing = await the_listing(desk_client, desk, team.id, "esther")

    assert positions(listing) == {**every_passage(ESTHER, "future"), out_of_order: "closed"}


async def test_a_team_that_closed_every_served_book_reads_a_named_book_with_every_passage_closed_and_none_current(  # noqa: E501
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH, *ESTHER, *JONAH)

    answers = {
        key: positions(await the_listing(desk_client, desk, team.id, key))
        for key in ("ruth", "esther", "jonah")
    }

    assert answers == {
        "ruth": every_passage(RUTH, "closed"),
        "esther": every_passage(ESTHER, "closed"),
        "jonah": every_passage(JONAH, "closed"),
    }


async def test_a_team_with_no_session_asking_for_jonah_reads_every_passage_future(
    desk_client, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk

    listing = await the_listing(desk_client, desk, team.id, "jonah")

    assert positions(listing) == every_passage(JONAH, "future")


async def test_naming_a_book_writes_nothing(desk_client, db_session, team_at_the_desk) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, RUTH[0])
    before = await row_counts(db_session)

    statuses = [
        (await the_answer(desk_client, desk, team.id, book)).status_code
        for book in ("ruth", "esther", "genesis")
    ]

    assert statuses == [200, 200, 422]
    assert await row_counts(db_session) == before
