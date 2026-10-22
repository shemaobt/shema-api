"""ENG-609 — a facilitator says "I went", and the room stops asking.

`NEEDS_PERSON` had one way out and it was the team's: a turn that lands. So the halt the
facilitator actually resolves — they walk over, they help, the team is not ready to speak
yet — stayed on the queue, and the tablet went on halting. The Desk could find the room
(ENG-605/#313) and could do nothing about it.

The other half is that the two halts were one word. A room stopped by its own hard stop
cannot go on; a room that has retold three times is *asking for a witness* and nothing is
refused. Both wrote `needs_person`, and no reader could tell which it was looking at.

Everything here is read through a route — the tablet's state, the facilitator's queue, the
team's history. The mark and the undo are HTTP calls by a real facilitator, and the halts are
raised the three ways the room actually raises them: the tablet's own route, the retell
budget.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.exceptions import PassageClosed
from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTakeKind
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from app.services.platform.storage import StoredObject
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    a_language,
    grant_facilitator_app_role,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.device_harness import a_linked_tablet
from tests.hard_stretch_harness import a_new_recording
from tests.hard_stretch_harness import row as the_row
from tests.turn_harness import the_room_agent_is

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
DEVICE = "tablet-da-equipe-1"

P = "P03"
ENGAGED = CoverageStatus.ENGAGED.value
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
FIRST_QUESTION = "Quem aparece nesta parte?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
EXCERPT = "Noemi voltou"

BLOCKING = "blocking"
WARNING = "warning"


# --- the room's voice, its ears, and its bucket -------------------------------------------


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio",
        mime_type="audio/mpeg",
        etag="e",
        cached=False,
        key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
    )
    return entry, False


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, facilitator_a: Facilitator
):
    """The room and the Desk on one app, because a halt is read from both sides.

    The synthesiser, the transcriber and the take bucket are the neighbours' fakes and no
    assertion here is about them: they stand in for the three services this slice has to
    reach through to get at a halt, and nothing more.
    """
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)

    async def _heard_speech(audio: bytes, **_: Any) -> Any:
        from app.services.internalization_room.hearing import HeardSpeech

        return HeardSpeech(text=TEAM_ANSWER)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard_speech)

    async def _silence(*_: Any, **__: Any) -> str:
        return ""

    monkeypatch.setattr(bt_api, "heard", _silence)
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: _MemoryStore())

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=DESK)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    tablet = await a_linked_tablet(db_session, team_id=facilitator_a.team_id)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=tablet.headers
    ) as c:
        yield c


# --- the two facilitators and their teams -------------------------------------------------


class Facilitator:
    """Somebody who holds the room's facilitator role and facilitates exactly one team."""

    def __init__(self, user_id: str, team_id: str, team_name: str, headers: dict[str, str]) -> None:
        self.id = user_id
        self.team_id = team_id
        self.team_name = team_name
        self.headers = headers


async def a_facilitator(db: AsyncSession, *, email: str, team_name: str) -> Facilitator:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=email)
    language = await a_language(db, name=f"Lingua {team_name}")
    project = await make_project(db, language.id, name=team_name)
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return Facilitator(user.id, project.id, team_name, {"Authorization": f"Bearer {access}"})


@pytest.fixture()
async def facilitator_a(db_session: AsyncSession) -> Facilitator:
    return await a_facilitator(db_session, email="ana@example.com", team_name="Equipe P")


@pytest.fixture()
async def facilitator_b(db_session: AsyncSession) -> Facilitator:
    """Facilitates Q and nothing else, which is the only caller that can tell the scoping
    apart from no scoping at all."""
    return await a_facilitator(db_session, email="bruno@example.com", team_name="Equipe Q")


# --- what the tablet and the facilitator do -----------------------------------------------


async def a_session(db: AsyncSession, *, team_id: str):
    """A conversation, for cases about attending or halting rather than about ENG-964's own
    boundary. It lands one turn unconditionally (ENG-964) so every case here keeps reading
    as a room the team held; this file's own subject is attending and halting, not that
    boundary, and none of its cases need a session without one.
    """
    session = await room.create_session(
        db,
        pericope=P,
        project_id=team_id,
    )
    return await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")


async def the_tablet_halts(client: httpx.AsyncClient, session_id: str) -> None:
    """The room in front of the team says it cannot go on without a person."""
    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person")
    assert asked.status_code == 200, asked.text[:300]


async def tablet_state(client: httpx.AsyncClient, session_id: str) -> dict:
    answer = await client.get(f"{IR}/sessions/{session_id}")
    assert answer.status_code == 200, answer.text[:300]
    return answer.json()


async def attend(client: httpx.AsyncClient, session_id: str, who: Facilitator) -> httpx.Response:
    return await client.post(
        f"{IR}/facilitator/sessions/{session_id}/attended", headers=who.headers
    )


