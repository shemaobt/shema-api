from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import (
    CheckRound,
    Finding,
    FindingKind,
    Nuance,
    VoicedVerdict,
)
from app.services.internalization_room.release import compose_internalization_release
from app.services.internalization_room.segments import (
    capture_segment,
    final_segments,
    retired_segments,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
    start_the_translation_over,
)
from app.services.internalization_room.takes import current_parts, takes_of
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import (
    PLAYBACK_BLOCKER,
    nothing_is_read_ahead,
    rehearsed_in_parts_of,
    release_blockers,
    room_client,
    stored_telling_back,
    the_bucket_is_in_memory,
)

PART_LENGTH_MS = 2000


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _told_and_heard(db: AsyncSession) -> tuple[IRSession, list[IRTake]]:
    session, parts = await rehearsed_in_parts_of(db, [2, 2])
    state = back_translation_of(session)
    state.played_by_take = [
        PlayedTake(
            take_id=part.id, played_ranges=[(0, PART_LENGTH_MS)], clip_duration_ms=PART_LENGTH_MS
        )
        for part in parts
    ]
    await save_back_translation(db, session, state)
    return session, parts


async def _checked_once(db: AsyncSession, session: IRSession) -> tuple[Finding, CheckRound]:
    told = await final_segments(db, session.id)
    finding = Finding(kind=FindingKind.MISSING, note="faltou Moabe", segment_id=told[0].id, chunk=1)
    nuance = Nuance(
        note="tornou, não voltou",
        chunk=2,
        segment_id=told[1].id,
        quote="voltou",
        story="tornou",
        take_id=told[1].take_id,
        starts_ms=told[1].starts_ms,
        ends_ms=told[1].ends_ms,
        voiced="now",
    )
    checked = CheckRound(
        at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        findings=[finding],
        spoken="No que vocês me traduziram, não ouvi Moabe.",
        outcome="pass",
        conferida=False,
        nuances=[nuance],
        heard_at=datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
    )
    state = back_translation_of(session)
    state.findings = [finding]
    state.nuances = [nuance]
    state.checks = [checked]
    state.checked = True
    state.checked_at = checked.at
    state.verdict = VoicedVerdict(clip_key="clipe-do-veredito")
    state.analysed_segment_ids = [one.id for one in told]
    await save_back_translation(db, session, state)
    return finding, checked


