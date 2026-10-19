"""ENG-1334 — the consultant reads the mother-tongue takes of a session, with her facts per take.

Every case drives the real application through the door the Desk reads by.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.services.internalization_room import takes as takes_service
from app.services.platform.storage import StoredObject
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import ensaio_take, retro_take
from tests.room_harness import the_bucket_is_in_memory

IR = "/api/internalization-room"
P = "P01"


class Signer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def __call__(
        self, bucket: str, key: str, *, expiry_minutes: int, response_content_type: str | None
    ) -> str:
        self.calls.append((key, expiry_minutes))
        return f"https://signed.example/{bucket}/{key}?grant={len(self.calls)}"


@pytest.fixture(autouse=True)
def signer(monkeypatch: pytest.MonkeyPatch) -> Signer:
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    signing = Signer()
    monkeypatch.setattr(takes_service, "generate_signed_download_url", signing)
    return signing


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


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


async def _keep(
    db: AsyncSession,
    session: IRSession,
    team: Project,
    *,
    ordinal: int | None,
    sha: str,
    size_bytes: int = 2048,
    created_at: datetime | None = None,
    pass_number: int | None = None,
) -> str:
    take = ensaio_take(
        session.id,
        ordinal=ordinal,
        sha256=sha,
        project_id=team.id,
        created_at=created_at,
        pass_number=pass_number,
    )
    take.size_bytes = size_bytes
    db.add(take)
    await db.commit()
    takes_service._store().objects[take.storage_key] = b"audio"
    return take.id


async def _read(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(
        f"{IR}/facilitator/sessions/{session_id}/mother-tongue-takes", headers=headers
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_the_takes_come_in_reading_order_each_named_by_its_position_among_the_parts(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    third = await _keep(db_session, session, team, ordinal=3, sha="c" * 64)
    first = await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    second = await _keep(db_session, session, team, ordinal=2, sha="b" * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [
        (first, 1),
        (second, 2),
        (third, 3),
    ]


async def test_a_rehearsal_told_whole_has_no_part_and_does_not_move_the_numbered_ones(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    first = await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    whole = await _keep(db_session, session, team, ordinal=None, sha="w" * 64)
    second = await _keep(db_session, session, team, ordinal=2, sha="b" * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [
        (whole, None),
        (first, 1),
        (second, 2),
    ]


async def test_the_size_is_in_kilobytes_rounded_half_up_as_her_page_rounds_it(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    for ordinal, size in enumerate((512, 1535, 1536, 2560), start=1):
        await _keep(
            db_session, session, team, ordinal=ordinal, sha=str(ordinal) * 64, size_bytes=size
        )

    body = await _read(client, consultant, session.id)

    assert [row["size_kb"] for row in body["takes"]] == [1, 1, 2, 3]


async def test_the_fingerprint_is_the_first_twelve_characters_of_the_sha256(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    await _keep(db_session, session, team, ordinal=1, sha="0123456789abcdef" * 4)

    body = await _read(client, consultant, session.id)

    assert [row["fingerprint"] for row in body["takes"]] == ["0123456789ab"]


async def test_the_time_is_the_moment_the_take_was_kept_with_its_offset(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    kept_at = datetime(2026, 9, 1, 10, 2, tzinfo=UTC)
    await _keep(db_session, session, team, ordinal=1, sha="a" * 64, created_at=kept_at)

    body = await _read(client, consultant, session.id)

    assert [row["recorded_at"] for row in body["takes"]] == ["2026-09-01T10:02:00+00:00"]


async def test_a_take_that_kept_no_duration_shows_none_never_one_guessed_from_its_size(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    await _keep(db_session, session, team, ordinal=1, sha="a" * 64, size_bytes=480_000)

    body = await _read(client, consultant, session.id)

    (row,) = body["takes"]
    assert "duration_ms" in row
    assert row["duration_ms"] is None


async def test_a_telling_back_and_a_part_recorded_again_are_not_listed_beside_the_part_that_stands(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    await _keep(db_session, session, team, ordinal=1, sha="a" * 64, pass_number=1)
    again = await _keep(db_session, session, team, ordinal=1, sha="b" * 64, pass_number=2)
    second = await _keep(db_session, session, team, ordinal=2, sha="c" * 64, pass_number=1)
    db_session.add(retro_take(session.id, ordinal=1, sha256="d" * 64, project_id=team.id))
    await db_session.commit()

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [(again, 1), (second, 2)]


async def test_each_take_carries_a_link_of_fifteen_minutes_and_a_second_read_mints_a_fresh_one(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
    signer: Signer,
) -> None:
    await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    await _keep(db_session, session, team, ordinal=2, sha="b" * 64)
    stored = [f"takes/{session.id}/ensaio/{sha * 64}" for sha in "ab"]

    first = [row["play_url"] for row in (await _read(client, consultant, session.id))["takes"]]
    second = [row["play_url"] for row in (await _read(client, consultant, session.id))["takes"]]

    assert [url.split("?")[0] for url in first] == [
        f"https://signed.example/balde-de-teste/{key}" for key in stored
    ]
    assert [url.split("?")[0] for url in second] == [url.split("?")[0] for url in first]
    assert set(first).isdisjoint(second)
    assert {minutes for _key, minutes in signer.calls} == {15}


async def test_a_take_the_bucket_does_not_hold_is_unread_and_the_others_still_answer(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
    bucket: MemoryStore,
    signer: Signer,
) -> None:
    for ordinal, sha in enumerate("abc", start=1):
        await _keep(db_session, session, team, ordinal=ordinal, sha=sha * 64)
    del bucket.objects[f"takes/{session.id}/ensaio/{'b' * 64}"]

    body = await _read(client, consultant, session.id)

    assert [(row["part"], row["unread"], row["play_url"] is None) for row in body["takes"]] == [
        (1, False, False),
        (2, True, True),
        (3, False, False),
    ]
    assert [key for key, _minutes in signer.calls] == [
        f"takes/{session.id}/ensaio/{sha * 64}" for sha in "ac"
    ]


class StoreThatFailsOn(MemoryStore):
    def __init__(self, broken: str) -> None:
        super().__init__()
        self.broken = broken

    async def stat(self, key: str) -> StoredObject | None:
        if key == self.broken:
            raise RuntimeError("the storage did not answer")
        return await super().stat(key)


async def test_a_take_the_storage_fails_to_answer_about_is_unread_and_the_read_still_answers(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = StoreThatFailsOn(f"takes/{session.id}/ensaio/{'b' * 64}")
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: failing)
    for ordinal, sha in enumerate("abc", start=1):
        await _keep(db_session, session, team, ordinal=ordinal, sha=sha * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["part"], row["unread"], row["play_url"] is None) for row in body["takes"]] == [
        (1, False, False),
        (2, True, True),
        (3, False, False),
    ]


async def test_a_take_the_signer_fails_to_link_is_unread_and_the_others_still_get_theirs(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
    signer: Signer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = f"takes/{session.id}/ensaio/{'b' * 64}"

    async def signing(
        bucket: str, key: str, *, expiry_minutes: int, response_content_type: str | None
    ) -> str:
        if key == broken:
            raise RuntimeError("the credentials did not resolve")
        return await signer(
            bucket, key, expiry_minutes=expiry_minutes, response_content_type=response_content_type
        )

    monkeypatch.setattr(takes_service, "generate_signed_download_url", signing)
    for ordinal, sha in enumerate("abc", start=1):
        await _keep(db_session, session, team, ordinal=ordinal, sha=sha * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["part"], row["unread"], row["play_url"] is None) for row in body["takes"]] == [
        (1, False, False),
        (2, True, True),
        (3, False, False),
    ]


async def _a_facilitator_of(db: AsyncSession, project: Project, email: str) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=email)
    await grant_room_app_role(db, user.id, "facilitator")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def test_the_owner_and_a_consultant_read_it_and_another_projects_reader_and_nobody_do_not(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    language = await make_language(db_session, name="Lang b", code="lb")
    other = await make_project(db_session, language.id, name="Team b")
    owner = await _a_facilitator_of(db_session, team, "dona@example.com")
    stranger = await _a_facilitator_of(db_session, other, "outra@example.com")
    await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    url = f"{IR}/facilitator/sessions/{session.id}/mother-tongue-takes"

    answers = {
        "owner": (await client.get(url, headers=owner)).status_code,
        "consultant": (await client.get(url, headers=consultant)).status_code,
        "stranger": (await client.get(url, headers=stranger)).status_code,
        "nobody": (await client.get(url)).status_code,
    }

    assert answers == {"owner": 200, "consultant": 200, "stranger": 404, "nobody": 401}


async def test_a_session_that_recorded_nothing_answers_an_empty_list_not_an_error(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
) -> None:
    body = await _read(client, consultant, session.id)

    assert body == {
        "session_id": session.id,
        "takes": [],
        "kept_rehearsals": [],
        "recording_grain": None,
        "finished_at": None,
    }


def _as_stored(row: Any) -> dict[str, Any]:
    return {column.key: getattr(row, column.key) for column in row.__mapper__.column_attrs}


async def test_reading_the_takes_changes_neither_the_session_nor_a_take(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    from app.db.models.internalization_room import IRTake

    await _keep(db_session, session, team, ordinal=1, sha="a" * 64)
    (take,) = (await db_session.execute(select(IRTake))).scalars().all()
    await db_session.refresh(session)
    before = (_as_stored(session), _as_stored(take))

    await _read(client, consultant, session.id)
    await _read(client, consultant, session.id)
    await db_session.refresh(session)
    await db_session.refresh(take)

    assert (_as_stored(session), _as_stored(take)) == before


async def test_the_part_is_the_position_among_the_numbered_parts_not_the_number_the_tablet_sent(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    team: Project,
    db_session: AsyncSession,
) -> None:
    second = await _keep(db_session, session, team, ordinal=2, sha="a" * 64)
    fifth = await _keep(db_session, session, team, ordinal=5, sha="b" * 64)

    body = await _read(client, consultant, session.id)

    assert [(row["take_id"], row["part"]) for row in body["takes"]] == [(second, 1), (fifth, 2)]
