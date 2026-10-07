"""The hand: what the team asks reaches a person, and the answer finds them again.

Until now the app stopped the recorder, threw the audio away, and drew a knot on the necklace
anyway — telling a team that cannot read that their question had been received. Everything
here exists so that knot stands for something.
"""

from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import NothingToHear, ReplyMovedOn, ValidationError
from app.db.models.auth import User
from app.db.models.internalization_room import IRCoverageEvent, IRQuestion, IRQuestionStatus
from app.services.auth.issue_tokens import issue_tokens
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room import questions as service
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room.voice_handles import team_audio_url
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.release_harness import a_claimed_device

DEVICE = "tablet-da-equipe-1"
OTHER_DEVICE = "tablet-de-outra-equipe"
TABLET_B = "tablet-da-equipe-2"
TABLET_OF_ANOTHER_TEAM = "tablet-da-equipe-vizinha"
OV = "OV-Ruth"
QUESTIONS = "/api/internalization-room/questions"
FACILITATOR_QUESTIONS = "/api/internalization-room/facilitator/questions"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


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


async def _raise_the_hand(client: httpx.AsyncClient, *, session_id: str) -> str:
    response = await client.post(
        QUESTIONS,
        params={"session_id": session_id},
        files={"file": ("pergunta.m4a", b"a equipe levantou a mao", "audio/mp4")},
    )
    assert response.status_code == 200, response.text
    return response.json()["question_id"]


async def _coverage_events(db: AsyncSession, session_id: str) -> list[IRCoverageEvent]:
    result = await db.execute(
        select(IRCoverageEvent).where(IRCoverageEvent.session_id == session_id)
    )
    return list(result.scalars().all())


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
    waiting = await service.replies_for(db_session, DEVICE, project_id=None)

    assert [q.id for q in waiting] == [question.id]
    assert store.objects[waiting[0].reply_audio_key or ""] == b"o facilitador respondeu"


