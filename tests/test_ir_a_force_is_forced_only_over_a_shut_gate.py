"""ENG-1259 — a force is recorded as forced only when it waived a blocker.

Her finalize records a facilitator's approval as forced only when the gate was shut; over a
passage conferida at that moment it is an ordinary approval (ADR 0080). A force over a clean
check with a part not heard still waives the listening and stays forced: that case lives with
the other forces past the gate (ENG-1305). A release stored before that rule, forced over a gate
that was open, keeps who pressed and reads as an ordinary approval everywhere.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import partial

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.opening_harness import desk_routes
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    desk_passage_release,
    desk_release_at,
    never_analysed_telling_back,
    ready_session,
    releases_of,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import room_client

FORCE = {"force": True}
THE_ANALYSTS_NOTE = "R7: a equipe acrescentou que Noemi voltou alegre"


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


async def test_the_facilitator_forces_a_never_checked_passage_with_one_take_approved_and_recorded_as_forced(  # noqa: E501
    room, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id, tell=never_analysed_telling_back)
    desk, facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert forced.json()["forced_at"] is not None
    (row,) = await releases_of(db_session, session.id)
    check = row.packet["check"]
    assert check["forced"] is True
    assert check["status"] == "forcada"
    assert check["forcedBlockers"] == ["telling_back_never_analysed"]
    assert row.forced_blockers == ["telling_back_never_analysed"]
    assert row.forced_by == facilitator.id


async def test_a_forced_approval_carries_its_open_findings_by_kind_and_place_and_never_the_analysts_note(  # noqa: E501
    room, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    session = await ready_session(
        db_session,
        project_id=team.id,
        tell=partial(told_back_with_an_open_finding, note=THE_ANALYSTS_NOTE),
    )
    (told,) = await final_segments(db_session, session.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    (row,) = await releases_of(db_session, session.id)
    assert row.packet["check"]["forced"] is True
    assert row.packet["check"]["findings"] == [
        {
            "kind": "addition",
            "frase": 1,
            "index": 1,
            "idx": told.id,
            "clipKey": told.take_id,
            "scene": "whole",
        }
    ]
    assert THE_ANALYSTS_NOTE in json.dumps(row.forced_open_findings, ensure_ascii=False), (
        "a nota nunca chegou ao estado, e a ausência dela no pacote não provaria nada"
    )
    assert THE_ANALYSTS_NOTE not in json.dumps(row.packet, ensure_ascii=False)


async def test_the_facilitator_forces_a_passage_conferida_at_that_moment_recorded_as_an_ordinary_approval(  # noqa: E501
    room, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert forced.json()["forced_at"] is None, "o Desk desenha forced_at como quem forçou"
    (row,) = await releases_of(db_session, session.id)
    assert (row.forced_by, row.forced_at, row.forced_blockers, row.forced_open_findings) == (
        None,
        None,
        None,
        None,
    )
    assert row.device_id is None, "só o tablet da equipe aprova com um aparelho"
    check = row.packet["check"]
    assert check["forced"] is False
    assert check["status"] == "conferida"
    assert (check["forcedBy"], check["forcedAt"], check["forcedBlockers"]) == (None, None, None)


async def test_a_release_stored_as_a_force_that_waived_nothing_reads_as_an_ordinary_approval_on_every_reader(  # noqa: E501
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    desk, facilitator = await at_the_desk(db_session, room_app, team)
    approved = await room.post(team_release(session.id), headers=team_headers(tablet))
    assert approved.status_code == 200, approved.text
    (row,) = await releases_of(db_session, session.id)
    pressed_at = datetime(2026, 10, 1, 14, 10, tzinfo=UTC)
    row.forced_by = facilitator.id
    row.forced_at = pressed_at
    row.forced_blockers = []
    row.packet = {
        **row.packet,
        "check": {
            **row.packet["check"],
            "forced": True,
            "forcedBy": facilitator.id,
            "forcedAt": pressed_at.isoformat(),
            "forcedBlockers": [],
        },
    }
    await db_session.commit()

    read = await room.get(f"{PREFIX}/sessions/{session.id}", headers=team_headers(tablet))
    listed = await desk_client.get(f"/api/facilitator/teams/{team.id}/pericopes", headers=desk)
    served = await room.get(desk_release_at(session.id, 1), headers=desk)
    forced_again = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert read.json()["approved"]["forced"] is False
    (passage,) = [entry for entry in listed.json() if entry["pericope"] == P]
    assert passage["release"]["forced_at"] is None
    check = served.json()["check"]
    assert (check["forced"], check["status"]) == (False, "conferida")
    assert (check["forcedBy"], check["forcedAt"], check["forcedBlockers"]) == (None, None, None)
    assert forced_again.json()["version"] == 1, "o mesmo rascunho devolve a release que existe"
    assert forced_again.json()["forced_at"] is None
    await db_session.refresh(row)
    assert (row.forced_by, row.forced_at) == (facilitator.id, pressed_at), (
        "a linha guarda quem apertou"
    )
