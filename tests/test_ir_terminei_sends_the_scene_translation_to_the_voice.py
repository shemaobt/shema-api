"""ENG-1321 — «terminei» sends the scene translation to the voice as a rehearsal turn.

A **Scene rehearsal** with at least one translated **Scene frase** is sent through the tablet's
door by reference and a turn id. The voice is handed her bracketed **Room note** and then the
live frases' words in recording order, with no recognizer and no audio, and the rehearsal is
frozen as sent. The Guide is a double that keeps what it was handed; everything else is the
room's own doors and tables.
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
import wave
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from app.services import internalization_room as room_service
from tests.baker import make_app, make_project_user_access, make_role, make_user, make_user_app_role
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.hearing_harness import nothing_settles
from tests.room_harness import the_room_speaks
from tests.turn_harness import the_room_agent_is

IR = "/api/internalization-room"
P = "P01"
GUIDE_LINE = "Obrigado. Vamos ver essa cena juntos."

THREE_PT = (
    "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena frase por frase "
    "(3 frases). Segue a tradução, na ordem:]"
)
TWO_PT = (
    "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena frase por frase "
    "(2 frases). Segue a tradução, na ordem:]"
)
ONE_PT = (
    "[A equipe ensaiou esta cena na língua materna e traduziu o ensaio da cena. Segue a tradução:]"
)
THREE_EN = (
    "[The team rehearsed this scene in their own language and translated the scene rehearsal "
    "phrase by phrase (3 phrases). The translation follows, in order:]"
)
ONE_EN = (
    "[The team rehearsed this scene in their own language and translated the scene rehearsal. "
    "The translation follows:]"
)


def recording(seconds: float, tone: int) -> bytes:
    """A 16 kHz mono WAV whose bytes differ by `tone`, so two recordings never share a hash."""
    frames = int(seconds * 16_000)
    sample = (tone % 30_000).to_bytes(2, "little", signed=True)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(sample * frames)
    return out.getvalue()


SCENE = recording(40, 1)


class Guide:
    """The voice: keeps every turn it is handed, and answers after `thinks` seconds."""

    def __init__(self) -> None:
        self.inputs: list[str] = []
        self.thinks = 0.0
        self.asked = asyncio.Event()
        self.holds: asyncio.Event | None = None

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.inputs.append(user_content)
        self.asked.set()
        if self.holds is not None:
            await self.holds.wait()
        await asyncio.sleep(self.thinks)
        return GUIDE_LINE


@dataclass
class Room:
    client: httpx.AsyncClient
    desk: dict[str, str]
    bucket: MemoryStore
    guide: Guide
    heard: list[dict[str, Any]]
    answers: list[str] = field(default_factory=list)


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import hearing
    from app.services.internalization_room import takes as takes_service
    from app.services.internalization_room.takes import take_store

    heard: list[dict[str, Any]] = []
    answers: list[str] = []

    async def _transcribe(audio: bytes, **kwargs: Any) -> str:
        heard.append({"audio": audio, **kwargs})
        return answers.pop(0)

    async def _sign(_bucket: str, key: str, **_: Any) -> str:
        return f"https://storage.example/{key}"

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", _sign)
    the_room_speaks(monkeypatch)
    guide = Guide()
    the_room_agent_is(monkeypatch, turn=guide)
    nothing_settles(monkeypatch)
    bucket = MemoryStore()

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        async with rival_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = _get_db
    test_app.dependency_overrides[take_store] = lambda: bucket

    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    facilitator = await make_user(db_session, email=f"leitor-{uuid.uuid4().hex[:8]}@example.com")
    await make_project_user_access(
        db_session, TABLET_TEAM, facilitator.id, role=ProjectRole.FACILITATOR
    )
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, facilitator.id, app.id, role.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, facilitator)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet.headers
    ) as client:
        yield Room(
            client=client,
            desk={"Authorization": f"Bearer {access}"},
            bucket=bucket,
            guide=guide,
            heard=heard,
            answers=answers,
        )


async def an_opened_session(
    room: Room, db: AsyncSession, *, language: str = "pt", pericope: str = P
) -> str:
    """A session whose opening the voice has already said, the voice's inputs then forgotten."""
    session = await room_service.create_session(
        db, project_id=TABLET_TEAM, language=language, pericope=pericope
    )
    session_id = str(session.id)
    opened = await room.client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    room.guide.inputs.clear()
    room.guide.asked.clear()
    return session_id


