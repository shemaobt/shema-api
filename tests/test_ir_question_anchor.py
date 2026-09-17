"""ENG-456 — the server anchors a raised question to the bead the coverage last moved.

No tablet in the field names an element key: the app has no element identity to send. What
it does carry, off the request, is the tracker `apply_coverage` already writes one event per
transition into. A hand raised with no `element_key` is anchored here to whichever bead this
session's own history moved last, so the facilitator's card names it without the app ever
learning a key (ENG-543 stands).

All six cases go in through the room's `POST /questions` and read back through the
facilitator's `GET /facilitator/questions`, exactly the way `test_internalization_room_
questions.py` and `test_facilitator_questions_inbox.py` already do. Coverage is moved through
`apply_coverage`, the same function `record_transitions` writes real rows for — never a row
built by hand — so the anchor answers what the tracker actually recorded.
"""

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import questions as service
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.labels import LabelledElement, labelled_elements
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

#: A fully translated passage — pt, en and es all carry real text for every bead — because
#: cases 1 and 2 assert the card in all three languages. `P03`, which the neighbouring test
#: files use, is one of the ten the catalogue has only in English (see
#: `test_ir_question_completeness.py`), so it cannot carry that assertion.
PERICOPE = "P01"

DEVICE = "tablet-da-equipe-1"
SURFACED = CoverageStatus.SURFACED.value
ENGAGED = CoverageStatus.ENGAGED.value

QUESTIONS = "/api/internalization-room/questions"
INBOX = "/api/internalization-room/facilitator/questions"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


def _label(key: str) -> LabelledElement:
    return next(e for e in labelled_elements(PERICOPE) if e.key == key)


def _labels(card: dict) -> tuple[str | None, str | None, str | None]:
    return (card["element_label_pt"], card["element_label_en"], card["element_label_es"])


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_team_and_its_facilitator(db: AsyncSession) -> tuple[object, dict[str, str]]:
    language = await make_language(db, name="Terena", code="tqe")
    team = await make_project(db, language.id, name="Equipe Terena")
    facilitator = await make_user(db, email="facilitadora@example.com")
    await make_project_user_access(db, team.id, facilitator.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, facilitator.id)
    return team, await auth_header(db, facilitator)


@pytest.fixture()
async def room_client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The tablet's side of the router — real HTTP, real SQLite, a faked speech store."""
    from app.api.internalization_room.questions import router as questions_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(
        get_settings(), "internalization_room_api_key", "chave-da-sala", raising=False
    )
    monkeypatch.setattr(service, "_store", lambda *a, **kw: MemoryStore())

    async def broken(audio: bytes, *, language: str, mime_type: str) -> str:
        raise TypeError("o transcritor nao esta sob teste aqui")

    monkeypatch.setattr(service, "transcribe_speech", broken)

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        headers={"X-Room-Key": "chave-da-sala", "X-Room-Device": DEVICE},
    ) as client:
        yield client


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
    """The facilitator's side of the same router, signed in as a person."""
    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


async def _raise(
    client: httpx.AsyncClient, *, session_id: str, element_key: str | None = None
) -> str:
    data = {} if element_key is None else {"element_key": element_key}
    response = await client.post(
        QUESTIONS,
        params={"session_id": session_id},
        data=data,
        files={"file": ("pergunta.m4a", b"a equipe levantou a mao", "audio/mp4")},
    )
    assert response.status_code == 200, response.text
    return response.json()["question_id"]


async def _card(client: httpx.AsyncClient, headers: dict[str, str], question_id: str) -> dict:
    response = await client.get(INBOX, headers=headers)
    assert response.status_code == 200, response.text
    (found,) = [q for q in response.json()["questions"] if q["question_id"] == question_id]
    return found


async def test_the_card_names_the_bead_the_room_was_on(
    db_session: AsyncSession, room_client, desk_client
) -> None:
    """Case 1 — a session that moved one bead, and a hand raised with no element_key."""
    team, headers = await a_team_and_its_facilitator(db_session)
    session = await session_service.create_session(
        db_session, pericope=PERICOPE, project_id=team.id
    )
    bead = element_keys(PERICOPE)[0]
    await session_service.apply_coverage(db_session, session.id, {bead: SURFACED})

    question_id = await _raise(room_client, session_id=session.id)

    card = await _card(desk_client, headers, question_id)
    expected = _label(bead)
    assert _labels(card) == (expected.label_pt, expected.label_en, expected.label_es)


