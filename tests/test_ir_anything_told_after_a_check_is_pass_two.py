from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.release import compose_internalization_release
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import back_translation_of, get_session
from app.services.internalization_room.takes import take_by_id
from tests.hard_stretch_harness import current
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    ScriptedAnalyst,
    nothing_is_read_ahead,
    played_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)

RETOLD = "Rute disse que iria aonde Noemi fosse."
TOLD_AGAIN = "told again after a verdict"


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def heard(*_: Any, **__: Any) -> str:
        return RETOLD

    monkeypatch.setattr(segments_api, "heard", heard)
    monkeypatch.setattr(bt_api, "heard", heard)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _checked(client: httpx.AsyncClient, db: AsyncSession) -> tuple[str, list[IRSegment]]:
    session, (part,) = await rehearsed_in_parts_of(db, [3])
    verdict = await press_terminei(client, session.id, report=played_every_part([part.id]))
    assert verdict.status_code == 200, verdict.text
    assert verdict.json()["checked"] is True
    return session.id, await final_segments(db, session.id)


async def _replaced(client: httpx.AsyncClient, session_id: str, stretch: IRSegment) -> None:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{stretch.id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": stretch.take_id,
            "starts_ms": str(stretch.starts_ms),
            "ends_ms": str(stretch.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase dois traduzida de novo", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


async def _told_on_a_new_slice(
    client: httpx.AsyncClient, session_id: str, beside: IRSegment
) -> None:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": beside.take_id,
            "starts_ms": str(beside.ends_ms),
            "ends_ms": str(beside.ends_ms + 1000),
        },
        files={"file": ("nova.m4a", b"uma frase nova depois da conferencia", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


def _line_of(reading: str, words: str) -> str:
    return next(line for line in reading.splitlines() if words in line)


async def test_a_frase_replaced_after_a_check_reaches_her_analyst_as_told_again(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    session_id, stretches = await _checked(client, db_session)

    await _replaced(client, session_id, stretches[1])
    again = await press_terminei(client, session_id)

    assert again.status_code == 200, again.text
    assert TOLD_AGAIN in _line_of(analyst.shown[-1], RETOLD), (
        "a frase traduzida de novo pelo /replace chegava à analista como primeira passada"
    )
    assert TOLD_AGAIN not in _line_of(analyst.shown[-1], "a frase 1, contada de volta")


async def test_the_recording_of_a_frase_replaced_after_a_check_is_kept_as_the_second_pass(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    session_id, stretches = await _checked(client, db_session)

    await _replaced(client, session_id, stretches[1])

    replaced = next(
        one for one in await current(db_session, session_id) if one.transcript == RETOLD
    )
    assert replaced.bridge_take_id is not None
    recording = await take_by_id(db_session, replaced.bridge_take_id)
    assert recording.pass_number == 2, (
        "a gravação da frase traduzida de novo ficava na primeira passada, e o texto na segunda"
    )


async def test_a_frase_replaced_after_a_clean_check_refuses_approval_until_a_new_check(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    session_id, stretches = await _checked(client, db_session)

    await _replaced(client, session_id, stretches[1])

    session = await get_session(db_session, session_id)
    _artifact, blockers = await compose_internalization_release(db_session, session)
    assert "telling_back_not_checked" in blockers, (
        "a aprovação passava pela rodada limpa de antes da frase traduzida de novo"
    )
    assert back_translation_of(session).verdict is None


async def test_a_new_frase_told_after_a_check_reaches_her_analyst_as_told_again(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    session_id, stretches = await _checked(client, db_session)

    await _told_on_a_new_slice(client, session_id, stretches[-1])
    again = await press_terminei(client, session_id)

    assert again.status_code == 200, again.text
    assert TOLD_AGAIN in _line_of(analyst.shown[-1], RETOLD), (
        "uma frase nova contada depois da conferência chegava à analista como primeira passada"
    )


async def test_a_new_frase_told_after_a_clean_check_refuses_approval_until_a_new_check(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    session_id, stretches = await _checked(client, db_session)

    await _told_on_a_new_slice(client, session_id, stretches[-1])

    session = await get_session(db_session, session_id)
    _artifact, blockers = await compose_internalization_release(db_session, session)
    assert "telling_back_not_checked" in blockers, (
        "a aprovação passava pela rodada limpa de antes da frase nova"
    )
    assert back_translation_of(session).verdict is None
