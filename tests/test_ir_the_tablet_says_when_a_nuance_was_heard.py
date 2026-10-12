from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import background
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import get_session
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    PREFIX,
    heard_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_analyst_is_scripted,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

ON_FRASE_2 = {
    "kind": "nuance",
    "note": "O jeito de contar mudou.",
    "frase": 2,
    "quote": "contada de volta",
    "story": "a história conta de outro jeito",
}
NAMES_FRASE_2 = "Só um detalhe, na frase 2: vocês traduziram «contada de volta»."


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.briefs.append(system_prompt)
        return self.line


async def _heard(client: Any, session_id: str, at: Any, **headers: str) -> Any:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/heard",
        json={"at": at},
        **({"headers": headers} if headers else {}),
    )


def _stamp(answer: Any) -> datetime | None:
    at = answer.json()["check_at"]
    return datetime.fromisoformat(at) if at else None


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch):
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    the_room_speaks(monkeypatch)
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_the_verdict_answer_carries_the_stamp_of_the_round_that_gave_it(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    report = await heard_every_part(db_session, session.id)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    first = await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    assert first.status_code == 200, first.text
    rounds = (await stored_telling_back(db_session, session)).checks
    assert len(rounds) == 1
    assert _stamp(first) == rounds[0].at, (
        "o tablet não tinha como dizer qual veredito tocou até o fim"
    )
    assert _stamp(again) == rounds[0].at, (
        "o veredito guardado voltava sem a marca da rodada que o deu"
    )


async def test_a_verdict_the_tablet_played_to_its_end_is_kept_heard_on_the_servers_clock(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    before = datetime.now(UTC)

    heard = await _heard(client, session.id, pressed.json()["check_at"])

    assert heard.status_code == 200, heard.text
    assert heard.json() == {"marked": True}
    [kept] = (await stored_telling_back(db_session, session)).checks
    assert kept.heard_at is not None, "o tablet não tinha onde dizer que o veredito tocou até o fim"
    assert kept.heard_at >= before, "a hora era a do tablet, não a do servidor"


async def test_only_the_first_report_that_a_verdict_was_heard_counts(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await _heard(client, session.id, pressed.json()["check_at"])
    [first] = (await stored_telling_back(db_session, session)).checks

    again = await _heard(client, session.id, pressed.json()["check_at"])

    assert again.status_code == 200, again.text
    assert again.json() == {"marked": False}, "ouvir a resposta de novo contava como outra escuta"
    [kept] = (await stored_telling_back(db_session, session)).checks
    assert kept.heard_at == first.heard_at, "a segunda escuta apagava a hora da primeira"


async def test_a_report_naming_no_round_of_this_session_marks_nothing(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    heard = await _heard(client, session.id, "2026-01-01T00:00:00Z")

    assert heard.status_code == 200, heard.text
    assert heard.json() == {"marked": False}
    assert [one.heard_at for one in (await stored_telling_back(db_session, session)).checks] == [
        None
    ], "uma marca que não é de rodada nenhuma dava o último veredito por ouvido"


async def test_a_report_from_another_projects_tablet_is_refused_and_marks_nothing(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email="owner@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger@example.com"
    )
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=owner.id)
    client.headers.update(team_headers(owner_credential))
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    refused = await _heard(
        client, session.id, pressed.json()["check_at"], **team_headers(stranger_credential)
    )

    assert refused.status_code == 404, refused.text
    assert [one.heard_at for one in (await stored_telling_back(db_session, session)).checks] == [
        None
    ], "o tablet de outro projeto dava o veredito desta equipe por ouvido"


ON_FRASE_3 = {
    "kind": "nuance",
    "note": "A parte ficou solta.",
    "frase": 3,
    "quote": "parte 2",
    "story": "a história diz qual parte",
}


def _handed(speaker: Speaker, brief: int = -1) -> list[int]:
    brief_text = speaker.briefs[brief].replace(CACHE_BREAK, "")
    handed = brief_text.split("## The findings for the whole passage\n\n", 1)[1]
    return [one["frase"] for one in json.loads(handed.split("\n\n`=== END", 1)[0])]


async def test_once_the_first_nuance_is_heard_the_next_press_names_the_next_one(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    report = await heard_every_part(db_session, session.id)
    analyst.readings = [{"findings": [ON_FRASE_3, ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    first = await press_terminei(client, session.id, report=report)
    await _heard(client, session.id, first.json()["check_at"])

    again = await press_terminei(client, session.id, report=report)

    assert again.status_code == 200, again.text
    assert [_handed(speaker, brief) for brief in range(len(speaker.briefs))] == [[2], [3]], (
        "depois de ouvir a nuance da frase 2, a próxima rodada repetia o veredito guardado"
    )


async def _frase_1_translated_again(db: AsyncSession, session: Any) -> None:
    stretch = (await final_segments(db, session.id))[0]
    await capture_segment(
        db,
        session,
        take_id=stretch.take_id,
        starts_ms=stretch.starts_ms,
        ends_ms=stretch.ends_ms,
        bridge_take_id="retro-de-novo",
        transcript="parte 0 traduzida outra vez",
        pass_number=2,
        replaces=stretch,
    )


async def test_a_nuance_whose_verdict_was_never_reported_heard_is_named_again(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}, {"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))
    await _frase_1_translated_again(db_session, session)

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    assert [_handed(speaker, brief) for brief in range(len(speaker.briefs))] == [[2], [2]], (
        "a equipe saiu enquanto o veredito tocava e a nuance nunca mais era dita"
    )


async def test_a_part_recorded_again_makes_its_said_nuance_sayable_even_in_the_same_words(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}, {"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    first = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await _heard(client, session.id, first.json()["check_at"])
    fresh = await record_the_part_again(db_session, session, parts[1], sha256="f" * 64)
    await tell_back_about(db_session, session, fresh, transcript="parte 1 contada de volta")

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    assert [_handed(speaker, brief) for brief in range(len(speaker.briefs))] == [[2], [2]], (
        "a parte foi gravada de novo e a nuance do áudio antigo calava a do novo"
    )


@asynccontextmanager
async def _the_same(db: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db


async def test_a_nuance_read_ahead_reaches_the_speaker_and_alone_still_confers(
    client, analyst, speaker, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _the_same(db_session))
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    await background.read_ahead(session_id=session.id)

    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    assert len(analyst.shown) == 1, "terminei leu de novo em vez de usar a leitura antecipada"
    assert _handed(speaker) == [2], (
        "a leitura antecipada jogava a nuance fora e o tablet nunca a ouvia"
    )
    answer = pressed.json()
    assert answer["checked"] is True, "uma nuance sozinha impedia a aprovação"
    assert answer["findings_remaining"] == 0, "a nuance entrava na conta dos achados em aberto"
    assert answer["findings"] == []


async def test_the_verdict_answer_names_the_nuance_it_named_and_a_replay_names_it_again(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    report = await heard_every_part(db_session, session.id)
    frase_2 = (await final_segments(db_session, session.id))[1]
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    first = await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    named = {"kind": "nuance", "frase": 2, "segment_id": frase_2.id}
    assert first.json()["named_nuance"] == named, (
        "o tablet não sabia qual frase o veredito nomeou e não tinha onde pôr a cor"
    )
    assert again.json()["named_nuance"] == named, "o veredito guardado voltava sem a sua nuance"


async def test_a_verdict_that_named_no_nuance_names_none_to_the_tablet(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_2]}]

    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )

    assert pressed.json()["named_nuance"] is None, (
        "a linha da frase ganhava a cor de uma nuance que a voz não disse"
    )


async def test_the_consultants_file_says_which_nuances_the_voice_already_said(
    client, analyst, speaker, db_session: AsyncSession
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [ON_FRASE_3, ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await _heard(client, session.id, pressed.json()["check_at"])

    read = await retroverification_file(db_session, await get_session(db_session, session.id))

    assert [(one.chunk, one.quote, one.story, one.said) for one in read.nuances] == [
        (2, "contada de volta", "a história conta de outro jeito", True),
        (3, "parte 2", "a história diz qual parte", False),
    ], "a consultora não via as nuances nem se a voz já as tinha dito"
