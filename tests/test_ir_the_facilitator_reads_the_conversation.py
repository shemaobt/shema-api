"""ENG-1126 — a facilitator reads a session's Conversation as turns in text.

The Conversation is the Internalization stage where the team and the Guide talk; the
telling-back round that follows has its own Station and is not part of it. The route answers
the turns in the order they were said, with the fail-safe lines marked and named.

Every case writes through the room's own turn route and reads through the Desk's route.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    ready_session,
    team_headers,
)
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

GUIDE_OPENING = "Vamos ouvir a historia de Rute. O que voces ja sabem dela?"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"
FIRST_ANSWER = "Noemi voltou para Belem com Rute"
SECOND_ANSWER = "Rute disse que ia junto com ela"
THIRD_ANSWER = "Noemi chegou na colheita da cevada"


class _Script:
    def __init__(self) -> None:
        self.said = ""
        self.mother_tongue = False
        self.fail_safe = False


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> _Script:
    scripted = _Script()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        if scripted.mother_tongue:
            return HeardSpeech(text=scripted.said, language_code="sw", language_probability=0.99)
        return HeardSpeech(text=scripted.said)

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            verdict = "regenerate" if scripted.fail_safe else "pass"
            return json.dumps({"verdict": verdict, "issues": []})
        return GUIDE_OPENING if not scripted.said else GUIDE_LINE

    async def voice(text: str, **_: Any):
        return (
            SynthesizedSpeech(
                audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/x.mp3"
            ),
            False,
        )

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    the_room_agent_is(monkeypatch, turn=model)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    return scripted


@pytest.fixture()
async def client(db_session: AsyncSession, test_engine, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    per_request = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def _conversation_of(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/conversation"


async def _the_team_says(
    client: httpx.AsyncClient, credential: str, session_id: str, turn_id: str
) -> httpx.Response:
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert response.status_code == 200, response.text[:300]
    return response


async def _the_room_opens(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> httpx.Response:
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    assert response.status_code == 200, response.text[:300]
    return response


async def _a_conversation(
    client: httpx.AsyncClient, db: AsyncSession, room_app, script: _Script
) -> tuple[str, dict[str, str], str]:
    """The opening and three turns: a plain one, a fail-safe line, and the room's note."""
    project, credential = await a_claimed_device(db)
    session = await create_session(db, language="pt", pericope=P, project_id=project.id)
    desk, _facilitator = await at_the_desk(db, room_app, project)

    await _the_room_opens(client, credential, session.id)

    script.said = FIRST_ANSWER
    await _the_team_says(client, credential, session.id, "turno-1")

    script.said = SECOND_ANSWER
    script.fail_safe = True
    await _the_team_says(client, credential, session.id, "turno-2")
    script.fail_safe = False

    script.said = THIRD_ANSWER
    script.mother_tongue = True
    await _the_team_says(client, credential, session.id, "turno-3")
    script.mother_tongue = False
    return session.id, desk, credential


async def _turns(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> list[dict]:
    response = await client.get(_conversation_of(session_id), headers=desk)
    assert response.status_code == 200, response.text
    return response.json()["turns"]


async def test_a_facilitator_reads_the_conversation_as_turns_in_order(
    client, db_session, room_app, script
) -> None:
    session_id, desk, _credential = await _a_conversation(client, db_session, room_app, script)

    turns = await _turns(client, session_id, desk)

    assert [(t["role"], t["text"]) for t in turns[:4]] == [
        ("guide", GUIDE_OPENING),
        ("team", FIRST_ANSWER),
        ("guide", GUIDE_LINE),
        ("team", SECOND_ANSWER),
    ]
    assert [t["role"] for t in turns[4:]] == ["guide", "room", "guide"]
    assert turns[5]["text"]
    assert all(t["at"] for t in turns)
    assert [t["at"] for t in turns] == sorted(t["at"] for t in turns)


async def test_only_the_fail_safe_line_is_marked_and_names_its_category(
    client, db_session, room_app, script
) -> None:
    session_id, desk, _credential = await _a_conversation(client, db_session, room_app, script)

    turns = await _turns(client, session_id, desk)

    marked = [t for t in turns if t["fail_safe"]]
    assert len(marked) == 1
    assert marked[0]["role"] == "guide"
    assert marked[0]["fail_safe_category"] == "unrepairable"
    assert all(
        t["fail_safe_category"] is None and t["fail_safe"] is False
        for t in turns
        if t is not marked[0]
    )


async def test_a_turn_the_tablet_resent_is_not_doubled(
    client, db_session, room_app, script
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    script.said = FIRST_ANSWER

    await _the_team_says(client, credential, session.id, "turno-1")
    await _the_team_says(client, credential, session.id, "turno-1")

    turns = await _turns(client, session.id, desk)
    assert [(t["role"], t["text"]) for t in turns] == [
        ("team", FIRST_ANSWER),
        ("guide", GUIDE_LINE),
    ]


async def test_the_telling_back_round_is_not_part_of_the_conversation(
    client, db_session, room_app, script
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    await append_exchange(
        db_session, session, team_utterance=FIRST_ANSWER, guide_response=GUIDE_LINE
    )
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    before = await _turns(client, session.id, desk)
    assert len(before) == 2
    await db_session.refresh(session)
    stored_before = len(session.messages or [])

    finished = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    assert finished.status_code == 200, finished.text

    await db_session.refresh(session)
    stored_after = len(session.messages or [])
    assert stored_after > stored_before, "the round wrote nothing, so this case proves nothing"
    assert await _turns(client, session.id, desk) == before


async def test_an_entry_stored_before_the_stamps_reads_as_conversation_with_no_moment(
    client, db_session, room_app, script
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    session.messages = [
        {"role": "guide", "text": GUIDE_OPENING},
        {"role": "team", "text": FIRST_ANSWER},
        {"role": "guide", "text": "linha fixa", "category": "D"},
    ]
    await db_session.commit()
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    turns = await _turns(client, session.id, desk)

    assert [(t["role"], t["text"], t["at"]) for t in turns] == [
        ("guide", GUIDE_OPENING, None),
        ("team", FIRST_ANSWER, None),
        ("guide", "linha fixa", None),
    ]
    assert turns[2]["fail_safe"] is True
    assert turns[2]["fail_safe_category"] == "inaudible"


async def test_a_facilitator_of_another_team_gets_the_session_reads_404(
    client, db_session, room_app, script
) -> None:
    mine, _credential = await a_claimed_device(db_session, email="dona@example.com")
    theirs, _other = await a_claimed_device(db_session, email="estranha@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=mine.id)
    owner, _her = await at_the_desk(db_session, room_app, mine)
    stranger, _them = await at_the_desk(db_session, room_app, theirs)

    refused = await client.get(_conversation_of(session.id), headers=stranger)
    unknown = await client.get(_conversation_of("nao-existe"), headers=owner)

    assert refused.status_code == 404, refused.text
    assert "turns" not in refused.json()
    assert unknown.status_code == 404
    assert (await client.get(_conversation_of(session.id), headers=owner)).status_code == 200


async def test_a_fail_safe_line_with_a_letter_no_category_has_is_still_marked(
    client, db_session, room_app, script
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    session.messages = [
        {"role": "guide", "text": "linha fixa", "outcome": "fail_safe", "category": "Z"}
    ]
    await db_session.commit()
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    (turn,) = await _turns(client, session.id, desk)

    assert turn["fail_safe"] is True
    assert turn["fail_safe_category"] is None
