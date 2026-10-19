"""ENG-1654 — the «Gravações» read serves the kept rehearsals and the heading remainder.

Every case drives the real application through the door the Desk reads by.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)

IR = "/api/internalization-room"
P = "P01"


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def team(db_session: AsyncSession) -> Project:
    language = await make_language(db_session, name="Lang a", code="la")
    return await make_project(db_session, language.id, name="Team a")


@pytest.fixture()
async def session(db_session: AsyncSession, team: Project) -> IRSession:
    return await open_ir_session(db_session, pericope=P, project_id=team.id)


def _opening(at: str) -> dict[str, Any]:
    return {"role": "guide", "text": "Boa tarde.", "at": at}


def _exchange(words: str, at: str) -> list[dict[str, Any]]:
    return [
        {"role": "team", "text": words, "at": at},
        {"role": "guide", "text": "Entendi.", "at": at, "mother_tongue": False},
    ]


def _kept(scope: str, key: str) -> dict[str, Any]:
    return {
        "scope": scope,
        "approved": True,
        "kept": {"storage_key": key, "content_type": "audio/mp4"},
    }


async def _told(
    db: AsyncSession,
    session: IRSession,
    exchanges: list[tuple[str, str]],
    retellings: dict[str, dict[str, Any]] | None,
) -> None:
    messages = [_opening("2026-10-19T10:00:00+00:00")]
    for words, at in exchanges:
        messages.extend(_exchange(words, at))
    session.messages = messages
    session.retellings = retellings
    await db.commit()


async def _read(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(
        f"{IR}/facilitator/sessions/{session_id}/mother-tongue-takes", headers=headers
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_a_kept_retelling_is_listed_with_its_turn_and_the_words_the_team_said(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    await _told(
        db_session,
        session,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/1")},
    )

    body = await _read(client, consultant, session.id)

    assert body["kept_rehearsals"] == [
        {"turn_number": 1, "words": "Noemi voltou com Rute", "from_other_session": False}
    ]


async def test_two_scopes_kept_are_both_listed_each_with_its_own_words(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    await _told(
        db_session,
        session,
        [
            ("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00"),
            ("Boaz viu Rute no campo", "2026-10-19T10:02:00+00:00"),
        ],
        {"1": _kept("S1", "k/1"), "2": _kept("S2", "k/2")},
    )

    body = await _read(client, consultant, session.id)

    assert [(row["turn_number"], row["words"]) for row in body["kept_rehearsals"]] == [
        (1, "Noemi voltou com Rute"),
        (2, "Boaz viu Rute no campo"),
    ]


async def test_a_scope_approved_twice_is_listed_in_its_latest_telling_not_its_first(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    await _told(
        db_session,
        session,
        [
            ("Noemi voltou", "2026-10-19T10:01:00+00:00"),
            ("Boaz viu Rute no campo", "2026-10-19T10:02:00+00:00"),
            ("Noemi voltou com Rute a Belém", "2026-10-19T10:03:00+00:00"),
        ],
        {"1": _kept("S1", "k/1"), "2": _kept("S2", "k/2"), "3": _kept("S1", "k/3")},
    )

    body = await _read(client, consultant, session.id)

    assert [(row["turn_number"], row["words"]) for row in body["kept_rehearsals"]] == [
        (2, "Boaz viu Rute no campo"),
        (3, "Noemi voltou com Rute a Belém"),
    ]


async def test_a_telling_that_kept_no_take_is_not_a_kept_rehearsal(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    await _told(
        db_session,
        session,
        [
            ("Noemi voltou", "2026-10-19T10:01:00+00:00"),
            ("Boaz viu Rute", "2026-10-19T10:02:00+00:00"),
            ("Rute respigou", "2026-10-19T10:03:00+00:00"),
        ],
        {
            "1": {"scope": "S1", "approved": False},
            "2": {"scope": "S2", "approved": True},
            "3": _kept("S3", "k/3"),
        },
    )

    body = await _read(client, consultant, session.id)

    assert [row["turn_number"] for row in body["kept_rehearsals"]] == [3]
