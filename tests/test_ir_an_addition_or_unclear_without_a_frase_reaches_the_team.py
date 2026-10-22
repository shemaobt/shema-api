from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.back_translation import (
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


async def test_an_addition_and_an_unclear_with_no_readable_frase_reach_the_team_unnumbered(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [_the_reply_with_two_unreadable_frases()]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["finding_kind"] == FindingKind.ADDITION.value, (
        "o acréscimo sem frase legível era jogado fora e a falta falava no lugar dele"
    )
    assert body["finding_segment_id"] is None
    assert body["findings_remaining"] == 3
    assert body["checked"] is False


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


async def test_a_reply_whose_every_finding_names_no_readable_frase_is_still_read(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [
        {
            "findings": [
                {"kind": "addition", "note": ADDITION_WITH_NO_FRASE},
                {"kind": "unclear", "note": UNCLEAR_OUT_OF_RANGE, "chunk": 0},
            ]
        }
    ]

    answered = await _finish(client, db_session, session.id)

    assert answered.status_code == 200, (
        "uma resposta cujos achados não tinham frase legível era recusada como ilegível"
    )
    body = answered.json()
    assert body["finding_kind"] == FindingKind.ADDITION.value
    assert body["findings_remaining"] == 2
    assert body["checked"] is False


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


async def test_the_retroverification_file_lists_what_named_no_readable_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [_the_reply_with_two_unreadable_frases()]

    await _finish(client, db_session, session.id)

    file = await retroverification_file(db_session, await get_session(db_session, session.id))

    assert [finding.kind for finding in file.findings] == [
        FindingKind.ADDITION.value,
        FindingKind.UNCLEAR.value,
        FindingKind.MISSING.value,
    ], "o arquivo do consultor perdia o que o analista disse sem número de frase"
    dumped = file.model_dump_json()
    assert ADDITION_WITH_NO_FRASE in dumped
    assert UNCLEAR_OUT_OF_RANGE in dumped
