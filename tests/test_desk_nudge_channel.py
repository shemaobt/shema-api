from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRTakeKind
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room import sessions as room
from app.services.internalization_room.hearing import HeardSpeech
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.hard_stretch_harness import MemoryStore, voice
from tests.release_harness import ready_session
from tests.room_harness import nothing_is_read_ahead
from tests.stream_harness import Listening, listening
from tests.turn_harness import the_room_agent_is

IR = "/api/internalization-room"
DESK = "/api/facilitator"
ROOM_KEY = "sala-de-teste"
P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
QUIET_SECONDS = 0.2


@dataclass
class Team:
    team_id: str
    device_id: str
    desk: dict[str, str]
    tablet: dict[str, str]


class _AgreeingModels:
    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
def ears() -> list[str]:
    return []


@pytest.fixture()
def desk_app(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, ears: list[str]) -> FastAPI:
    from app.api.facilitator.devices import facilitator_devices_router
    from app.api.facilitator.nudges import facilitator_nudges_router
    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import segments as segments_api
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services import internalization_room as full_room
    from app.services.internalization_room import questions as question_service
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)
    monkeypatch.setattr(full_room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: MemoryStore())
    monkeypatch.setattr(question_service, "_store", lambda *_, **__: MemoryStore())

    async def _transcribed(*_: Any, **__: Any) -> str:
        return "a equipe perguntou quem era Noemi"

    monkeypatch.setattr(question_service, "transcribe_speech", _transcribed)

    async def _heard_speech(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belém com Rute")

    monkeypatch.setattr(sessions_api, "heard_speech", _heard_speech)

    async def _heard(*_: Any, **__: Any) -> str:
        return ears.pop(0) if ears else "a equipe contou este trecho"

    monkeypatch.setattr(bt_api, "heard", _heard)
    monkeypatch.setattr(segments_api, "heard", _heard)
    nothing_is_read_ahead(monkeypatch)
    the_room_agent_is(monkeypatch, turn=_AgreeingModels())

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=f"{DESK}/teams")
    test_app.include_router(facilitator_nudges_router, prefix=f"{DESK}/teams")
    test_app.include_router(facilitator_devices_router, prefix=f"{DESK}/devices")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture()
async def client(desk_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=desk_app), base_url="http://test"
    ) as c:
        yield c


