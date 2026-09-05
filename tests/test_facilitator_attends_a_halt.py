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
budget, and the assessor failing until the room hard-stops.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRTakeKind
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import MAX_RETELLS
from app.services.platform.storage import StoredObject
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
ROOM_KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"

P = "P03"
ENGAGED = CoverageStatus.ENGAGED.value
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
FIRST_QUESTION = "Quem aparece nesta parte?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
EXCERPT = "Noemi voltou"
AUDIO = b"a equipe explicou este trecho em portugues"

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
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
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
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)
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
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
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
    language = await make_language(db, name=f"Lingua {team_name}", code=email[:3])
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


async def a_session(db: AsyncSession, *, team_id: str, ready_to_close: bool = False):
    return await room.create_session(
        db,
        pericope=P,
        project_id=team_id,
        bridge_mode="guided_microchecks" if ready_to_close else None,
    )


async def the_tablet_halts(client: httpx.AsyncClient, session_id: str) -> None:
    """The room in front of the team says it cannot go on without a person."""
    asked = await client.post(
        f"{IR}/sessions/{session_id}/needs-person", headers={"X-Room-Key": ROOM_KEY}
    )
    assert asked.status_code == 200, asked.text[:300]


async def tablet_state(client: httpx.AsyncClient, session_id: str) -> dict:
    answer = await client.get(f"{IR}/sessions/{session_id}", headers={"X-Room-Key": ROOM_KEY})
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


# --- Case 1 — the mark lifts the halt, and the lift is readable ---------------------------


async def test_a_facilitator_who_went_lifts_the_halt_and_the_lift_is_readable(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """The halt the facilitator resolves is the one nothing could resolve.

    A landing turn is the team's way out and it was the only way out, so a room helped by a
    person who then leaves the team gathering their thoughts stayed halted — on the queue, on
    the tablet — until the team spoke. What the facilitator can now say is that they went.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)

    standing = await queued(client, facilitator_a, session.id)
    assert standing is not None, "a sala parou e a fila não a mostra"
    assert standing["halt"] == BLOCKING
    assert standing["project_id"] == facilitator_a.team_id
    assert standing["team_name"] == facilitator_a.team_name, (
        "a fila cruza equipes e sem o nome da equipe não se sabe para onde ir"
    )
    assert standing["attended_at"] is None
    assert standing["attended_by"] is None

    marked = await attend(client, session.id, facilitator_a)

    assert marked.status_code == 200, marked.text[:300]
    answered = marked.json()
    assert answered["status"] == "in_progress"
    assert answered["halt"] is None
    assert answered["attended_at"]
    assert answered["attended_by"] == facilitator_a.id

    state = await tablet_state(client, session.id)
    assert state["status"] == "in_progress"
    assert state["halt"] is None, (
        "o tablet precisa de um sinal, não de dois: sem parada, sem tipo de parada"
    )

    assert await queued(client, facilitator_a, session.id) is None, (
        "a sala atendida continua na fila de quem já foi até ela"
    )

    card = await history_row(client, facilitator_a, session.id)
    assert card["needs_person"] is False
    assert card["last_halt"] == BLOCKING, (
        "o histórico é onde a parada que houve não se perde ao ser levantada"
    )
    assert card["attended_at"]
    assert card["attended_by"] == facilitator_a.id


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
    assert (await tablet_state(client, session.id))["status"] == "in_progress"


# --- Case 3 — undo restores the halt ------------------------------------------------------


async def test_undoing_the_mark_puts_the_room_back_to_asking(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """A mark is a claim a person can withdraw, and withdrawing it is saying nobody went.

    So the room asks again — with the kind of halt it had, not a fresh generic one — and the
    queue takes it back. Without this, a mistaken tap is a room that silently stops asking.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    await the_tablet_halts(client, session.id)
    assert (await attend(client, session.id, facilitator_a)).status_code == 200

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
    """Undo puts back the halt there was, and where there was none it puts back none.

    The dangerous reading of "undo re-halts an open room" halts a conversation in full flow
    that nobody ever had to help — a room stopped by a stray tap on the Desk.

    This is the mark being *withdrawn*, not absent: the facilitator went to a room that was
    running fine, said so, and changed their mind. So the first guard in `unattend` — was
    there a mark at all — cannot be what saves it, and the kind is what has to.

    Found by mutation. As first written this case only undid a mark that was never made, and
    then dropping ``and session.halt_kind is not None`` from `unattend` killed nothing at
    all: every case reaching the undo left early on the mark being absent, or carried
    ``DONE``. The room nobody marked is the case below.
    """
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
    the_assessor_agrees: None,
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
    the_assessor_agrees: None,
) -> None:
    """The intersection the two cases above each cover only half of.

    A room halts, the team comes back on its own, and a facilitator marks the row anyway —
    the queue they were reading was a minute stale, and they did go. Then they undo.

    Nothing about that undo may halt the room: the visit lifted no halt, so there is none to
    put back. `halt_kind` cannot answer this, because it is never cleared — it says "this
    session was halted at some point, ever", not "this visit lifted a halt". Whether the mark
    lifted anything is a different fact and has to be recorded as one.
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
    the_assessor_agrees: None,
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


async def test_undoing_a_visit_after_the_team_came_back_does_not_stop_them_again(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_assessor_agrees: None,
) -> None:
    """The same staleness as `halt_kind`, one step further along, and it bites the same way.

    Here the visit really did lift a halt, so `lifted_halt` is set and an undo would put it
    back. Then the team comes back and a turn lands. That turn would have lifted the halt on
    its own — it is the team's own exit and always was — so by the time the facilitator
    notices they tapped the wrong row there is nothing left for the undo to restore.

    Without this, the fourth column only moves the defect: a conversation in full flow stops
    and returns to the queue because somebody corrected a tap made ten minutes earlier.
    """
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
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
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
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": take_id,
            "starts_ms": "0",
            "ends_ms": "9000",
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def test_the_retell_budget_running_out_is_a_warning_and_not_a_block(
    client: httpx.AsyncClient, db_session: AsyncSession, facilitator_a: Facilitator
) -> None:
    """ENG-706 — the room asks for somebody to come and watch, and refuses nothing.

    Written the same word as the hard stop, it read to every consumer as a room that had
    stopped. The Desk needs to tell "go and see this" from "this cannot continue", because
    they are different walks.
    """
    session = await a_session(db_session, team_id=facilitator_a.team_id)
    take_id = await _a_rehearsal(client, session.id)

    for _ in range(MAX_RETELLS - 1):
        spending = await _tell_back_again(client, session.id, take_id)
        assert spending.status_code == 200, spending.text[:300]
        assert spending.json()["needs_person"] is False, (
            "a sala pediu uma pessoa antes de o orçamento acabar"
        )

    spent = await _tell_back_again(client, session.id, take_id)

    assert spent.status_code == 200, spent.text[:300]
    assert spent.json()["needs_person"] is True, (
        "o orçamento de reconto acabou e a sala não pediu ninguém"
    )

    assert (await tablet_state(client, session.id))["halt"] == WARNING
    standing = await queued(client, facilitator_a, session.id)
    assert standing is not None
    assert standing["halt"] == WARNING


@pytest.fixture()
def target_checkpoint() -> str:
    return next(checkpoint for checkpoint in checkpoints_for(P) if checkpoint.critical).id


class _AgreeingModels:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
def the_assessor_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Guide and Validator work; only the comprehension assessor cannot be reached.

    Copied from `test_internalization_room_turn_durability.py`, which is where the hard stop
    is already driven over HTTP — this file reaches it the same way rather than reaching
    inside the service to fake the outcome.
    """
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _AgreeingModels()
    )

    async def _assessor(**_: Any) -> str:
        raise RuntimeError("assessor transport is down")

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.comprehension.assessor"],
        "call_agent",
        _assessor,
    )


