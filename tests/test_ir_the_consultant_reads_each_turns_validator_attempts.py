"""ENG-1582 — the consultant's turn read serves each turn's Validator attempts, in order.

The Validator's attempts are stored with the turn since ENG-1200 and the turns route gave only
their count. Every case speaks a turn through the tablet's own door with the Guide and the
Validator scripted, then reads it back as the Desk's facilitator does.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session
from tests.baker import make_app, make_role
from tests.release_harness import PREFIX, P, a_claimed_device, at_the_desk
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_team_says, the_turn_is_scripted


class _Model:
    def __init__(self, drafts: list[str], replies: list[str]) -> None:
        self.drafts = drafts
        self.replies = replies
        self.drafted = 0
        self.judged = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" not in system_prompt:
            self.drafted += 1
            return self.drafts[self.drafted - 1]
        self.judged += 1
        return self.replies[self.judged - 1]


def _verdict(verdict: str, issues: list[dict[str, str]] | None = None, **rest: str) -> str:
    return json.dumps({"verdict": verdict, "issues": issues or [], **rest})


def _issue(problem: str, claim: str) -> dict[str, str]:
    return {"problem": problem, "claim": claim, "explanation": f"porque {claim}"}


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
def the_room_hears(monkeypatch: pytest.MonkeyPatch):
    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="a fome chegou")

    def _install(drafts: list[str], replies: list[str]) -> None:
        the_turn_is_scripted(monkeypatch, heard=heard, model=_Model(drafts, replies))

    return _install


async def _the_last_turn_as_the_desk_reads_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> dict[str, Any]:
    project, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, project)
    session = await create_session(db_session, project_id=project.id, language="pt", pericope=P)
    await append_exchange(db_session, session, team_utterance="a fome", guide_response="…")
    await the_team_says(client, tablet, session.id, "turno")
    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/turns", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["turns"][-1]


async def test_a_turn_sent_back_once_then_passed_reads_two_attempts_in_order_the_first_with_every_issue(  # noqa: E501
    client, db_session, room_app, the_room_hears
) -> None:
    issues = [_issue("imported_knowledge", "Rute casou"), _issue("leading", "diga que sim")]
    the_room_hears(
        ["Rute casou com Malom.", "O que Rute fez?"],
        [_verdict("regenerate", issues), _verdict("pass")],
    )

    turn = await _the_last_turn_as_the_desk_reads_it(client, db_session, room_app)

    assert turn["voice"]["attempts"] == 2
    assert turn["voice"]["trace"] == [
        {
            "attempt": 1,
            "draft": "Rute casou com Malom.",
            "verdict": "regenerate",
            "issues": issues,
            "corrected": None,
            "note": None,
        },
        {
            "attempt": 2,
            "draft": "O que Rute fez?",
            "verdict": "pass",
            "issues": [],
            "corrected": None,
            "note": None,
        },
    ]
