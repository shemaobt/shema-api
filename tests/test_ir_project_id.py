"""ENG-440 — the room's tables learn whose conversation it was.

A session is anonymous today: nothing in ``ir_sessions`` says which team held it, which is
why the Desk cannot filter by team and why five issues wait on this one.

The link is the device credential ENG-443 issues. It is the only device-to-project link
that exists: ``X-Room-Device`` is a string the app mints for itself and it matches no row
anywhere, so it cannot resolve a project no matter how much code is pointed at it.
"""

import base64

import google_crc32c
import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRTakeKind
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room import questions as room_questions
from app.services.internalization_room import sessions as room_sessions
from app.services.internalization_room import takes as room_takes
from app.services.platform.storage import StoredObject
from tests.baker import make_language, make_project, make_project_user_access, make_user

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
SELF_ISSUED_DEVICE = "a" * 32


class MemoryStore:
    """The bucket seam the store protocols document: an in-memory dict, no GCS.

    Satisfies what both a question's speech store and a take's store need, so these tests
    exercise the real write paths without a bucket.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        data = self.objects.get(key)
        if data is None:
            return None
        return StoredObject(
            size=len(data),
            crc32c=base64.b64encode(google_crc32c.Checksum(data).digest()).decode(),
        )


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


async def a_claimed_device(db: AsyncSession, *, email="fac@example.com"):
    """A device linked to a project. Returns (project, credential)."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    return project, claimed.credential


# Behaviour 1 — a session opened by a linked device carries its project.


async def test_a_session_opened_by_a_linked_device_carries_that_devices_project(client, db_session):
    project, credential = await a_claimed_device(db_session)

    opened = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": "OV"},
    )

    assert opened.status_code == 200, opened.text
    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id == project.id


async def test_a_session_opened_with_an_unrecognised_credential_is_refused(client, db_session):
    """An unrecognised credential is refused, not quietly ignored.

    This case used to assert the opposite — 200, with the session carrying no project —
    and that was right while the credential was only a hint about scoping. ENG-448 makes it
    authentication, and the two readings cannot both hold: ignoring a credential that does
    not resolve is exactly not authenticating by it. A caller presenting a string that
    matches no device is told so, and does not get in on the strength of the shared key it
    also sent.

    The shared key **is** in this request deliberately. Without it the refusal would prove
    nothing new — every request lacking both is already refused — and what is being asserted
    here is that a bad credential is not rescued by a good key.
    """
    await a_claimed_device(db_session)

    opened = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: "b" * 64},
        json={"pericope": "OV"},
    )

    assert opened.status_code == 401, opened.text


# Behaviour 2 — the question inherits the session's project, it does not recompute it.


async def test_a_question_takes_its_project_from_the_session_not_from_the_device(
    db_session,
):
    """Inheritance, so that one source wins if the two ever disagree.

    The device string on the question is unrelated to any claimed device — exactly the
    case where recomputing from the device would silently produce a different answer from
    the session it belongs to.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await room_sessions.create_session(db_session, pericope="OV", project_id=project.id)

    question = await room_questions.raise_question(
        db_session,
        device_id=SELF_ISSUED_DEVICE,
        session_id=session.id,
        pericope=session.pericope,
        project_id=session.project_id,
        audio=b"anything",
        store=MemoryStore(),
    )

    assert question.project_id == project.id


async def test_a_take_takes_its_project_from_the_session(db_session):
    project, _credential = await a_claimed_device(db_session)
    session = await room_sessions.create_session(db_session, pericope="OV", project_id=project.id)

    take = await room_takes.store_take(
        db_session,
        session_id=session.id,
        device_id=SELF_ISSUED_DEVICE,
        pericope=session.pericope,
        project_id=session.project_id,
        kind=IRTakeKind.ENSAIO,
        scope=session.pericope,
        audio=b"audio",
        content_type="audio/m4a",
        store=MemoryStore(),
    )

    assert take.project_id == project.id


# Behaviour 3 — an unclaimed device does the same thing in all three tables.


async def test_a_session_opened_without_a_claimed_device_is_accepted_with_no_project(
    client, db_session
):
    opened = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV"}
    )

    assert opened.status_code == 200, opened.text
    session = await room_sessions.get_session(db_session, opened.json()["session_id"])
    assert session.project_id is None


async def test_a_question_from_a_session_with_no_project_has_no_project(db_session):
    session = await room_sessions.create_session(db_session, pericope="OV")

    question = await room_questions.raise_question(
        db_session,
        device_id=SELF_ISSUED_DEVICE,
        session_id=session.id,
        pericope=session.pericope,
        project_id=session.project_id,
        audio=b"anything",
        store=MemoryStore(),
    )

    assert question.project_id is None


async def test_a_take_from_a_session_with_no_project_has_no_project(db_session):
    session = await room_sessions.create_session(db_session, pericope="OV")

    take = await room_takes.store_take(
        db_session,
        session_id=session.id,
        device_id=SELF_ISSUED_DEVICE,
        pericope=session.pericope,
        project_id=session.project_id,
        kind=IRTakeKind.ENSAIO,
        scope=session.pericope,
        audio=b"audio",
        content_type="audio/m4a",
        store=MemoryStore(),
    )

    assert take.project_id is None


# Behaviour 4 — ir_takes carries project_id and not team_id.


async def test_a_stored_take_answers_with_a_project_and_the_old_name_is_gone(db_session):
    """Asserted by writing and reading back rather than by grepping for a column name.

    A grep would pass on a model that still declares team_id beside project_id; only a
    round trip says which one the write path actually fills.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await room_sessions.create_session(db_session, pericope="OV", project_id=project.id)

    take = await room_takes.store_take(
        db_session,
        session_id=session.id,
        device_id=SELF_ISSUED_DEVICE,
        pericope=session.pericope,
        project_id=session.project_id,
        kind=IRTakeKind.ENSAIO,
        scope=session.pericope,
        audio=b"audio",
        content_type="audio/m4a",
        store=MemoryStore(),
    )
    read_back = await room_takes.take_by_id(db_session, take.id)

    assert read_back.project_id == project.id
    assert not hasattr(read_back, "team_id")


