"""ENG-792 — a facilitator lifts a tablet's halt from the Desk, and the long press is heard.

ENG-624 gave a tablet with no session a way to say it needs a person, and gave that halt one
exit: the tablet opening a session. So the queue drained only when the room came back on its
own. The person who walked over, helped, and left had no way to say so, and the row they had
already answered stayed at the top of everyone else's queue.

The other half is the tablet's. A halted tablet shows something to press when somebody
arrives, and until now that press reached nothing — the server did not know a person was
standing in the room, so neither did the Desk.

Everything here goes in through a route and comes out through what a facilitator can read:
the person queue and the team's devices panel and session history. No row is asserted, and
no service is called for its answer, because a fact nobody can reach through the API is the
half of this slice that would not exist.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.unlink_device import unlink_device
from app.services.internalization_room import sessions as room
from app.services.internalization_room.comprehension.checkpoints import checkpoints_for
from app.services.internalization_room.comprehension.evidence import EvidenceMethod
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
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
DEVICES = "/api/facilitator/devices"
ROOM_KEY = "sala-de-teste"
ROOM_KEY_HEADER = "X-Room-Key"

P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
FIRST_QUESTION = "Quem aparece nesta parte?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
EXCERPT = "Noemi voltou"


# --- the neighbours a landing turn goes through -------------------------------------------


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio",
        mime_type="audio/mpeg",
        etag="e",
        cached=False,
        key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
    )
    return entry, False


class _AgreeingModels:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's door and both of the Desk's, because the mark crosses all three.

    The tablet halts through the room, the facilitator marks through the devices router, and
    what changed is read through the teams router. A test app carrying fewer than three could
    not see the thing this slice is.

    The synthesiser and the transcriber are the neighbours' fakes and nothing here asserts on
    them: they stand in for the services a landing turn reaches through, and a landing turn is
    how case 6 gets the halt lifted the way the team lifts it.
    """
    from fastapi import FastAPI

    from app.api.facilitator.devices import facilitator_devices_router
    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room.hearing import HeardSpeech

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)

    async def _heard_speech(audio: bytes, **_: Any) -> Any:
        return HeardSpeech(text=TEAM_ANSWER)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard_speech)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=DESK)
    test_app.include_router(facilitator_devices_router, prefix=DEVICES)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- the two teams, their facilitators, and their tablets ---------------------------------


@dataclass(frozen=True)
class Team:
    """A team and the one person who facilitates it. A team is a project in this system."""

    project: Any
    user: Any
    headers: dict[str, str]


@dataclass(frozen=True)
class Tablet:
    """A claimed device and the credential that lets it name itself."""

    device_id: str
    credential: str


async def a_team(db: AsyncSession, *, code: str) -> Team:
    """A team, its language and its facilitator. ``code`` is unique across the languages."""
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=f"facilitador-{code}@example.com")
    language = await make_language(db, name=f"Lingua {code}", code=code)
    project = await make_project(db, language.id, name=f"Equipe {code}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return Team(project=project, user=user, headers={"Authorization": f"Bearer {access}"})


async def a_tablet(db: AsyncSession, team: Team, *, label: str | None = None) -> Tablet:
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=team.user, code=minted.claim_code, project_id=team.project.id, label=label
    )
    return Tablet(device_id=claimed.device.id, credential=claimed.credential)


@pytest.fixture()
async def team_a(db_session: AsyncSession) -> Team:
    return await a_team(db_session, code="eqa")


@pytest.fixture()
async def team_b(db_session: AsyncSession) -> Team:
    """Facilitates its own team and nothing else — the only caller that can tell the scoping
    apart from no scoping at all."""
    return await a_team(db_session, code="eqb")


# --- what the tablet and the facilitator do -----------------------------------------------


async def the_tablet_halts(client: httpx.AsyncClient, device_id: str) -> httpx.Response:
    """The tablet with no session says it cannot go on without a person."""
    return await client.post(
        f"{IR}/devices/{device_id}/needs-person", headers={ROOM_KEY_HEADER: ROOM_KEY}
    )


async def attend(client: httpx.AsyncClient, device_id: str, who: Team) -> httpx.Response:
    return await client.post(f"{DEVICES}/{device_id}/attended", headers=who.headers)


async def unattend(client: httpx.AsyncClient, device_id: str, who: Team) -> httpx.Response:
    return await client.delete(f"{DEVICES}/{device_id}/attended", headers=who.headers)


async def queued_devices(client: httpx.AsyncClient, who: Team) -> list[dict]:
    """The devices half of the person queue, for the facilitator holding ``who``'s headers."""
    answered = await client.get(f"{IR}/facilitator/sessions", headers=who.headers)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["devices"]


