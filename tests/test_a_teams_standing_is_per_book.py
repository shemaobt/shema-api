"""ENG-1709 — a team's progression and standing are per served book.

A team is complete only when every served book is, and it stands in one book, its **Current
book**: the book of its latest live session while that book has a passage left, else the first
of Ruth, Esther and Jonah that has one. The Desk reads the Current book on every door, and the
team detail lists each book's count beside it.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.progression import resolve, standing
from tests.baker import having_finished_the_passage, make_app, make_role, open_ir_session
from tests.opening_harness import a_scripted_room, desk_routes
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client

ESTHER = [meaning_map.pericope_num for meaning_map in load_book("Esther")]
JONAH = [meaning_map.pericope_num for meaning_map in load_book("Jonah")]
RUTH = [meaning_map.pericope_num for meaning_map in load_book("Ruth")]

_later = itertools.count(1)


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


async def the_latest(db: AsyncSession, session_id: str) -> None:
    """Stamp this session as the team's most recent activity, past every other one."""
    moment = datetime.now(UTC) + timedelta(days=1, minutes=next(_later))
    await db.execute(update(IRSession).where(IRSession.id == session_id).values(updated_at=moment))
    await db.commit()


async def the_guide_spoke_last_in(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(IRSession)
        .where(IRSession.id == session_id)
        .values(messages=[{"role": "guide", "content": "Vamos ouvir."}])
    )
    await db.commit()
    await the_latest(db, session_id)


async def having_closed(db: AsyncSession, team_id: str, *passages: str) -> IRSession:
    session = None
    for passage in passages:
        session = await open_ir_session(db, pericope=passage, project_id=team_id)
        await having_finished_the_passage(db, session)
    assert session is not None
    return session


async def having_closed_and_approved(
    db: AsyncSession, room: httpx.AsyncClient, tablet: str, team_id: str, *passages: str
) -> None:
    for passage in passages:
        session = await ready_session(db, pericope=passage, project_id=team_id)
        approved = await room.post(team_release(session.id), headers=team_headers(tablet))
        assert approved.status_code == 200, approved.text[:300]
        await having_finished_the_passage(db, session)


async def the_panorama_opened_and_heard(
    room: httpx.AsyncClient, db: AsyncSession, tablet: str, panorama: str
) -> str:
    opened = await room.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"pericope": panorama, "language": "pt"},
    )
    assert opened.status_code == 200, opened.text[:300]
    session_id = opened.json()["session_id"]
    spoken = await room.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(tablet),
        data={"turn_id": "abertura"},
    )
    assert spoken.status_code == 200, spoken.text[:300]
    await the_latest(db, session_id)
    return session_id


async def an_open_naming_no_passage(
    room: httpx.AsyncClient, tablet: str, *, after: str | None = None
) -> httpx.Response:
    body: dict[str, str | None] = {"pericope": None, "language": "pt"}
    if after is not None:
        body["after_session"] = after
    return await room.post(f"{PREFIX}/sessions", headers=team_headers(tablet), json=body)


