"""ENG-844 — a team's approval writes a release, numbered per pericope per project.

The packet used to be composed on demand and named by nothing: two reads a day apart were
two packets under no name, and nothing in the schema said a team had approved anything. The
approval writes a row now, numbered from one and never reused, carrying the packet as it was
approved — so a re-record cannot take version 1 away from the comments hanging off it.

The version is never the caller's to send and the number is not defended by the allocation
alone: the unique index is what makes two approvals racing for one number impossible rather
than unlikely, which is the race ENG-639 already recorded against stretch positions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.database import Base
from app.core.enums import ProjectRole
from app.db.models.auth import Role
from app.db.models.internalization_room import IRRelease
from app.services.internalization_room import release as release_module
from app.services.internalization_room.sessions import create_session
from tests.baker import (
    make_app,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)
from tests.test_internalization_room_release import P, _one_stretch, _ready_session
from tests.test_ir_project_id import KEY, PREFIX, a_claimed_device

REPO_ROOT = Path(__file__).resolve().parent.parent

APP_KEY = "internalization-room"

#: What the packet says it is. One constant because the number moves for reasons that have
#: nothing to do with this rule, and a version written into six assertions is six places to
#: forget.
SCHEMA_VERSION = "tripod.internalization-release.v0.5"

REVISION = "20260910_rel01"
PREVIOUS_REVISION = "20260910_hard01"
TABLE = "ir_releases"
UNIQUE_INDEX = "uq_ir_releases_version"
SEEDED_SESSION = "3f6f7a1e-0f0e-4f7a-9d55-0b1c2d3e4f50"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def _team(credential: str) -> dict[str, str]:
    return {"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: credential}


async def _facilitator(db: AsyncSession, room_app, project=None) -> dict[str, str]:
    """A Desk caller who facilitates ``project``, or nobody's team when it is None."""
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=f"desk-{uuid.uuid4()}@example.com")
    role = (
        await db.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db, user.id, room_app.id, role.id)
    if project is not None:
        await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def _releases_of(db: AsyncSession, session_id: str) -> list[IRRelease]:
    rows = await db.execute(
        select(IRRelease).where(IRRelease.session_id == session_id).order_by(IRRelease.version)
    )
    return list(rows.scalars().all())


async def test_a_credentialed_team_that_approves_gets_version_one(client, db_session):
    project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session, project_id=project.id)

    approved = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential)
    )

    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["version"] == 1
    assert len(body["package_sha256"]) == 64
    assert set(body["package_sha256"]) <= set("0123456789abcdef")
    assert body["approved_at"]
    stored = await _releases_of(db_session, session.id)
    assert [row.version for row in stored] == [1]
    assert body["package_sha256"] == stored[0].package_sha256
    assert body["release_id"] == stored[0].id
    assert stored[0].packet["release_id"] == body["release_id"]
    assert stored[0].packet["version"] == 1
    assert stored[0].packet["package_sha256"] == body["package_sha256"]


async def test_approving_again_with_nothing_changed_returns_the_same_release(client, db_session):
    project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session, project_id=project.id)

    first = await client.post(f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential))
    second = await client.post(f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential))

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["release_id"] == first.json()["release_id"]
    assert first.json()["version"] == 1
    assert second.json()["version"] == 1
    assert [row.version for row in await _releases_of(db_session, session.id)] == [1]


async def test_a_re_record_approved_again_mints_version_two_and_keeps_version_one(
    client, db_session
):
    """One more stretch told is what moves the content here, and it stands for the re-record.

    A **Rebuild** reaches the packet the same way — it re-points every stretch at the file it
    rebuilt, so the composed content differs — and it costs a whole recording to stage. What
    the version turns on is the hash, not which edit changed it, so the cheaper change proves
    the rule; `compose.py` owns the rebuild path and its own tests.
    """
    project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session, project_id=project.id)

    first = await client.post(f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential))
    version_one = (await _releases_of(db_session, session.id))[0]
    as_approved = json.dumps(version_one.packet, sort_keys=True)

    await _one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    second = await client.post(f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential))

    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2
    assert second.json()["release_id"] != first.json()["release_id"]
    assert second.json()["package_sha256"] != first.json()["package_sha256"]
    await db_session.refresh(version_one)
    assert json.dumps(version_one.packet, sort_keys=True) == as_approved, (
        "a versão 1 tem que continuar sendo o pacote aprovado, byte por byte, depois da regravação"
    )


