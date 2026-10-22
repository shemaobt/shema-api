"""A check redone over a capture that landed first does not confer the passage.

`terminei` reads the stretches that stand, then writes the exchange, then saves the check. A
frase captured in between lands first and leaves the passage unchecked and with no verdict,
and the check's save is refused for its stale read and redone on top. The redo carried the
check's own `checked` and verdict over the capture's, so the passage read as conferida over a
stretch the analyst never read, and the release stopped asking for a check.

The capture lands from a session of its own while the exchange is written, the way a frase
told on the other tablet would.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room import verdict_round
from app.services.internalization_room.back_translation import VoicedVerdict
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    release_blockers,
    room_client,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

PASSED = json.dumps({"verdict": "pass", "issues": []})


class Speaker:
    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return PASSED
        return "Vocês contaram bem."


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_check_redone_over_a_capture_that_landed_first_leaves_the_passage_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    told = await final_segments(db_session, session.id)
    state = back_translation_of(session)
    state.analysed_segment_ids = [stretch.id for stretch in told]
    state.verdict = VoicedVerdict(clip_key="clipe-0", fixed_line="A", used_fail_safe=True)
    await save_back_translation(db_session, session, state)
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

    async with rival_factory() as fresh_db:
        landed = await get_session(fresh_db, session.id)
        stored = back_translation_of(landed)
        assert (stored.checked, stored.verdict) == (False, None), (
            "a conferência refeita sobre a captura levava o seu checked e o seu veredito, e a "
            "passagem ficava conferida com uma frase que o analista nunca leu"
        )
        assert "telling_back_not_checked" in await release_blockers(fresh_db, landed), (
            "o lançamento deixava de pedir a conferência que a frase nova desfez"
        )