async def the_detail(desk_client: httpx.AsyncClient, desk: dict, team_id: str) -> dict:
    answered = await desk_client.get(f"/api/facilitator/teams/{team_id}", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def the_card(
    desk_client: httpx.AsyncClient, desk: dict, team_id: str, *, filter: str = "all"
) -> dict | None:
    answered = await desk_client.get(
        "/api/facilitator/teams", headers=desk, params={"filter": filter}
    )
    assert answered.status_code == 200, answered.text[:300]
    return next((t for t in answered.json()["teams"] if t["team_id"] == team_id), None)


async def the_pericopes(desk_client: httpx.AsyncClient, desk: dict, team_id: str) -> list[dict]:
    answered = await desk_client.get(f"/api/facilitator/teams/{team_id}/pericopes", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


def positions(body: list[dict]) -> dict[str, str]:
    return {entry["pericope"]: entry["position"] for entry in body}


def the_book(detail: dict, book: str) -> dict:
    return next(entry for entry in detail["books"] if entry["book"] == book)


# ------------------------------------------------------------------------------- acceptance 1


async def test_a_team_with_every_ruth_passage_closed_and_approved_reads_ruth_complete_esther_and_jonah_untouched_and_the_team_not_complete(  # noqa: E501
    room, desk_client, db_session, team_at_the_desk
) -> None:
    team, tablet, desk = team_at_the_desk
    await having_closed_and_approved(db_session, room, tablet, team.id, *RUTH)

    detail = await the_detail(desk_client, desk, team.id)

    assert detail["books"] == [
        {"book": "Esther", "passage_total": 18, "approved_total": 0, "complete": False},
        {"book": "Jonah", "passage_total": 5, "approved_total": 0, "complete": False},
        {"book": "Ruth", "passage_total": 14, "approved_total": 14, "complete": True},
    ]
    assert detail["state"] != "complete"


async def test_the_work_queue_does_not_file_a_team_done_with_ruth_under_complete(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)

    card = await the_card(desk_client, desk, team.id)

    assert card is not None
    assert card["state"] == "in_progress"
    assert card["active_passage"]["pericope"] == "E01"
    assert await the_card(desk_client, desk, team.id, filter="complete") is None


async def test_a_team_that_closed_every_passage_of_every_served_book_is_complete(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH, *ESTHER, *JONAH)

    card = await the_card(desk_client, desk, team.id)
    detail = await the_detail(desk_client, desk, team.id)

    assert card is not None
    assert card["state"] == "complete"
    assert card["active_passage"] is None
    assert [entry["complete"] for entry in detail["books"]] == [True, True, True]


async def test_a_team_with_one_passage_left_in_jonah_is_not_complete(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH, *ESTHER, *JONAH[:-1])

    card = await the_card(desk_client, desk, team.id)

    assert card is not None
    assert card["state"] != "complete"


# ------------------------------------------------------------------------------- acceptance 2


async def test_a_team_done_with_ruth_that_opens_jonahs_panorama_and_asks_for_the_next_passage_with_no_session_named_gets_j01(  # noqa: E501
    room, db_session, team_at_the_desk, monkeypatch
) -> None:
    a_scripted_room(monkeypatch)
    team, tablet, _desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)
    await the_panorama_opened_and_heard(room, db_session, tablet, "OV-Jonah")

    opened = await an_open_naming_no_passage(room, tablet)

    assert opened.status_code == 200, opened.text[:300]
    assert opened.json()["pericope"] == "J01"


async def test_the_same_open_following_the_panorama_session_gets_j01(
    room, db_session, team_at_the_desk, monkeypatch
) -> None:
    a_scripted_room(monkeypatch)
    team, tablet, _desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)
    panorama = await the_panorama_opened_and_heard(room, db_session, tablet, "OV-Jonah")

    opened = await an_open_naming_no_passage(room, tablet, after=panorama)

    assert opened.status_code == 200, opened.text[:300]
    assert opened.json()["pericope"] == "J01"


async def test_an_open_with_no_passage_for_a_team_whose_latest_session_is_in_jonah_never_lands_in_ruth(  # noqa: E501
    room, db_session, team_at_the_desk
) -> None:
    team, tablet, _desk = team_at_the_desk
    await the_latest(db_session, (await having_closed(db_session, team.id, "J01")).id)

    opened = await an_open_naming_no_passage(room, tablet)

    assert opened.status_code == 200, opened.text[:300]
    assert opened.json()["pericope"] == "J02"


async def test_a_team_done_with_ruth_that_opened_nothing_else_opens_esthers_first_passage(
    room, db_session, team_at_the_desk
) -> None:
    team, tablet, _desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)

    opened = await an_open_naming_no_passage(room, tablet)

    assert opened.status_code == 200, opened.text[:300]
    assert opened.json()["pericope"] == "E01"


# ------------------------------------------------------------------------------- acceptance 3


