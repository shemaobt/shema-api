"""ENG-1761 — a visit and its undo name the halt count the Desk read.

The Desk reads a room, a facilitator taps, and the write lands seconds later. A halt raised in
between is a different ask from the one somebody saw, so a write naming the count it read is
refused once the count has moved, and the Desk reads again.

The room halts through the tablet's own door, a warning comes from a stretch told until it is
hard, and the Desk reads through its two reads: the queue and «Sessões».
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import sessions as room
from tests.baker import grant_facilitator_app_role, make_project_user_access, make_user
from tests.device_harness import a_linked_tablet
from tests.halt_harness import (
    IR,
    SESSIONS,
    Facilitator,
    a_facilitator,
    a_session,
    a_warning_is_raised,
    queued,
    tablet_state,
    the_tablet_halts,
    the_team_opens_the_session,
)
from tests.halt_harness import desk_session_row as session_row
from tests.hard_stretch_harness import MemoryStore, voice

HALT_MOVED = "HALT_MOVED"


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, facilitator_a: Facilitator
):
    from fastapi import FastAPI

    from app.api.facilitator.sessions import facilitator_sessions_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    async def _words(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho"

    monkeypatch.setattr(bt_api, "heard", _words)
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: MemoryStore())

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_sessions_router, prefix=SESSIONS)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    tablet = await a_linked_tablet(db_session, team_id=facilitator_a.team_id)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet.headers
    ) as c:
        yield c


@pytest.fixture()
async def facilitator_a(db_session: AsyncSession) -> Facilitator:
    return await a_facilitator(db_session, email="ana@example.com", team_name="Equipe P")


@pytest.fixture()
async def colleague(db_session: AsyncSession, facilitator_a: Facilitator) -> Facilitator:
    """Facilitates A's team too: the one whose later visit a stale undo must not clear."""
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="carla@example.com")
    await make_project_user_access(
        db_session, facilitator_a.team_id, user.id, role=ProjectRole.FACILITATOR
    )
    await grant_facilitator_app_role(db_session, user.id)
    access, _refresh = await issue_tokens(db_session, user)
    return Facilitator(
        user.id,
        facilitator_a.team_id,
        facilitator_a.team_name,
        {"Authorization": f"Bearer {access}"},
    )


@pytest.fixture()
async def facilitator_b(db_session: AsyncSession) -> Facilitator:
    return await a_facilitator(db_session, email="bruno@example.com", team_name="Equipe Q")


def the_visit(session_id: str) -> str:
    return f"{IR}/facilitator/sessions/{session_id}/attended"


def named_as(halt: int | str | None, warning: str | None) -> dict[str, int | str]:
    named: dict[str, int | str] = {} if halt is None else {"halt": halt}
    return named | ({} if warning is None else {"warning": warning})


async def attend(
    client: httpx.AsyncClient,
    session_id: str,
    who: Facilitator,
    *,
    halt: int | str | None,
    warning: str | None = None,
) -> httpx.Response:
    return await client.post(
        the_visit(session_id), params=named_as(halt, warning), headers=who.headers
    )


async def undo(
    client: httpx.AsyncClient,
    session_id: str,
    who: Facilitator,
    *,
    halt: int | str | None,
    warning: str | None = None,
) -> httpx.Response:
    return await client.delete(
        the_visit(session_id), params=named_as(halt, warning), headers=who.headers
    )