async def a_rehearsal(
    room: Room, session_id: str, audio: bytes = SCENE, scene: str | None = "S2"
) -> str:
    kept = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals",
        data={} if scene is None else {"scene": scene},
        files={"file": ("cena.wav", audio, "audio/wav")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["rehearsal_id"])


async def a_frase(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    place: tuple[int, int],
    said: str,
    *,
    tone: int,
    replaces: str | None = None,
    after_restart: str | None = None,
) -> httpx.Response:
    room.answers.append(said)
    data = {"starts_ms": str(place[0]), "ends_ms": str(place[1])}
    if replaces is not None:
        data["replaces"] = replaces
    if after_restart is not None:
        data["after_restart"] = after_restart
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/frases",
        data=data,
        files={"file": ("frase.wav", recording(1, tone), "audio/wav")},
    )


async def translated(
    room: Room, session_id: str, rehearsal_id: str, frases: list[tuple[tuple[int, int], str]]
) -> list[str]:
    """The frases recorded in the order given, each heard as its words; their ids by place."""
    for offset, (place, said) in enumerate(frases):
        kept = await a_frase(room, session_id, rehearsal_id, place, said, tone=100 + offset)
        assert kept.status_code == 200, kept.text
    listed = (await the_rehearsal(room, session_id, rehearsal_id))["frases"]
    return [frase["frase_id"] for frase in listed]


async def the_rehearsal(room: Room, session_id: str, rehearsal_id: str) -> dict[str, Any]:
    listed = await room.client.get(f"{IR}/sessions/{session_id}/scene-rehearsals")
    assert listed.status_code == 200, listed.text
    (found,) = [r for r in listed.json()["scene_rehearsals"] if r["rehearsal_id"] == rehearsal_id]
    return dict(found)


async def read_by_the_desk(room: Room, session_id: str, rehearsal_id: str) -> dict[str, Any]:
    read = await room.client.get(
        f"{IR}/facilitator/sessions/{session_id}/scene-rehearsals", headers=room.desk
    )
    assert read.status_code == 200, read.text
    (found,) = [r for r in read.json()["scene_rehearsals"] if r["rehearsal_id"] == rehearsal_id]
    return dict(found)


async def send(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    turn_id: str | None = None,
    *,
    closes: str | None = None,
) -> httpx.Response:
    data = {"turn_id": turn_id or str(uuid.uuid4())}
    if closes is not None:
        data["closes"] = closes
    return await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send", data=data
    )


async def claimed_by_hand(
    db: AsyncSession, rehearsal_id: str, turn_id: str, ago: timedelta
) -> None:
    """A claim left on the row by a request that is no longer running, landed nowhere."""
    from sqlalchemy import update

    from app.db.models.internalization_room import IRSceneRehearsal

    await db.execute(
        update(IRSceneRehearsal)
        .where(IRSceneRehearsal.id == rehearsal_id)
        .values(sent_at=datetime.now(UTC) - ago, sent_turn_id=turn_id)
    )
    await db.commit()