@pytest.fixture()
def the_assessor_agrees(monkeypatch: pytest.MonkeyPatch, target_checkpoint: str) -> None:
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _AgreeingModels()
    )

    async def _assessor(**_: Any) -> str:
        return json.dumps(
            {
                "observations": [
                    {
                        "checkpoint_id": target_checkpoint,
                        "result": "demonstrated",
                        "evidence_excerpt": EXCERPT,
                        "rationale": "names the return",
                    }
                ],
                "mother_tongue_practice_reported": False,
                "practice_evidence_excerpt": "",
            }
        )

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.comprehension.assessor"],
        "call_agent",
        _assessor,
    )


@pytest.fixture()
async def waiting_room(
    db_session: AsyncSession, facilitator_a: Facilitator, target_checkpoint: str
):
    """A room of A's team that has asked its question and is waiting on the answer."""
    session = await room.create_session(
        db_session,
        language="pt",
        pericope=P,
        project_id=facilitator_a.team_id,
        bridge_mode="guided_microchecks",
    )
    session = await room.append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )
    state = room.comprehension_of(session)
    state.active_probe = ActiveProbe(
        id="probe-1",
        checkpoint_ids=[target_checkpoint],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )
    return await room.save_comprehension(db_session, session, state)


async def the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/turns",
        headers={"X-Room-Key": ROOM_KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


async def test_the_hard_stop_is_a_blocking_halt(
    client: httpx.AsyncClient,
    facilitator_a: Facilitator,
    waiting_room,
    the_assessor_is_down: None,
) -> None:
    """The assessor failing three turns running is the room saying it cannot go on.

    Driven through the turn route, the way `test_the_hard_stop_outlives_the_request_that_
    raised_it` drives it: the halt this asks about is the one the room raises for itself.
    """
    halted = False
    for _ in range(6):
        answered = await the_team_answers(client, waiting_room.id)
        assert answered.status_code == 200, answered.text[:300]
        if (await tablet_state(client, waiting_room.id))["status"] == "needs_person":
            halted = True
            break

    assert halted, "o assessor caiu turno após turno e a sala nunca parou"
    assert (await tablet_state(client, waiting_room.id))["halt"] == BLOCKING
    standing = await queued(client, facilitator_a, waiting_room.id)
    assert standing is not None
    assert standing["halt"] == BLOCKING


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
    session = await a_session(db_session, team_id=facilitator_a.team_id, ready_to_close=True)
    await room.save_comprehension(db_session, session, _ready_comprehension())
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


def _ready_comprehension() -> ComprehensionState:
    """Calibration, evidence, practice and consent — everything the floor no longer implies."""
    return ComprehensionState(
        ledger=[
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
            )
            for index, checkpoint in enumerate(checkpoints_for(P))
        ],
        practiced_scene_ids=scene_ids_for(P),
        recording_consent_given=True,
    )


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
    session = await a_session(db_session, team_id=facilitator_a.team_id, ready_to_close=True)
    await room.save_comprehension(db_session, session, _ready_comprehension())
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
    the_assessor_agrees: None,
) -> None:
    """The team's own way out is untouched, and it does not erase who went.

    `append_exchange` is deliberately left alone by this slice: a landing turn goes on lifting
    a halt of either kind, which `test_the_pause_is_not_a_latch` already holds. The regression
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
