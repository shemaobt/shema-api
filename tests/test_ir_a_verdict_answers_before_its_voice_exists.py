from __future__ import annotations

import asyncio
import importlib
import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.clip_flight_harness import (
    Elevenlabs,
    WriteOnceBucket,
    another_instance,
    voice_room_client,
)
from tests.room_harness import (
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    the_analyst_reads,
)

VERDICT = "Vocês contaram bem."


@pytest.fixture()
def elevenlabs() -> Elevenlabs:
    return Elevenlabs(b"the verdict")


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, elevenlabs: Elevenlabs):
    the_analyst_reads(monkeypatch)

    async def _speaker(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return VERDICT

    monkeypatch.setattr(
        importlib.import_module("app.services.internalization_room.run_turn"),
        "call_agent",
        _speaker,
    )
    async with voice_room_client(
        db_session, monkeypatch, elevenlabs=elevenlabs, bucket=WriteOnceBucket()
    ) as c:
        yield c


async def test_terminei_answers_while_the_verdicts_voice_is_still_being_made(
    client: httpx.AsyncClient, db_session: AsyncSession, elevenlabs: Elevenlabs
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 2)
    report = played_every_part([part.id for part in parts])

    elevenlabs.held.clear()
    try:
        answered = await asyncio.wait_for(press_terminei(client, session.id, report=report), 1)
        listening = asyncio.create_task(client.get(answered.json()["audio_url"]))
        await asyncio.sleep(0.05)
    finally:
        elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert answered.status_code == 200
    assert heard.content == b"the verdict"
    assert len(elevenlabs.texts) == 1, "o veredito era sintetizado antes de o terminei responder"


async def test_a_verdict_whose_voice_failed_is_voiced_from_what_the_session_kept(
    client: httpx.AsyncClient, db_session: AsyncSession, elevenlabs: Elevenlabs
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 2)
    elevenlabs.failures = 1

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )
    await asyncio.sleep(0.05)
    another_instance()
    heard = await client.get(answered.json()["audio_url"])

    assert answered.status_code == 200
    assert heard.status_code == 200, (
        "o veredito cuja voz falhou não tinha de onde ser refeito, e o tablet ficava sem ele"
    )
    assert heard.content == b"the verdict"
    assert elevenlabs.texts[-1] == elevenlabs.texts[0]


async def test_terminei_pressed_again_hands_back_the_address_that_can_still_be_voiced(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 2)
    report = played_every_part([part.id for part in parts])

    first = await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    assert again.json()["audio_url"] == first.json()["audio_url"], (
        "o segundo terminei devolvia o endereço sem a sessão, que não refaz a voz que falhou"
    )