async def test_an_answer_never_reaches_another_team(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    assert await service.replies_for(db_session, OTHER_DEVICE, project_id=None) == []


async def test_an_answer_survives_the_session_it_was_asked_in(db_session: AsyncSession) -> None:
    """A facilitator may answer hours later, when that passage is long closed."""
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    waiting = await service.replies_for(db_session, DEVICE, project_id=None)

    assert waiting[0].session_id == "sessao-1"
    assert len(waiting) == 1


async def test_a_reply_is_offered_once_and_not_again(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="user-1", store=store
    )

    await service.mark_heard(db_session, question)

    assert await service.replies_for(db_session, DEVICE, project_id=None) == []


async def test_resolved_elsewhere_never_arrives_in_the_app(db_session: AsyncSession) -> None:
    """The facilitator will speak to the team directly, so nothing should be waiting."""
    team, facilitator = await _a_team_and_its_facilitator(db_session)
    store = MemoryStore()
    question = await _raise(db_session, store, project_id=team.id)

    await service.resolve_elsewhere(db_session, question, answered_by="user-1")

    assert question.status is IRQuestionStatus.RESOLVED
    assert await service.replies_for(db_session, DEVICE, project_id=None) == []
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

    waiting = await service.replies_for(db_session, DEVICE, project_id=None)
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

    waiting = await service.replies_for(db_session, DEVICE, project_id=None)
    assert [q.id for q in waiting] == [question.id]


async def _served_reply(client: httpx.AsyncClient, question_id: str) -> str | None:
    response = await client.get(f"{QUESTIONS}/replies")
    assert response.status_code == 200, response.text
    served = {r["question_id"]: r["audio_url"] for r in response.json()["replies"]}
    return served.get(question_id)


async def test_a_reply_recorded_again_while_the_first_played_is_still_offered(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"primeira", answered_by="fac", store=store
    )
    first = await _served_reply(room_client, question.id)
    await service.answer_with_voice(
        db_session, question, audio=b"segunda", answered_by="fac", store=store
    )
    second = await _served_reply(room_client, question.id)

    response = await room_client.post(f"{QUESTIONS}/{question.id}/heard", json={"audio_url": first})

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "REPLY_MOVED_ON"
    assert second is not None and second != first
    assert await _served_reply(room_client, question.id) == second, (
        "o tablet terminava a primeira e marcava a pergunta, e o servidor carimbava a "
        "segunda, que ninguém ouviu — a correção sumia do próximo pull"
    )


async def test_the_reply_the_tablet_heard_is_the_current_one_and_leaves_the_pull(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )
    current = await _served_reply(room_client, question.id)

    response = await room_client.post(
        f"{QUESTIONS}/{question.id}/heard", json={"audio_url": current}
    )

    assert response.status_code == 200, response.text
    assert await _served_reply(room_client, question.id) is None


async def test_a_tablet_that_names_no_reply_still_marks_the_question_heard(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    response = await room_client.post(f"{QUESTIONS}/{question.id}/heard")

    assert response.status_code == 200, response.text
    assert await _served_reply(room_client, question.id) is None, (
        "o app em campo não manda corpo nenhum; recusar o POST sem o campo faria toda "
        "resposta voltar a tocar para sempre"
    )


async def test_a_reply_recorded_again_between_the_read_and_the_stamp_is_not_stamped(
    db_session: AsyncSession,
) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"primeira", answered_by="fac", store=store
    )
    heard = team_audio_url(question.reply_audio_key or "")
    await db_session.execute(
        text("UPDATE ir_questions SET reply_audio_key = :key WHERE id = :id"),
        {
            "key": f"internalization-room/questions/{question.id}/resposta-segunda.m4a",
            "id": question.id,
        },
    )
    await db_session.commit()

    with pytest.raises(ReplyMovedOn):
        await service.mark_heard(db_session, question, audio_url=heard)

    stamped = await db_session.execute(
        text("SELECT heard_at FROM ir_questions WHERE id = :id"), {"id": question.id}
    )
    assert stamped.scalar_one() is None, (
        "a comparação lia a linha antes da segunda resposta entrar, e o UPDATE sem condição "
        "carimbava a segunda do mesmo jeito"
    )


async def test_a_question_of_another_project_is_not_marked_heard_on_a_matching_device_id(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email="owner-heard@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger-heard@example.com"
    )
    store = MemoryStore()
    question = await _raise(db_session, store, project_id=owner.id)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    refused = await room_client.post(
        f"{QUESTIONS}/{question.id}/heard", headers={"X-Device-Credential": stranger_credential}
    )

    assert refused.status_code == 404, refused.text[:300]
    await db_session.refresh(question)
    assert question.heard_at is None, (
        "o id do aparelho é declarado pelo próprio tablet; a rota do áudio ao lado já "
        "conferia o projeto do credencial, e esta marcava a pergunta de outra equipe como "
        "ouvida com o mesmo id de aparelho"
    )

    allowed = await room_client.post(
        f"{QUESTIONS}/{question.id}/heard", headers={"X-Device-Credential": owner_credential}
    )
    assert allowed.status_code == 200, allowed.text[:300]


async def test_a_question_of_another_project_is_not_listed_to_a_matching_device_id(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email="owner-list@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger-list@example.com"
    )
    store = MemoryStore()
    question = await _raise(db_session, store, project_id=owner.id)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    refused = await room_client.get(
        f"{QUESTIONS}/replies", headers={"X-Device-Credential": stranger_credential}
    )
    allowed = await room_client.get(
        f"{QUESTIONS}/replies", headers={"X-Device-Credential": owner_credential}
    )

    assert refused.status_code == 200, refused.text[:300]
    assert refused.json()["replies"] == [], (
        "o id do aparelho é declarado pelo próprio tablet; o áudio e a marca de ouvida já "
        "conferiam o projeto do credencial, e a lista entregava a pergunta respondida de "
        "outra equipe com o mesmo id de aparelho"
    )
    assert [r["question_id"] for r in allowed.json()["replies"]] == [question.id]


async def test_a_question_that_names_no_project_is_still_listed_to_a_claimed_device(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    _team, credential = await a_claimed_device(db_session, email="unowned-list@example.com")
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    response = await room_client.get(
        f"{QUESTIONS}/replies", headers={"X-Device-Credential": credential}
    )

    assert [r["question_id"] for r in response.json()["replies"]] == [question.id], (
        "a maioria das perguntas de hoje nasce de uma sessão da chave compartilhada e não "
        "nomeia projeto; exigir igualdade esvaziava a fila de quem já tem credencial"
    )


async def test_the_shared_key_still_lists_a_project_question_by_device(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team, _credential = await a_claimed_device(db_session, email="shared-list@example.com")
    store = MemoryStore()
    question = await _raise(db_session, store, project_id=team.id)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )

    assert await _served_reply(room_client, question.id) is not None, (
        "a chave compartilhada não nomeia aparelho nem projeto, e a fila dela é por aparelho "
        "como sempre foi; conferir projeto ali a deixaria sem as respostas que já recebe"
    )


async def test_a_question_nobody_answered_cannot_be_heard(db_session: AsyncSession) -> None:
    question = await _raise(db_session, MemoryStore())

    with pytest.raises(NothingToHear):
        await service.mark_heard(db_session, question)

    await db_session.refresh(question)
    assert question.heard_at is None, (
        "o UPDATE sem condição carimbava heard_at numa pergunta aberta, e a Mesa mostrava "
        "'ouvida' num cartão que ninguém respondeu"
    )


async def test_a_question_nobody_answered_answers_the_tablet_with_its_own_code(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    question = await _raise(db_session, MemoryStore())

    response = await room_client.post(f"{QUESTIONS}/{question.id}/heard")

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "NOTHING_TO_HEAR"


async def test_a_second_mark_keeps_the_first_listen(db_session: AsyncSession) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )
    heard = team_audio_url(question.reply_audio_key or "")
    first = (await service.mark_heard(db_session, question, audio_url=heard)).heard_at
    assert first is not None

    again = await service.mark_heard(db_session, question, audio_url=heard)
    bare = await service.mark_heard(db_session, question)

    assert again.heard_at == first, "a marca repetida sobrescrevia o instante da primeira escuta"
    assert bare.heard_at == first


async def test_a_repeated_mark_for_the_current_reply_is_agreement(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    store = MemoryStore()
    question = await _raise(db_session, store)
    await service.answer_with_voice(
        db_session, question, audio=b"resposta", answered_by="fac", store=store
    )
    current = await _served_reply(room_client, question.id)
    await room_client.post(f"{QUESTIONS}/{question.id}/heard", json={"audio_url": current})

    response = await room_client.post(
        f"{QUESTIONS}/{question.id}/heard", json={"audio_url": current}
    )

    assert response.status_code == 200, response.text


async def test_a_panorama_question_keeps_the_sessions_own_pericope(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    """A hand raised on the Book Panorama screen names OV-Ruth, never a fallback or a book id
    stripped of its prefix (ENG-802)."""
    session = await session_service.create_session(db_session, pericope="OV")
    assert session.pericope == OV

    question_id = await _raise_the_hand(room_client, session_id=session.id)

    question = await db_session.get(IRQuestion, question_id)
    assert question is not None
    assert question.pericope == OV
    assert question.pericope == session.pericope


async def test_raising_a_hand_in_the_panorama_touches_no_coverage(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    """The boundary this half of ENG-779 does not move: the hand reads no map, reads the
    coverage events once (the SELECT behind `last_bead_moved_in_session`, the anchor that ENG-456
    added) and writes none, so the session's necklace is exactly what it was before the question."""
    session = await session_service.create_session(db_session, pericope="OV")
    state_before = dict(session.coverage_state)
    events_before = await _coverage_events(db_session, session.id)

    await _raise_the_hand(room_client, session_id=session.id)

    await db_session.refresh(session)
    assert session.coverage_state == state_before
    assert await _coverage_events(db_session, session.id) == events_before


@dataclass(frozen=True)
class _TeamWithTwoTablets:
    team_id: str
    facilitator: User
    tablet_a: dict[str, str]
    tablet_b: dict[str, str]


def _tablet(device: str, credential: str) -> dict[str, str]:
    return {"X-Room-Device": device, "X-Device-Credential": credential}


async def _a_team_with_two_tablets(db: AsyncSession, *, email: str) -> _TeamWithTwoTablets:
    facilitator = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    team = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, team.id, facilitator.id, role=ProjectRole.FACILITATOR)
    credentials = []
    for _ in range(2):
        minted = await create_device(db)
        claimed = await claim_device_as_facilitator(
            db, user=facilitator, code=minted.claim_code, project_id=team.id
        )
        credentials.append(claimed.credential)
    return _TeamWithTwoTablets(
        team_id=team.id,
        facilitator=facilitator,
        tablet_a=_tablet(DEVICE, credentials[0]),
        tablet_b=_tablet(TABLET_B, credentials[1]),
    )


async def _a_reply_to_a_question_asked_on(
    db: AsyncSession, *, device: str, project_id: str | None
) -> IRQuestion:
    store = MemoryStore()
    question = await _raise(db, store, device=device, project_id=project_id)
    return await service.answer_with_voice(
        db, question, audio=b"resposta da facilitadora", answered_by="fac", store=store
    )


async def _listed_on(client: httpx.AsyncClient, tablet: dict[str, str]) -> list[str]:
    response = await client.get(f"{QUESTIONS}/replies", headers=tablet)
    assert response.status_code == 200, response.text[:300]
    return [reply["question_id"] for reply in response.json()["replies"]]


async def _played_to_the_end_on(
    client: httpx.AsyncClient, tablet: dict[str, str], question: IRQuestion
) -> httpx.Response:
    return await client.post(
        f"{QUESTIONS}/{question.id}/heard",
        headers=tablet,
        json={"audio_url": team_audio_url(question.reply_audio_key or "")},
    )


async def test_a_reply_to_a_question_asked_on_tablet_a_is_listed_on_tablet_b_of_the_team(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-lista@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )

    assert await _listed_on(room_client, team.tablet_b) == [reply.id], (
        "a resposta é da equipe: a equipe perguntou no tablet A e agora trabalha no B, e a "
        "resposta nunca chegava"
    )


async def test_a_reply_played_to_the_end_on_tablet_b_is_no_longer_unheard_on_tablet_a(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-ouviu@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )

    heard = await _played_to_the_end_on(room_client, team.tablet_b, reply)

    assert heard.status_code == 200, heard.text[:300]
    assert await _listed_on(room_client, team.tablet_a) == [], (
        "ouvida até o fim em um tablet da equipe, a resposta conta como ouvida para a equipe "
        "inteira"
    )


async def test_a_tablet_of_another_team_never_lists_the_reply(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-dona@example.com")
    _neighbour, credential = await a_claimed_device(db_session, email="vizinha-lista@example.com")
    await _a_reply_to_a_question_asked_on(db_session, device=DEVICE, project_id=team.team_id)

    assert await _listed_on(room_client, _tablet(TABLET_OF_ANOTHER_TEAM, credential)) == [], (
        "a resposta é da equipe que perguntou; um tablet de outra equipe nunca a vê"
    )


async def test_a_tablet_of_another_team_cannot_mark_the_reply_heard(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-marca@example.com")
    _neighbour, credential = await a_claimed_device(db_session, email="vizinha-marca@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )

    refused = await _played_to_the_end_on(
        room_client, _tablet(TABLET_OF_ANOTHER_TEAM, credential), reply
    )

    assert refused.status_code == 404, refused.text[:300]
    assert await _listed_on(room_client, team.tablet_a) == [reply.id], (
        "outra equipe não ouve pela equipe que perguntou; a resposta segue não ouvida"
    )


async def test_a_reply_nobody_marked_heard_stays_listed_on_both_tablets_of_the_team(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-metade@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )
    await _listed_on(room_client, team.tablet_b)

    assert await _listed_on(room_client, team.tablet_a) == [reply.id]
    assert await _listed_on(room_client, team.tablet_b) == [reply.id], (
        "tocada pela metade e parada, a resposta segue não ouvida nos dois tablets"
    )


async def test_the_desk_shows_a_reply_heard_on_another_tablet_as_heard_by_the_team(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-mesa@example.com")
    await grant_facilitator_app_role(db_session, team.facilitator.id)
    access, _refresh = await issue_tokens(db_session, team.facilitator)
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )
    heard = await _played_to_the_end_on(room_client, team.tablet_b, reply)
    assert heard.status_code == 200, heard.text[:300]

    desk = await room_client.get(
        FACILITATOR_QUESTIONS,
        params={"team_id": team.team_id},
        headers={"Authorization": f"Bearer {access}"},
    )

    assert desk.status_code == 200, desk.text[:300]
    [card] = desk.json()["questions"]
    assert card["heard_at"] is not None, (
        "a Mesa mostra «✓ ouvida pela equipe» quando qualquer tablet da equipe ouviu, não só "
        "o que perguntou"
    )


async def test_a_reply_already_heard_on_the_asking_tablet_stays_heard_for_the_whole_team(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-antiga@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )
    await service.mark_heard(db_session, reply)

    assert await _listed_on(room_client, team.tablet_b) == [], (
        "uma resposta já ouvida no tablet que perguntou continua ouvida para a equipe inteira"
    )
    assert await _listed_on(room_client, team.tablet_a) == [], (
        "a marca guardada antes de a resposta ser da equipe não muda"
    )


async def test_a_question_with_no_team_stays_with_the_tablet_that_asked(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-sem-time@example.com")
    reply = await _a_reply_to_a_question_asked_on(db_session, device=DEVICE, project_id=None)

    assert await _listed_on(room_client, team.tablet_b) == [], (
        "uma pergunta sem equipe não é de equipe nenhuma; só o tablet que perguntou a recebe"
    )
    refused = await _played_to_the_end_on(room_client, team.tablet_b, reply)
    assert refused.status_code == 404, refused.text[:300]
    assert await _listed_on(room_client, team.tablet_a) == [reply.id], (
        "o tablet que perguntou segue recebendo a resposta da pergunta sem equipe"
    )


async def test_a_caller_with_no_team_lists_only_the_replies_to_its_own_devices_questions(
    db_session: AsyncSession, room_client: httpx.AsyncClient
) -> None:
    team = await _a_team_with_two_tablets(db_session, email="equipe-chave@example.com")
    reply = await _a_reply_to_a_question_asked_on(
        db_session, device=DEVICE, project_id=team.team_id
    )

    assert await _listed_on(room_client, {"X-Room-Device": TABLET_B}) == [], (
        "a chave compartilhada não nomeia equipe; a fila dela segue por aparelho"
    )
    assert await _listed_on(room_client, {"X-Room-Device": DEVICE}) == [reply.id], (
        "pela chave compartilhada, o aparelho que perguntou segue recebendo a resposta"
    )