async def conversation(db: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    db.expire_all()
    stored = await room_service.get_session(db, session_id)
    return list(stored.messages or [])


async def three_translated(room: Room, session_id: str, rehearsal_id: str) -> list[str]:
    return await translated(
        room,
        session_id,
        rehearsal_id,
        [((5000, 9000), "dois"), ((0, 4000), "um"), ((10000, 14000), "três")],
    )


async def test_three_translated_frases_reach_the_voice_after_her_note_with_3_frases_in_recording_order(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await three_translated(room, session_id, rehearsal_id)

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{THREE_PT} um dois três"]


async def test_one_translated_frase_reaches_the_voice_after_her_note_with_no_count(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{ONE_PT} um"]


async def test_a_frase_translated_again_reaches_the_voice_only_in_its_newer_form(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    _first, second, _third = await three_translated(room, session_id, rehearsal_id)
    again = await a_frase(
        room, session_id, rehearsal_id, (5000, 9000), "dois de novo", tone=200, replaces=second
    )
    assert again.status_code == 200, again.text

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{THREE_PT} um dois de novo três"]


async def test_a_rehearsal_translated_over_half_its_recording_is_sent(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 10000), "um"), ((10000, 20000), "dois")])

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{TWO_PT} um dois"]


async def test_an_english_session_hands_the_voice_her_english_note(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session, language="en")
    three = await a_rehearsal(room, session_id)
    await translated(
        room,
        session_id,
        three,
        [((5000, 9000), "two"), ((0, 4000), "one"), ((10000, 14000), "three")],
    )
    one = await a_rehearsal(room, session_id, recording(20, 2))
    await translated(room, session_id, one, [((0, 4000), "one")])

    sent_three = await send(room, session_id, three)
    sent_one = await send(room, session_id, one)

    assert sent_three.status_code == 200, sent_three.text
    assert sent_one.status_code == 200, sent_one.text
    assert room.guide.inputs == [f"{THREE_EN} one two three", f"{ONE_EN} one"]


async def test_a_second_terminei_on_a_sent_rehearsal_is_refused_and_nothing_new_reaches_the_voice(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await three_translated(room, session_id, rehearsal_id)
    first = await send(room, session_id, rehearsal_id, "turno-a")
    assert first.status_code == 200, first.text
    handed = list(room.guide.inputs)
    kept = await conversation(db_session, session_id)

    second = await send(room, session_id, rehearsal_id, "turno-b")

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "SCENE_REHEARSAL_SENT"
    assert room.guide.inputs == handed
    assert await conversation(db_session, session_id) == kept


async def test_a_rehearsal_labelled_scene_2_reaches_the_voice_with_no_label_and_the_stored_turn_keeps_scene_2(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id, scene="S2")
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{ONE_PT} um"]
    guide_entry = (await conversation(db_session, session_id))[-1]
    assert guide_entry["scene_rehearsal"]["scene"] == "S2"


async def test_a_panorama_do_livro_refuses_the_send(room: Room, db_session: AsyncSession) -> None:
    session = await room_service.create_session(
        db_session, project_id=TABLET_TEAM, language="pt", pericope="OV-Ruth"
    )

    sent = await send(room, str(session.id), str(uuid.uuid4()))

    assert sent.status_code == 400, sent.text
    assert sent.json()["code"] == "PANORAMA_RECORDS_NOTHING"
    assert room.guide.inputs == []


async def test_the_send_runs_no_recognizer_and_stores_no_audio(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await three_translated(room, session_id, rehearsal_id)
    heard_before = len(room.heard)
    stored_before = dict(room.bucket.objects)

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    assert len(room.heard) == heard_before
    assert room.bucket.objects == stored_before


async def test_the_stored_turn_keeps_her_note_the_words_the_rehearsal_its_frases_and_the_recordings_length_and_the_rehearsal_keeps_when_it_was_sent_and_which_turn_answered_it(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id, scene="S2")
    await three_translated(room, session_id, rehearsal_id)

    sent = await send(room, session_id, rehearsal_id, "turno-da-cena")

    assert sent.status_code == 200, sent.text
    note, words, guide = (await conversation(db_session, session_id))[-3:]
    assert (note["role"], note["text"], note.get("room_note")) == ("team", THREE_PT, True)
    assert (words["role"], words["text"], words.get("room_note")) == ("team", "um dois três", None)
    assert (guide["role"], guide["text"]) == ("guide", GUIDE_LINE)
    assert guide["scene_rehearsal"] == {
        "rehearsal_id": rehearsal_id,
        "n": 1,
        "frases": 3,
        "scene": "S2",
    }
    assert guide["take_ms"] == 40_000
    assert (await read_by_the_desk(room, session_id, rehearsal_id))["sent_at"] is not None
    answered_by = await db_session.execute(
        text("SELECT sent_turn_id FROM ir_scene_rehearsals WHERE id = :id"), {"id": rehearsal_id}
    )
    assert answered_by.scalar_one() == "turno-da-cena"


async def test_a_rehearsal_with_no_frase_is_refused_and_stays_unsent(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 422, sent.text
    assert room.guide.inputs == []
    assert (await read_by_the_desk(room, session_id, rehearsal_id))["sent_at"] is None


async def test_a_rehearsal_this_session_never_kept_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    other_session = await an_opened_session(room, db_session)
    others = await a_rehearsal(room, other_session)
    await translated(room, other_session, others, [((0, 4000), "um")])

    foreign = await send(room, session_id, others)
    unknown = await send(room, session_id, str(uuid.uuid4()))

    assert foreign.status_code == 404, foreign.text
    assert unknown.status_code == 404, unknown.text
    assert room.guide.inputs == []


async def test_the_same_terminei_resent_under_its_turn_id_hears_the_first_reply_and_reaches_the_voice_once(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await three_translated(room, session_id, rehearsal_id)

    first = await send(room, session_id, rehearsal_id, "o-mesmo-turno")
    again = await send(room, session_id, rehearsal_id, "o-mesmo-turno")

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert again.json() == first.json()
    assert len(room.guide.inputs) == 1


async def test_a_frase_set_aside_by_a_restart_is_not_sent(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um"), ((5000, 9000), "dois")])
    attempt = str(uuid.uuid4())
    restarted = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
        data={"attempt": attempt},
    )
    assert restarted.status_code == 200, restarted.text
    again = await a_frase(
        room, session_id, rehearsal_id, (0, 4000), "outra vez", tone=300, after_restart=attempt
    )
    assert again.status_code == 200, again.text

    sent = await send(room, session_id, rehearsal_id, closes=attempt)

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{ONE_PT} outra vez"]


async def test_a_send_whose_turn_never_lands_leaves_the_rehearsal_sendable(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    monkeypatch.setattr(get_settings(), "internalization_room_turn_bound_ms", 300)
    room.guide.thinks = 1.0

    lost = await send(room, session_id, rehearsal_id, "turno-perdido")

    assert lost.status_code == 502, lost.text
    assert (await read_by_the_desk(room, session_id, rehearsal_id))["sent_at"] is None
    room.guide.thinks = 0.0
    landed = await send(room, session_id, rehearsal_id, "turno-que-chega")
    assert landed.status_code == 200, landed.text
    assert room.guide.inputs == [f"{ONE_PT} um", f"{ONE_PT} um"]


async def test_a_frase_arriving_after_the_send_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    sent = await send(room, session_id, rehearsal_id)
    assert sent.status_code == 200, sent.text

    late = await a_frase(room, session_id, rehearsal_id, (5000, 9000), "tarde", tone=400)

    assert late.status_code == 409, late.text
    assert late.json()["code"] == "SCENE_REHEARSAL_SENT"


async def test_a_late_failure_under_a_turn_id_that_already_landed_leaves_the_rehearsal_sent(
    room: Room, db_session: AsyncSession, rival_factory
) -> None:
    """The same turn id resent to another instance drafts again; when that draft fails after the
    first one landed, the rehearsal stays sent under the turn that answered it."""
    from app.core.config import get_settings
    from app.db.models.internalization_room import IRSceneRehearsal, IRSession
    from app.services.internalization_room.scene_rehearsals import send_the_scene_rehearsal

    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    sent = await send(room, session_id, rehearsal_id, "turno-que-chegou")
    assert sent.status_code == 200, sent.text

    async def another_instance_fails(**_: Any) -> Any:
        raise RuntimeError("a outra instância caiu")

    async with rival_factory() as db:
        with pytest.raises(RuntimeError):
            await send_the_scene_rehearsal(
                db,
                await db.get(IRSession, session_id),
                await db.get(IRSceneRehearsal, rehearsal_id),
                turn_id="turno-que-chegou",
                closes=None,
                project_id=TABLET_TEAM,
                bound_s=get_settings().internalization_room_turn_bound_ms / 1000,
                draft=another_instance_fails,
            )

    assert (await read_by_the_desk(room, session_id, rehearsal_id))["sent_at"] is not None
    late = await send(room, session_id, rehearsal_id, "outro-turno")
    assert late.status_code == 409, late.text
    assert late.json()["code"] == "SCENE_REHEARSAL_SENT"


async def test_a_send_before_the_restart_it_closes_has_landed_is_refused_and_goes_through_once_it_has(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um"), ((5000, 9000), "dois")])
    attempt = str(uuid.uuid4())
    for offset, (place, said) in enumerate([((0, 4000), "outro um"), ((5000, 9000), "outro dois")]):
        held = await a_frase(
            room, session_id, rehearsal_id, place, said, tone=500 + offset, after_restart=attempt
        )
        assert held.status_code == 200, held.text

    early = await send(room, session_id, rehearsal_id, "terminei", closes=attempt)

    assert early.status_code == 409, early.text
    assert early.json()["code"] == "RESTART_OUT_OF_ORDER"
    assert room.guide.inputs == []
    restarted = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
        data={"attempt": attempt},
    )
    assert restarted.status_code == 200, restarted.text
    again = await send(room, session_id, rehearsal_id, "terminei", closes=attempt)
    assert again.status_code == 200, again.text
    assert room.guide.inputs == [f"{TWO_PT} outro um outro dois"]


async def test_a_send_while_a_frase_waits_on_a_restart_still_on_its_way_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    held = await a_frase(
        room,
        session_id,
        rehearsal_id,
        (0, 4000),
        "outro um",
        tone=600,
        after_restart=str(uuid.uuid4()),
    )
    assert held.status_code == 200, held.text

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 409, sent.text
    assert sent.json()["code"] == "RESTART_OUT_OF_ORDER"
    assert room.guide.inputs == []


async def test_a_terminei_while_another_is_still_reaching_the_voice_is_told_it_is_being_sent(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    room.guide.holds = asyncio.Event()
    first = asyncio.create_task(send(room, session_id, rehearsal_id, "tablet-um"))
    await asyncio.wait_for(room.guide.asked.wait(), timeout=10)

    meanwhile = await send(room, session_id, rehearsal_id, "tablet-dois")

    assert meanwhile.status_code == 409, meanwhile.text
    assert meanwhile.json()["code"] == "SCENE_REHEARSAL_SENDING"
    room.guide.holds.set()
    landed = await asyncio.wait_for(first, timeout=10)
    assert landed.status_code == 200, landed.text
    after = await send(room, session_id, rehearsal_id, "tablet-dois")
    assert after.status_code == 409, after.text
    assert after.json()["code"] == "SCENE_REHEARSAL_SENT"
    assert room.guide.inputs == [f"{ONE_PT} um"]


async def test_a_release_by_a_draft_whose_claim_a_resend_renewed_leaves_the_rehearsal_being_sent(
    room: Room, db_session: AsyncSession, rival_factory
) -> None:
    """Instance A drafts turn T; T resent to instance B drafts again and renews the claim; A
    then fails and releases. The rehearsal is still B's to send."""
    from app.core.config import get_settings
    from app.db.models.internalization_room import IRSceneRehearsal, IRSession
    from app.services.internalization_room.scene_rehearsals import send_the_scene_rehearsal

    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    bound_s = get_settings().internalization_room_turn_bound_ms / 1000
    a_drafts, b_drafts = asyncio.Event(), asyncio.Event()

    async def instance_a_fails(**_: Any) -> Any:
        a_drafts.set()
        await b_drafts.wait()
        raise RuntimeError("a instância A caiu")

    async def instance_b_drafts(**_: Any) -> Any:
        b_drafts.set()
        await asyncio.sleep(3600)

    async def on_an_instance(draft: Any) -> Any:
        async with rival_factory() as db:
            session = await db.get(IRSession, session_id)
            rehearsal = await db.get(IRSceneRehearsal, rehearsal_id)
            return await send_the_scene_rehearsal(
                db,
                session,
                rehearsal,
                turn_id="turno-t",
                closes=None,
                project_id=TABLET_TEAM,
                bound_s=bound_s,
                draft=draft,
            )

    a = asyncio.create_task(on_an_instance(instance_a_fails))
    await asyncio.wait_for(a_drafts.wait(), timeout=10)
    b = asyncio.create_task(on_an_instance(instance_b_drafts))
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(a, timeout=10)

    meanwhile = await send(room, session_id, rehearsal_id, "turno-t2")

    b.cancel()
    assert meanwhile.status_code == 409, meanwhile.text
    assert meanwhile.json()["code"] == "SCENE_REHEARSAL_SENDING"
    assert room.guide.inputs == []


async def test_a_claim_left_by_a_request_long_gone_is_free_for_a_new_terminei(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    await claimed_by_hand(db_session, rehearsal_id, "turno-perdido", timedelta(hours=1))

    sent = await send(room, session_id, rehearsal_id, "turno-novo")

    assert sent.status_code == 200, sent.text
    assert room.guide.inputs == [f"{ONE_PT} um"]
    answered_by = await db_session.execute(
        text("SELECT sent_turn_id FROM ir_scene_rehearsals WHERE id = :id"), {"id": rehearsal_id}
    )
    assert answered_by.scalar_one() == "turno-novo"


async def test_the_rehearsal_turns_guide_entry_names_the_sessions_language(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session, language="en")
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "one")])

    sent = await send(room, session_id, rehearsal_id)

    assert sent.status_code == 200, sent.text
    guide = (await conversation(db_session, session_id))[-1]
    assert guide["language"] == "en"
    assert guide["take_ms"] == 40_000


async def test_a_send_naming_an_attempt_that_is_not_the_current_one_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    attempt = str(uuid.uuid4())
    restarted = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
        data={"attempt": attempt},
    )
    assert restarted.status_code == 200, restarted.text
    again = await a_frase(
        room, session_id, rehearsal_id, (0, 4000), "outro um", tone=700, after_restart=attempt
    )
    assert again.status_code == 200, again.text

    stale = await send(room, session_id, rehearsal_id)

    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "RESTART_OUT_OF_ORDER"
    assert room.guide.inputs == []


async def test_a_claim_still_waiting_on_a_drafting_opening_is_not_taken_over(
    room: Room, db_session: AsyncSession
) -> None:
    """A send that waited on the opening drafts after the wait, with its whole turn bound."""
    from app.core.config import get_settings

    settings = get_settings()
    turn_s = settings.internalization_room_turn_bound_ms / 1000
    wait_s = settings.internalization_room_opening_wait_ms / 1000
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    await claimed_by_hand(
        db_session, rehearsal_id, "turno-que-esperou", timedelta(seconds=turn_s + 30 + wait_s / 2)
    )

    sent = await send(room, session_id, rehearsal_id, "turno-novo")

    assert sent.status_code == 409, sent.text
    assert sent.json()["code"] == "SCENE_REHEARSAL_SENDING"
    assert room.guide.inputs == []


async def test_a_frase_while_the_rehearsal_is_being_sent_is_told_so(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    await claimed_by_hand(db_session, rehearsal_id, "turno-em-voo", timedelta(0))

    frase = await a_frase(room, session_id, rehearsal_id, (5000, 9000), "dois", tone=800)

    assert frase.status_code == 409, frase.text
    assert frase.json()["code"] == "SCENE_REHEARSAL_SENDING"


async def test_a_restart_while_the_rehearsal_is_being_sent_is_told_so(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await an_opened_session(room, db_session)
    rehearsal_id = await a_rehearsal(room, session_id)
    await translated(room, session_id, rehearsal_id, [((0, 4000), "um")])
    await claimed_by_hand(db_session, rehearsal_id, "turno-em-voo", timedelta(0))

    restarted = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/restart",
        data={"attempt": str(uuid.uuid4())},
    )

    assert restarted.status_code == 409, restarted.text
    assert restarted.json()["code"] == "SCENE_REHEARSAL_SENDING"