async def unattend(client: httpx.AsyncClient, session_id: str, who: Facilitator) -> httpx.Response:
    return await client.delete(
        f"{IR}/facilitator/sessions/{session_id}/attended", headers=who.headers
    )


async def the_queue(client: httpx.AsyncClient, who: Facilitator) -> list[dict]:
    listed = await client.get(f"{IR}/facilitator/sessions", headers=who.headers)
    assert listed.status_code == 200, listed.text[:300]
    return listed.json()["sessions"]


async def queued(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict | None:
    return next(
        (row for row in await the_queue(client, who) if row["session_id"] == session_id), None
    )


async def history_row(client: httpx.AsyncClient, who: Facilitator, session_id: str) -> dict:
    answer = await client.get(f"{DESK}/{who.team_id}/sessions", headers=who.headers)
    assert answer.status_code == 200, answer.text[:300]
    return next(card for card in answer.json() if card["session_id"] == session_id)


# --- Case 1 — the visit is a record, and the halt stays the team's ----------------------


async def test_a_facilitators_visit_writes_nothing_on_a_halted_rooms_status(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The Desk says somebody went, and the room's status is the team's to change (ADR 0076)."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    marked = await attend(client, session.id, facilitator_a)

    assert marked.status_code == 200, marked.text[:300]
    answered = marked.json()
    assert answered["attended_at"]
    assert answered["attended_by"] == facilitator_a.id
    assert answered["status"] == "needs_person", "a visita da mesa levantou a parada do tablet"
    assert answered["halt"] == BLOCKING

    card = await history_row(client, facilitator_a, session.id)
    assert card["needs_person"] is True
    assert card["attended_by"] == facilitator_a.id


async def test_a_visit_after_the_team_tapped_changes_nothing_in_the_tablets_next_read(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The tap is the tablet's own; what it reads is the same before a visit, after it and after
    its undo, so nothing the Desk marks can move the team."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    def seen(state: dict) -> tuple:
        return state["status"], state["halt"]

    before = seen(await tablet_state(client, session.id))
    assert (await attend(client, session.id, facilitator_a)).status_code == 200
    after_the_visit = seen(await tablet_state(client, session.id))
    assert (await unattend(client, session.id, facilitator_a)).status_code == 200
    after_the_undo = seen(await tablet_state(client, session.id))

    assert before == ("needs_person", BLOCKING)
    assert after_the_visit == before, "a visita da mesa mudou o que o tablet lê"
    assert after_the_undo == before, "desfazer a visita mudou o que o tablet lê"


# --- Case 2 — scoped ----------------------------------------------------------------------


async def test_a_facilitator_of_another_team_cannot_mark_this_room_attended(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    facilitator_b: Facilitator,
) -> None:
    """The case without which this route works and writes to any session in the installation.

    Tied to the positive read below on purpose: a route that refused everybody would pass the
    404 and be just as wrong, and nothing about an empty world looks broken.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    refused = await attend(client, session.id, facilitator_b)

    assert refused.status_code == 404, refused.text[:300]

    state = await tablet_state(client, session.id)
    assert state["status"] == "needs_person"
    assert state["halt"] == BLOCKING, "a parada caiu por mão de quem não facilita esta equipe"

    card = await history_row(client, facilitator_a, session.id)
    assert card["needs_person"] is True
    assert card["attended_at"] is None
    assert card["attended_by"] is None

    allowed = await attend(client, session.id, facilitator_a)
    assert allowed.status_code == 200, (
        "quem facilita a equipe deixou de conseguir marcar — o escopo aperta demais"
    )
    assert allowed.json()["attended_by"] == facilitator_a.id, (
        "a porta abriu para quem facilita a equipe, mas a marca não entrou — "
        "o 404 acima passaria com uma rota que não escreve nada"
    )


async def test_another_teams_facilitator_cannot_undo_a_mark_either(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    facilitator_b: Facilitator,
) -> None:
    """The undo carries the same scope as the mark, or the halt comes back by a stranger."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    assert (await attend(client, session.id, facilitator_a)).status_code == 200

    refused = await unattend(client, session.id, facilitator_b)

    assert refused.status_code == 404, refused.text[:300]
    card = await history_row(client, facilitator_a, session.id)
    assert card["attended_by"] == facilitator_a.id


# --- Case 3 — the visit drains the queue, and the undo fills it again ---------------------


async def test_an_attended_halted_room_leaves_the_queue_and_undoing_the_visit_puts_it_back(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The queue lists a halted room while nobody is marked as having gone (ADR 0076).

    A mark is a claim a person can withdraw, so a mistaken tap brings the room back.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    assert await queued(client, facilitator_a, session.id) is not None

    assert (await attend(client, session.id, facilitator_a)).status_code == 200
    assert await queued(client, facilitator_a, session.id) is None, (
        "a sala atendida continua na fila de quem já foi até ela"
    )

    undone = await unattend(client, session.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    answered = undone.json()
    assert answered["status"] == "needs_person"
    assert answered["halt"] == BLOCKING
    assert answered["attended_at"] is None
    assert answered["attended_by"] is None

    state = await tablet_state(client, session.id)
    assert state["status"] == "needs_person"
    assert state["halt"] == BLOCKING

    back = await queued(client, facilitator_a, session.id)
    assert back is not None, "desfazer a marca não devolveu a sala à fila"
    assert back["halt"] == BLOCKING

    card = await history_row(client, facilitator_a, session.id)
    assert card["needs_person"] is True
    assert card["attended_at"] is None
    assert card["attended_by"] is None


async def test_undoing_a_visit_to_a_room_that_never_halted_does_not_invent_a_halt(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """Withdrawing a mark on a room running fine leaves it running: a stray tap on the Desk
    never halts a conversation in full flow."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    marked = await attend(client, session.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"], "sem carimbo não há retirada a testar"

    undone = await unattend(client, session.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] is None
    assert undone.json()["attended_at"] is None

    state = await tablet_state(client, session.id)
    assert state["status"] == "in_progress", (
        "desfazer a visita a uma sala que nunca parou pôs a equipe a pedir uma pessoa"
    )
    assert state["halt"] is None


async def test_undoing_a_mark_nobody_made_changes_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """Nothing to withdraw is not an error: 200, and the room is left exactly as it was."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)

    undone = await unattend(client, session.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] is None

    state = await tablet_state(client, session.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None, "uma sala que nunca parou passou a pedir uma pessoa"


async def test_undoing_a_mark_nobody_made_does_not_re_halt_a_room_that_healed_itself(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    """The reachable half of "undoing an unmarked session is a no-op".

    A room that halted and was resumed by the team carries the kind of that halt for good —
    that is what makes the history readable afterwards. So "put back the halt it had" has
    something to put back here, and nobody ever claimed a visit. Undo must still do nothing.

    Found by mutation: deleting the "was there a mark to undo?" guard killed no case, because
    the only no-op case was a room that had never halted at all, where the kind is null and a
    second guard catches it by accident. This is the case that holds the first guard.
    """
    await the_tablet_halts(client, waiting_room.id)
    answered = await the_team_answers(client, waiting_room.id)
    assert answered.status_code == 200, answered.text[:300]
    assert (await tablet_state(client, waiting_room.id))["status"] == "in_progress"

    undone = await unattend(client, waiting_room.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] is None
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress", (
        "desfazer uma visita que ninguém marcou parou uma conversa em curso"
    )
    assert state["halt"] is None


async def test_undoing_a_visit_to_a_room_the_team_restarted_itself_does_not_halt_it_again(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    """The intersection the two cases above each cover only half of.

    A room halts, the team comes back on its own, and a facilitator marks the row anyway —
    the queue they were reading was a minute stale, and they did go. Then they undo.

    Nothing about that undo may halt the room: a visit lifts nothing, so its undo puts nothing
    back.
    """
    await the_tablet_halts(client, waiting_room.id)
    answered = await the_team_answers(client, waiting_room.id)
    assert answered.status_code == 200, answered.text[:300]
    assert (await tablet_state(client, waiting_room.id))["status"] == "in_progress"

    marked = await attend(client, waiting_room.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"], "sem carimbo não há retirada a testar"

    undone = await unattend(client, waiting_room.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] is None
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress", (
        "desfazer uma visita que não levantou parada nenhuma parou a equipe de novo"
    )
    assert state["halt"] is None


async def test_a_second_halt_is_not_reported_as_a_room_somebody_already_went_to(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    """A new ask is an unattended ask, whoever answered the last one.

    The stamps are what a facilitator reads to skip a row somebody else already walked to. A
    room that halts again after a visit is a room nobody has been to *for this halt*, and
    carrying the old visit forward makes the queue tell them to skip it.

    Sharper than it looks: a successful mark takes the row off the queue, so a halted row can
    only ever carry stamps by carrying stale ones. The field the queue documents as "somebody
    has been here" would be delivered exclusively by that mistake.
    """
    await the_tablet_halts(client, waiting_room.id)
    marked = await attend(client, waiting_room.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"]
    assert await queued(client, facilitator_a, waiting_room.id) is None

    await the_tablet_halts(client, waiting_room.id)

    asking_again = await queued(client, facilitator_a, waiting_room.id)
    assert asking_again is not None, "a sala parou outra vez e não voltou para a fila"
    assert asking_again["halt"] == BLOCKING
    assert asking_again["attended_at"] is None, (
        "a parada nova chegou à fila marcada como já atendida, e quem lê a fila a pula"
    )
    assert asking_again["attended_by"] is None


async def test_a_halt_asked_while_a_visit_was_landing_is_still_listed(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    rival_factory,
) -> None:
    """The visit a new halt clears may have landed after the ask read the room."""
    async with rival_factory() as asking, rival_factory() as visiting:
        read_before_the_visit = await room.get_session(asking, waiting_room.id)
        await room.attend(
            visiting, await room.get_session(visiting, waiting_room.id), by=facilitator_a.id
        )

        await room.mark_needs_person(asking, read_before_the_visit)

    asking_now = await queued(client, facilitator_a, waiting_room.id)
    assert asking_now is not None, "a parada nova herdou a visita anterior e sumiu da fila"
    assert asking_now["attended_at"] is None


async def test_a_warning_raised_while_a_visit_was_landing_is_still_listed(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
    rival_factory,
) -> None:
    """The visit a new warning clears may have landed after the warning read the room."""
    session_id = waiting_room.id
    async with rival_factory() as warning, rival_factory() as visiting:
        read_before_the_visit = await room.get_session(warning, session_id)
        await room.attend(
            visiting, await room.get_session(visiting, session_id), by=facilitator_a.id
        )

        await room.raise_a_warning(warning, read_before_the_visit)
    db_session.expire_all()

    warned = await queued(client, facilitator_a, session_id)
    assert warned is not None, "o aviso novo herdou a visita anterior e sumiu da fila"
    assert warned["halt"] == WARNING
    assert warned["attended_at"] is None


async def test_a_warning_a_visit_ended_while_a_halt_was_asked_stays_ended(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
    rival_factory,
) -> None:
    """The halt clears a visit that landed after it read the room, and keeps what it ended."""
    async with rival_factory() as warning:
        await room.raise_a_warning(warning, await room.get_session(warning, waiting_room.id))
    async with rival_factory() as asking, rival_factory() as visiting:
        read_before_the_visit = await room.get_session(asking, waiting_room.id)
        await room.attend(
            visiting, await room.get_session(visiting, waiting_room.id), by=facilitator_a.id
        )

        await room.mark_needs_person(asking, read_before_the_visit)
    db_session.expire_all()

    returned = await the_team_opens_the_session(client)

    assert returned["status"] == "in_progress"
    assert returned["halt"] is None, "a parada nova trouxe de volta o aviso que a visita encerrou"


async def test_undoing_a_visit_after_the_team_came_back_does_not_stop_them_again(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    """A conversation in full flow never stops because somebody corrected an old tap."""
    await the_tablet_halts(client, waiting_room.id)
    marked = await attend(client, waiting_room.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"]

    answered = await the_team_answers(client, waiting_room.id)
    assert answered.status_code == 200, answered.text[:300]
    assert (await tablet_state(client, waiting_room.id))["status"] == "in_progress"

    undone = await unattend(client, waiting_room.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] is None
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress", (
        "a equipe já tinha voltado e desfazer a marca parou a conversa outra vez"
    )
    assert state["halt"] is None
    assert await queued(client, facilitator_a, waiting_room.id) is None


async def the_team_opens_the_session(client: httpx.AsyncClient) -> dict:
    opened = await client.post(f"{IR}/sessions", json={"pericope": P, "language": "pt"})
    assert opened.status_code == 200, opened.text[:300]
    return opened.json()


async def test_only_the_teams_return_lifts_the_halt_and_it_keeps_the_visit(
    client: httpx.AsyncClient, facilitator_a: Facilitator, waiting_room
) -> None:
    """A visit leaves the halt standing; the tablet opening the session again lifts it."""
    await the_tablet_halts(client, waiting_room.id)
    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200
    assert (await tablet_state(client, waiting_room.id))["status"] == "needs_person"

    reopened = await the_team_opens_the_session(client)

    assert reopened["session_id"] == waiting_room.id
    assert reopened["status"] == "in_progress"
    assert reopened["halt"] is None
    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["attended_at"], "a volta da equipe apagou o registro da visita"
    assert card["attended_by"] == facilitator_a.id


async def test_undoing_a_visit_after_the_team_reopened_the_session_writes_nothing(
    client: httpx.AsyncClient, facilitator_a: Facilitator, waiting_room
) -> None:
    await the_tablet_halts(client, waiting_room.id)
    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200
    await the_team_opens_the_session(client)

    undone = await unattend(client, waiting_room.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress", "desfazer a visita parou a equipe de novo"
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None


# --- Case 4 — the halt says its kind, from each writer ------------------------------------


async def test_the_tablets_own_halt_is_a_blocking_one(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The room in front of the team decided it cannot go on: nothing else may land."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)

    await the_tablet_halts(client, session.id)

    assert (await tablet_state(client, session.id))["halt"] == BLOCKING
    standing = await queued(client, facilitator_a, session.id)
    assert standing is not None
    assert standing["halt"] == BLOCKING


async def _a_rehearsal(client: httpx.AsyncClient, session_id: str) -> str:
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": P},
        files={"file": ("tomada.m4a", b"a equipe ensaiou a passagem", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text[:300]
    return kept.json()["take_id"]


async def _tell_back_again(
    client: httpx.AsyncClient, session_id: str, take_id: str
) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Device": DEVICE},
        data={
            "take_id": take_id,
            "starts_ms": "0",
            "ends_ms": "9000",
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", a_new_recording(), "audio/mp4")},
    )


async def test_a_hard_stretch_is_a_warning_and_not_a_block(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    the_telling_is_heard: None,
) -> None:
    """ENG-706 — the room asks for somebody to come and watch, and refuses nothing.

    Written the same word as the hard stop, it read to every consumer as a room that had
    stopped. The Desk needs to tell "go and see this" from "this cannot continue", because
    they are different walks.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    take_id = await _a_rehearsal(client, session.id)

    for _ in range(RETELLS_BEFORE_A_WARNING - 1):
        telling = await _tell_back_again(client, session.id, take_id)
        assert telling.status_code == 200, telling.text[:300]
        assert telling.json()["needs_person"] is False, (
            "a sala pediu uma pessoa antes da terceira contagem do trecho"
        )

    spent = await _tell_back_again(client, session.id, take_id)

    assert spent.status_code == 200, spent.text[:300]
    assert spent.json()["needs_person"] is True, (
        "o trecho foi contado três vezes e a sala não pediu ninguém"
    )

    assert (await tablet_state(client, session.id))["halt"] == WARNING
    standing = await queued(client, facilitator_a, session.id)
    assert standing is not None
    assert standing["halt"] == WARNING


class _AgreeingModels:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
def the_models_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Guide drafts and the Validator passes it."""
    the_room_agent_is(monkeypatch, turn=_AgreeingModels())


@pytest.fixture()
async def waiting_room(db_session: AsyncSession, facilitator_a: Facilitator):
    """A room of A's team that has asked its question and is waiting on the answer."""
    session = await room.create_session(
        db_session,
        language="pt",
        pericope=P,
        project_id=facilitator_a.team_id,
    )
    session = await room.append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )
    return session


async def the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/turns",
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


# --- Case 5 — a mark on a room that is not halted -----------------------------------------


async def test_a_facilitator_can_say_they_went_to_a_room_that_never_asked(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """They went anyway, and that is worth recording — but it moves nothing.

    A mark that pushed an untroubled conversation through the state machine would be a Desk
    tap that changes what the team is doing.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)

    marked = await attend(client, session.id, facilitator_a)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["status"] == "in_progress"
    assert marked.json()["halt"] is None

    card = await history_row(client, facilitator_a, session.id)
    assert card["attended_at"]
    assert card["attended_by"] == facilitator_a.id
    assert card["last_halt"] is None, "uma sala que nunca parou não tem última parada"
    assert card["state"] == "in_progress"


async def test_undoing_the_mark_on_a_finished_passage_leaves_it_finished(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """`DONE` is terminal, and the undo is not a way back into a closed passage."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    marked = await attend(client, session.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"], "não houve carimbo, logo não há limpeza a provar"

    await room.apply_coverage(db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED))
    assert (await tablet_state(client, session.id))["status"] == "done"

    undone = await unattend(client, session.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "done", "desfazer a marca reabriu uma passagem conferida"
    assert undone.json()["attended_at"] is None
    assert (await tablet_state(client, session.id))["status"] == "done"

    card = await history_row(client, facilitator_a, session.id)
    assert card["attended_at"] is None
    assert card["attended_by"] is None
    assert card["state"] == "complete"


async def test_a_finished_passage_waits_on_the_queue_without_being_a_halt(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The queue's other half, which waits on a person for a different reason.

    A finished passage is waiting to be carried into Refine, and that is not a room that
    stopped. The row still has to name its team, because the whole point of this listing is
    deciding where to go, and that half is what a mutation can reach.

    **`halt is None` here cannot fail today, and is kept for the reason
    `test_a_session_that_ended_is_never_reported_as_still_halted` keeps its own such
    assertion**: `apply_coverage` closes only a session that is already `IN_PROGRESS`, so no
    path in today's state machine reaches `DONE` carrying a standing halt, and `halt_kind`
    stays null on a passage that simply completed. It is the contract the field promises
    rather than an artifact of which paths exist — and a later slice that does close a halted
    session is exactly when it starts being able to fail.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await room.apply_coverage(db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED))

    waiting = await queued(client, facilitator_a, session.id)

    assert waiting is not None, "uma passagem conferida saiu da fila de quem a carrega adiante"
    assert waiting["status"] == "done"
    assert waiting["halt"] is None, "uma passagem conferida apareceu como sala parada"
    assert waiting["team_name"] == facilitator_a.team_name
    assert waiting["project_id"] == facilitator_a.team_id


# --- Case 6 — idempotent, and the stamp outlives a landing turn ---------------------------


async def test_marking_twice_keeps_the_moment_the_facilitator_actually_went(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """Two taps are one visit. The second must not move the moment it records.

    A stamp that moves on every tap is a record of when somebody last touched the Desk, not
    of when somebody went to the room — and the queue's own age is read off it.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    first = await attend(client, session.id, facilitator_a)
    second = await attend(client, session.id, facilitator_a)

    assert first.status_code == second.status_code == 200, second.text[:300]
    went_at = first.json()["attended_at"]
    assert went_at, "sem um primeiro carimbo, `igual ao primeiro` é `None == None`"
    assert second.json()["attended_at"] == went_at
    assert second.json()["attended_by"] == facilitator_a.id


async def test_a_turn_that_lands_still_lifts_the_halt_and_keeps_the_mark(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    """The team's own way out is untouched, and it does not erase who went.

    A landing turn goes on lifting a blocking halt, which `test_the_pause_is_not_a_latch`
    already holds, and never a warning (ENG-1163). The regression
    locked here is the other direction — the turn must not take the record of the visit with
    it, because the queue and the history are how anybody afterwards knows somebody went.
    """
    await the_tablet_halts(client, waiting_room.id)
    marked = await attend(client, waiting_room.id, facilitator_a)
    assert marked.status_code == 200, marked.text[:300]
    went_at = marked.json()["attended_at"]
    assert went_at, "sem carimbo antes do turno, sobreviver ao turno não quer dizer nada"

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None

    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["needs_person"] is False
    assert card["attended_by"] == facilitator_a.id
    assert _instant(card["attended_at"]) == _instant(went_at), (
        "o turno que aterrou apagou quando a pessoa foi"
    )


def _instant(moment: str) -> datetime:
    """The same instant however the route that answered it spells the offset.

    `AttendedResponse` serves a string built with `isoformat` and `TeamSessionResponse` a
    real `datetime` pydantic renders — so one ends `+00:00` and the other `Z`. Both name the
    clock, which is the rule this codebase keeps; comparing the spellings instead of the
    instants would be asserting which of the two house shapes a field happens to sit on.
    """
    assert moment.endswith(("Z", "+00:00")), f"{moment!r} não diz em que relógio está"
    return datetime.fromisoformat(moment)


# --- Case 7 — a warning stands apart from the status (ENG-1163) ---------------------------


@pytest.fixture()
def the_telling_is_heard(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.internalization_room import back_translation as bt_api

    async def _words(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho"

    monkeypatch.setattr(bt_api, "heard", _words)


async def a_warning_is_raised(client: httpx.AsyncClient, session_id: str) -> None:
    """The team tells the same stretch back until it becomes a hard stretch."""
    take_id = await _a_rehearsal(client, session_id)
    for _ in range(RETELLS_BEFORE_A_WARNING):
        telling = await _tell_back_again(client, session_id, take_id)
        assert telling.status_code == 200, telling.text[:300]
    assert telling.json()["needs_person"] is True, "o trecho difícil não levantou o aviso"


async def test_a_standing_warning_reads_as_a_warning_while_the_room_goes_on(
    client: httpx.AsyncClient, waiting_room, the_telling_is_heard: None
) -> None:
    """A warning refuses nothing, so the room is still in progress while it stands."""
    await a_warning_is_raised(client, waiting_room.id)

    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress", "o aviso parou a sala como se fosse um bloqueio"
    assert state["halt"] == WARNING


async def test_the_desk_attending_ends_the_warning(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
) -> None:
    await a_warning_is_raised(client, waiting_room.id)

    marked = await attend(client, waiting_room.id, facilitator_a)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["halt"] is None
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None, "a visita da mesa não encerrou o aviso"


async def test_one_visit_ends_a_warning_and_leaves_the_blocking_halt_over_it_to_the_team(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    """The visit is the warning's only end (ADR 0039); the blocking halt is the team's."""
    await a_warning_is_raised(client, waiting_room.id)
    await the_tablet_halts(client, waiting_room.id)

    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200

    visited = await tablet_state(client, waiting_room.id)
    assert visited["status"] == "needs_person", "a visita da mesa levantou o bloqueio"
    assert visited["halt"] == BLOCKING

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None, "a visita não encerrou o aviso que estava embaixo"


async def test_the_warning_reads_again_once_a_turn_lifts_the_blocking_halt_over_it(
    client: httpx.AsyncClient,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    """The lift here is a landing turn, which lifts the blocking halt and never a warning."""
    await a_warning_is_raised(client, waiting_room.id)
    await the_tablet_halts(client, waiting_room.id)
    assert (await tablet_state(client, waiting_room.id))["halt"] == BLOCKING

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] == WARNING, "o bloqueio saiu e levou junto o aviso que estava embaixo"


async def test_a_turn_that_lands_never_ends_a_warning(
    client: httpx.AsyncClient,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    """Hand test 7.4: the mark vanished at the next read once the team went on talking."""
    await a_warning_is_raised(client, waiting_room.id)

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "in_progress"
    assert state["halt"] == WARNING, "o turno que aterrou apagou o aviso"


async def test_undoing_the_visit_brings_the_warning_back(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
) -> None:
    await a_warning_is_raised(client, waiting_room.id)
    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200

    undone = await unattend(client, waiting_room.id, facilitator_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["status"] == "in_progress"
    assert undone.json()["halt"] == WARNING
    assert (await tablet_state(client, waiting_room.id))["halt"] == WARNING, (
        "desfazer a visita não trouxe o aviso de volta"
    )


async def test_the_desk_lists_a_room_under_a_warning_on_both_rows(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
) -> None:
    """The queue and the team card say the same as the tablet (ADR 0046, invariant 15)."""
    await a_warning_is_raised(client, waiting_room.id)

    row = await queued(client, facilitator_a, waiting_room.id)
    assert row is not None, "a sala com aviso saiu da fila da mesa"
    assert row["status"] == "in_progress"
    assert row["halt"] == WARNING

    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["needs_person"] is False
    assert card["halt"] == WARNING


async def test_a_new_block_does_not_bring_back_a_warning_somebody_already_attended(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    """A new ask clears the visit, and the warning that visit ended stays ended."""
    await a_warning_is_raised(client, waiting_room.id)
    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200
    await the_tablet_halts(client, waiting_room.id)
    assert (await tablet_state(client, waiting_room.id))["halt"] == BLOCKING

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    assert (await tablet_state(client, waiting_room.id))["halt"] is None, (
        "o bloqueio novo trouxe de volta um aviso que a mesa já tinha atendido"
    )
    assert await queued(client, facilitator_a, waiting_room.id) is None


async def test_a_warning_on_a_finished_passage_leaves_it_finished(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    the_telling_is_heard: None,
) -> None:
    """The telling-back runs on a passage the floor closed, and a warning refuses nothing."""
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await room.apply_coverage(db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED))
    assert (await tablet_state(client, session.id))["status"] == "done"

    await a_warning_is_raised(client, session.id)

    state = await tablet_state(client, session.id)
    assert state["status"] == "done", "o aviso reabriu uma passagem que já estava fechada"
    assert state["halt"] == WARNING
    rows = [
        row for row in await the_queue(client, facilitator_a) if row["session_id"] == session.id
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "done"
    assert rows[0]["halt"] == WARNING


# --- Case 8 — the queue row says when the warning was raised (ENG-1180) -------------------


async def a_closed_passage(db: AsyncSession, session) -> None:
    await room.apply_coverage(db, session.id, dict.fromkeys(element_keys(P), ENGAGED))


async def an_old_row(db: AsyncSession, session_id: str) -> None:
    session = await room.get_session(db, session_id)
    session.status = IRSessionStatus.NEEDS_PERSON
    session.halt_kind = HaltKind.BLOCKING.value
    session.halts_raised = session.halts_raised + 1
    await db.commit()


async def test_the_queue_row_says_when_the_warning_was_raised(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    before = datetime.now(UTC)
    await a_warning_is_raised(client, waiting_room.id)
    after = datetime.now(UTC)
    assert (await the_team_answers(client, waiting_room.id)).status_code == 200

    row = await queued(client, facilitator_a, waiting_room.id)

    assert row is not None
    assert row["warned_at"] is not None, "a fila não diz desde quando o aviso está de pé"
    assert before <= _instant(row["warned_at"]) <= after, (
        "o momento do aviso andou com o turno seguinte"
    )


async def test_the_team_cards_session_row_says_when_the_warning_was_raised(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
    the_models_agree: None,
) -> None:
    before = datetime.now(UTC)
    await a_warning_is_raised(client, waiting_room.id)
    after = datetime.now(UTC)
    assert (await the_team_answers(client, waiting_room.id)).status_code == 200

    card = await history_row(client, facilitator_a, waiting_room.id)

    assert card["warned_at"] is not None, "o cartão não diz desde quando o aviso está de pé"
    assert before <= _instant(card["warned_at"]) <= after, (
        "o momento do aviso andou com o turno seguinte"
    )


async def test_once_attended_no_warning_moment_and_after_the_undo_it_is_back(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
) -> None:
    await a_closed_passage(db_session, waiting_room)
    await a_warning_is_raised(client, waiting_room.id)
    assert (await tablet_state(client, waiting_room.id))["status"] == "done"
    raised = await queued(client, facilitator_a, waiting_room.id)
    assert raised is not None and raised["warned_at"] is not None
    moment = _instant(raised["warned_at"])

    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200

    attended = await queued(client, facilitator_a, waiting_room.id)
    assert attended is not None
    assert attended["warned_at"] is None, "a fila manteve o aviso que a mesa atendeu"
    assert (await history_row(client, facilitator_a, waiting_room.id))["warned_at"] is None, (
        "o cartão manteve o aviso que a mesa atendeu"
    )

    assert (await unattend(client, waiting_room.id, facilitator_a)).status_code == 200

    undone = await queued(client, facilitator_a, waiting_room.id)
    assert undone is not None and undone["warned_at"] is not None
    assert _instant(undone["warned_at"]) == moment, "desfazer a visita não trouxe o momento"
    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["warned_at"] is not None
    assert _instant(card["warned_at"]) == moment


async def test_a_blocking_halt_over_a_warning_keeps_its_moment(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_telling_is_heard: None,
) -> None:
    before = datetime.now(UTC)
    await a_warning_is_raised(client, waiting_room.id)
    after = datetime.now(UTC)
    await the_tablet_halts(client, waiting_room.id)

    row = await queued(client, facilitator_a, waiting_room.id)

    assert row is not None
    assert row["halt"] == BLOCKING
    assert row["warned_at"] is not None, "o bloqueio por cima escondeu o momento do aviso"
    assert before <= _instant(row["warned_at"]) <= after
    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["halt"] == BLOCKING
    assert card["warned_at"] is not None
    assert before <= _instant(card["warned_at"]) <= after


async def test_no_warning_raised_no_warning_moment(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    row = await queued(client, facilitator_a, session.id)

    assert row is not None
    assert row["warned_at"] is None
    assert (await history_row(client, facilitator_a, session.id))["warned_at"] is None


# --- Case 9 — a closed passage never blocks again (ENG-1180) ------------------------------


async def test_a_closed_passage_refuses_a_needs_person_ask(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
) -> None:
    await a_closed_passage(db_session, waiting_room)
    assert (await attend(client, waiting_room.id, facilitator_a)).status_code == 200
    went = (await history_row(client, facilitator_a, waiting_room.id))["attended_at"]

    asked = await client.post(f"{IR}/sessions/{waiting_room.id}/needs-person")

    assert 400 <= asked.status_code < 500, asked.text[:300]
    assert asked.json()["code"] == "PASSAGE_CLOSED"
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "done", "o pedido numa passagem fechada a parou de novo"
    assert state["halt"] is None
    card = await history_row(client, facilitator_a, waiting_room.id)
    assert card["last_halt"] is None, "o pedido recusado escreveu o tipo da parada"
    assert card["attended_at"] == went, "o pedido recusado apagou a visita"


async def test_a_closed_passages_halt_stands_under_a_visit_and_the_return_makes_it_done(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
) -> None:
    await a_closed_passage(db_session, waiting_room)
    await an_old_row(db_session, waiting_room.id)

    marked = await attend(client, waiting_room.id, facilitator_a)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["status"] == "needs_person", "a visita da mesa mexeu no status"

    reopened = await the_team_opens_the_session(client)

    assert reopened["status"] == "done", "a volta da equipe reabriu uma passagem fechada"
    assert reopened["halt"] is None


async def test_a_landing_turns_lift_on_a_closed_passage_leaves_it_done(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    await a_closed_passage(db_session, waiting_room)
    await an_old_row(db_session, waiting_room.id)
    closed = (await history_row(client, facilitator_a, waiting_room.id))["ended_at"]

    answered = await the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    state = await tablet_state(client, waiting_room.id)
    assert state["status"] == "done", "o turno reabriu uma passagem fechada"
    assert state["halt"] is None
    assert (await history_row(client, facilitator_a, waiting_room.id))["ended_at"] == closed, (
        "a passagem foi reaberta e fechada de novo"
    )


async def test_a_closed_passage_never_reads_needs_person_nor_in_progress_after_any_write(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    facilitator_a: Facilitator,
    waiting_room,
    the_models_agree: None,
) -> None:
    await a_closed_passage(db_session, waiting_room)
    await an_old_row(db_session, waiting_room.id)
    closed = (await history_row(client, facilitator_a, waiting_room.id))["ended_at"]
    writes = {
        "turn": lambda: the_team_answers(client, waiting_room.id),
        "attend": lambda: attend(client, waiting_room.id, facilitator_a),
        "undo": lambda: unattend(client, waiting_room.id, facilitator_a),
        "ask": lambda: client.post(f"{IR}/sessions/{waiting_room.id}/needs-person"),
    }

    for name, write in writes.items():
        await write()
        status = (await tablet_state(client, waiting_room.id))["status"]
        assert status == "done", f"depois de {name} a passagem fechada leu {status}"
        ended = (await history_row(client, facilitator_a, waiting_room.id))["ended_at"]
        assert ended == closed, f"depois de {name} a passagem foi reaberta e fechada de novo"


async def test_a_passage_closed_while_the_ask_was_on_its_way_refuses_it_too(
    db_session: AsyncSession, waiting_room
) -> None:
    read_before_the_close = await room.get_session(db_session, waiting_room.id)
    await db_session.execute(
        update(IRSession)
        .where(IRSession.id == waiting_room.id)
        .values(status=IRSessionStatus.DONE, ended_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await db_session.commit()

    halts_before = read_before_the_close.halts_raised

    with pytest.raises(PassageClosed):
        await room.mark_needs_person(db_session, read_before_the_close)

    stored = await the_row(db_session, waiting_room.id)
    assert stored.status is IRSessionStatus.DONE, "o pedido atrasado parou uma passagem fechada"
    assert stored.halt_kind is None
    assert stored.halts_raised == halts_before