async def test_the_packet_names_its_release_and_says_which_schema_it_is(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session, project_id=project.id)
    desk = await _facilitator(db_session, room_app, project)

    before = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/release", headers=desk)
    approved = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential)
    )
    after = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/release", headers=desk)
    await _one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    redrafted = await client.get(
        f"{PREFIX}/facilitator/sessions/{session.id}/release", headers=desk
    )

    assert before.status_code == 200, before.text
    assert before.json()["release_id"] is None
    assert before.json()["version"] is None
    assert after.json()["schema_version"] == SCHEMA_VERSION
    assert after.json()["release_id"] == approved.json()["release_id"]
    assert after.json()["version"] == 1
    assert after.json()["package_sha256"] == approved.json()["package_sha256"]
    assert redrafted.json()["release_id"] is None, (
        "o rascunho de agora não é o que foi aprovado, e nomear a versão 1 diria que é"
    )
    assert redrafted.json()["version"] is None


async def test_two_approvals_cannot_take_one_number(db_session):
    project, _credential = await a_claimed_device(db_session)
    session = await create_session(db_session, pericope=P, project_id=project.id)
    for stamp in ("a" * 64, "b" * 64):
        db_session.add(
            IRRelease(
                session_id=session.id,
                project_id=project.id,
                pericope=P,
                version=1,
                package_sha256=stamp,
                packet={},
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


async def test_the_version_is_never_the_callers(client, db_session):
    project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session, project_id=project.id)

    approved = await client.post(
        f"{PREFIX}/sessions/{session.id}/release",
        headers=_team(credential),
        json={"version": 7},
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 1


async def test_a_session_on_the_shared_key_is_refused_with_a_named_conflict(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session)
    desk = await _facilitator(db_session, room_app, project)

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers={"X-Room-Key": KEY}
    )
    read = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/release", headers=desk)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "RELEASE_WITHOUT_PROJECT"
    assert await _releases_of(db_session, session.id) == []
    assert read.status_code == 404, (
        "a leitura do facilitador para uma sessão sem projeto continua sendo 404, como na main"
    )


async def test_a_passage_the_packet_refuses_is_not_approved_either(client, db_session):
    """The blockers the packet already raises are the whole of the gate this route has.

    Whether a passage *may* be approved is ENG-882 and is not here; what has to hold until
    then is that the approval refuses exactly where the read refuses, and leaves no row
    behind when it does.
    """
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, pericope=P, project_id=project.id)

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential)
    )

    assert refused.status_code == 409, refused.text
    assert "no_telling_back" in refused.json()["detail"]
    assert await _releases_of(db_session, session.id) == []


async def test_an_approval_that_loses_the_race_for_a_number_is_answered_not_numbered(
    client, db_session, monkeypatch
):
    """Two approvals read the same last version, and only one of them can write it.

    The race is staged by holding the read still — `_latest_release` answers as it did before
    the winner committed — because that is exactly what the loser of a real race saw, and two
    event loops racing on one SQLite file would prove less about the rule and more about the
    file. Everything after the read is real: the allocation, the insert, and the index that
    refuses it.
    """
    project, credential = await a_claimed_device(db_session)
    session_id = (await _ready_session(db_session, project_id=project.id)).id
    winner = IRRelease(
        session_id=session_id,
        project_id=project.id,
        pericope=P,
        version=1,
        package_sha256="c" * 64,
        packet={},
    )
    db_session.add(winner)
    await db_session.commit()

    async def _as_it_was_before_the_winner(*_args, **_kwargs):
        return None

    monkeypatch.setattr(release_module, "_latest_release", _as_it_was_before_the_winner)
    refused = await client.post(
        f"{PREFIX}/sessions/{session_id}/release", headers=_team(credential)
    )

    assert refused.status_code == 409, refused.text
    db_session.expunge_all()
    numbered = (
        await db_session.execute(
            select(IRRelease.version).where(IRRelease.session_id == session_id)
        )
    ).scalars()
    assert list(numbered) == [1], (
        "o perdedor da corrida não pode deixar uma segunda linha com o mesmo número"
    )


async def test_a_second_conversation_about_one_passage_shares_the_sequence(client, db_session):
    """The number is per pericope and per project, so two sessions do not both mint v1.

    And "unchanged" is measured against that last release, whichever session wrote it: the
    first session approving again after the second one landed is a later draft of the passage,
    not the draft it approved before.
    """
    project, credential = await a_claimed_device(db_session)
    first_session = await _ready_session(db_session, project_id=project.id)
    second_session = await _ready_session(db_session, project_id=project.id)

    first = await client.post(
        f"{PREFIX}/sessions/{first_session.id}/release", headers=_team(credential)
    )
    second = await client.post(
        f"{PREFIX}/sessions/{second_session.id}/release", headers=_team(credential)
    )
    again = await client.post(
        f"{PREFIX}/sessions/{first_session.id}/release", headers=_team(credential)
    )

    assert [first.json()["version"], second.json()["version"]] == [1, 2]
    assert again.json()["version"] == 3
    assert again.json()["package_sha256"] == first.json()["package_sha256"]
    assert again.json()["release_id"] != first.json()["release_id"]