# Behaviour 6 — filtering by project uses the index.


@pytest.mark.parametrize("table", ["ir_sessions", "ir_questions", "ir_takes"])
async def test_filtering_by_project_uses_the_index(db_session, table):
    plan = (
        await db_session.execute(
            text(f"EXPLAIN QUERY PLAN SELECT id FROM {table} WHERE project_id = 'x'")
        )
    ).all()

    rendered = " ".join(str(row) for row in plan)
    assert "project_id" in rendered, f"{table} filtered by project without its index: {rendered}"


# The routes are what hand the project down now, so they are what has to be watched.
# The services take it as an argument, which means a caller can simply not pass it —
# and every service-level test here would still be green while production wrote nulls.


@pytest.fixture()
def stored_in_memory(monkeypatch: pytest.MonkeyPatch):
    """Point both write paths at the in-memory bucket their protocols document."""
    store = MemoryStore()
    monkeypatch.setattr(room_questions, "_store", lambda *a, **k: store)
    monkeypatch.setattr(room_takes, "_store", lambda *a, **k: store)
    return store


async def test_the_question_route_carries_the_sessions_project(
    client, db_session, stored_in_memory
):
    project, credential = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": "OV"},
    )
    session_id = opened.json()["session_id"]

    raised = await client.post(
        f"{PREFIX}/questions",
        params={"session_id": session_id},
        headers={"X-Room-Key": KEY, "X-Room-Device": SELF_ISSUED_DEVICE},
        files={"file": ("q.m4a", b"pergunta", "audio/mp4")},
    )

    assert raised.status_code == 200, raised.text
    question = await room_questions.get_question(db_session, raised.json()["question_id"])
    assert question.project_id == project.id


async def test_the_take_route_carries_the_sessions_project(client, db_session, stored_in_memory):
    project, credential = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": "OV"},
    )
    session_id = opened.json()["session_id"]

    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": SELF_ISSUED_DEVICE},
        data={"kind": "ensaio", "scope": "OV"},
        files={"file": ("t.m4a", b"take", "audio/mp4")},
    )

    assert kept.status_code == 200, kept.text
    take = await room_takes.take_by_id(db_session, kept.json()["take_id"])
    assert take.project_id == project.id


async def test_the_back_translation_chunk_route_carries_the_sessions_project(
    client, db_session, stored_in_memory, monkeypatch
):
    """The chunk path, which is the one that runs once per stretch with the team waiting.

    The take is stored before the transcriber is called, so stubbing the transcriber does
    not stub the thing under test — it only keeps a network call out of a unit test.
    """
    from app.api.internalization_room import back_translation as bt_api

    async def _heard(*_a, **_k) -> str:
        return "told back"

    monkeypatch.setattr(bt_api, "heard", _heard)

    project, credential = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY, DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": "OV"},
    )
    session_id = opened.json()["session_id"]
    rehearsal = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": SELF_ISSUED_DEVICE},
        data={"kind": "ensaio", "scope": "OV"},
        files={"file": ("t.m4a", b"ensaio", "audio/mp4")},
    )

    sent = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": SELF_ISSUED_DEVICE},
        data={
            "retelling": "false",
            "take_id": rehearsal.json()["take_id"],
            "starts_ms": "0",
            "ends_ms": "9000",
        },
        files={"file": ("c.m4a", b"chunk", "audio/mp4")},
    )

    assert sent.status_code == 200, sent.text
    stored = await room_takes.takes_of(db_session, session_id)
    assert stored, "the chunk was not kept"
    assert all(take.project_id == project.id for take in stored)
