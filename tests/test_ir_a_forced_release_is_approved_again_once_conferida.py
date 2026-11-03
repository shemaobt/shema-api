"""ENG-1837 — a forced release is approved again once the telling is conferida.

Her approve gate offers «Aprovar como rascunho final» again when the current release was
forced and the telling is now conferida, and her finalize mints the next version, forced only
when the gate was shut (approveGate.ts, finalize/route.ts at 18fa7c4). The room used to answer
that approval with the forced release, so a passage the team did check stayed forced for ever.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Nuance,
)
from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.device_harness import TABLET_TEAM
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    at_the_desk,
    checked_and_heard,
    checked_heard_and_approved,
    desk_release,
    ready_session,
    releases_of,
    reported_playback,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import room_client


@pytest.fixture()
async def room(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_a_forced_draft_whose_telling_comes_back_conferida_is_approved_as_v2_not_answered_with_v1(  # noqa: E501
    room, db_session, room_app
) -> None:
    team = await db_session.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    session = await ready_session(db_session, tell=told_back_with_an_open_finding)
    forced = await room.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.json()["version"] == 1, forced.text

    version = await checked_heard_and_approved(room, db_session, session.id)
    read = await room.get(f"{PREFIX}/sessions/{session.id}")

    assert version == 2, "a equipe aprovava a narração conferida e recebia de volta a v1 forçada"
    assert read.status_code == 200, read.text
    assert (read.json()["approved"]["version"], read.json()["approved"]["forced"]) == (2, False)


async def test_a_facilitator_forcing_a_forced_draft_whose_telling_came_back_conferida_mints_an_ordinary_v2(  # noqa: E501
    room, db_session, room_app
) -> None:
    team = await db_session.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    session = await ready_session(db_session, tell=told_back_with_an_open_finding)
    session_id = session.id
    first = await room.post(desk_release(session_id), headers=desk, json={"force": True})
    assert first.json()["version"] == 1, first.text
    await db_session.refresh(session)
    await checked_and_heard(db_session, session)

    again = await room.post(desk_release(session_id), headers=desk, json={"force": True})

    assert again.status_code == 200, again.text
    assert (again.json()["version"], again.json()["forced_at"]) == (2, None), (
        "o Desk forçava de novo a narração conferida e recebia a v1 com o relógio da força"
    )
    second = max(await releases_of(db_session, session_id), key=lambda row: row.version)
    assert (second.forced_by, second.packet["check"]["status"]) == (None, "conferida")


async def checked_with_only_a_nuance_and_heard(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    nuance = Nuance(
        note="a equipe disse de outro jeito",
        chunk=1,
        segment_id=told[0].id,
        quote="voltou com Rute",
        story="a história diz que Rute foi com ela",
        take_id=told[0].take_id,
        starts_ms=told[0].starts_ms,
        ends_ms=told[0].ends_ms,
    )
    await reported_playback(
        db,
        session,
        BackTranslationState(
            scope=session.pericope,
            findings=[],
            nuances=[nuance],
            checked=True,
            analysed_segment_ids=[one.id for one in told],
            checks=[
                CheckRound(
                    at=datetime.now(UTC),
                    spoken="Só um detalhe, na frase 1: vocês disseram de outro jeito.",
                    outcome="pass",
                    conferida=True,
                    nuances=[nuance],
                )
            ],
        ),
    )


async def test_a_forced_draft_whose_check_comes_back_with_only_a_nuance_is_approved_as_a_conferida_v2(  # noqa: E501
    room, db_session, room_app
) -> None:
    team = await db_session.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    session = await ready_session(db_session, tell=told_back_with_an_open_finding)
    session_id = session.id
    forced = await room.post(desk_release(session_id), headers=desk, json={"force": True})
    assert forced.json()["version"] == 1, forced.text
    db_session.expire_all()
    session = await db_session.get(IRSession, session_id)
    assert session is not None
    await checked_with_only_a_nuance_and_heard(db_session, session)

    answered = await room.post(team_release(session_id))
    read = await room.get(f"{PREFIX}/sessions/{session_id}")

    assert answered.status_code == 200, answered.text
    assert answered.json()["version"] == 2, (
        "uma checagem só com nuance não contava como conferida e a equipe recebia a v1 forçada"
    )
    assert (read.json()["approved"]["version"], read.json()["approved"]["forced"]) == (2, False)
    second = max(await releases_of(db_session, session_id), key=lambda row: row.version)
    assert (second.forced_by, second.packet["check"]["status"]) == (None, "conferida")
