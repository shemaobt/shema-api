"""The hand: what the team asks reaches a person, and the answer finds them again.

Until now the app stopped the recorder, threw the audio away, and drew a knot on the necklace
anyway — telling a team that cannot read that their question had been received. Everything
here exists so that knot stands for something.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRQuestionStatus
from app.services.internalization_room import questions as service
from tests.baker import make_language, make_project, make_project_user_access, make_user

DEVICE = "tablet-da-equipe-1"
OTHER_DEVICE = "tablet-de-outra-equipe"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


async def _raise(
    db: AsyncSession, store: MemoryStore, *, device: str = DEVICE, project_id: str | None = None
):
    return await service.raise_question(
        db,
        device_id=device,
        session_id="sessao-1",
        pericope="P03",
        audio=b"a equipe perguntou",
        project_id=project_id,
        store=store,
    )


async def _a_team_and_its_facilitator(db: AsyncSession):
    """A team and the person the inbox answers to.

    The queue is read by somebody now: since ENG-452 a question belongs to a team and is
    reachable only by whoever facilitates it, so a test asking "is it still waiting" has to
    say who is waiting on it.
    """
    language = await make_language(db, name="Terena", code="tqe")
    team = await make_project(db, language.id, name="Equipe Terena")
    facilitator = await make_user(db, email="facilitadora@example.com")
    await make_project_user_access(db, team.id, facilitator.id, role=ProjectRole.FACILITATOR)
    return team, facilitator


async def _still_open(db: AsyncSession, facilitator) -> list[str]:
    page = await service.inbox_page(db, facilitator, wanted=IRQuestionStatus.OPEN)
    return [question.id for question in page.questions]


async def test_the_question_audio_is_kept_not_dropped(db_session: AsyncSession) -> None:
    store = MemoryStore()

    question = await _raise(db_session, store)

    assert store.objects[question.audio_key] == b"a equipe perguntou"
    assert question.status is IRQuestionStatus.OPEN


async def test_a_question_with_no_audio_is_refused(db_session: AsyncSession) -> None:
    """Better to fail loudly than to draw a knot for silence."""
    with pytest.raises(ValidationError):
        await service.raise_question(
            db_session,
            device_id=DEVICE,
            session_id="sessao-1",
            pericope="P03",
            audio=b"",
            store=MemoryStore(),
        )


async def test_it_waits_in_the_queue_until_a_person_takes_it(db_session: AsyncSession) -> None:
    team, facilitator = await _a_team_and_its_facilitator(db_session)
    question = await _raise(db_session, MemoryStore(), project_id=team.id)

    assert await _still_open(db_session, facilitator) == [question.id]


async def test_an_answer_reaches_the_team_that_asked(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)

    await service.answer_with_voice(
        db_session, question, audio=b"o facilitador respondeu", answered_by="user-1", store=store
    )
    waiting = await service.replies_for(db_session, DEVICE)

    assert [q.id for q in waiting] == [question.id]
    assert store.objects[waiting[0].reply_audio_key or ""] == b"o facilitador respondeu"


async def test_an_answer_never_reaches_another_team(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    assert await service.replies_for(db_session, OTHER_DEVICE) == []


async def test_an_answer_survives_the_session_it_was_asked_in(db_session: AsyncSession) -> None:
    """A facilitator may answer hours later, when that passage is long closed."""
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    waiting = await service.replies_for(db_session, DEVICE)

    assert waiting[0].session_id == "sessao-1"
    assert len(waiting) == 1


async def test_a_reply_is_offered_once_and_not_again(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    await service.mark_heard(db_session, question)

    assert await service.replies_for(db_session, DEVICE) == []


async def test_resolved_elsewhere_never_arrives_in_the_app(db_session: AsyncSession) -> None:
    """The facilitator will speak to the team directly, so nothing should be waiting."""
    team, facilitator = await _a_team_and_its_facilitator(db_session)
    store = MemoryStore()
    question = await _raise(db_session, store, project_id=team.id)

    await service.resolve_elsewhere(db_session, question, answered_by="user-1")

    assert question.status is IRQuestionStatus.RESOLVED
    assert await service.replies_for(db_session, DEVICE) == []
    assert await _still_open(db_session, facilitator) == []


async def test_who_answered_is_recorded(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)

    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-42", store=store
    )

    assert question.answered_by == "user-42"
    assert question.answered_at is not None


async def test_a_corrected_reply_reaches_a_team_that_heard_the_first(
    db_session: AsyncSession,
) -> None:
    """The facilitator realises they were wrong and records the right answer."""
    store = MemoryStore()
    question = await service.raise_question(
        db_session,
        device_id=DEVICE,
        session_id="s1",
        pericope="P01",
        audio=b"pergunta",
        store=store,
    )
    await service.answer_with_voice(
        db_session, question, audio=b"errado", answered_by="fac", store=store
    )
    await service.mark_heard(db_session, question)

    await service.answer_with_voice(
        db_session, question, audio=b"certo", answered_by="fac", store=store
    )

    waiting = await service.replies_for(db_session, DEVICE)
    assert [q.id for q in waiting] == [question.id], (
        "o heard_at da primeira filtrava a correção para sempre, e a equipe ficava com a "
        "renderização errada sem meio de descobrir"
    )


async def test_resolving_does_not_bury_a_reply_nobody_has_heard(
    db_session: AsyncSession,
) -> None:
    store = MemoryStore()
    question = await service.raise_question(
        db_session,
        device_id=DEVICE,
        session_id="s1",
        pericope="P01",
        audio=b"pergunta",
        store=store,
    )
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    with pytest.raises(ValidationError):
        await service.resolve_elsewhere(db_session, question, answered_by="fac")

    waiting = await service.replies_for(db_session, DEVICE)
    assert [q.id for q in waiting] == [question.id]