async def the_queue_row(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict:
    row = await queued(client, who, session_id)
    assert row is not None, "a sala não está na fila"
    return row


def refused_as_moved(answer: httpx.Response, *, now: int, warned: str | None = None) -> None:
    assert answer.status_code == 409, answer.text[:300]
    assert answer.json()["code"] == HALT_MOVED
    assert answer.json()["halts_raised"] == now
    assert moment(answer.json()["warned_at"]) == moment(warned)


def moment(served: str | None) -> datetime | None:
    return None if served is None else datetime.fromisoformat(served)


async def a_second_warning(db: AsyncSession, session_id: str) -> None:
    await room.raise_a_warning(db, await room.get_session(db, session_id))


# --- The reads carry the halt count -------------------------------------------------------


async def test_the_queue_row_carries_the_rooms_halt_count(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    first = (await the_queue_row(client, facilitator_a, session.id))["halts_raised"]

    await the_team_opens_the_session(client)
    await the_tablet_halts(client, session.id)

    assert first == 1
    assert (await the_queue_row(client, facilitator_a, session.id))["halts_raised"] == 2


async def test_the_desks_session_read_carries_the_halt_count(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    row = await session_row(client, facilitator_a, session.id)

    assert row["halts_raised"] == 1
    assert (
        row["halts_raised"]
        == (await the_queue_row(client, facilitator_a, session.id))["halts_raised"]
    )


async def test_the_desks_reads_carry_the_warning_a_visit_names(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)

    await a_warning_is_raised(client, session.id)

    queued_moment = (await the_queue_row(client, facilitator_a, session.id))["warned_at"]
    listed_moment = (await session_row(client, facilitator_a, session.id))["warned_at"]
    assert queued_moment is not None
    assert moment(listed_moment) == moment(queued_moment)


# --- A stale write is refused -------------------------------------------------------------


async def test_attending_the_halt_seen_before_a_newer_halt_is_refused_and_the_newer_halt_stays_unattended(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    seen = (await the_queue_row(client, facilitator_a, session.id))["halts_raised"]
    await the_tablet_halts(client, session.id)

    refused = await attend(client, session.id, facilitator_a, halt=seen)

    refused_as_moved(refused, now=2)
    assert (await the_queue_row(client, facilitator_a, session.id))["attended_at"] is None


async def test_undoing_a_visit_to_an_older_halt_is_refused_and_the_colleagues_visit_stays(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    colleague: Facilitator,
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    assert (await attend(client, session.id, facilitator_a, halt=1)).status_code == 200
    await the_tablet_halts(client, session.id)
    assert (await attend(client, session.id, colleague, halt=2)).status_code == 200

    refused = await undo(client, session.id, facilitator_a, halt=1)

    refused_as_moved(refused, now=2)
    assert (await session_row(client, facilitator_a, session.id))["attended_by"] == colleague.id


async def test_attending_the_warning_seen_before_a_newer_warning_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await a_warning_is_raised(client, session.id)
    seen = await the_queue_row(client, facilitator_a, session.id)
    await a_second_warning(db_session, session.id)
    newer = await session_row(client, facilitator_a, session.id)

    refused = await attend(
        client, session.id, facilitator_a, halt=seen["halts_raised"], warning=seen["warned_at"]
    )

    refused_as_moved(refused, now=seen["halts_raised"], warned=newer["warned_at"])
    still = await the_queue_row(client, facilitator_a, session.id)
    assert still["halt"] == "warning"
    assert still["attended_at"] is None


async def test_undoing_a_visit_to_an_older_warning_is_refused_and_the_colleagues_visit_to_the_newer_one_stays(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    colleague: Facilitator,
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await a_warning_is_raised(client, session.id)
    seen = await the_queue_row(client, facilitator_a, session.id)
    halt, warning = seen["halts_raised"], seen["warned_at"]
    assert (await attend(client, session.id, facilitator_a, halt=halt, warning=warning)).is_success
    await a_second_warning(db_session, session.id)
    newer = await the_queue_row(client, colleague, session.id)
    assert (
        await attend(client, session.id, colleague, halt=halt, warning=newer["warned_at"])
    ).is_success

    refused = await undo(client, session.id, facilitator_a, halt=halt, warning=warning)

    refused_as_moved(refused, now=halt, warned=newer["warned_at"])
    assert (await session_row(client, facilitator_a, session.id))["attended_by"] == colleague.id


async def test_a_visit_naming_no_warning_to_a_room_under_one_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await a_warning_is_raised(client, session.id)
    row = await the_queue_row(client, facilitator_a, session.id)

    refused = await attend(client, session.id, facilitator_a, halt=row["halts_raised"])

    refused_as_moved(refused, now=row["halts_raised"], warned=row["warned_at"])


# --- A current write lands as it always did -----------------------------------------------


async def test_attending_the_current_halt_stamps_it_as_today(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    marked = await attend(client, session.id, facilitator_a, halt=1)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_by"] == facilitator_a.id
    assert await queued(client, facilitator_a, session.id) is None
    assert (await tablet_state(client, session.id))["status"] == "needs_person"


async def test_a_second_tap_on_the_same_halt_keeps_the_first_stamp(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    first = await attend(client, session.id, facilitator_a, halt=1)
    second = await attend(client, session.id, facilitator_a, halt=1)

    assert second.status_code == 200, second.text[:300]
    assert second.json()["attended_at"] == first.json()["attended_at"]


async def test_undoing_the_visit_to_the_current_halt_puts_the_room_back_on_the_queue(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    assert (await attend(client, session.id, facilitator_a, halt=1)).status_code == 200

    undone = await undo(client, session.id, facilitator_a, halt=1)

    assert undone.status_code == 200, undone.text[:300]
    assert (await the_queue_row(client, facilitator_a, session.id))["attended_at"] is None


async def test_a_room_that_never_halted_is_attended_at_count_zero(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)

    marked = await attend(client, session.id, facilitator_a, halt=0)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_by"] == facilitator_a.id


# --- A write that names no count ----------------------------------------------------------


@pytest.mark.parametrize("bad", [None, -1, "x", 2**31])
async def test_a_visit_that_names_no_halt_is_refused_and_writes_nothing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    colleague: Facilitator,
    bad: int | str | None,
) -> None:
    unattended = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, unattended.id)
    attended = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, attended.id)
    assert (await attend(client, attended.id, colleague, halt=1)).status_code == 200
    stamped = await session_row(client, facilitator_a, attended.id)

    marked = await attend(client, unattended.id, facilitator_a, halt=bad)
    undone = await undo(client, attended.id, facilitator_a, halt=bad)

    assert marked.status_code == 422, marked.text[:300]
    assert undone.status_code == 422, undone.text[:300]
    assert (await session_row(client, facilitator_a, unattended.id))["attended_at"] is None
    after = await session_row(client, facilitator_a, attended.id)
    assert (after["attended_at"], after["attended_by"]) == (
        stamped["attended_at"],
        stamped["attended_by"],
    )


async def test_a_visit_naming_its_warning_on_another_clock_is_the_same_visit(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await a_warning_is_raised(client, session.id)
    row = await the_queue_row(client, facilitator_a, session.id)
    elsewhere = moment(row["warned_at"]).astimezone(timezone(timedelta(hours=-3)))  # type: ignore[union-attr]

    marked = await attend(
        client,
        session.id,
        facilitator_a,
        halt=row["halts_raised"],
        warning=elsewhere.isoformat(),
    )

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_by"] == facilitator_a.id


async def test_a_visit_naming_a_warning_with_no_offset_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await a_warning_is_raised(client, session.id)
    row = await the_queue_row(client, facilitator_a, session.id)
    no_offset = moment(row["warned_at"]).replace(tzinfo=None).isoformat()  # type: ignore[union-attr]

    marked = await attend(
        client, session.id, facilitator_a, halt=row["halts_raised"], warning=no_offset
    )

    assert marked.status_code == 422, marked.text[:300]
    assert (await the_queue_row(client, facilitator_a, session.id))["attended_at"] is None


@pytest.mark.parametrize("write", [attend, undo], ids=["attend", "undo"])
@pytest.mark.parametrize("naming_the_real_count", [True, False], ids=["real", "other"])
async def test_another_teams_room_answers_not_found_whatever_halt_it_names(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    facilitator_b: Facilitator,
    write: Any,
    naming_the_real_count: bool,
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    real = (await the_queue_row(client, facilitator_a, session.id))["halts_raised"]

    answer = await write(
        client, session.id, facilitator_b, halt=real if naming_the_real_count else 99
    )

    assert answer.status_code == 404, answer.text[:300]
    assert "halts_raised" not in answer.json()
