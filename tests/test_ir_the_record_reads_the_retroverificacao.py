"""ENG-1343 — the record reads a session's retroverificação in her order, without the analyst.

Marcia's observation room shows the check as one block: its state, the open findings, the
nuances apart, the release check line, every translated frase, the re-opened approved version
and every conferência with the voice's words, and never the analyst's note. The retroverification
file is the only read that carries any of it, and it carries the note, so the record reads a
route of its own.

Every case drives the real application through the door the Desk reads by.
"""

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
)
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    one_stretch,
    ready_session,
    releases_of,
    team_headers,
    team_release,
)
from tests.room_harness import room_client

#: A note no other string in the answer contains, so a case can ask where the analyst's words
#: travelled without matching anything else by accident.
THE_ANALYSTS_NOTE = "NOTA-DO-ANALISTA-9c24"

FIRST_LINE = "Na frase 1 vocês disseram que Noemi voltou alegre. Ouçam de novo esse trecho."
SECOND_LINE = "Ficou muito bom. A tradução de vocês conta a passagem inteira."


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
    """One stretch the voice sent back once over an addition and passed on the second check."""
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
