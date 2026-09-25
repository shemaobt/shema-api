"""ENG-1145 — an addition or an unclear that names no readable frase is not raised.

Marcia's rule ties every finding to the **Chunk** it names. A missing element still lands
without one — the story simply has not been told that far, and the team is sent back to the
rehearsal for it. An addition or an unclear naming no chunk at all, or one outside the reading
the analyst was given, names nothing the team can act on: it is dropped with a log line, the
way the retired evidence kind already is, and the rest of the reply is still read.

Henok decided on 2026-09-25 that only the no-stretch branch of `closing_block` retires: an
**unclear** the analyst still manages to land on a stretch keeps `CLOSING_SPOKEN`, because the
boundary question it asks is unaffected by this rule. `points_at_a_stretch` already excludes
`unclear` from the two-microphones screen, and that stays.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.back_translation import (
    CLOSING_MISSING_TO_REHEARSAL,
    CLOSING_ON_SCREEN,
    CLOSING_SPOKEN,
    FindingKind,
)
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import get_session
from tests.room_harness import (
    Room,
    ScriptedAnalyst,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)

PARSER_LOGGER = "app.services.internalization_room.back_translation"

ADDITION_WITH_NO_FRASE = "Rute foi junto (o analista não deu o número da frase)"
UNCLEAR_OUT_OF_RANGE = "não deu para ouvir (o analista apontou uma frase que não existe)"


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _finish(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> httpx.Response:
    return await press_terminei(client, session_id, report=await heard_every_part(db, session_id))


def _missing(chunk: int, *, where: str, note: str = "o fim da história") -> dict[str, Any]:
    return {"kind": "missing", "note": note, "chunk": chunk, "where": where}


def _the_reply_with_two_unreadable_frases() -> dict[str, Any]:
    return {
        "findings": [
            {"kind": "addition", "note": ADDITION_WITH_NO_FRASE},
            {"kind": "unclear", "note": UNCLEAR_OUT_OF_RANGE, "chunk": 99},
            _missing(3, where="after"),
        ]
    }


async def test_an_addition_and_an_unclear_with_no_readable_frase_are_dropped(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T1, the ticket's test. Only the missing reaches the tablet, and the log names the rest.

    Three stretches told, an addition naming no frase, an unclear naming frase 99 (there are
    only three), and a missing after the last one. Both unreadable findings are dropped; the
    missing is the only one the verdict carries, and it closes on the speech that sends the
    team back to the rehearsal rather than one of the two-microphone screens.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [_the_reply_with_two_unreadable_frases()]

    with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
        answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["finding_kind"] == FindingKind.MISSING.value
    assert body["finding_segment_id"] is None, "sem frase legível, a falta não tem endereço"
    assert body["findings_remaining"] == 1
    assert body["checked"] is False

    brief = room.briefs[-1]
    assert CLOSING_MISSING_TO_REHEARSAL in brief
    assert CLOSING_SPOKEN not in brief
    assert CLOSING_ON_SCREEN.format(session_language="Portuguese") not in brief

    assert (
        f"named addition with no readable frase (note: {ADDITION_WITH_NO_FRASE})" in caplog.text
    ), "a linha do próprio log nomeia o tipo e traz a nota, antes de ecoar a resposta bruta"
    assert f"named unclear with no readable frase (note: {UNCLEAR_OUT_OF_RANGE})" in caplog.text


async def test_an_addition_naming_its_frase_still_answers_on_its_stretch(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """T2. A readable frase is untouched by the drop rule."""
    session, _parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 2}]}]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["finding_kind"] == FindingKind.ADDITION.value
    assert body["finding_segment_id"] == told[1].id
    assert body["findings_remaining"] == 1
    assert body["checked"] is False


async def test_a_reply_that_drops_every_finding_it_named_is_refused(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """T5. Henok's decision on send-back 1: a reply reduced to nothing confers nothing.

    An addition naming no frase and an unclear naming frase 0 (out of range): both are
    dropped, and nothing else was named, so the reply is unusable — refused the way a
    malformed reply is, never read as the clean telling-back that blesses the passage. Without
    this rule `[addition no chunk, unclear chunk 0]` came back `checked: true`.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    unusable_reply = {
        "findings": [
            {"kind": "addition", "note": ADDITION_WITH_NO_FRASE},
            {"kind": "unclear", "note": UNCLEAR_OUT_OF_RANGE, "chunk": 0},
        ]
    }
    analyst.readings = [unusable_reply, unusable_reply]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 502, answered.text
    assert answered.json()["code"] == "UNREADABLE_REPLY"
    assert room.briefs == [], "sem leitura utilizável não há veredito: o Falante não é chamado"

    again = await _finish(client, db_session, session.id)
    assert again.status_code == 502, "nada foi salvo: o próximo terminei pergunta de novo"
    assert analyst.readings == [], "as duas leituras consumiram a fila do analista"


async def test_a_reply_naming_no_finding_at_all_still_confers(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """Control for T5: a reply that never named a finding is still the clean reading it was."""
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": []}]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["checked"] is True


async def test_the_retroverification_file_lists_none_of_what_was_dropped(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    """T4. What the room dropped reaches neither the tablet nor the consultant's file."""
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [_the_reply_with_two_unreadable_frases()]

    await _finish(client, db_session, session.id)

    file = await retroverification_file(db_session, await get_session(db_session, session.id))

    assert [finding.kind for finding in file.findings] == [FindingKind.MISSING.value]
    dumped = file.model_dump_json()
    assert ADDITION_WITH_NO_FRASE not in dumped
    assert UNCLEAR_OUT_OF_RANGE not in dumped
