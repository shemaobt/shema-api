"""ENG-1236 — the room's open door returns the team's latest session of a pericope, created once.

Every open asks the server, and the server answers with the session it holds for that team,
pericope and language, whatever its state, minting one only when none exists. The cases go
through `POST /sessions` and the turn route with the credentials of real teams' tablets, and
read what a tablet or the Desk observes: the id it is handed, the turns the Desk reads, the
one opening. Two cases read the table, because what they assert is that no second row exists
and the Desk does not list a session nobody entered.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.internalization_room import sessions as sessions_api
from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    attend,
    get_session,
    is_panorama,
)
from app.services.internalization_room.voice_handles import clip_url
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    having_finished_the_passage,
    make_app,
    make_project_user_access,
    make_role,
    make_user,
    open_ir_session,
)
from tests.release_harness import KEY, PREFIX, P, a_claimed_device, at_the_desk, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks
from tests.text_seam_harness import RUNNER_KEY
from tests.turn_harness import the_room_agent_is

FIRST = load_book(ROOM_BOOK)[0].pericope_num
GUIDE_OPENING = "Vamos ouvir a historia de Rute. O que voces ja sabem dela?"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"
ANSWERS = (
    "Noemi voltou para Belem com Rute",
    "Rute disse que ia junto com ela",
    "Noemi chegou na colheita da cevada",
)


class _Script:
    def __init__(self) -> None:
        self.said = ""


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> _Script:
    scripted = _Script()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=scripted.said)

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_OPENING if not scripted.said else GUIDE_LINE

    async def voice(text: str, **_: Any):
        return (
            SynthesizedSpeech(
                audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/x.mp3"
            ),
            False,
        )

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    the_room_agent_is(monkeypatch, turn=model)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    return scripted


@pytest.fixture()
def prepared(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    async def _remember(session_id: str, *_: Any, **__: Any) -> None:
        asked.append(session_id)

    monkeypatch.setattr(sessions_api, "prepare_opening", _remember)
    return asked


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(
        db_session, monkeypatch, runner_key=RUNNER_KEY, per_request=per_request
    ) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def another_tablet_of(db: AsyncSession, team: Project) -> str:
    """A tablet a facilitator of this team claimed, and the credential it calls with."""
    user = await make_user(db, email=f"fac-{uuid.uuid4()}@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=team.id
    )
    return claimed.credential


async def the_tablet_opens(
    client: httpx.AsyncClient, credential: str, body: dict[str, Any]
) -> dict[str, Any]:
    opened = await client.post(f"{PREFIX}/sessions", headers=team_headers(credential), json=body)
    assert opened.status_code == 200, opened.text[:300]
    return opened.json()


async def the_room_opens(client: httpx.AsyncClient, credential: str, session_id: str) -> None:
    spoken = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    assert spoken.status_code == 200, spoken.text[:300]


async def the_team_says(
    client: httpx.AsyncClient, script: _Script, credential: str, session_id: str, said: str
) -> None:
    script.said = said
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": str(uuid.uuid4())},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert response.status_code == 200, response.text[:300]


async def three_turns_on(
    client: httpx.AsyncClient, script: _Script, credential: str, session_id: str
) -> None:
    await the_room_opens(client, credential, session_id)
    for said in ANSWERS:
        await the_team_says(client, script, credential, session_id, said)


async def what_the_team_said(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> list[str]:
    read = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/conversation", headers=desk
    )
    assert read.status_code == 200, read.text[:300]
    return [turn["text"] for turn in read.json()["turns"] if turn["role"] == "team"]


async def sessions_of(
    per_request: async_sessionmaker[AsyncSession], team: Project, pericope: str
) -> list[IRSession]:
    async with per_request() as fresh:
        rows = await fresh.execute(
            select(IRSession).where(IRSession.project_id == team.id, IRSession.pericope == pericope)
        )
        return list(rows.scalars().all())


async def test_a_team_that_reopens_a_pericope_after_three_turns_lands_on_the_same_session_with_its_three_turns(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await three_turns_on(client, script, tablet, opened["session_id"])

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    assert reopened["session_id"] == opened["session_id"]
    assert await what_the_team_said(client, desk, reopened["session_id"]) == list(ANSWERS)


async def test_a_second_tablet_of_the_same_team_opening_the_same_pericope_gets_the_same_session(
    client, db_session, room_app, script
) -> None:
    team, first_tablet = await a_claimed_device(db_session)
    second_tablet = await another_tablet_of(db_session, team)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, first_tablet, {"pericope": P, "language": "pt"})
    await three_turns_on(client, script, first_tablet, opened["session_id"])

    joined = await the_tablet_opens(client, second_tablet, {"pericope": P, "language": "pt"})

    assert joined["session_id"] == opened["session_id"]
    assert await what_the_team_said(client, desk, joined["session_id"]) == list(ANSWERS)


async def test_two_tablets_opening_the_same_pericope_at_the_same_instant_get_one_session_and_hear_one_opening(  # noqa: E501
    client, db_session, per_request, script
) -> None:
    team, first_tablet = await a_claimed_device(db_session)
    second_tablet = await another_tablet_of(db_session, team)
    body = {"pericope": P, "language": "pt"}

    first, second = await asyncio.gather(
        the_tablet_opens(client, first_tablet, body),
        the_tablet_opens(client, second_tablet, body),
    )
    await the_room_opens(client, first_tablet, first["session_id"])
    await the_room_opens(client, second_tablet, second["session_id"])

    assert first["session_id"] == second["session_id"]
    stored = await sessions_of(per_request, team, P)
    assert [session.id for session in stored] == [first["session_id"]]
    assert [m["text"] for m in stored[0].messages if m["role"] == "guide"] == [GUIDE_OPENING]


async def test_a_reinstalled_tablet_opening_the_pericope_resumes_the_servers_session(
    client, db_session, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await three_turns_on(client, script, tablet, opened["session_id"])
    reinstalled = await another_tablet_of(db_session, team)

    resumed = await the_tablet_opens(client, reinstalled, {"pericope": P, "language": "pt"})

    assert resumed["session_id"] == opened["session_id"]


async def test_the_panorama_reopened_after_a_relaunch_is_the_same_panorama_session_and_no_second_opening_is_prepared(  # noqa: E501
    client, db_session, prepared
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    launched = await the_tablet_opens(client, tablet, {"pericope": "OV"})

    relaunched = await the_tablet_opens(client, tablet, {"pericope": "OV"})

    assert is_panorama(relaunched["pericope"])
    assert relaunched["session_id"] == launched["session_id"]
    assert prepared == [launched["session_id"]]


async def test_a_teams_latest_session_wins_when_the_team_already_holds_several_for_one_pericope(
    client, db_session
) -> None:
    team, tablet = await a_claimed_device(db_session)
    touched_last = await open_ir_session(db_session, pericope=P, project_id=team.id)
    touched_first = await open_ir_session(db_session, pericope=P, project_id=team.id)
    for session, created, touched in (
        (
            touched_last,
            datetime(2026, 9, 28, 10, 0, tzinfo=UTC),
            datetime(2026, 9, 30, 10, 0, tzinfo=UTC),
        ),
        (
            touched_first,
            datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
            datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        ),
    ):
        await db_session.execute(
            update(IRSession)
            .where(IRSession.id == session.id)
            .values(created_at=created, updated_at=touched)
        )
    await db_session.commit()

    opened = await the_tablet_opens(client, tablet, {"pericope": P})

    assert opened["session_id"] == touched_last.id


async def test_the_teams_entered_conversation_wins_over_a_newer_empty_launch(
    client, db_session
) -> None:
    team, tablet = await a_claimed_device(db_session)
    conversation = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await append_exchange(
        db_session, conversation, team_utterance=ANSWERS[0], guide_response=GUIDE_LINE
    )
    launch = await open_ir_session(db_session, pericope=P, project_id=team.id)
    for session, touched in (
        (conversation, datetime(2026, 9, 29, 10, 0, tzinfo=UTC)),
        (launch, datetime(2026, 9, 30, 10, 0, tzinfo=UTC)),
    ):
        await db_session.execute(
            update(IRSession)
            .where(IRSession.id == session.id)
            .values(created_at=touched, updated_at=touched)
        )
    await db_session.commit()

    opened = await the_tablet_opens(client, tablet, {"pericope": P})

    assert opened["session_id"] == conversation.id


async def test_another_team_opening_the_same_pericope_gets_its_own_session(
    client, db_session
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    _other, other_tablet = await a_claimed_device(db_session, email="outra@example.com")
    ours = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    theirs = await the_tablet_opens(client, other_tablet, {"pericope": P, "language": "pt"})

    assert theirs["session_id"] != ours["session_id"]


async def test_a_caller_with_no_team_still_gets_a_fresh_session_on_every_open(client) -> None:
    body = {"pericope": P, "language": "pt"}
    first = await client.post(f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json=body)
    second = await client.post(f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json=body)

    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] != second.json()["session_id"]


async def test_the_text_seam_still_mints_a_session_on_every_open(client) -> None:
    body = {"pericopeId": P, "language": "pt"}
    first = await client.post(f"{PREFIX}/text-seam/session", json=body)
    second = await client.post(f"{PREFIX}/text-seam/session", json=body)

    assert first.status_code == second.status_code == 200
    assert first.json()["sessionId"] != second.json()["sessionId"]


async def test_a_pericope_opened_before_the_panorama_keeps_the_panorama_heard_once_the_team_comes_back_to_it_from_the_panorama(  # noqa: E501
    client, db_session, prepared
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    worked = await the_tablet_opens(client, tablet, {"pericope": FIRST})
    panorama = await the_tablet_opens(client, tablet, {"pericope": "OV"})
    assert is_panorama(panorama["pericope"])

    entered = await the_tablet_opens(
        client, tablet, {"pericope": FIRST, "after_session": panorama["session_id"]}
    )
    relaunched = await the_tablet_opens(client, tablet, {"pericope": "OV"})

    assert entered["session_id"] == worked["session_id"]
    assert relaunched["session_id"] == worked["session_id"]


async def test_a_closed_pericopes_session_is_returned_as_it_stands(
    client, db_session, per_request
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": P})
    async with per_request() as fresh:
        await having_finished_the_passage(fresh, await get_session(fresh, opened["session_id"]))

    reopened = await the_tablet_opens(client, tablet, {"pericope": P})

    assert reopened["session_id"] == opened["session_id"]
    assert reopened["status"] == "done"


async def waiting_at_the_desk(client: httpx.AsyncClient, desk: dict[str, str]) -> dict[str, Any]:
    queue = await client.get(f"{PREFIX}/facilitator/sessions", headers=desk)
    assert queue.status_code == 200, queue.text[:300]
    return {row["session_id"]: row["halt"] for row in queue.json()["sessions"]}


async def a_halted_room(
    client: httpx.AsyncClient, tablet: str, desk: dict[str, str]
) -> dict[str, Any]:
    opened = await the_tablet_opens(client, tablet, {"pericope": P})
    called = await client.post(
        f"{PREFIX}/sessions/{opened['session_id']}/needs-person", headers=team_headers(tablet)
    )
    assert called.status_code == 200, called.text[:300]
    assert (await waiting_at_the_desk(client, desk)) == {opened["session_id"]: "blocking"}
    return opened


async def test_a_tablet_relaunched_in_a_room_halted_by_its_call_for_a_person_gets_the_session_back_unhalted(  # noqa: E501
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    halted = await a_halted_room(client, tablet, desk)

    relaunched = await the_tablet_opens(client, tablet, {"pericope": P})

    assert relaunched["session_id"] == halted["session_id"]
    assert relaunched["halt"] is None
    assert relaunched["status"] == "in_progress"
    assert await waiting_at_the_desk(client, desk) == {}


def the_visit(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/attended"


async def test_a_visit_undone_after_the_tablet_reopened_the_room_leaves_the_room_going(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    halted = await a_halted_room(client, tablet, desk)
    visited = await client.post(the_visit(halted["session_id"]), headers=desk)
    assert visited.status_code == 200, visited.text[:300]
    await the_tablet_opens(client, tablet, {"pericope": P})

    undone = await client.delete(the_visit(halted["session_id"]), headers=desk)

    assert undone.status_code == 200, undone.text[:300]
    assert await waiting_at_the_desk(client, desk) == {}


async def test_a_visit_that_lands_while_the_tablet_reopens_the_room_leaves_nothing_to_put_back(
    client, db_session, room_app, test_engine
) -> None:
    """The visit commits between the open's read of the halt and the open's write, which is
    the order two requests can take in the field: the open's write is held until the
    facilitator's own request has landed, through the room's real `attend`."""
    team, tablet = await a_claimed_device(db_session)
    desk, facilitator = await at_the_desk(db_session, room_app, team)
    halted = await a_halted_room(client, tablet, desk)
    url = test_engine.url.render_as_string(hide_password=False)
    landed: list[str] = []
    visited: list[str] = []

    async def visit() -> None:
        engine = create_async_engine(url)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await attend(db, await get_session(db, halted["session_id"]), by=facilitator.id)
            visited.append(halted["session_id"])
        await engine.dispose()

    def the_visit_lands_first(_conn, _cursor, statement, *_: Any) -> None:
        if landed or not statement.startswith("UPDATE ir_sessions"):
            return
        landed.append(statement)
        other = threading.Thread(target=asyncio.run, args=(visit(),))
        other.start()
        other.join()

    event.listen(test_engine.sync_engine, "before_cursor_execute", the_visit_lands_first)
    try:
        await the_tablet_opens(client, tablet, {"pericope": P})
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", the_visit_lands_first)
    assert landed, "the open wrote nothing for the visit to land before"
    assert visited == [halted["session_id"]], "the visit never committed"

    undone = await client.delete(the_visit(halted["session_id"]), headers=desk)

    assert undone.status_code == 200, undone.text[:300]
    assert await waiting_at_the_desk(client, desk) == {}


PREPARED_OPENING = "Esta e a primeira linha da passagem, preparada durante o Panorama."
PREPARED_CLIP = "tts/prepared.mp3"


async def test_a_prepared_opening_is_never_handed_to_a_session_the_team_already_spoke_in(
    client, db_session, per_request, script, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def a_line_is_ready(session_id: str, *_: Any, **__: Any) -> None:
        async with per_request() as fresh:
            panorama = await get_session(fresh, session_id)
            panorama.prepared_speech = PREPARED_OPENING
            panorama.prepared_audio_key = PREPARED_CLIP
            panorama.prepared_pericope = FIRST
            await fresh.commit()

    monkeypatch.setattr(sessions_api, "prepare_opening", a_line_is_ready)
    _team, tablet = await a_claimed_device(db_session)
    worked = await the_tablet_opens(client, tablet, {"pericope": FIRST})
    await three_turns_on(client, script, tablet, worked["session_id"])
    panorama = await the_tablet_opens(client, tablet, {"pericope": "OV"})
    assert is_panorama(panorama["pericope"])
    entered = await the_tablet_opens(
        client, tablet, {"pericope": FIRST, "after_session": panorama["session_id"]}
    )
    assert entered["session_id"] == worked["session_id"]

    asked_again = await client.post(
        f"{PREFIX}/sessions/{entered['session_id']}/turns", headers=team_headers(tablet)
    )
    script.said = "E depois?"
    answered = await client.post(
        f"{PREFIX}/sessions/{entered['session_id']}/turns",
        headers=team_headers(tablet),
        data={"turn_id": str(uuid.uuid4())},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert asked_again.status_code == answered.status_code == 200
    heard = [asked_again.json()["audio_url"], answered.json()["audio_url"]]
    assert clip_url(PREPARED_CLIP) not in heard
    async with per_request() as fresh:
        said = (await get_session(fresh, entered["session_id"])).messages
    assert PREPARED_OPENING not in [line["text"] for line in said if line["role"] == "guide"]
