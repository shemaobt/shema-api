from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.services.internalization_room import verdict_round
from app.services.internalization_room.back_translation import VoicedVerdict
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from app.services.internalization_room.takes import declared_parts_by_key
from tests.text_seam_harness import (
    RUNNER_KEY,
    Analyst,
    Speaker,
    the_analyst_reads,
    the_app,
    the_speaker_says,
)

SEAM = "/api/internalization-room/text-seam/back-translation"
FRASE = {
    "clipKey": "S1",
    "coversFrom": 0,
    "coversTo": 20,
    "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo e voltou.",
}


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    return the_speaker_says(monkeypatch)


@pytest.fixture()
async def client(
    db_session: AsyncSession, analyst: Analyst, speaker: Speaker, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


async def test_a_round_the_merge_stores_unchecked_after_a_stretch_was_told_answers_not_conferida(
    client: httpx.AsyncClient,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = await client.post(
        f"{SEAM}/session",
        json={
            "pericopeId": "P02",
            "language": "Brazilian Portuguese",
            "clips": [{"key": "S1", "durationMs": 30000}],
        },
    )
    session_id = str(declared.json()["sessionId"])
    written = verdict_round.append_exchange

    async def written_after_a_stretch_was_told(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as telling_db:
            telling = await get_session(telling_db, session_id)
            checked = back_translation_of(telling)
            checked.analysed_segment_ids = ["a-conferencia-da-outra-tablet"]
            checked.checked = True
            checked.verdict = VoicedVerdict(clip_key="clipe-da-outra-tablet")
            await save_back_translation(telling_db, telling, checked)
            part = (await declared_parts_by_key(telling_db, session_id))["S1"]
            await capture_and_note_a_hard_stretch(
                telling_db,
                await get_session(telling_db, session_id),
                take_id=part.id,
                starts_ms=20000,
                ends_ms=21000,
                transcript="uma frase contada durante a conferência",
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_stretch_was_told)

    played = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": [FRASE]})
    assert played.status_code == 200, played.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session_id))
    assert stored.checked is False
    assert played.json()["conferida"] is False, (
        "a rodada que o merge guardou sem conferir, por causa de uma frase contada, respondia "
        "conferida verdadeira ao runner"
    )
