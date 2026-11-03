from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSegment
from app.services.internalization_room import verdict_round
from app.services.internalization_room.back_translation import (
    CheckRound,
    VoicedVerdict,
)
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sentences import lay_in_a_sentence
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
    start_the_translation_over,
)
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    PART_MS,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import rehearsed_in_wav, spoken
from tests.turn_harness import the_speaker_answers

SAID = "Vocês contaram bem."


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_verdict_the_merge_stores_unchecked_after_a_lay_in_answers_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_speaker_answers(monkeypatch, SAID)
    session, _, ((frase, _other),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    report = await heard_every_part(db_session, session.id, duration_ms=2000)
    written = verdict_round.append_exchange

    async def written_after_a_sentence_was_laid_in(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as laying_db:
            await lay_in_a_sentence(
                laying_db,
                await get_session(laying_db, session.id),
                await laying_db.get(IRSegment, frase.id),
                sentence_id="sentence-0001",
                audio=spoken(1.0),
                device_id="tablet-da-equipe",
                store=store,
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_sentence_was_laid_in)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.checked is False
    assert pressed.json()["checked"] is False, (
        "o veredito que o merge guardou sem conferir respondia checked verdadeiro, e a tablet "
        "oferecia o rascunho final que o servidor recusa"
    )


async def test_a_verdict_the_merge_stores_unchecked_after_a_restart_answers_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_speaker_answers(monkeypatch, SAID)
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _ = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    report = await heard_every_part(db_session, session.id)
    written = verdict_round.append_exchange

    async def written_after_a_restart(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as restarting_db:
            await start_the_translation_over(
                restarting_db, await get_session(restarting_db, session.id)
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_restart)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.checked is False
    assert pressed.json()["checked"] is False, (
        "o veredito que leu antes do recomeço e o merge guardou sem conferir respondia checked "
        "verdadeiro, e a tablet oferecia o rascunho final que o servidor recusa"
    )


async def test_a_verdict_the_merge_stores_unchecked_after_a_stretch_was_told_answers_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_speaker_answers(monkeypatch, SAID)
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, (part, _other) = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    told = await final_segments(db_session, session.id)
    state = back_translation_of(session)
    state.analysed_segment_ids = [stretch.id for stretch in told]
    state.verdict = VoicedVerdict(clip_key="clipe-0", fixed_line="A", used_fail_safe=True)
    await save_back_translation(db_session, session, state)
    report = await heard_every_part(db_session, session.id)
    written = verdict_round.append_exchange

    async def written_after_a_stretch_was_told(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as telling_db:
            await capture_and_note_a_hard_stretch(
                telling_db,
                await get_session(telling_db, session.id),
                take_id=part.id,
                starts_ms=PART_MS,
                ends_ms=PART_MS + 1000,
                bridge_take_id="retro-novo",
                transcript="uma frase contada durante a conferência",
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_stretch_was_told)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.checked is False
    assert pressed.json()["checked"] is False, (
        "o veredito que leu antes da frase contada e o merge guardou sem conferir respondia "
        "checked verdadeiro, e a tablet oferecia o rascunho final que o servidor recusa"
    )


async def test_a_finding_the_voice_said_is_still_answered_when_a_fresh_check_stands_after_a_restart(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    analyst.readings = [{"findings": [{"kind": "missing", "note": "Orfa não apareceu."}]}]
    the_room_speaks(monkeypatch)
    the_speaker_answers(monkeypatch, SAID)
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _ = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    report = await heard_every_part(db_session, session.id)
    fresh_at = datetime(2026, 10, 12, 22, 0, tzinfo=UTC)
    fresh_round = CheckRound(
        at=fresh_at, findings=[], spoken="Contaram bem.", outcome="pass", conferida=True
    )
    written = verdict_round.append_exchange

    async def written_after_a_restart_and_a_clean_check(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as restarting_db:
            await start_the_translation_over(
                restarting_db, await get_session(restarting_db, session.id)
            )
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            fresh = back_translation_of(checking)
            fresh.checks = [fresh_round]
            fresh.checked_at = fresh_at
            fresh.checked = True
            fresh.verdict = VoicedVerdict(clip_key="clipe-depois-do-recomeço")
            fresh.analysed_segment_ids = ["a-frase-contada-depois-do-recomeço"]
            await save_back_translation(checking_db, checking, fresh)
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_restart_and_a_clean_check)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.checked is True
    assert pressed.json()["checked"] is False, (
        "a voz da rodada velha dizia o que faltou e a resposta dizia conferida"
    )