async def test_the_most_recent_move_wins(
    db_session: AsyncSession, room_client, desk_client
) -> None:
    """Case 2 — separates "most recently moved" from "first moved" and from "furthest"."""
    team, headers = await a_team_and_its_facilitator(db_session)
    session = await session_service.create_session(
        db_session, pericope=PERICOPE, project_id=team.id
    )
    a, b = element_keys(PERICOPE)[:2]
    await session_service.apply_coverage(db_session, session.id, {a: SURFACED})
    await session_service.apply_coverage(db_session, session.id, {b: SURFACED})

    first_question = await _raise(room_client, session_id=session.id)
    first_card = await _card(desk_client, headers, first_question)
    assert first_card["element_label_en"] == _label(b).label_en

    await session_service.apply_coverage(db_session, session.id, {a: ENGAGED})
    second_question = await _raise(room_client, session_id=session.id)
    second_card = await _card(desk_client, headers, second_question)
    assert second_card["element_label_en"] == _label(a).label_en


async def test_no_move_no_anchor(db_session: AsyncSession, room_client, desk_client) -> None:
    """Case 3 — regression lock: a session whose coverage never moved anchors nothing.

    Passes against the untouched worktree already; kept as a lock rather than a target.
    """
    team, headers = await a_team_and_its_facilitator(db_session)
    session = await session_service.create_session(
        db_session, pericope=PERICOPE, project_id=team.id
    )

    question_id = await _raise(room_client, session_id=session.id)

    card = await _card(desk_client, headers, question_id)
    assert _labels(card) == (None, None, None)


async def test_another_sessions_bead_is_not_borrowed(
    db_session: AsyncSession, room_client, desk_client
) -> None:
    """Case 4 — only this session's own events count, even for the same team and passage."""
    team, headers = await a_team_and_its_facilitator(db_session)
    a, b, c = element_keys(PERICOPE)[:3]
    s1 = await session_service.create_session(db_session, pericope=PERICOPE, project_id=team.id)
    s2 = await session_service.create_session(db_session, pericope=PERICOPE, project_id=team.id)
    await session_service.apply_coverage(db_session, s1.id, {a: SURFACED})

    first_question = await _raise(room_client, session_id=s2.id)
    first_card = await _card(desk_client, headers, first_question)
    assert _labels(first_card) == (None, None, None), (
        "a pergunta de S2 herdou o bead que S1 moveu, e cada sessao tem sua propria historia"
    )

    await session_service.apply_coverage(db_session, s2.id, {b: SURFACED})
    await session_service.apply_coverage(db_session, s1.id, {c: SURFACED})
    second_question = await _raise(room_client, session_id=s2.id)
    second_card = await _card(desk_client, headers, second_question)
    assert second_card["element_label_en"] == _label(b).label_en, (
        "S1 moveu C depois, mas C nao e desta sessao"
    )


async def test_a_key_the_client_sends_is_kept(
    db_session: AsyncSession, room_client, desk_client
) -> None:
    """Case 5 — regression lock: a key the app sends is more specific than the anchor.

    Passes against the untouched worktree already, because the form field is a straight
    passthrough today; kept as a lock so the anchor never overrides an explicit key.
    """
    team, headers = await a_team_and_its_facilitator(db_session)
    a, b = element_keys(PERICOPE)[:2]
    session = await session_service.create_session(
        db_session, pericope=PERICOPE, project_id=team.id
    )
    await session_service.apply_coverage(db_session, session.id, {a: SURFACED})

    question_id = await _raise(room_client, session_id=session.id, element_key=b)

    card = await _card(desk_client, headers, question_id)
    assert card["element_label_en"] == _label(b).label_en


async def test_the_anchor_and_the_tracker_cannot_drift(
    db_session: AsyncSession, room_client, desk_client
) -> None:
    """Case 6 — the issue's third criterion in behavioural form.

    One merge reports two beads; only one of them actually rises in rank, the way
    `test_a_merge_that_changes_nothing_writes_no_event` drives `record_transitions`. The card
    must name the bead that rose, not the one merely present in the merge's `after` dict.
    """
    team, headers = await a_team_and_its_facilitator(db_session)
    x, y = element_keys(PERICOPE)[:2]
    session = await session_service.create_session(
        db_session, pericope=PERICOPE, project_id=team.id
    )
    await session_service.apply_coverage(db_session, session.id, {x: ENGAGED})

    # x is reported again at the same status it already holds — no rise, no event — while y
    # rises for the first time and does get one.
    await session_service.apply_coverage(db_session, session.id, {x: ENGAGED, y: SURFACED})

    question_id = await _raise(room_client, session_id=session.id)

    card = await _card(desk_client, headers, question_id)
    assert card["element_label_en"] == _label(y).label_en, (
        "o cartao nomeou o bead apenas relatado no merge, nao o que realmente subiu de rank"
    )