async def a_team(db: AsyncSession, *, tag: str) -> Team:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=f"{tag}@example.com")
    language = await make_language(db, name=f"Lingua {tag}", code=tag[:3])
    project = await make_project(db, language.id, name=f"Equipe {tag}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    access, _refresh = await issue_tokens(db, user)
    return Team(
        team_id=project.id,
        device_id=claimed.device.id,
        desk={"Authorization": f"Bearer {access}"},
        tablet={
            "X-Room-Key": ROOM_KEY,
            DEVICE_CREDENTIAL_HEADER: claimed.credential,
            "X-Room-Device": claimed.device.id,
        },
    )


@pytest.fixture()
async def team(db_session: AsyncSession) -> Team:
    return await a_team(db_session, tag="ana")


@pytest.fixture()
async def other_team(db_session: AsyncSession) -> Team:
    return await a_team(db_session, tag="bruno")


def the_stream(app: FastAPI, team_id: str, desk: dict[str, str]):
    return listening(app, f"{DESK}/teams/{team_id}/nudges", desk)


async def nudges_heard(desk: Listening) -> list[str]:
    heard: list[str] = []
    while True:
        try:
            chunk = await asyncio.wait_for(desk.chunks.get(), timeout=QUIET_SECONDS)
        except TimeoutError:
            return sorted(heard)
        assert chunk.startswith(b"event: nudge\ndata: "), chunk
        assert chunk.endswith(b"\n\n"), chunk
        _event, data, *_rest = chunk.decode().split("\n")
        heard.append(json.loads(data.removeprefix("data: "))["what"])


async def a_session(db: AsyncSession, team: Team) -> str:
    session = await room.create_session(db, pericope=P, project_id=team.team_id, language="pt")
    await room.append_exchange(db, session, team_utterance="", guide_response=GUIDE_LINE)
    return str(session.id)


async def raise_a_hand(client: httpx.AsyncClient, team: Team, session_id: str) -> str:
    raised = await client.post(
        f"{IR}/questions",
        params={"session_id": session_id},
        headers=team.tablet,
        files={"file": ("pergunta.m4a", b"a equipe levantou a mao", "audio/mp4")},
    )
    assert raised.status_code == 200, raised.text
    return str(raised.json()["question_id"])


async def the_team_speaks(client: httpx.AsyncClient, team: Team, session_id: str) -> None:
    answered = await client.post(
        f"{IR}/sessions/{session_id}/turns",
        headers=team.tablet,
        files={"file": ("resposta.m4a", b"a equipe respondeu", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


async def the_tablet_halts(client: httpx.AsyncClient, team: Team, session_id: str) -> None:
    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person", headers=team.tablet)
    assert asked.status_code == 200, asked.text


async def rehearse(client: httpx.AsyncClient, team: Team, session_id: str) -> str:
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers=team.tablet,
        data={"kind": IRTakeKind.ENSAIO.value, "scope": P},
        files={"file": ("ensaio.m4a", b"a equipe ensaiou a passagem inteira", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def tell(
    client: httpx.AsyncClient,
    team: Team,
    session_id: str,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    *,
    again: bool = False,
) -> httpx.Response:
    data = {"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)}
    if again:
        data["retelling"] = "true"
    told = await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers=team.tablet,
        data=data,
        files={"file": ("trecho.m4a", b"a equipe contou o trecho", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return told


async def stretches(client: httpx.AsyncClient, team: Team, session_id: str) -> list[dict]:
    state = await client.get(f"{IR}/sessions/{session_id}", headers=team.tablet)
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


async def replace(
    client: httpx.AsyncClient, team: Team, session_id: str, take_id: str, stretch: dict
) -> httpx.Response:
    replaced = await client.post(
        f"{IR}/sessions/{session_id}/segments/{stretch['segment_id']}/replace",
        headers=team.tablet,
        data={
            "take_id": take_id,
            "starts_ms": str(stretch["starts_ms"]),
            "ends_ms": str(stretch["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")},
    )
    assert replaced.status_code == 200, replaced.text
    return replaced


async def test_a_raised_hand_reaches_the_teams_open_stream_as_one_hands_nudge(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        assert desk.status == 200
        assert desk.headers["content-type"].startswith("text/event-stream")
        assert desk.headers["cache-control"] == "no-cache"
        assert desk.headers["x-accel-buffering"] == "no"

        await raise_a_hand(client, team, session_id)

        event, data, *rest = (await desk.next_chunk()).decode().split("\n")

    assert event == "event: nudge"
    assert json.loads(data.removeprefix("data: ")) == {"what": "hands"}, (
        "a mão levantada só chegava à Mesa quando o facilitador recarregava a página"
    )
    assert rest == ["", ""]


async def test_a_quiet_stream_still_says_it_is_alive(
    desk_app: FastAPI, team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.facilitator import nudges as nudges_api

    assert nudges_api.KEEP_ALIVE_SECONDS == 15.0
    monkeypatch.setattr(nudges_api, "KEEP_ALIVE_SECONDS", 0.01)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        heard = await desk.next_chunk()

    assert heard == b": keep-alive\n\n", (
        "uma sala quieta deixava a conexão muda, e o proxy a cortava antes do próximo nudge"
    )


async def test_a_facilitator_of_another_team_is_refused_and_never_listens(
    desk_app: FastAPI, client: httpx.AsyncClient, team: Team, other_team: Team
) -> None:
    from app.services.internalization_room.nudge_channel import _subscribers

    refused_by_the_team_route = await client.get(
        f"{DESK}/teams/{team.team_id}", headers=other_team.desk
    )

    async with the_stream(desk_app, team.team_id, other_team.desk) as stranger:
        assert stranger.status == 404, "a Mesa de outra equipe ouvia a sala desta"
        body = json.loads(await stranger.next_chunk())
        assert team.team_id not in _subscribers

    async with the_stream(desk_app, "equipe-que-nao-existe", other_team.desk) as nobody:
        assert nobody.status == 404
        assert "equipe-que-nao-existe" not in _subscribers

    assert body == refused_by_the_team_route.json(), (
        "a recusa do canal dizia algo que as rotas da equipe não dizem"
    )


async def test_a_desk_that_hangs_up_is_no_longer_a_listener(desk_app: FastAPI, team: Team) -> None:
    from app.services.internalization_room.nudge_channel import _subscribers

    async with the_stream(desk_app, team.team_id, team.desk):
        assert team.team_id in _subscribers

    assert team.team_id not in _subscribers, (
        "a fila de uma Mesa que desligou ficava no registro e recebia cada nudge "
        "até o processo morrer"
    )


async def test_a_nudge_reaches_only_its_own_team(
    desk_app: FastAPI,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    team: Team,
    other_team: Team,
) -> None:
    session_id = await a_session(db_session, team)

    async with (
        the_stream(desk_app, team.team_id, team.desk) as ours,
        the_stream(desk_app, other_team.team_id, other_team.desk) as theirs,
    ):
        assert (ours.status, theirs.status) == (200, 200)
        await raise_a_hand(client, team, session_id)

        assert await nudges_heard(ours) == ["hands"]
        assert await nudges_heard(theirs) == [], "a Mesa de outra equipe ouviu esta sala"


async def test_a_turn_nudges_sessions(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        await the_team_speaks(client, team, session_id)

        assert await nudges_heard(desk) == ["sessions"]


async def test_a_session_opened_from_the_teams_tablet_nudges_sessions_and_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, team: Team
) -> None:
    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        opened = await client.post(f"{IR}/sessions", headers=team.tablet, json={"pericope": P})
        assert opened.status_code == 200, opened.text

        assert await nudges_heard(desk) == ["halts", "sessions"], (
            "abrir uma sessão levanta a parada do tablet e a Mesa não ficava sabendo"
        )


async def test_a_reply_a_resolve_and_a_heard_nudge_hands(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    answered_id = await raise_a_hand(client, team, session_id)
    resolved_id = await raise_a_hand(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        replied = await client.post(
            f"{IR}/facilitator/questions/{answered_id}/reply",
            headers=team.desk,
            files={"file": ("resposta.m4a", b"a facilitadora respondeu", "audio/mp4")},
        )
        assert replied.status_code == 200, replied.text
        assert await nudges_heard(desk) == ["hands"], "a resposta não chegou à Mesa"

        heard = await client.post(f"{IR}/questions/{answered_id}/heard", headers=team.tablet)
        assert heard.status_code == 200, heard.text
        assert await nudges_heard(desk) == ["hands"], "a equipe ouviu e a Mesa não soube"

        resolved = await client.post(
            f"{IR}/facilitator/questions/{resolved_id}/resolve", headers=team.desk
        )
        assert resolved.status_code == 200, resolved.text
        assert await nudges_heard(desk) == ["hands"], "a mão resolvida não chegou à Mesa"


async def test_a_call_for_a_person_and_its_arrival_nudge_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        await the_tablet_halts(client, team, session_id)
        assert await nudges_heard(desk) == ["halts"], "a sala parou e a Mesa não soube"

        arrived = await client.post(
            f"{IR}/sessions/{session_id}/person-arrived", headers=team.tablet
        )
        assert arrived.status_code == 200, arrived.text
        assert await nudges_heard(desk) == ["halts"], "alguém chegou e a Mesa não soube"


async def test_a_tablets_call_for_a_person_without_a_session_nudges_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, team: Team
) -> None:
    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        asked = await client.post(
            f"{IR}/devices/{team.device_id}/needs-person", headers={"X-Room-Key": ROOM_KEY}
        )
        assert asked.status_code == 200, asked.text

        assert await nudges_heard(desk) == ["halts"], (
            "o tablet sem sessão parou e a faixa de Atendimento não soube"
        )


async def test_attending_a_session_and_undoing_it_nudge_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    attended = f"{IR}/facilitator/sessions/{session_id}/attended"

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        marked = await client.post(attended, headers=team.desk)
        assert marked.status_code == 200, marked.text
        assert await nudges_heard(desk) == ["halts"]

        undone = await client.delete(attended, headers=team.desk)
        assert undone.status_code == 200, undone.text
        assert await nudges_heard(desk) == ["halts"]


async def test_attending_a_tablet_and_undoing_it_nudge_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, team: Team
) -> None:
    attended = f"{DESK}/devices/{team.device_id}/attended"

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        marked = await client.post(attended, headers=team.desk)
        assert marked.status_code == 200, marked.text
        assert await nudges_heard(desk) == ["halts"]

        undone = await client.delete(attended, headers=team.desk)
        assert undone.status_code == 200, undone.text
        assert await nudges_heard(desk) == ["halts"]


async def test_a_kept_take_nudges_takes(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        await rehearse(client, team, session_id)

        assert await nudges_heard(desk) == ["takes"]


async def test_a_divide_a_replace_and_a_chunk_nudge_stretches(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    take_id = await rehearse(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        await tell(client, team, session_id, take_id, 0, 9000)
        assert await nudges_heard(desk) == ["stretches"], "o trecho contado não chegou à Mesa"
        await tell(client, team, session_id, take_id, 9000, 18000)
        await nudges_heard(desk)
        first, second = await stretches(client, team, session_id)

        divided = await client.post(
            f"{IR}/sessions/{session_id}/segments/{first['segment_id']}/divide",
            headers=team.tablet,
            json={"at_ms": 4000},
        )
        assert divided.status_code == 200, divided.text
        assert await nudges_heard(desk) == ["stretches"], "o trecho dividido não chegou à Mesa"

        await replace(client, team, session_id, take_id, second)
        assert await nudges_heard(desk) == ["stretches"], "a correção não chegou à Mesa"


async def test_a_replace_nobody_could_make_out_still_nudges_stretches(
    desk_app: FastAPI,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    team: Team,
    ears: list[str],
) -> None:
    session_id = await a_session(db_session, team)
    take_id = await rehearse(client, team, session_id)
    await tell(client, team, session_id, take_id, 0, 9000)
    (stretch,) = await stretches(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        ears.append("")
        unheard = await replace(client, team, session_id, take_id, stretch)
        assert unheard.json()["captured"] is False

        assert await nudges_heard(desk) == ["stretches"]


async def test_a_chunk_that_raises_the_hard_stretch_warning_nudges_stretches_and_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    take_id = await rehearse(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        for _ in range(room.RETELLS_BEFORE_A_WARNING):
            told = await tell(client, team, session_id, take_id, 0, 9000, again=True)
            heard = await nudges_heard(desk)
            if told.json()["needs_person"]:
                break

    assert told.json()["needs_person"] is True
    assert heard == ["halts", "stretches"], (
        "o trecho difícil chamou alguém e a faixa de Atendimento não soube"
    )


async def test_a_replace_that_raises_the_hard_stretch_warning_nudges_stretches_and_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    take_id = await rehearse(client, team, session_id)
    await tell(client, team, session_id, take_id, 0, 9000)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        for _ in range(room.RETELLS_BEFORE_A_WARNING):
            (stretch,) = await stretches(client, team, session_id)
            replaced = await replace(client, team, session_id, take_id, stretch)
            heard = await nudges_heard(desk)
            if replaced.json()["needs_person"]:
                break

    assert replaced.json()["needs_person"] is True
    assert heard == ["halts", "stretches"]


async def test_finishing_the_check_nudges_verdict(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    await rehearse(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        finished = await client.post(
            f"{IR}/sessions/{session_id}/back-translation/finish", headers=team.tablet
        )
        assert finished.status_code == 200, finished.text

        assert await nudges_heard(desk) == ["verdict"]


async def test_a_release_the_teams_or_the_forced_one_nudges_release(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    approved_by_the_team = await ready_session(db_session, project_id=team.team_id)
    forced_at_the_desk = await ready_session(db_session, project_id=team.team_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        approved = await client.post(
            f"{IR}/sessions/{approved_by_the_team.id}/release", headers=team.tablet
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["blockers"] == []
        assert await nudges_heard(desk) == ["release"]

        forced = await client.post(
            f"{IR}/facilitator/sessions/{forced_at_the_desk.id}/release",
            headers=team.desk,
            json={"force": True},
        )
        assert forced.status_code == 200, forced.text
        assert await nudges_heard(desk) == ["release"]


async def test_a_turn_that_lifts_a_halt_nudges_sessions_and_halts(
    desk_app: FastAPI, client: httpx.AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    session_id = await a_session(db_session, team)
    await the_tablet_halts(client, team, session_id)

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        await the_team_speaks(client, team, session_id)

        assert await nudges_heard(desk) == ["halts", "sessions"], (
            "o turno que aterrissou tirou a parada e a faixa de Atendimento não soube"
        )


async def test_a_write_on_a_session_with_no_team_nudges_nobody_and_does_not_fail(
    desk_app: FastAPI, client: httpx.AsyncClient, team: Team
) -> None:
    from app.services.internalization_room.nudge_channel import _subscribers

    async with the_stream(desk_app, team.team_id, team.desk) as desk:
        assert desk.status == 200
        opened = await client.post(
            f"{IR}/sessions", headers={"X-Room-Key": ROOM_KEY}, json={"pericope": P}
        )
        assert opened.status_code == 200, opened.text
        halted = await client.post(
            f"{IR}/sessions/{opened.json()['session_id']}/needs-person",
            headers={"X-Room-Key": ROOM_KEY},
        )
        assert halted.status_code == 200, halted.text

        assert await nudges_heard(desk) == []
        assert None not in _subscribers, "uma escrita sem equipe abriu lugar no registro"