async def test_a_packet_stops_naming_its_release_once_the_passage_moved_on(
    client, db_session, room_app
):
    """The read and the approval answer one question, so they cannot answer it differently.

    A second conversation about the same passage takes v2, and the first session's packet is
    no longer the approved draft of that passage even though nothing in that session changed.
    Naming its v1 anyway would point Marcia's comments at a draft the passage has left, and it
    is the exact case where a session-scoped read and a project-scoped approval disagree.
    """
    project, credential = await a_claimed_device(db_session)
    first_session = await _ready_session(db_session, project_id=project.id)
    second_session = await _ready_session(db_session, project_id=project.id)
    desk = await _facilitator(db_session, room_app, project)

    await client.post(f"{PREFIX}/sessions/{first_session.id}/release", headers=_team(credential))
    named = await client.get(
        f"{PREFIX}/facilitator/sessions/{first_session.id}/release", headers=desk
    )
    await client.post(f"{PREFIX}/sessions/{second_session.id}/release", headers=_team(credential))
    moved_on = await client.get(
        f"{PREFIX}/facilitator/sessions/{first_session.id}/release", headers=desk
    )

    assert named.json()["version"] == 1
    assert moved_on.json()["release_id"] is None, (
        "a v1 deixou de ser o rascunho aprovado da passagem quando a v2 pousou"
    )
    assert moved_on.json()["version"] is None
    assert moved_on.json()["package_sha256"] == named.json()["package_sha256"]


async def test_a_credentialed_tablet_is_refused_by_name_on_a_session_with_no_project(
    client, db_session
):
    """Criterion 5 is about the session, not about who is holding the tablet.

    A room opened on the shared key names no project, and a claimed tablet asking to approve
    it has to be told why it cannot be numbered — 404 would say the conversation is not there,
    which is the one thing that is not true.
    """
    _project, credential = await a_claimed_device(db_session)
    session = await _ready_session(db_session)

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential)
    )

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "RELEASE_WITHOUT_PROJECT"
    assert await _releases_of(db_session, session.id) == []


async def test_no_team_writes_a_release_on_another_teams_passage(client, db_session):
    """There is no team route that reads a release, so writing is the whole of the rule here."""
    project_a, credential_a = await a_claimed_device(db_session, email="a@example.com")
    _project_b, credential_b = await a_claimed_device(db_session, email="b@example.com")
    session = await _ready_session(db_session, project_id=project_a.id)

    stranger = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential_b)
    )
    owner = await client.post(
        f"{PREFIX}/sessions/{session.id}/release", headers=_team(credential_a)
    )

    assert stranger.status_code == 404, stranger.text
    assert owner.status_code == 200, owner.text
    assert [row.version for row in await _releases_of(db_session, session.id)] == [1]


def _run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argv],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
        capture_output=True,
        text=True,
    )


async def _tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
    await engine.dispose()
    return set(names)


async def _scalar(database_url: str, sql: str, params: dict) -> object:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql), params)).scalar_one_or_none()
    await engine.dispose()
    return value


async def _indexes(database_url: str, table: str) -> dict[str, tuple[bool, list[str]]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        found = await conn.run_sync(lambda sync: inspect(sync).get_indexes(table))
    await engine.dispose()
    return {index["name"]: (bool(index["unique"]), list(index["column_names"])) for index in found}


@pytest.fixture()
async def applied_database(tmp_path) -> str:
    """The post-migration schema with rows in it, stamped as applied, ready to be walked.

    Alembic's full chain does not run on SQLite, which is why the sibling migration tests
    build the tables from ``Base.metadata`` and stamp the revision under test rather than
    upgrading into it.

    The session row is what makes the round trip worth running: a downgrade that scratched a
    table it never created would be found here and nowhere else.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_releases_migration.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, comprehension, language,"
                " created_at) VALUES (:id, 'P03', 'in_progress', '[]', 0, '{}', '{}', '{}',"
                " '{}', 'pt', '2026-09-10 09:00:00')"
            ),
            {"id": SEEDED_SESSION},
        )
    await engine.dispose()

    stamped = _run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def test_the_migration_creates_the_table_and_its_unique_index_both_ways(applied_database):
    down = _run_alembic(applied_database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert TABLE not in await _tables(applied_database)

    up = _run_alembic(applied_database, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert TABLE in await _tables(applied_database)
    assert (await _indexes(applied_database, TABLE)).get(UNIQUE_INDEX) == (
        True,
        ["project_id", "pericope", "version"],
    ), "sem o índice único sobre essas colunas a alocação sozinha é a corrida do ENG-639"
    assert (
        await _scalar(
            applied_database,
            "SELECT pericope FROM ir_sessions WHERE id = :id",
            {"id": SEEDED_SESSION},
        )
        == "P03"
    ), "a ida e volta não pode arranhar as tabelas que a migração não criou"
