"""ENG-1197 — `terminei` reaches the check only on her conditions, and refuses in her order.

Her check (bt/check/route.ts:64-78 at her freeze) refuses a frase awaiting its translation
first, then a part not yet heard, then, on a joined recording, a stretch nothing translates,
and last a passage with nothing translated at all. Each refusal is a code the tablet turns into
her screen line; none of them asks the analyst or saves anything.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSession, IRTake
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.sessions import create_session, get_session
from tests.device_harness import TABLET_TEAM
from tests.release_harness import PREFIX, P
from tests.room_harness import (
    PLAYBACK_BLOCKER,
    Analyst,
    Room,
    a_piece_still_to_be_told,
    another_rehearsal_take,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    release_blockers,
    release_packet,
    room_client,
    stored_telling_back,
    stretch_on,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

#: Her P-unheard line, from her file at the freeze (prompts/fail_safe_utterances.md:111),
#: and its name by position: her P steps are start, tell, unheard, approved.
UNHEARD_LINE = "Ainda falta ouvir um trecho da gravação antes de eu conferir."
UNHEARD_BY_POSITION = "P2"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _recorded_and_never_translated(
    db: AsyncSession, parts: int
) -> tuple[IRSession, list[IRTake]]:
    session = await create_session(db, pericope=P, project_id=TABLET_TEAM, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await db.commit()
    takes = [
        await another_rehearsal_take(
            db,
            session,
            sha256=chr(ord("a") + index) * 64,
            scope=f"parte-{index + 1}",
            ordinal=index + 1,
        )
        for index in range(parts)
    ]
    return session, takes


async def _transcript(db: AsyncSession, session_id: str) -> list[Any]:
    return list((await get_session(db, session_id)).messages or [])


@pytest.mark.parametrize("recorded", [0, 2], ids=["nothing recorded", "two parts recorded"])
async def test_a_recording_heard_through_with_no_frase_translated_is_refused_in_silence(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst, room: Room, recorded: int
) -> None:
    session, parts = await _recorded_and_never_translated(db_session, recorded)
    was = await stored_telling_back(db_session, session)

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "NOTHING_TRANSLATED"
    assert body["checked"] is False
    assert body["audio_url"] == "", "ela só mostra «ainda não tem frase traduzida», sem voz"
    assert body["fixed_line"] == "", "o D-1 dizia que a sala não ouviu, e nada foi dito"
    assert room.said == []
    assert analyst.readings == 0
    assert await _transcript(db_session, session.id) == []
    assert (await stored_telling_back(db_session, session)).waited == was.waited


async def test_a_part_heard_with_nothing_translated_over_it_is_read_with_the_rest_not_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    fresh = await record_the_part_again(db_session, session, second, sha256="d" * 64)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] is None
    assert analyst.readings == 1, "nela a checagem roda e o Analista nomeia o que falta"
    assert body["audio_url"] != ""


async def test_a_part_never_played_is_refused_as_unheard_before_nothing_translated(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second) = await _recorded_and_never_translated(db_session, 2)

    answered = await press_terminei(client, session.id, report=played_every_part([first.id]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "PART_UNHEARD", "ela recusa o que não foi ouvido antes do vazio"
    assert body["unheard_take_ids"] == [second.id]
    assert analyst.readings == 0


async def test_a_part_with_nothing_translated_over_it_still_has_to_be_heard(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    fresh = await record_the_part_again(db_session, session, second, sha256="d" * 64)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "PART_UNHEARD"
    assert body["unheard_take_ids"] == [fresh.id]
    assert analyst.readings == 0, "o Analista leria uma passagem com uma parte nunca ouvida"


async def test_the_unheard_refusal_names_her_line_by_position_and_synthesizes_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession, room: Room
) -> None:
    session, (first, _second, third) = await rehearsed_in_parts(db_session, 3)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["fixed_line"] == UNHEARD_BY_POSITION
    assert body["audio_url"] == ""
    assert room.said == [], "a linha era sintetizada no terminei, fora da porta das falas dela"

    line = await client.get(f"{PREFIX}/fixed-lines/{body['fixed_line']}", params={"language": "pt"})

    assert line.status_code == 200, line.text
    assert room.said == [UNHEARD_LINE]


async def test_a_frase_awaiting_its_translation_is_refused_first_and_no_h_line_is_said(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst, room: Room
) -> None:
    session, (first, second) = await rehearsed_in_parts(db_session, 2)
    piece = await a_piece_still_to_be_told(
        db_session, session, await stretch_on(db_session, session, second)
    )
    was = await stored_telling_back(db_session, session)

    answered = await press_terminei(client, session.id, report=played_every_part([first.id]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "FRASE_AWAITING", "a frase que espera vem antes da parte não ouvida"
    assert body["untold_segment_id"] == piece.id
    assert body["unheard_take_ids"] == []
    assert body["audio_url"] == ""
    assert body["fixed_line"] == ""
    assert room.said == [], "as falas H não são dela e nunca são ditas"
    assert analyst.readings == 0
    assert (await stored_telling_back(db_session, session)).waited == was.waited


async def test_a_part_recorded_again_heard_and_checked_releases_with_nothing_told_over_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    fresh = await record_the_part_again(db_session, session, second, sha256="d" * 64)
    checked = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id, third.id])
    )
    assert checked.json()["checked"] is True, checked.text

    packet = await release_packet(db_session, session)

    assert packet["back_translation"]["checked"] is True, (
        "ela aprova sem barrar a parte não contada"
    )


async def test_a_part_recorded_again_and_never_played_blocks_the_release_as_unheard(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    await record_the_part_again(db_session, session, second, sha256="d" * 64)
    refused = await press_terminei(
        client, session.id, report=played_every_part([first.id, third.id])
    )
    assert refused.json()["refusal"] == "PART_UNHEARD", refused.text

    blockers = await release_blockers(db_session, session)

    assert "untold_part" not in blockers
    assert PLAYBACK_BLOCKER in blockers, "uma parte que ninguém ouviu viajava sem bloqueio"


async def _down(*_: Any, **__: Any) -> Any:
    raise UpstreamServiceError("o provedor não respondeu")


def _the_analyst_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_agent_is(monkeypatch, analyst=_down)


def _the_speaker_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_agent_is(monkeypatch, turn=_down)


def _the_voice_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.internalization_room import back_translation as bt_api

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _down)


@pytest.mark.parametrize(
    "take_it_down",
    [_the_analyst_is_down, _the_speaker_is_down, _the_voice_is_down],
    ids=["analyst", "speaker", "voice"],
)
async def test_a_check_whose_model_is_down_saves_nothing_and_terminei_again_retries(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    take_it_down: Any,
) -> None:
    session, parts = await rehearsed_in_parts(db_session, 2)
    report = played_every_part([part.id for part in parts])
    was = await stored_telling_back(db_session, session)
    take_it_down(monkeypatch)

    refused = await press_terminei(client, session.id, report=report)

    assert refused.status_code == 200, "um 502 o tablet lê como sem conexão"
    body = refused.json()
    assert body["refusal"] == "CHECK_UNAVAILABLE"
    assert body["checked"] is False
    assert body["audio_url"] == ""
    assert body["fixed_line"] == ""
    assert await _transcript(db_session, session.id) == []
    kept = await stored_telling_back(db_session, session)
    assert kept.checks == was.checks
    assert kept.analysed_segment_ids == was.analysed_segment_ids
    assert kept.verdict is None

    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    again = await press_terminei(client, session.id, report=report)

    assert again.json()["refusal"] is None, again.text
    assert again.json()["checked"] is True
