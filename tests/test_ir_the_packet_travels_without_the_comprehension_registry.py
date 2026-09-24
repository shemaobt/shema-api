from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    a_claimed_device,
    at_the_desk,
    desk_release,
    ready_session,
)
from tests.room_harness import room_client

LEGACY_COMPREHENSION = {
    "ledger": [
        {
            "kind": "evidence",
            "id": "ev-0",
            "unit_id": "proposition:P03:P1",
            "probe_id": "probe-0",
            "method": "micro_tellback",
            "result": "carry_to_refine",
        }
    ],
    "active_probe": {
        "id": "probe-1",
        "checkpoint_ids": ["proposition:P03:P1"],
        "method": "micro_tellback",
        "purpose": "initial_check",
        "practice_scene_ids": [],
    },
    "practiced_scene_ids": ["S1"],
    "invited_scene_id": "S2",
}


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_the_desks_packet_says_v0_7_and_carries_no_comprehension_or_readiness(
    client, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 200, read.text
    packet = read.json()
    assert packet["schema_version"] == "tripod.internalization-release.v0.7"
    assert "comprehension" not in packet, (
        "o pacote levava ao Refine um registro de compreensão que ninguém mais escreve"
    )
    assert "readiness" not in packet, (
        "o pacote dizia ready_for_refine ao lado de um needs_more_work que nada mais resolve"
    )


async def test_a_session_holding_an_august_ledger_releases_without_counting_its_open_point(
    client, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    session.comprehension = LEGACY_COMPREHENSION
    await db_session.commit()
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 200, read.text
    packet = read.json()
    assert "comprehension" not in packet
    assert packet["open_questions"] == 0, (
        "o ponto levado ao Refine no ledger de agosto contava como pergunta aberta"
    )
