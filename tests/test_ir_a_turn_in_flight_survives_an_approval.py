"""ENG-1259 — a team turn in flight when the team's approval lands is answered, not refused.

The approval claims the session's version so a Zerar or a moved session refuses the mint
(ADR 0066), and a turn whose Guide was still answering then lost the session's write guard
and the Guide's paid line with it. The approval moves nothing in the conversation, so the turn lands
once more on the new version; a turn that lost to another turn is still refused (ADR 0080).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.release import approve_release
from app.services.internalization_room.sessions import append_exchange, get_session
from app.services.internalization_room.voice_handles import from_handle
from tests.release_harness import (
    TABLET,
    a_claimed_device,
    ready_session,
    releases_of,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import a_turn_is_sent, the_team_says, the_turn_is_scripted

WORDS = "A Noemi voltou com a Rute."
REPLY = "Isso. E o que a Rute disse para ela?"
RIVAL_WORDS = "Sim."
RIVAL_REPLY = "Contem mais."

Meanwhile = Callable[[], Awaitable[None]]


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def while_the_guide_answers() -> list[Meanwhile]:
    return []


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    per_request,
    while_the_guide_answers: list[Meanwhile],
    monkeypatch: pytest.MonkeyPatch,
):
    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=WORDS)

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        while while_the_guide_answers:
            await while_the_guide_answers.pop(0)()
        return REPLY

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def _a_session_ready_for_release(db_session: AsyncSession) -> tuple[str, str]:
    project, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    return tablet, session.id


def _the_team_approves_meanwhile(per_request, session_id: str) -> Meanwhile:
    async def approve() -> None:
        async with per_request() as rival:
            await approve_release(rival, await get_session(rival, session_id), device_id=TABLET)

    return approve


def _another_turn_lands_meanwhile(per_request, session_id: str) -> Meanwhile:
    async def speak() -> None:
        async with per_request() as rival:
            await append_exchange(
                rival,
                await get_session(rival, session_id),
                team_utterance=RIVAL_WORDS,
                guide_response=RIVAL_REPLY,
            )

    return speak


async def _stored_messages(per_request, session_id: str) -> list[dict[str, Any]]:
    async with per_request() as fresh:
        return list((await get_session(fresh, session_id)).messages or [])


async def _a_turn_overtaken_by_the_teams_approval(
    client, db_session, per_request, while_the_guide_answers
) -> tuple[str, str]:
    tablet, session_id = await _a_session_ready_for_release(db_session)
    while_the_guide_answers.append(_the_team_approves_meanwhile(per_request, session_id))
    await the_team_says(client, tablet, session_id, "turno-1")
    return tablet, session_id


async def test_a_team_turn_whose_guide_is_answering_when_the_teams_approval_lands_is_answered_and_kept(  # noqa: E501
    client, db_session, per_request, while_the_guide_answers
) -> None:
    tablet, session_id = await _a_session_ready_for_release(db_session)
    while_the_guide_answers.append(_the_team_approves_meanwhile(per_request, session_id))

    answered = await a_turn_is_sent(client, tablet, session_id, "turno-1")

    assert answered.status_code == 200, (
        f"a aprovação levou a versão e o turno em voo perdeu a fala do Guia: {answered.text[:300]}"
    )
    messages = await _stored_messages(per_request, session_id)
    assert [(m["role"], m["text"]) for m in messages[-2:]] == [("team", WORDS), ("guide", REPLY)]
    handle = httpx.URL(answered.json()["audio_url"]).path.rsplit("/", 1)[-1]
    served = from_handle(handle, settings=get_settings())
    assert served == messages[-1]["voice_key"], "a equipe não ouve a resposta que ficou guardada"
    assert [row.version for row in await releases_of(db_session, session_id)] == [1], (
        "a aprovação não gravou, e o turno não correu contra nada"
    )


async def test_the_approval_stands_after_the_turn_lands(
    client, db_session, per_request, while_the_guide_answers
) -> None:
    tablet, session_id = await _a_turn_overtaken_by_the_teams_approval(
        client, db_session, per_request, while_the_guide_answers
    )
    (first,) = await releases_of(db_session, session_id)

    again = await client.post(team_release(session_id), headers=team_headers(tablet))

    assert again.status_code == 200, again.text
    assert again.json()["release_id"] == first.packet["release_id"]
    assert again.json()["version"] == 1, "o turno não moveu nada do pacote, e nasceu uma v2"


async def test_a_team_turn_whose_conversation_another_turn_moved_is_still_refused(
    client, db_session, per_request, while_the_guide_answers
) -> None:
    tablet, session_id = await _a_session_ready_for_release(db_session)
    while_the_guide_answers.append(_another_turn_lands_meanwhile(per_request, session_id))

    refused = await a_turn_is_sent(client, tablet, session_id, "turno-1")

    assert refused.status_code == 409, refused.text[:300]
    assert refused.json()["code"] == "CONFLICT"
    texts = [m["text"] for m in await _stored_messages(per_request, session_id)]
    assert texts.count(RIVAL_WORDS) == 1, "o turno recusado escreveu por cima do que o outro disse"
    assert WORDS not in texts
    assert REPLY not in texts
