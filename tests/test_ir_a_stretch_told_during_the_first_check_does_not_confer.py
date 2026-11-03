"""A stretch told while the first check of a never-analysed session is in flight does not confer.

The capture's uncheck returns at once on a session the analyst never read, so the stored
telling-back is unchanged when the stretch lands, and the verdict's save found the stored row
equal to the one it read and wrote itself as it was, `checked` and all, over a passage with a
stretch its `analysed_segment_ids` never named. Every later check round already lands unchecked
when a stretch is told during it; the first one did not.

The capture lands from a session of its own while the exchange is written, the way a frase told
on the other tablet would.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room import verdict_round
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import back_translation_of, get_session
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    release_blockers,
    release_packet,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

PASSED = json.dumps({"verdict": "pass", "issues": []})
SAID = "Vocês contaram bem."


class Speaker:
    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return PASSED
        return SAID


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_stretch_told_during_the_first_check_leaves_the_passage_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    told = await final_segments(db_session, session.id)
    report = await heard_every_part(db_session, session.id)
    written = verdict_round.append_exchange

    async def written_after_a_capture(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as capturing_db:
            capturing = await get_session(capturing_db, session.id)
            await capture_and_note_a_hard_stretch(
                capturing_db,
                capturing,
                take_id=told[-1].take_id,
                starts_ms=told[-1].ends_ms,
                ends_ms=told[-1].ends_ms + 1000,
                transcript="e Rute ficou com Noemi",
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_capture)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text
    assert pressed.json()["checked"] is False, (
        "a tablet que apertou terminei ouvia que a passagem estava conferida, quando a "
        "conferência que ela tinha acabado de fazer já tinha sido desfeita"
    )

    async with rival_factory() as fresh_db:
        landed = await get_session(fresh_db, session.id)
        stored = back_translation_of(landed)
        assert (stored.checked, stored.verdict) == (False, None), (
            "a primeira conferência gravava o seu checked por cima de uma frase contada durante "
            "ela, e a passagem ficava conferida com uma frase que o analista nunca leu"
        )
        assert [one.spoken for one in stored.checks] == [SAID], (
            "a rodada da primeira conferência não ficava guardada ao ser desfeita"
        )
        assert [one["text"] for one in landed.messages if one["role"] == "guide"] == [SAID], (
            "a conversa do veredito que chegou depois da frase contada não ficava guardada"
        )
        assert "telling_back_not_checked" in await release_blockers(fresh_db, landed), (
            "o lançamento deixava passar a passagem que a frase contada durante a conferência "
            "desfez"
        )


async def test_a_first_check_with_no_stretch_told_during_it_still_confers(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    report = await heard_every_part(db_session, session.id)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as fresh_db:
        landed = await get_session(fresh_db, session.id)
        stored = back_translation_of(landed)
        assert (stored.checked, stored.verdict is not None) == (True, True), (
            "uma primeira conferência em que ninguém contou nada de novo deixava a passagem "
            "sem conferir"
        )
        assert await release_packet(fresh_db, landed), (
            "o lançamento recusava uma passagem que a primeira conferência tinha conferido"
        )