async def _restart(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(f"{PREFIX}/sessions/{session_id}/back-translation/restart")


async def test_every_frase_leaves_the_reading_and_stays_kept_as_a_retired_row(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _told_and_heard(db_session)
    told = [one.id for one in await final_segments(db_session, session.id)]

    restarted = await _restart(client, session.id)

    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["segments"] == [], "as frases traduzidas continuavam na tela"
    assert await final_segments(db_session, session.id) == []
    assert sorted(one.id for one in await retired_segments(db_session, session.id)) == sorted(
        told
    ), "as quatro frases traduzidas eram apagadas em vez de guardadas"


async def test_the_findings_and_the_kept_rounds_are_archived_and_the_record_starts_with_no_check(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _told_and_heard(db_session)
    finding, checked = await _checked_once(db_session, session)

    restarted = await _restart(client, session.id)

    assert restarted.status_code == 200, restarted.text
    stored = await stored_telling_back(db_session, session)
    assert stored.superseded[-1].findings == [finding], "o achado da conferência era apagado"
    assert stored.superseded[-1].checks == [checked], (
        "a rodada guardada, com o detalhe e a hora em que foi ouvido, era apagada"
    )
    assert (stored.findings, stored.nuances, stored.checks) == ([], [], []), (
        "a passagem recomeçada ainda carregava a conferência de antes"
    )
    assert (stored.checked, stored.checked_at, stored.verdict, stored.analysed_segment_ids) == (
        False,
        None,
        None,
        None,
    ), "a passagem recomeçada ainda estava conferida"


async def test_the_recording_and_the_full_listen_stay_so_the_passage_told_again_is_not_heard_again(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _told_and_heard(db_session)

    restarted = await _restart(client, session.id)
    assert restarted.status_code == 200, restarted.text
    for part in parts:
        await capture_segment(
            db_session,
            await get_session(db_session, session.id),
            take_id=part.id,
            starts_ms=0,
            ends_ms=PART_LENGTH_MS,
            bridge_take_id=f"de-novo-{part.ordinal}",
            transcript="a parte contada de novo",
        )

    assert [one.id for one in current_parts(await takes_of(db_session, session.id))] == [
        part.id for part in parts
    ], "o recomeço levava a gravação junto"
    assert PLAYBACK_BLOCKER not in await release_blockers(db_session, session), (
        "a escuta inteira da equipe era pedida de novo depois do recomeço"
    )


async def test_the_first_frase_told_after_a_restart_is_frase_one(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _told_and_heard(db_session)

    restarted = await _restart(client, session.id)
    assert restarted.status_code == 200, restarted.text
    first = await capture_segment(
        db_session,
        await get_session(db_session, session.id),
        take_id=parts[1].id,
        starts_ms=0,
        ends_ms=1000,
        bridge_take_id="de-novo",
        transcript="a primeira frase de novo",
    )

    assert first.ordinal == 1, "a frase nova continuava a contagem de antes"
    assert [one.id for one in await final_segments(db_session, session.id)] == [first.id], (
        "a frase nova não era a frase 1 da passagem"
    )


async def test_a_restart_redone_over_a_check_that_landed_first_leaves_no_check_and_keeps_its_round(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session, _ = await _told_and_heard(db_session)
    landed_finding = Finding(kind=FindingKind.ADDITION, note="acrescentou o campo", chunk=3)
    landed_round = CheckRound(
        at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
        findings=[landed_finding],
        spoken="Vocês falaram do campo; isso está na história?",
        outcome="pass",
        conferida=False,
    )
    async with rival_factory() as checking_db, rival_factory() as restarting_db:
        checking = await get_session(checking_db, session.id)
        restarting = await get_session(restarting_db, session.id)
        landed = back_translation_of(checking)
        landed.findings.append(landed_finding)
        landed.checks.append(landed_round)
        landed.checked = True
        landed.verdict = VoicedVerdict(clip_key="clipe-conferida")
        await save_back_translation(checking_db, checking, landed)

        await start_the_translation_over(restarting_db, restarting)

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert (stored.findings, stored.checks, stored.checked, stored.verdict) == (
        [],
        [],
        False,
        None,
    ), "a conferência que chegou primeiro voltava por cima do recomeço"
    assert stored.superseded[-1].findings == [landed_finding], (
        "o achado que chegou primeiro sumia em vez de ficar guardado"
    )
    assert stored.superseded[-1].checks == [landed_round], (
        "a rodada que chegou primeiro sumia em vez de ficar guardada"
    )


async def test_a_restart_whose_record_cannot_be_written_leaves_every_frase_where_it_was(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.internalization_room import sessions as sessions_service

    session, _ = await _told_and_heard(db_session)
    session_id = session.id
    told = [one.id for one in await final_segments(db_session, session_id)]

    async def refused(*_: object, **__: object) -> None:
        raise ConflictError("the record moved under every try")

    monkeypatch.setattr(sessions_service, "save_back_translation", refused)
    with pytest.raises(ConflictError):
        await start_the_translation_over(db_session, session)
    await db_session.rollback()

    assert [one.id for one in await final_segments(db_session, session_id)] == told, (
        "as frases saíam da leitura e a conferência de antes ficava de pé"
    )


async def test_the_packet_after_a_restart_carries_the_archived_findings_and_none_of_the_rounds(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _told_and_heard(db_session)
    await _checked_once(db_session, session)

    restarted = await _restart(client, session.id)
    assert restarted.status_code == 200, restarted.text
    packet, _ = await compose_internalization_release(
        db_session, await get_session(db_session, session.id)
    )

    (attempt,) = packet["back_translation"]["superseded_attempts"]
    assert set(attempt) == {"findings", "played_by_take", "played_ranges", "clip_duration_ms"}, (
        "o pacote para o Refine mudava de forma com as rodadas guardadas"
    )
    assert [finding["kind"] for finding in attempt["findings"]] == ["missing"]
    assert '"note"' not in json.dumps(packet["back_translation"]), (
        "a nota do analista viajava para o Refine dentro da rodada guardada"
    )


async def test_a_tablet_of_another_team_cannot_start_the_translation_over(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _told_and_heard(db_session)
    told = [one.id for one in await final_segments(db_session, session.id)]
    _stranger, credential = await a_claimed_device(db_session, email="estranho@example.com")

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/restart", headers=team_headers(credential)
    )

    assert refused.status_code == 404, refused.text
    assert [one.id for one in await final_segments(db_session, session.id)] == told, (
        "um tablet de outra equipe recomeçava a tradução desta"
    )
