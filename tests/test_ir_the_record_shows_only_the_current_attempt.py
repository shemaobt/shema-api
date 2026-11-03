from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

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
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    one_stretch,
    ready_session,
    session_retro,
    team_headers,
)
from tests.room_harness import room_client

THE_ANALYSTS_NOTE = "NOTA-DO-ANALISTA-1624"
THE_VOICES_WORDS = "Na frase 1 vocês disseram que Noemi voltou alegre. Ouçam de novo esse trecho."
THE_SAID_QUOTE = "CITACAO-DITA-1624"
THE_UNSAID_QUOTE = "CITACAO-NAO-DITA-1624"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _checked_once(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await one_stretch(db, session, "Noemi voltou alegre")
    finding = Finding(
        kind=FindingKind.ADDITION, note=THE_ANALYSTS_NOTE, segment_id=told.id, chunk=1
    )

    def nuance(quote: str, voiced: Literal["now"] | None) -> Nuance:
        return Nuance(
            note="tornou, não voltou",
            chunk=1,
            segment_id=told.id,
            quote=quote,
            story="tornou",
            take_id=told.take_id,
            starts_ms=told.starts_ms,
            ends_ms=told.ends_ms,
            voiced=voiced,
        )

    return BackTranslationState(
        scope=session.pericope,
        analysed_segment_ids=[told.id],
        findings=[finding],
        checks=[
            CheckRound(
                at=datetime(2026, 10, 20, 14, 5, tzinfo=UTC),
                findings=[finding],
                spoken=THE_VOICES_WORDS,
                outcome="pass",
                conferida=False,
                nuances=[nuance(THE_SAID_QUOTE, "now"), nuance(THE_UNSAID_QUOTE, None)],
                heard_at=datetime(2026, 10, 20, 14, 6, tzinfo=UTC),
            )
        ],
    )


async def _restarted(
    client: httpx.AsyncClient, db: AsyncSession, room_app
) -> tuple[IRSession, dict[str, str]]:
    project, credential = await a_claimed_device(db)
    session = await ready_session(db, project_id=project.id, tell=_checked_once)
    desk, _facilitator = await at_the_desk(db, room_app, project)
    restarted = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/restart",
        headers=team_headers(credential),
    )
    assert restarted.status_code == 200, restarted.text
    return session, desk


async def _the_file(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> dict:
    answered = await session_retro(client, session_id, desk)
    assert answered.status_code == 200, answered.text
    return answered.json()


async def test_the_file_keeps_the_restarted_frases_with_their_words_apart_from_the_current_ones(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session, desk = await _restarted(client, db_session, room_app)

    the_file = await _the_file(client, session.id, desk)

    assert [one["transcript"] for one in the_file["history"]] == ["Noemi voltou alegre"], (
        "a frase traduzida antes do recomeçar sumia do arquivo"
    )
    assert the_file["frases"] == [], "a frase de antes ainda contava como a de agora"


async def test_the_record_after_a_restart_reads_only_the_frase_told_since(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session, desk = await _restarted(client, db_session, room_app)
    await db_session.refresh(session)
    await one_stretch(db_session, session, "Noemi voltou de Moabe")

    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/retro", headers=desk)

    assert answered.status_code == 200, answered.text
    retro = answered.json()
    assert [one["transcript"] for one in retro["frases"]] == ["Noemi voltou de Moabe"], (
        "o registro mostrava a frase traduzida antes do recomeçar"
    )
    assert (retro["findings"], retro["nuances"], retro["checks"]) == ([], [], []), (
        "o registro mostrava a conferência de antes do recomeçar"
    )
