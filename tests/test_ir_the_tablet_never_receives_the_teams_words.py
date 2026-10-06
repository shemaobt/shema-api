"""ENG-1335 — answers to the team's device never carry the words of a telling.

The team's own words, the analyst's notes on a finding and the verdict's text are the
facilitator's to read, at the Desk. The tablet only plays audio. The cases below speak and
read through the room's real doors with a sentinel as what the team said, and the guard reads
the mounted app so a door added tomorrow is held to the same rule.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.db.models.internalization_room import IRSegment
from app.models.internalization_room import ConversationTurn
from app.services.internalization_room.back_translation import Finding
from app.services.internalization_room.coverage import coverage_view
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.turn_dedup import remember_turn
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    team_headers,
)
from tests.room_harness import (
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)
from tests.room_route_audit_harness import models_in, room_app_routes
from tests.turn_harness import the_room_agent_is, the_speaker_answers

SENTINEL = "SENTINELA-A-FALA-DA-EQUIPE-NAO-SAI-DA-MESA"
FINDING_NOTE = "SENTINELA-NOTA-DO-ANALISTA-NAO-SAI-DA-MESA"
VERDICT_DRAFT = "SENTINELA-FALA-DO-VEREDITO-NAO-SAI-DA-MESA"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"

TRANSCRIPT, NOTE, TEXT = IRSegment.transcript.key, "note", "text"
WORDS = {TRANSCRIPT, NOTE, TEXT}


def _keys(body: Any) -> set[str]:
    if isinstance(body, dict):
        return set(body) | {key for value in body.values() for key in _keys(value)}
    if isinstance(body, list):
        return {key for value in body for key in _keys(value)}
    return set()


@pytest.fixture()
def said(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    heard_now = [SENTINEL]

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=heard_now[0])

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE

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
    return heard_now


@pytest.fixture()
async def client(db_session: AsyncSession, test_engine, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    per_request = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


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


async def _audio_less(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> httpx.Response:
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    assert response.status_code == 200, response.text[:300]
    return response


async def test_a_spoken_turns_answer_to_the_tablet_carries_no_transcript(
    client, db_session, said
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)

    answered = await _the_team_says(client, credential, session.id, "turno-1")

    assert "transcript" not in answered.json()
    assert SENTINEL not in answered.text


async def test_the_same_turn_read_by_the_facilitator_still_shows_the_teams_words(
    client, db_session, room_app, said
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    await _the_team_says(client, credential, session.id, "turno-1")

    read = await client.get(
        f"{PREFIX}/facilitator/sessions/{session.id}/conversation", headers=desk
    )

    assert read.status_code == 200, read.text
    assert [(t["role"], t["text"]) for t in read.json()["turns"]] == [
        ("team", SENTINEL),
        ("guide", GUIDE_LINE),
    ]


async def test_a_turn_answer_stored_before_the_change_is_served_without_its_transcript(
    client, db_session, said
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    await remember_turn(
        db_session,
        session_id=session.id,
        turn_id="turno-antigo",
        response={
            "session_id": session.id,
            "transcript": SENTINEL,
            "coverage": coverage_view(session).model_dump(mode="json"),
            "done": False,
            "turn_id": "turno-antigo",
        },
    )
    await db_session.commit()

    resent = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers=team_headers(credential),
        data={"turn_id": "turno-antigo"},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    looked = await client.get(
        f"{PREFIX}/sessions/{session.id}/turns/turno-antigo", headers=team_headers(credential)
    )

    for answer in (resent, looked):
        assert answer.status_code == 200, answer.text
        assert "transcript" not in answer.json()
        assert SENTINEL not in answer.text


def test_no_tablet_door_answers_with_a_model_that_carries_the_teams_words() -> None:
    assert NOTE in Finding.model_fields and TEXT in ConversationTurn.model_fields, (
        "uma fonte do lado do facilitador mudou de nome; a guarda procuraria o que nao existe"
    )

    carrying = {
        (sorted(route.methods)[0], route.path, model.__name__): sorted(
            WORDS & set(model.model_fields)
        )
        for route in room_app_routes()
        for model in models_in(route.response_model)
        if WORDS & set(model.model_fields)
    }

    assert not carrying, f"estas portas do tablet respondem com as palavras da equipe: {carrying}"


def test_the_guard_walks_the_turn_door_and_the_verdict_door() -> None:
    walked = {(sorted(r.methods)[0], r.path) for r in room_app_routes()}

    assert ("POST", f"{PREFIX}/sessions/{{session_id}}/turns") in walked
    assert ("POST", f"{PREFIX}/sessions/{{session_id}}/back-translation/finish") in walked


async def test_the_opening_and_the_say_it_again_answers_carry_no_transcript(
    client, db_session, said
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)

    opening = await _audio_less(client, credential, session.id)
    again = await _audio_less(client, credential, session.id)

    assert "transcript" not in opening.json()
    assert "transcript" not in again.json()


async def test_a_rehearsal_takes_answer_carries_none_of_the_teams_words(client, db_session) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 1)

    answered = await upload_a_part(client, session.id, part=None, audio=b"audio")

    assert answered.status_code == 200, answered.text
    assert not (WORDS & _keys(answered.json()))


async def test_the_verdicts_answer_to_the_tablet_carries_no_telling_note_or_verdict_text(
    client, db_session, monkeypatch
) -> None:
    the_speaker_answers(monkeypatch, VERDICT_DRAFT)
    analyst = the_analyst_is_scripted(monkeypatch)
    session, _parts = await rehearsed_in_parts(db_session, 1)
    analyst.readings = [{"findings": [{"kind": "addition", "note": FINDING_NOTE, "chunk": 1}]}]

    answered = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    assert answered.status_code == 200, answered.text
    for sentinel in ("parte 0 contada de volta", FINDING_NOTE, VERDICT_DRAFT):
        assert sentinel not in answered.text
