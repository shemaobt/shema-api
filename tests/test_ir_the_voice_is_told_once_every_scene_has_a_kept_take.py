"""ENG-1379 — the voice is told once every scene of the passage has a kept take.

In her app, once the team's own passing retelling of every part is kept, the Guide reads her
KEPT REHEARSALS note right after SCENE REHEARSALS, so it may offer the numbered replay buttons
before the send-off (her src/turn/sceneRehearsals.ts:57-66, app/lib/liveTurn.ts:454-458). The
note is read from the takes kept as the session stood when the turn began, never stored, and
never read by the Validator. Ours kept the takes (ENG-1378) and told the voice nothing.
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
from app.services.internalization_room import background
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.sessions import get_session
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_turn_is_scripted
from tests.turn_harness import the_room_agent_is

KEPT = (
    "KEPT REHEARSALS: the team's own passing retellings of every part of this passage are "
    "saved. Small numbered buttons on their screen replay each part in the team's own voice. "
    "Before the send-off you may offer this once, warmly: if a part has gone cold, they can "
    "tap its number and hear their own telling of it again. Never require it. These kept "
    "takes are practice audio for listening only."
)
NO_SCENE_SENT = (
    "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
    "none. Parts with none: S1, S2, S3."
)
TOLD = "Teve fome em Belem e Elimeleque foi com Noemi e os filhos para Moabe."


def kept(scope: str) -> dict[str, Any]:
    return {
        "scope": scope,
        "approved": True,
        "kept": {"storage_key": f"takes/{scope}.m4a", "content_type": "audio/m4a"},
    }


class Models:
    def __init__(self) -> None:
        self.guide_systems: list[str] = []
        self.validator_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_inputs.append(f"{system_prompt}\n{user_content}")
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide_systems.append(system_prompt)
        return "Isso. Vocês contaram a cena inteira."

    def facts(self, turn: int) -> str:
        return self.guide_systems[turn].partition(CACHE_BREAK)[2]


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def verdict() -> dict[str, Any]:
    return {}


@pytest.fixture()
def spoken() -> dict[str, Any]:
    return {}


@pytest.fixture()
def models() -> Models:
    return Models()


@pytest.fixture()
async def client(
    db_session: AsyncSession, per_request, verdict, spoken, models, monkeypatch
) -> AsyncIterator[httpx.AsyncClient]:
    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=TOLD, **spoken)

    async def reader(**_: Any) -> str:
        return json.dumps({"decisions": [], **verdict})

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    @asynccontextmanager
    async def fresh() -> AsyncIterator[AsyncSession]:
        async with per_request() as session:
            yield session

    the_turn_is_scripted(monkeypatch, heard=heard, model=models)
    the_room_agent_is(monkeypatch, classifier=reader)
    monkeypatch.setattr(sessions_api, "settle_coverage", background.settle_coverage)
    monkeypatch.setattr(background, "AsyncSessionLocal", fresh)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as built:
        yield built


async def _a_p02_session(client: httpx.AsyncClient, db_session: AsyncSession) -> tuple[str, str]:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P02"},
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
        files={"file": ("resposta.m4a", b"a equipe contando", "audio/m4a")},
    )
    assert told.status_code == 200, told.text[:300]


async def _the_takes_stand(
    per_request: async_sessionmaker[AsyncSession], session_id: str, retellings: dict[str, Any]
) -> None:
    async with per_request() as fresh:
        stored = await get_session(fresh, session_id)
        stored.retellings = retellings
        await fresh.commit()


async def test_every_scene_told_and_judged_complete_tells_the_voice_on_the_next_turn(
    client, db_session, verdict, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)

    for n, scope in enumerate(("S1", "S2", "S3"), start=1):
        verdict["retelling"] = {"scope": scope, "approved": True}
        await _the_team_tells(client, tablet, session_id, f"turno-{n}")
    verdict.clear()
    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert f"{NO_SCENE_SENT}\n\n{KEPT}\n\n" in models.facts(4), (
        "com as três cenas guardadas, a voz não lia a nota dos ensaios guardados logo depois "
        "dos ensaios de cena"
    )
    assert "KEPT REHEARSALS" not in models.facts(3), (
        "o turno que guardou a última cena já contava a tomada que só ficou guardada depois dele"
    )


async def test_two_of_three_scenes_kept_tell_the_voice_nothing(
    client, db_session, verdict, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)

    for n, scope in enumerate(("S1", "S2"), start=1):
        verdict["retelling"] = {"scope": scope, "approved": True}
        await _the_team_tells(client, tablet, session_id, f"turno-{n}")
    verdict.clear()
    await _the_team_tells(client, tablet, session_id, "turno-3")

    assert not any("KEPT REHEARSALS" in system for system in models.guide_systems), (
        "com duas das três cenas guardadas, a voz já ouvia que todas estavam guardadas"
    )


async def test_a_scene_approved_with_no_take_kept_counts_for_no_kept_take(
    client, db_session, per_request, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)
    await _the_takes_stand(
        per_request,
        session_id,
        {"1": kept("S1"), "2": kept("S2"), "3": {"scope": "S3", "approved": True}},
    )

    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert "KEPT REHEARSALS" not in models.facts(-1), (
        "um ensaio do microfone vermelho aprovado, sem tomada guardada, contava como guardado"
    )


async def test_a_mother_tongue_take_of_the_last_scene_never_completes_the_kept_takes(
    client, db_session, verdict, spoken, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)
    for n, scope in enumerate(("S1", "S2"), start=1):
        verdict["retelling"] = {"scope": scope, "approved": True}
        await _the_team_tells(client, tablet, session_id, f"turno-{n}")

    verdict["retelling"] = {"scope": "S3", "approved": True}
    spoken.update(language_code="es", language_probability=0.99)
    await _the_team_tells(client, tablet, session_id, "turno-3")
    verdict.clear()
    spoken.clear()
    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert "KEPT REHEARSALS" not in models.facts(-1), (
        "uma tomada na língua materna virava a tomada guardada da última cena"
    )


async def test_a_whole_passage_take_stands_for_no_scene(
    client, db_session, per_request, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)
    await _the_takes_stand(
        per_request, session_id, {"1": kept("S1"), "2": kept("S2"), "3": kept("whole")}
    )

    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert "KEPT REHEARSALS" not in models.facts(-1), (
        "a tomada da passagem inteira contava como a tomada da cena que faltava"
    )


async def test_the_note_is_never_stored_with_the_turn(
    client, db_session, per_request, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)
    await _the_takes_stand(
        per_request, session_id, {"1": kept("S1"), "2": kept("S2"), "3": kept("S3")}
    )

    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert KEPT in models.facts(-1), "com as três cenas guardadas a voz não lia a nota"
    async with per_request() as fresh:
        stored = await get_session(fresh, session_id)
    assert "KEPT REHEARSALS" not in json.dumps(stored.messages), (
        "a nota dos ensaios guardados ficou guardada na conversa"
    )
    assert "KEPT REHEARSALS" not in json.dumps(stored.retellings), (
        "a nota dos ensaios guardados ficou guardada com os vereditos"
    )


async def test_the_validator_reads_neither_the_scene_rehearsals_nor_the_kept_rehearsals(
    client, db_session, per_request, models
) -> None:
    tablet, session_id = await _a_p02_session(client, db_session)
    await _the_takes_stand(
        per_request, session_id, {"1": kept("S1"), "2": kept("S2"), "3": kept("S3")}
    )

    await _the_team_tells(client, tablet, session_id, "turno-4")

    assert KEPT in models.facts(-1), "com as três cenas guardadas a voz não lia a nota"
    read = "\n".join(models.validator_inputs)
    assert models.validator_inputs, "o Validador nem foi chamado"
    for fact in ("SCENE REHEARSALS", "KEPT REHEARSALS"):
        assert fact not in read, f"o Validador lia {fact!r}"