async def queued_device(client: httpx.AsyncClient, who: Team, device_id: str) -> dict | None:
    return next(
        (row for row in await queued_devices(client, who) if row["device_id"] == device_id), None
    )


async def device_rows(client: httpx.AsyncClient, who: Team) -> dict[str, dict]:
    """What the team's devices panel says, device by device."""
    listed = await client.get(f"{DESK}/{who.project.id}/devices", headers=who.headers)
    assert listed.status_code == 200, listed.text[:300]
    return {row["device_id"]: row for row in listed.json()}


def moment(served: str) -> datetime:
    """One instant, however the route that served it spelled the offset.

    The queue serves these as strings it formats itself and the history serves them as
    datetimes Pydantic formats, so the same instant reaches this file as ``+00:00`` from one
    and ``Z`` from the other. Comparing the text would assert which module a field came out
    of; what the cases are about is whether it is the same moment.
    """
    return datetime.fromisoformat(served.replace("Z", "+00:00"))


async def open_a_session(client: httpx.AsyncClient, credential: str) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions",
        headers={DEVICE_CREDENTIAL_HEADER: credential},
        json={"pericope": P},
    )


# --- Case 1 — the mark lifts the halt, and the lift is readable ---------------------------


async def test_marking_a_tablet_attended_lifts_its_halt_and_records_who_went(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team
) -> None:
    """The halt ENG-624 could raise and only the tablet could lower.

    A person walks over to a tablet that stopped, helps, and leaves. Nothing about that
    reaches the server: the tablet may not come back for an hour, and until it does the row
    sits at the top of the queue every other facilitator reads.

    The second tablet is not decoration. With one device on the team, a panel that stamped
    every row would pass this, and so would a queue that listed nothing at all.
    """
    stopped = await a_tablet(db_session, team_a, label="Tablet da Ana")
    working = await a_tablet(db_session, team_a)

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200
    standing = await queued_device(client, team_a, stopped.device_id)
    assert standing is not None, "o tablet parou e a fila não o mostra"
    assert standing["attended_at"] is None
    assert standing["attended_by"] is None

    marked = await attend(client, stopped.device_id, team_a)

    assert marked.status_code == 200, marked.text[:300]
    answered = marked.json()
    assert answered["device_id"] == stopped.device_id
    assert answered["needs_person_since"] is None, (
        "quem foi até o tablet o atendeu, e a parada continua de pé"
    )
    assert answered["attended_at"]
    assert answered["attended_by"] == team_a.user.id

    assert await queued_device(client, team_a, stopped.device_id) is None, (
        "o tablet atendido continua na fila de quem já foi até ele"
    )

    panel = await device_rows(client, team_a)
    assert panel[stopped.device_id]["needs_person_since"] is None
    assert panel[stopped.device_id]["attended_at"] == answered["attended_at"]
    assert panel[stopped.device_id]["attended_by"] == team_a.user.id
    assert panel[working.device_id]["attended_at"] is None
    assert panel[working.device_id]["attended_by"] is None

    again = await attend(client, stopped.device_id, team_a)

    assert again.status_code == 200, again.text[:300]
    assert again.json()["attended_at"] == answered["attended_at"], (
        "dois toques são uma visita, e a marca passou a dizer quando alguém mexeu na mesa"
    )


# --- Case 2 — scoped ----------------------------------------------------------------------


async def test_only_a_facilitator_of_the_tablets_own_team_can_mark_it_attended(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team, team_b: Team
) -> None:
    """Without this the route writes to any tablet in the installation.

    A route that refused everybody would pass every refusal here and be just as wrong, and
    nothing about a world where nothing works looks broken — so the case ends by having A
    mark the very tablet B was refused. The refusals only mean something beside that.

    A tablet taken out of service is refused differently, and the difference is the point.
    It is not somebody else's tablet and not an id that was never minted — it is a tablet
    nobody can walk to, so there is no visit to record. Telling that apart from "no such
    thing" is safe here in a way it is not elsewhere: the caller already facilitates it.
    """
    stopped = await a_tablet(db_session, team_a)
    retired = await a_tablet(db_session, team_a)
    await unlink_device(db_session, user=team_a.user, device_id=retired.device_id)

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200

    refused = await attend(client, stopped.device_id, team_b)

    assert refused.status_code == 404, refused.text[:300]
    assert await queued_device(client, team_a, stopped.device_id) is not None, (
        "a parada caiu por mão de quem não facilita esta equipe"
    )

    assert (await attend(client, str(uuid.uuid4()), team_a)).status_code == 404
    assert (await attend(client, retired.device_id, team_a)).status_code == 409

    allowed = await attend(client, stopped.device_id, team_a)

    assert allowed.status_code == 200, allowed.text[:300]
    assert allowed.json()["attended_by"] == team_a.user.id
    assert await queued_device(client, team_a, stopped.device_id) is None