async def test_a_team_with_no_sessions_stands_in_ruth_on_its_first_passage_with_no_book_approved_or_complete(  # noqa: E501
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk

    listed = positions(await the_pericopes(desk_client, desk, team.id))
    detail = await the_detail(desk_client, desk, team.id)
    card = await the_card(desk_client, desk, team.id)

    assert list(listed) == RUTH
    assert listed == {passage: "current" if passage == "P01" else "future" for passage in RUTH}
    assert [(entry["approved_total"], entry["complete"]) for entry in detail["books"]] == [
        (0, False),
        (0, False),
        (0, False),
    ]
    assert card is not None
    assert card["active_passage"]["pericope"] == "P01"


@pytest.mark.parametrize("book", ["Esther", "Jonah"])
def test_the_standing_of_a_book_the_team_is_not_in_has_no_current_passage(book: str) -> None:
    passages = standing(
        set(), book=book, here=resolve(set(), book="Ruth"), releases={}, findings={}
    )

    assert {entry.position.value for entry in passages} == {"future"}


# ------------------------------------------------------------------ the Current book, every door


async def test_every_desk_door_reads_the_book_the_team_is_in(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await the_latest(db_session, (await having_closed(db_session, team.id, "J01")).id)

    card = await the_card(desk_client, desk, team.id)
    listed = positions(await the_pericopes(desk_client, desk, team.id))
    detail = await the_detail(desk_client, desk, team.id)
    coverage = await desk_client.get(f"/api/facilitator/teams/{team.id}/coverage", headers=desk)

    assert card is not None
    assert card["active_passage"]["pericope"] == "J02"
    assert listed == {
        "J01": "closed",
        "J02": "current",
        "J03": "future",
        "J04": "future",
        "J05": "future",
    }
    assert list(listed) == JONAH
    assert detail["approved_total"] == 0
    assert detail["closed_total"] == 1
    assert coverage.status_code == 200, coverage.text[:300]
    assert [bead["key"] for bead in coverage.json()] == element_keys("J02")


async def test_a_teams_ruth_work_still_counts_in_ruths_entry_while_it_is_in_jonah(
    room, desk_client, db_session, team_at_the_desk
) -> None:
    team, tablet, desk = team_at_the_desk
    await having_closed_and_approved(db_session, room, tablet, team.id, "P01", "P02")
    await the_latest(db_session, (await having_closed(db_session, team.id, "J01")).id)

    detail = await the_detail(desk_client, desk, team.id)
    listed = await the_pericopes(desk_client, desk, team.id)

    assert the_book(detail, "Ruth")["approved_total"] == 2
    assert [entry["pericope"] for entry in listed] == JONAH


async def test_the_books_the_standing_lists_are_the_books_get_books_serves_in_its_order(
    room, desk_client, db_session, team_at_the_desk
) -> None:
    team, tablet, desk = team_at_the_desk

    served = await room.get(f"{PREFIX}/books", headers=team_headers(tablet))
    detail = await the_detail(desk_client, desk, team.id)

    assert served.status_code == 200, served.text[:300]
    assert [entry["book"] for entry in detail["books"]] == served.json()["books"]


# ---------------------------------------------------------------------- edges of the Current book


async def test_a_zerard_session_does_not_hold_the_team_in_its_book(
    room, desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, "P01")
    jonah = await open_ir_session(db_session, pericope="J01", project_id=team.id)
    await the_guide_spoke_last_in(db_session, jonah.id)
    zerado = await room.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/J01/archive", headers=desk
    )
    assert zerado.status_code == 200, zerado.text[:300]

    card = await the_card(desk_client, desk, team.id)
    listed = await the_pericopes(desk_client, desk, team.id)

    assert card is not None
    assert card["active_passage"]["pericope"] == "P02"
    assert [entry["pericope"] for entry in listed] == RUTH


async def test_a_stored_session_naming_a_pericope_no_served_book_holds_is_passed_over(
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, "P01")
    stray = IRSession(
        pericope="Q01",
        project_id=team.id,
        status=IRSessionStatus.IN_PROGRESS,
        messages=[],
        coverage_state={},
        back_translation={},
        language="pt",
    )
    db_session.add(stray)
    await db_session.commit()
    await the_guide_spoke_last_in(db_session, stray.id)

    card = await the_card(desk_client, desk, team.id)

    assert card is not None
    assert card["active_passage"]["pericope"] == "P02"


async def test_a_session_on_a_closed_passage_of_a_finished_book_leaves_the_team_in_the_next_book_with_a_passage_left(  # noqa: E501
    desk_client, db_session, team_at_the_desk
) -> None:
    team, _tablet, desk = team_at_the_desk
    await having_closed(db_session, team.id, *RUTH)
    again = await open_ir_session(db_session, pericope="P05", project_id=team.id)
    await the_latest(db_session, again.id)

    card = await the_card(desk_client, desk, team.id)
    listed = await the_pericopes(desk_client, desk, team.id)

    assert card is not None
    assert card["active_passage"]["pericope"] == "E01"
    assert card["state"] == "in_progress"
    assert [entry["pericope"] for entry in listed] == ESTHER
