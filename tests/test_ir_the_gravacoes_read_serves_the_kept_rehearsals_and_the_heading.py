"""ENG-1654 — the «Gravações» read serves the kept rehearsals and the heading remainder.

Every case drives the real application through the door the Desk reads by.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.db.models.project import Project
from app.services.internalization_room.sessions import create_session
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_user,
    open_ir_session,
)
from tests.release_harness import ensaio_take
from tests.signer_harness import Signer, the_bucket_signs

IR = "/api/internalization-room"
P = "P01"


@pytest.fixture(autouse=True)
def signer(monkeypatch: pytest.MonkeyPatch) -> Signer:
    return the_bucket_signs(monkeypatch)


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
        {
            "turn_number": 1,
            "words": "Noemi voltou com Rute",
            "from_other_session": False,
            "scope": "S1",
            "audio_url": "https://signed.example/balde-de-teste/k/1?grant=1",
        }
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


async def test_a_kept_rehearsal_names_its_scene_or_the_whole_passage(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    await _told(
        db_session,
        session,
        [
            ("Boaz viu Rute no campo", "2026-10-19T10:01:00+00:00"),
            ("Noemi voltou com Rute", "2026-10-19T10:02:00+00:00"),
        ],
        {"1": _kept("S2", "k/1"), "2": _kept("whole", "k/2")},
    )

    body = await _read(client, consultant, session.id)

    assert [(row["turn_number"], row["scope"]) for row in body["kept_rehearsals"]] == [
        (1, "S2"),
        (2, "whole"),
    ]


async def test_a_kept_rehearsal_carries_a_link_to_its_audio_signed_when_it_is_read(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
    signer: Signer,
) -> None:
    await _told(
        db_session,
        session,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/1")},
    )

    first = await _read(client, consultant, session.id)
    second = await _read(client, consultant, session.id)

    assert [row["audio_url"] for row in first["kept_rehearsals"]] == [
        "https://signed.example/balde-de-teste/k/1?grant=1"
    ]
    assert [row["audio_url"] for row in second["kept_rehearsals"]] == [
        "https://signed.example/balde-de-teste/k/1?grant=2"
    ]
    assert signer.calls == [("k/1", 15, "audio/mp4"), ("k/1", 15, "audio/mp4")]


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


async def test_a_rehearsal_kept_in_another_session_of_the_team_is_listed_marked_and_in_time_order(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    earlier = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await _told(
        db_session,
        earlier,
        [
            ("Noemi partiu", "2026-10-18T09:01:00+00:00"),
            ("Noemi chegou", "2026-10-18T09:02:00+00:00"),
            ("Boaz viu Rute no campo", "2026-10-18T09:03:00+00:00"),
        ],
        {"3": _kept("S2", "k/earlier")},
    )
    await _told(
        db_session,
        session,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/1")},
    )

    body = await _read(client, consultant, session.id)

    assert body["kept_rehearsals"] == [
        {
            "turn_number": 3,
            "words": "Boaz viu Rute no campo",
            "from_other_session": True,
            "scope": "S2",
            "audio_url": "https://signed.example/balde-de-teste/k/earlier?grant=1",
        },
        {
            "turn_number": 1,
            "words": "Noemi voltou com Rute",
            "from_other_session": False,
            "scope": "S1",
            "audio_url": "https://signed.example/balde-de-teste/k/1?grant=2",
        },
    ]


async def test_a_sibling_sessions_rehearsal_is_signed_from_its_own_recording_and_nothing_is_stored(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    sibling = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await _told(
        db_session,
        sibling,
        [("Boaz viu Rute no campo", "2026-10-18T09:01:00+00:00")],
        {"1": _kept("S2", "k/sibling")},
    )
    await _told(
        db_session,
        session,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/1")},
    )

    body = await _read(client, consultant, session.id)
    await db_session.refresh(sibling)
    await db_session.refresh(session)

    assert [(row["from_other_session"], row["audio_url"]) for row in body["kept_rehearsals"]] == [
        (True, "https://signed.example/balde-de-teste/k/sibling?grant=1"),
        (False, "https://signed.example/balde-de-teste/k/1?grant=2"),
    ]
    assert sibling.retellings == {"1": _kept("S2", "k/sibling")}
    assert session.retellings == {"1": _kept("S1", "k/1")}


async def test_a_scope_kept_in_two_sessions_is_listed_once_in_the_later_telling(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    earliest = await open_ir_session(db_session, pericope=P, project_id=team.id)
    middle = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await _told(
        db_session,
        session,
        [
            ("Noemi partiu", "2026-10-20T08:01:00+00:00"),
            ("Noemi voltou com Rute a Belém", "2026-10-20T08:02:00+00:00"),
        ],
        {"2": _kept("S1", "k/latest")},
    )
    await _told(
        db_session,
        earliest,
        [("Noemi voltou", "2026-10-18T09:01:00+00:00")],
        {"1": _kept("S1", "k/earliest")},
    )
    await _told(
        db_session,
        middle,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/middle")},
    )

    from_the_latest = await _read(client, consultant, session.id)
    from_the_earliest = await _read(client, consultant, earliest.id)

    assert from_the_latest["kept_rehearsals"] == [
        {
            "turn_number": 2,
            "words": "Noemi voltou com Rute a Belém",
            "from_other_session": False,
            "scope": "S1",
            "audio_url": "https://signed.example/balde-de-teste/k/latest?grant=1",
        }
    ]
    assert from_the_earliest["kept_rehearsals"] == [
        {
            "turn_number": 2,
            "words": "Noemi voltou com Rute a Belém",
            "from_other_session": True,
            "scope": "S1",
            "audio_url": "https://signed.example/balde-de-teste/k/latest?grant=2",
        }
    ]


async def test_a_scope_told_again_in_a_later_session_links_the_later_audio(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    later = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await _told(
        db_session,
        session,
        [("Noemi voltou", "2026-10-18T09:01:00+00:00")],
        {"1": _kept("S1", "k/first")},
    )
    await _told(
        db_session,
        later,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/second")},
    )

    body = await _read(client, consultant, session.id)

    assert [(row["words"], row["audio_url"]) for row in body["kept_rehearsals"]] == [
        ("Noemi voltou com Rute", "https://signed.example/balde-de-teste/k/second?grant=1")
    ]


async def test_another_team_language_passage_or_zerar_adds_nothing_to_the_list(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    language = await make_language(db_session, name="Lang b", code="lb")
    other_team = await make_project(db_session, language.id, name="Team b")
    decoys = [
        await open_ir_session(db_session, pericope=P, project_id=other_team.id),
        await create_session(db_session, pericope=P, project_id=team.id, language="en"),
        await open_ir_session(db_session, pericope="P02", project_id=team.id),
        await open_ir_session(db_session, pericope=P, project_id=team.id),
    ]
    decoys[3].archive_id = "zerar-1"
    for number, decoy in enumerate(decoys):
        await _told(
            db_session,
            decoy,
            [("Das outras", f"2026-10-18T09:0{number}:00+00:00")],
            {"1": _kept(f"S{number + 2}", f"k/{number}")},
        )
    await _told(
        db_session,
        session,
        [("Noemi voltou com Rute", "2026-10-19T10:01:00+00:00")],
        {"1": _kept("S1", "k/1")},
    )

    body = await _read(client, consultant, session.id)

    assert body["kept_rehearsals"] == [
        {
            "turn_number": 1,
            "words": "Noemi voltou com Rute",
            "from_other_session": False,
            "scope": "S1",
            "audio_url": "https://signed.example/balde-de-teste/k/1?grant=1",
        }
    ]


async def test_a_session_a_zerar_archived_lists_its_own_zerar_and_not_the_live_work(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    team: Project,
    db_session: AsyncSession,
) -> None:
    sessions = [await open_ir_session(db_session, pericope=P, project_id=team.id) for _ in range(4)]
    viewed, mate, _live_now, another_zerar = sessions
    viewed.archive_id = mate.archive_id = "zerar-1"
    another_zerar.archive_id = "zerar-2"
    for number, (each, scope) in enumerate(zip(sessions, ["S1", "S2", "S3", "S4"], strict=True)):
        await _told(
            db_session,
            each,
            [(f"Palavras de {scope}", f"2026-10-18T09:0{number}:00+00:00")],
            {"1": _kept(scope, f"k/{scope}")},
        )

    body = await _read(client, consultant, viewed.id)

    assert [(row["words"], row["from_other_session"]) for row in body["kept_rehearsals"]] == [
        ("Palavras de S1", False),
        ("Palavras de S2", True),
    ]


async def _recorded(
    db: AsyncSession, session: IRSession, team: Project, ordinals: list[int | None]
) -> None:
    for number, ordinal in enumerate(ordinals):
        db.add(
            ensaio_take(session.id, ordinal=ordinal, sha256=str(number) * 64, project_id=team.id)
        )
    await db.commit()


async def test_a_passage_recorded_with_no_part_number_is_told_whole(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    await _recorded(db_session, session, team, [None])

    body = await _read(client, consultant, session.id)

    assert body["recording_grain"] == "whole"


async def test_a_passage_recorded_in_numbered_parts_is_told_in_parts(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    await _recorded(db_session, session, team, [1, 2])

    body = await _read(client, consultant, session.id)

    assert body["recording_grain"] == "parts"


async def test_a_session_that_recorded_nothing_claims_no_grain(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
) -> None:
    body = await _read(client, consultant, session.id)

    assert body["recording_grain"] is None


def _release(session: IRSession, version: int, approved_at: datetime) -> IRRelease:
    return IRRelease(
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        version=version,
        package_sha256=str(version) * 64,
        packet={},
        approved_at=approved_at,
    )


async def test_the_finish_is_the_approval_of_the_latest_release_of_the_session(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    db_session.add(_release(session, 1, datetime(2026, 10, 17, 12, 0, tzinfo=UTC)))
    db_session.add(_release(session, 2, datetime(2026, 10, 19, 15, 30, tzinfo=UTC)))
    await db_session.commit()

    body = await _read(client, consultant, session.id)

    assert body["finished_at"] == "2026-10-19T15:30:00+00:00"


async def test_a_session_with_no_release_of_its_own_has_no_finish_whatever_its_team_approved(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    sibling = await open_ir_session(db_session, pericope=P, project_id=team.id)
    db_session.add(_release(sibling, 1, datetime(2026, 10, 17, 12, 0, tzinfo=UTC)))
    await db_session.commit()

    body = await _read(client, consultant, session.id)

    assert body["finished_at"] is None
