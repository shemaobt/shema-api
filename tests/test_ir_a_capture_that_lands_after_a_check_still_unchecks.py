"""ENG-1412 — a frase told while a check lands still un-checks the passage it changed.

The chunks door reads the telling-back state, then waits on the transcriber, then captures.
A capture after a check undoes what the check left, and it decided that on the state it read
— so a check that passed during the transcription was seen by the capture's redo as a field
the capture had not touched, and the passage stood checked with a stretch the analyst never
read, which is all the release gate asks.

The check lands from a session of its own while the transcriber is still working, the way a
`terminei` from the other tablet would.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSegment, IRSession
from app.services.internalization_room.back_translation import VoicedVerdict
from app.services.internalization_room.release import compose_internalization_release
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_frase_told_while_a_check_passes_leaves_the_passage_unchecked_not_checked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [2])
    told = await final_segments(db_session, session.id)

    async def heard_while_a_check_passes(*_: Any, **__: Any) -> str:
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            state = back_translation_of(checking)
            state.checked = True
            state.analysed_segment_ids = [stretch.id for stretch in told]
            await save_back_translation(checking_db, checking, state)
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(bt_api, "heard", heard_while_a_check_passes)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": part.id,
            "starts_ms": str(told[-1].ends_ms),
            "ends_ms": str(told[-1].ends_ms + 1000),
        },
        files={"file": ("nova.m4a", b"uma frase nova durante a conferencia", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text

    async with rival_factory() as fresh_db:
        stored = back_translation_of(await get_session(fresh_db, session.id))
    assert stored.checked is False, (
        "a captura refeita sobre a conferência que passou mantinha o checked, e a passagem "
        "ficava conferida com uma frase que o analista nunca leu"
    )


async def _a_frase_told_beside(client, session_id: str, beside: IRSegment) -> None:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": beside.take_id,
            "starts_ms": str(beside.ends_ms),
            "ends_ms": str(beside.ends_ms + 1000),
        },
        files={"file": ("nova.m4a", b"uma frase nova antes de conferir", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text


async def test_a_frase_corrected_while_a_clean_check_lands_is_unchecked_not_approved(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [2])

    async def heard(*_: Any, **__: Any) -> str:
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(bt_api, "heard", heard)
    await _a_frase_told_beside(
        client, session.id, (await final_segments(db_session, session.id))[-1]
    )
    told = await final_segments(db_session, session.id)

    async def heard_while_a_clean_check_lands(*_: Any, **__: Any) -> str:
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            state = back_translation_of(checking)
            state.checked = True
            state.analysed_segment_ids = [stretch.id for stretch in told]
            state.verdict = VoicedVerdict(clip_key="clipe-da-conferencia")
            await save_back_translation(checking_db, checking, state)
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(segments_api, "heard", heard_while_a_clean_check_lands)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[-1].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": told[-1].take_id,
            "starts_ms": str(told[-1].starts_ms),
            "ends_ms": str(told[-1].ends_ms),
        },
        files={
            "file": ("de-novo.m4a", b"a frase dois corrigida durante a conferencia", "audio/mp4")
        },
    )
    assert answered.status_code == 200, answered.text

    async with rival_factory() as fresh_db:
        corrected = await get_session(fresh_db, session.id)
        stored = back_translation_of(corrected)
        _artifact, blockers = await compose_internalization_release(fresh_db, corrected)
    assert stored.checked is False, (
        "a correção lida como nunca analisada não salvava nada, e a passagem ficava conferida "
        "com uma frase que o analista nunca leu"
    )
    assert stored.verdict is None, (
        "o veredito da conferência que nunca ouviu a frase corrigida ficava guardado"
    )
    assert "telling_back_not_checked" in blockers, (
        "a aprovação passava pela conferência limpa que caiu durante a transcrição"
    )


async def test_a_frase_corrected_with_no_check_anywhere_writes_no_verdict_and_stays_unread(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [2])
    told = await final_segments(db_session, session.id)

    async def heard(*_: Any, **__: Any) -> str:
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(segments_api, "heard", heard)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[-1].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": told[-1].take_id,
            "starts_ms": str(told[-1].starts_ms),
            "ends_ms": str(told[-1].ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase dois corrigida sem conferencia", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text

    async with rival_factory() as fresh_db:
        corrected = await get_session(fresh_db, session.id)
        stored = back_translation_of(corrected)
        _artifact, blockers = await compose_internalization_release(fresh_db, corrected)
    assert stored.verdict is None, "a correção sem conferência alguma escrevia um veredito"
    assert "telling_back_never_analysed" in blockers, (
        "a correção sem conferência alguma deixava a passagem como lida pelo analista"
    )


async def test_a_frase_corrected_on_a_passage_never_checked_leaves_the_session_row_untouched(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [2])
    told = await final_segments(db_session, session.id)

    async def heard(*_: Any, **__: Any) -> str:
        return "e Rute ficou com Noemi"

    monkeypatch.setattr(segments_api, "heard", heard)
    monkeypatch.setattr(bt_api, "heard", heard)

    await _a_frase_told_beside(client, session.id, told[-1])
    last_active = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    async with rival_factory() as setup:
        await setup.execute(
            update(IRSession).where(IRSession.id == session.id).values(updated_at=last_active)
        )
        await setup.commit()
        before = await get_session(setup, session.id)
    assert back_translation_of(before).never_analysed

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[0].id}/replace",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": told[0].take_id,
            "starts_ms": str(told[0].starts_ms),
            "ends_ms": str(told[0].ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a frase um corrigida sem conferencia", "audio/mp4")},
    )
    assert answered.status_code == 200, answered.text

    async with rival_factory() as after_db:
        after = await get_session(after_db, session.id)
    assert after.updated_at == last_active, (
        "a correção sem conferência regravava o mesmo estado e movia o updated_at da sessão"
    )
    assert after.version == before.version
