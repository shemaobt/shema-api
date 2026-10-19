"""ENG-1378 (b) — a telling the voice approved is kept for the team to hear again.

In her app the team's own audio of a turn becomes the kept take of the scope it told when
the reading after the reply finds the voice treated that telling as complete (her
api/turn/route.ts:397-411). Ours threw a turn's audio away once it was heard, so nothing
could ever be kept.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.services.internalization_room import background
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_turn_is_scripted
from tests.turn_harness import the_room_agent_is

TAKE = b"a equipe contando a cena da fome"
TOLD = "Teve fome em Belem e Elimeleque foi com Noemi e os filhos para Moabe."


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def verdict() -> dict[str, Any]:
    return {}


@pytest.fixture()
def lands() -> list[int]:
    return []


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    per_request,
    verdict,
    lands,
    bucket,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    read: list[int] = []

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=TOLD)

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Isso. Vocês contaram a cena inteira."

    async def reader(**_: Any) -> str:
        read.append(1)
        if lands and len(read) > lands[0]:
            raise RuntimeError("o classificador caiu")
        return json.dumps({"decisions": [], **verdict})

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    async def sign(_bucket: str, key: str, **_: Any) -> str:
        return f"https://storage.example/{key}"

    @asynccontextmanager
    async def fresh() -> AsyncIterator[AsyncSession]:
        async with per_request() as session:
            yield session

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    the_room_agent_is(monkeypatch, classifier=reader)
    monkeypatch.setattr(sessions_api, "settle_coverage", background.settle_coverage)
    monkeypatch.setattr(background, "AsyncSessionLocal", fresh)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", sign)
    async with room_client(db_session, monkeypatch, per_request=per_request) as built:
        yield built


async def _a_p01_session(client: httpx.AsyncClient, db_session: AsyncSession) -> tuple[str, str]:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P01"},
    )
    session_id = opened.json()["session_id"]
    await the_room_opens(client, tablet, session_id)
    return tablet, session_id


async def _the_team_tells(
    client: httpx.AsyncClient, tablet: str, session_id: str, turn_id: str
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(tablet),
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", TAKE, "audio/m4a")},
    )
    assert told.status_code == 200, told.text[:300]


async def _kept(client: httpx.AsyncClient, tablet: str, session_id: str) -> list[dict[str, Any]]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", headers=team_headers(tablet))
    assert read.status_code == 200, read.text[:300]
    return read.json()["kept_takes"]


async def test_a_telling_the_voice_approved_keeps_its_audio_and_the_session_serves_it(
    client, db_session, verdict, bucket
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    verdict["retelling"] = {"scope": "S1", "approved": True}

    await _the_team_tells(client, tablet, session_id, "turno-1")

    stored = [key for key, audio in bucket.objects.items() if audio == TAKE]
    assert len(stored) == 1, (
        "a voz aprovava a recontagem e o áudio da equipe era jogado fora depois de ouvido"
    )
    assert await _kept(client, tablet, session_id) == [
        {"scope": "S1", "turn_number": 1, "audio_url": f"https://storage.example/{stored[0]}"}
    ], "a leitura da sessão não dizia qual cena ficou guardada nem onde ouvir"


async def test_a_telling_the_voice_sent_back_or_did_not_judge_keeps_nothing(
    client, db_session, verdict, bucket
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)

    verdict["retelling"] = {"scope": "S1", "approved": False}
    await _the_team_tells(client, tablet, session_id, "turno-1")
    verdict.clear()
    await _the_team_tells(client, tablet, session_id, "turno-2")

    assert TAKE not in bucket.objects.values(), (
        "uma recontagem que a voz mandou contar de novo ficava guardada como aprovada"
    )
    assert await _kept(client, tablet, session_id) == []


async def test_a_scene_told_and_approved_twice_is_heard_in_its_latest_telling(
    client, db_session, verdict, bucket
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)

    for turn, scope in enumerate(["S1", "S1", "S2"], start=1):
        verdict["retelling"] = {"scope": scope, "approved": True}
        await _the_team_tells(client, tablet, session_id, f"turno-{turn}")

    assert [
        (take["scope"], take["turn_number"]) for take in await _kept(client, tablet, session_id)
    ] == [("S1", 2), ("S2", 3)], "a cena aprovada duas vezes tocava as duas tomadas, e a velha"


async def test_a_session_with_no_verdict_yet_reads_as_holding_no_kept_take(
    client, db_session
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)

    assert await _kept(client, tablet, session_id) == [], (
        "uma sessão sem veredito nenhum não abria na leitura do tablet"
    )


async def test_a_reader_that_falls_mid_turn_keeps_nothing_and_the_names_still_count(
    client, db_session, per_request, verdict, lands, bucket
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    verdict["retelling"] = {"scope": "S1", "approved": True}
    lands.append(1)

    await _the_team_tells(client, tablet, session_id, "turno-1")

    async with per_request() as fresh:
        stored = await get_session(fresh, session_id)
    assert stored.retellings is None, (
        "o leitor caía no meio do turno e a aprovação da leitura que chegou guardava a tomada"
    )
    assert TAKE not in bucket.objects.values()
    assert await _kept(client, tablet, session_id) == []
    assert stored.coverage_state["being:S1:B3"] == "engaged", (
        "sem o leitor, a Noemi que a equipe disse deixava de contar"
    )
