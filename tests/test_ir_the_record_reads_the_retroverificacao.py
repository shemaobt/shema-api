from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Finding,
    FindingKind,
    Nuance,
)
from app.services.internalization_room.segments import capture_segment
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    desk_release,
    one_stretch,
    ready_session,
    releases_of,
    team_headers,
    team_release,
    the_one_part_of,
)
from tests.room_harness import room_client

THE_ANALYSTS_NOTE = "NOTA-DO-ANALISTA-9c24"

FIRST_LINE = "Na frase 1 vocês disseram que Noemi voltou alegre. Ouçam de novo esse trecho."
SECOND_LINE = "Ficou muito bom. A tradução de vocês conta a passagem inteira."
NUANCE_LINE = "Na frase 1 falta dizer que Noemi voltou de Moabe."


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def desk_record_retro(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/retro"


async def _the_retro(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> dict:
    answered = await client.get(desk_record_retro(session_id), headers=desk)
    assert answered.status_code == 200, answered.text
    return answered.json()


async def _checked_twice(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=session.pericope,
        checked=True,
        analysed_segment_ids=[told.id],
        checks=[
            CheckRound(
                at=datetime(2026, 10, 20, 14, 5, tzinfo=UTC),
                findings=[
                    Finding(
                        kind=FindingKind.ADDITION,
                        note=THE_ANALYSTS_NOTE,
                        segment_id=told.id,
                        chunk=1,
                    )
                ],
                spoken=FIRST_LINE,
                outcome="pass",
                conferida=False,
            ),
            CheckRound(
                at=datetime(2026, 10, 20, 14, 20, tzinfo=UTC),
                spoken=SECOND_LINE,
                outcome="pass",
                conferida=True,
            ),
        ],
    )


async def test_a_passage_approved_after_two_checks_reads_conferida_with_both_conferencias(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_checked_twice)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text

    retro = await _the_retro(client, session.id, desk)

    (row,) = await releases_of(db_session, session.id)
    assert retro["status"] == "conferida"
    assert retro["version"] == 1
    assert retro["approved_at"] == row.approved_at.isoformat()
    assert [one["spoken"] for one in retro["checks"]] == [FIRST_LINE, SECOND_LINE]
    assert [one["conferida"] for one in retro["checks"]] == [False, True]
    assert [(one["kind"], one["frase"]) for one in retro["checks"][0]["findings"]] == [
        ("addition", 1)
    ]
    assert retro["checks"][1]["findings"] == []


async def test_a_forced_approval_reads_forcada_at_the_moment_the_facilitator_forced_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text

    retro = await _the_retro(client, session.id, desk)

    (row,) = await releases_of(db_session, session.id)
    assert row.forced_at is not None
    assert retro["status"] == "forcada"
    assert retro["forced_at"] == row.forced_at.isoformat()
    assert retro["version"] == 1


async def _a_missing_element_and_a_nuance(
    db: AsyncSession, session: IRSession
) -> BackTranslationState:
    told = await one_stretch(db, session)
    missing = Finding(kind=FindingKind.MISSING, note=THE_ANALYSTS_NOTE, segment_id=told.id, chunk=1)
    nuance = Nuance(
        note=THE_ANALYSTS_NOTE,
        chunk=1,
        segment_id=told.id,
        quote="Noemi voltou com Rute",
        story="Noemi voltou de Moabe com Rute",
        take_id=told.take_id,
        starts_ms=told.starts_ms,
        ends_ms=told.ends_ms,
    )
    return BackTranslationState(
        scope=session.pericope,
        findings=[missing],
        nuances=[nuance],
        checked=False,
        analysed_segment_ids=[told.id],
        checks=[
            CheckRound(
                at=datetime(2026, 10, 20, 14, 5, tzinfo=UTC),
                findings=[missing],
                spoken=NUANCE_LINE,
                outcome="pass",
                conferida=False,
                nuances=[nuance.model_copy(update={"voiced": "before"})],
            )
        ],
    )


async def test_a_missing_element_reads_as_an_open_finding_and_the_nuance_apart_from_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(
        db_session, project_id=project.id, tell=_a_missing_element_and_a_nuance
    )
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    retro = await _the_retro(client, session.id, desk)

    assert [(one["kind"], one["frase"]) for one in retro["findings"]] == [("missing", 1)]
    assert [(one["frase"], one["said"]) for one in retro["nuances"]] == [(1, True)]
    assert retro["status"] == "sem_conferencia"


async def _one_finding_of_each_kind(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await one_stretch(db, session)
    findings = [
        Finding(kind=kind, note=THE_ANALYSTS_NOTE, segment_id=told.id, chunk=1, fills_silence=fills)
        for kind, fills in (
            (FindingKind.MISSING, False),
            (FindingKind.ADDITION, False),
            (FindingKind.ADDITION, True),
            (FindingKind.UNCLEAR, False),
        )
    ]
    return BackTranslationState(
        scope=session.pericope,
        findings=findings,
        checked=False,
        analysed_segment_ids=[told.id],
        checks=[
            CheckRound(
                at=datetime(2026, 10, 20, 14, 5, tzinfo=UTC),
                findings=findings,
                spoken=FIRST_LINE,
                outcome="pass",
                conferida=False,
            )
        ],
    )


async def test_an_addition_that_fills_a_silence_reads_as_a_filled_silence_beside_her_other_kinds(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_one_finding_of_each_kind)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    retro = await _the_retro(client, session.id, desk)

    her_four = ["missing", "addition", "silence", "unclear"]
    assert [one["kind"] for one in retro["findings"]] == her_four
    assert [one["kind"] for one in retro["checks"][0]["findings"]] == her_four


FIVE_FRASES = (
    ("Noemi ouviu que o Senhor tinha dado comida ao povo", 0, 12000, 1),
    ("ela saiu de Moabe com as duas noras", 12000, 24000, 1),
    ("no caminho ela disse para elas voltarem", 24000, 36000, 1),
    ("Orfa beijou a sogra e voltou", 36000, 48000, 1),
    ("Rute ficou com Noemi e não quis voltar", 48000, 55000, 2),
)


async def _told_in_five_frases(db: AsyncSession, session: IRSession) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    told = [
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=f"retro-{starts_ms}",
            transcript=text,
            pass_number=pass_number,
        )
        for text, starts_ms, ends_ms, pass_number in FIVE_FRASES
    ]
    await capture_segment(db, session, take_id=part.id, starts_ms=55000, ends_ms=61000)
    return BackTranslationState(
        scope=session.pericope, checked=True, analysed_segment_ids=[one.id for one in told]
    )


async def test_five_frases_told_read_as_five_translated_frases_with_their_stretch_and_words(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_in_five_frases)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    retro = await _the_retro(client, session.id, desk)

    part = await the_one_part_of(db_session, session)
    assert [
        (one["frase"], one["transcript"], one["starts_ms"], one["ends_ms"], one["pass_number"])
        for one in retro["frases"]
    ] == [
        (1, "Noemi ouviu que o Senhor tinha dado comida ao povo", 0, 12000, 1),
        (2, "ela saiu de Moabe com as duas noras", 12000, 24000, 1),
        (3, "no caminho ela disse para elas voltarem", 24000, 36000, 1),
        (4, "Orfa beijou a sogra e voltou", 36000, 48000, 1),
        (5, "Rute ficou com Noemi e não quis voltar", 48000, 55000, 2),
    ]
    assert {(one["take_id"], one["scene"]) for one in retro["frases"]} == {(part.id, "whole")}