# --- Case 3 — the undo brings the halt back, with the moment it had ------------------------


async def test_undoing_the_mark_puts_the_halt_back_at_the_moment_it_was_raised(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team
) -> None:
    """A mark is a claim about the physical world, and the tap can be on the wrong row.

    What comes back is the *original* moment and not the moment of the undo. The queue is
    ordered by that moment, newest halt first, and the facilitator reads the age off it — so
    an undo that restamped would put a tablet that stopped twenty minutes ago at the head of
    the list, above rooms that really did stop after it, announcing a halt that never happened.
    """
    stopped = await a_tablet(db_session, team_a)

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200
    raised = await queued_device(client, team_a, stopped.device_id)
    assert raised is not None
    since = raised["since"]

    assert (await attend(client, stopped.device_id, team_a)).status_code == 200
    assert await queued_device(client, team_a, stopped.device_id) is None

    undone = await unattend(client, stopped.device_id, team_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["attended_at"] is None
    assert undone.json()["attended_by"] is None

    asking_again = await queued_device(client, team_a, stopped.device_id)
    assert asking_again is not None, "ninguém foi, afinal, e o tablet não voltou a pedir"
    assert asking_again["since"] == since, (
        "a parada voltou com a hora do arrependimento, e a fila mente sobre quem espera há mais"
        " tempo"
    )
    assert asking_again["attended_at"] is None
    assert asking_again["attended_by"] is None


# --- Case 4 — the undo moves nothing once the tablet has come back ------------------------


async def test_undoing_the_mark_after_the_tablet_came_back_does_not_stop_it_again(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team
) -> None:
    """The tablet opening a session is its own exit and would have lifted the halt anyway.

    So by the time the facilitator notices they tapped the wrong row there is nothing left
    for the undo to restore. Without this, the undo only moves the defect: a tablet in the
    middle of a session goes back on the queue because somebody corrected a ten-minute-old
    tap, and the facilitator walks to a room that is working.
    """
    stopped = await a_tablet(db_session, team_a)

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200
    assert await queued_device(client, team_a, stopped.device_id) is not None
    assert (await attend(client, stopped.device_id, team_a)).status_code == 200

    resumed = await open_a_session(client, stopped.credential)
    assert resumed.status_code == 200, resumed.text[:300]

    undone = await unattend(client, stopped.device_id, team_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["attended_at"] is None
    assert undone.json()["needs_person_since"] is None
    assert await queued_device(client, team_a, stopped.device_id) is None, (
        "o tablet já tinha voltado e desfazer a marca o parou outra vez"
    )
    assert (await device_rows(client, team_a))[stopped.device_id]["needs_person_since"] is None


# --- Case 5 — a mark on a tablet that never halted -----------------------------------------


async def test_a_tablet_that_never_halted_can_be_marked_and_moves_nowhere(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team
) -> None:
    """They went anyway, and that is worth recording; halting a working tablet is not.

    The undo of such a mark is the case that separates "put back what this mark lifted" from
    "put back a halt": there was none, so nothing comes back and the tablet stays out of the
    queue it was never in.
    """
    working = await a_tablet(db_session, team_a)

    marked = await attend(client, working.device_id, team_a)

    assert marked.status_code == 200, marked.text[:300]
    assert marked.json()["attended_at"]
    assert marked.json()["attended_by"] == team_a.user.id
    assert marked.json()["needs_person_since"] is None
    assert await queued_devices(client, team_a) == []

    undone = await unattend(client, working.device_id, team_a)

    assert undone.status_code == 200, undone.text[:300]
    assert undone.json()["attended_at"] is None
    assert await queued_devices(client, team_a) == [], (
        "desfazer uma visita a um tablet que nunca parou inventou uma parada"
    )
    assert (await device_rows(client, team_a))[working.device_id]["needs_person_since"] is None


# --- Case 6 — the long press reaches the server, once per halt -----------------------------


@pytest.fixture()
def target_checkpoint() -> str:
    return next(checkpoint for checkpoint in checkpoints_for(P) if checkpoint.critical).id


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
async def waiting_room(db_session: AsyncSession, team_a: Team, target_checkpoint: str):
    """A room of A's team that has asked its question and is waiting on the answer."""
    session = await room.create_session(
        db_session,
        language="pt",
        pericope=P,
        project_id=team_a.project.id,
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


async def the_session_halts(client: httpx.AsyncClient, session_id: str) -> None:
    asked = await client.post(
        f"{IR}/sessions/{session_id}/needs-person", headers={ROOM_KEY_HEADER: ROOM_KEY}
    )
    assert asked.status_code == 200, asked.text[:300]


async def somebody_arrives(
    client: httpx.AsyncClient, session_id: str, *, credential: str
) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/person-arrived",
        headers={DEVICE_CREDENTIAL_HEADER: credential},
    )


async def the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{IR}/sessions/{session_id}/turns",
        headers={ROOM_KEY_HEADER: ROOM_KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


async def queued_session(client: httpx.AsyncClient, who: Team, session_id: str) -> dict | None:
    listed = await client.get(f"{IR}/facilitator/sessions", headers=who.headers)
    assert listed.status_code == 200, listed.text[:300]
    return next((row for row in listed.json()["sessions"] if row["session_id"] == session_id), None)


async def history_row(client: httpx.AsyncClient, who: Team, session_id: str) -> dict:
    answer = await client.get(f"{DESK}/{who.project.id}/sessions", headers=who.headers)
    assert answer.status_code == 200, answer.text[:300]
    return next(card for card in answer.json() if card["session_id"] == session_id)


async def test_the_long_press_is_recorded_once_and_a_new_halt_is_a_new_wait(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    team_a: Team,
    waiting_room,
    the_assessor_agrees: None,
) -> None:
    """Somebody is standing in the room, and until now only the room knew.

    The halt says a person is needed and nothing said one had come. A facilitator reading the
    queue could not tell a room still waiting from one a colleague was already standing in,
    so two people walk to the same room while another waits.

    **First touch wins.** The moment is when somebody arrived, and a press that restamped
    would record the last time a hand brushed the screen — a team pressing again because
    nothing visibly happened would keep resetting the very fact the Desk reads.

    **A new halt is a new wait.** The room stopped again, after the team came back and a turn
    landed; whoever came the first time answered a halt that is over. Carrying the moment
    forward would show the new halt as already answered, and nobody would go.
    """
    tablet = await a_tablet(db_session, team_a)
    await the_session_halts(client, waiting_room.id)

    touched = await somebody_arrives(client, waiting_room.id, credential=tablet.credential)

    assert touched.status_code == 200, touched.text[:300]
    arrived = touched.json()["person_arrived_at"]
    assert arrived, "o toque longo chegou ao servidor e não deixou hora nenhuma"
    assert touched.json()["session_id"] == waiting_room.id

    standing = await queued_session(client, team_a, waiting_room.id)
    assert standing is not None
    assert moment(standing["person_arrived_at"]) == moment(arrived)
    card = await history_row(client, team_a, waiting_room.id)
    assert moment(card["person_arrived_at"]) == moment(arrived)

    again = await somebody_arrives(client, waiting_room.id, credential=tablet.credential)

    assert again.status_code == 200, again.text[:300]
    assert again.json()["person_arrived_at"] == arrived, (
        "o segundo toque moveu a hora, e a mesa passa a ler quando a tela foi tocada"
    )

    answered = await the_team_answers(client, waiting_room.id)
    assert answered.status_code == 200, answered.text[:300]
    await the_session_halts(client, waiting_room.id)

    asking_again = await queued_session(client, team_a, waiting_room.id)
    assert asking_again is not None, "a sala parou outra vez e a fila não a mostra"
    assert asking_again["person_arrived_at"] is None, (
        "a parada nova nasceu já atendida pela visita da parada anterior"
    )


# --- Case 8 — a tablet that halts again is not a halt somebody already answered ------------


async def test_a_tablet_that_halts_again_after_a_visit_comes_back_unanswered(
    client: httpx.AsyncClient, db_session: AsyncSession, team_a: Team
) -> None:
    """A new ask is an unattended ask, on the device side as on the session side.

    A tablet is marked attended, which lifts its halt and takes it off the queue. Then it
    stops again — without ever opening a session, which is the whole shape ENG-624 exists for.
    Carrying the visit forward puts the row back on the queue already stamped with somebody's
    name, and the facilitator reading it skips a tablet nobody has been to. The mark would be
    delivering that reading exclusively by being stale, which is the argument
    ``mark_needs_person`` makes for clearing the same pair on a session.
    """
    stopped = await a_tablet(db_session, team_a)

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200
    assert (await attend(client, stopped.device_id, team_a)).status_code == 200
    assert await queued_device(client, team_a, stopped.device_id) is None

    assert (await the_tablet_halts(client, stopped.device_id)).status_code == 200

    asking_again = await queued_device(client, team_a, stopped.device_id)
    assert asking_again is not None, "o tablet parou de novo e a fila não o mostra"
    assert asking_again["attended_at"] is None, (
        "a parada nova nasceu já atendida pela visita da parada anterior"
    )
    assert asking_again["attended_by"] is None
    assert (await device_rows(client, team_a))[stopped.device_id]["attended_at"] is None
