"""ENG-1199 — a facilitator reads a session's turns, each with its speech facts and its voice.

Every turn is produced through the room's own turn route, with the recognizer, the model and
the speech engine doubled at the seams the suite already uses, and read back through the
facilitator's turns route and its per-turn audio door. The one exception is the turn stored
before this change, whose shape no route writes any more.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import llm
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.oral_collector import gcs_utils
from app.services.platform import tts
from tests.baker import make_app, make_role
from tests.release_harness import APP_KEY, PREFIX, P, a_claimed_device, at_the_desk, team_headers
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is

PASS = {"verdict": "pass", "issues": []}
NEXT_VOICE = "vozDepoisDoDeploy00"
REGENERATE = {
    "verdict": "regenerate",
    "issues": [{"problem": "ungrounded", "claim": "x", "explanation": "o mapa não diz"}],
}
OPENING = "Vamos ouvir a história de Rute. O que vocês já sabem dela?"
WORDS = [
    "Noemi voltou para Belém com Rute",
    "Rute disse que ia junto com ela",
    "Noemi chegou na colheita da cevada",
    "Boaz viu Rute no campo",
]
LINES = [
    "Vamos ficar nesta cena. O que vocês contariam?",
    "E depois disso, o que aconteceu?",
    "Quem estava com elas na estrada?",
    "O que vocês lembram do campo?",
]


def _heard(words: str, **facts: Any) -> HeardSpeech:
    return HeardSpeech(
        text=words,
        bridge_language="pt",
        language_code=facts.pop("language_code", "pt"),
        language_probability=facts.pop("language_probability", 0.97),
        take_ms=facts.pop("take_ms", 6000),
        **facts,
    )


class Script:
    """What the recognizer hears next, and what the Guide and the Validator answer."""

    def __init__(self) -> None:
        self.heard = _heard(WORDS[0])
        self.drafts: list[str] = []
        self.verdicts: list[dict[str, Any]] = []

    async def hear(self, *_: Any, **__: Any) -> HeardSpeech:
        return self.heard

    async def model(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps(self.verdicts.pop(0) if self.verdicts else PASS)
        return self.drafts.pop(0) if self.drafts else LINES[0]


class Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        self.objects[key] = data
        return data


class ElevenLabs:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.voices: list[str] = []

    async def get(self, *_: Any, **__: Any) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, content=b"", text="")

    async def post(self, url: str, *, json: dict[str, Any], **_: Any) -> SimpleNamespace:
        self.spoken.append(json["text"])
        self.voices.append(url.rsplit("/", 1)[-1])
        return SimpleNamespace(status_code=200, content=f"voz {len(self.spoken)}".encode(), text="")


class Anthropic:
    """The provider behind the real model ladder: one rung refused, every call a little slow."""

    def __init__(self, drafts: list[str], refuses: str = "", takes_s: float = 0.0) -> None:
        self.drafts = drafts
        self.refuses = refuses
        self.takes_s = takes_s

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        if kwargs["model"] == self.refuses:
            raise anthropic.NotFoundError(
                "nope",
                response=httpx.Response(
                    status_code=404,
                    request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
                ),
                body=None,
            )
        await asyncio.sleep(self.takes_s)
        system = "".join(block["text"] for block in kwargs["system"])
        validating = "corrected_response" in system
        text = json.dumps(PASS) if validating else (self.drafts.pop(0) if self.drafts else "Ok.")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


@pytest.fixture(autouse=True)
def _no_rung_outlives_its_test():
    llm._SETTLED.clear()
    yield
    llm._SETTLED.clear()


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> Script:
    scripted = Script()

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", scripted.hear)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    the_room_agent_is(monkeypatch, turn=scripted.model)
    return scripted


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> Bucket:
    store = Bucket()
    monkeypatch.setattr(tts, "_default_store", lambda _: store)
    return store


@pytest.fixture()
def elevenlabs(monkeypatch: pytest.MonkeyPatch) -> ElevenLabs:
    voice = ElevenLabs()
    monkeypatch.setattr(tts, "_make_client", lambda: voice)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    return voice


@pytest.fixture()
def signed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def sign(bucket: str, key: str, **_: Any) -> str:
        return f"https://signed.test/{bucket}/{key}"

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "plataforma", raising=False)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", sign)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(
    db_session: AsyncSession, per_request, bucket, elevenlabs, signed, monkeypatch
) -> Any:
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


class Room:
    """One team's session, the tablet that speaks in it, and the Desk that reads it."""

    def __init__(self, session_id: str, credential: str, desk: dict[str, str], team: str) -> None:
        self.session_id = session_id
        self.credential = credential
        self.desk = desk
        self.team = team


async def _a_room(db: AsyncSession, room_app) -> Room:
    project, credential = await a_claimed_device(db)
    session = await create_session(db, language="pt", pericope=P, project_id=project.id)
    desk, _facilitator = await at_the_desk(db, room_app, project)
    return Room(session.id, credential, desk, project.id)


async def _opens(client: httpx.AsyncClient, room: Room) -> dict[str, Any]:
    response = await client.post(
        f"{PREFIX}/sessions/{room.session_id}/turns", headers=team_headers(room.credential)
    )
    assert response.status_code == 200, response.text[:300]
    return response.json()


async def _says(client: httpx.AsyncClient, room: Room, turn_id: str, **cut: str) -> dict[str, Any]:
    response = await client.post(
        f"{PREFIX}/sessions/{room.session_id}/turns",
        headers=team_headers(room.credential),
        data={"turn_id": turn_id, **cut},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert response.status_code == 200, response.text[:300]
    return response.json()


def _turns_of(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/turns"


async def _read(client: httpx.AsyncClient, room: Room) -> list[dict[str, Any]]:
    response = await client.get(_turns_of(room.session_id), headers=room.desk)
    assert response.status_code == 200, response.text[:300]
    return response.json()["turns"]


async def _play(client: httpx.AsyncClient, room: Room, turn: dict[str, Any]) -> str:
    response = await client.get(turn["voice"]["audio_url"], headers=room.desk)
    assert response.status_code == 307, response.text[:300]
    return response.headers["location"].removeprefix("https://signed.test/plataforma/")


async def _what_the_tablet_heard(client: httpx.AsyncClient, room: Room, audio_url: str) -> bytes:
    heard = await client.get(audio_url, headers=team_headers(room.credential))
    assert heard.status_code == 200, heard.text[:300]
    return heard.content


async def _row(per_request: async_sessionmaker[AsyncSession], session_id: str) -> tuple:
    async with per_request() as db:
        row = (
            await db.execute(
                select(
                    IRSession.messages,
                    IRSession.updated_at,
                    IRSession.status,
                    IRSession.version,
                ).where(IRSession.id == session_id)
            )
        ).one()
    return tuple(row)


async def test_a_session_of_five_turns_reads_as_five_pairs_oldest_first_each_with_the_teams_and_the_voices_facts(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, *LINES]
    await _opens(client, room)
    for number, words in enumerate(WORDS):
        script.heard = _heard(words, language_probability=0.9 + number / 100, take_ms=5000 + number)
        await _says(client, room, f"turno-{number}")

    turns = await _read(client, room)

    assert [turn["voice"]["text"] for turn in turns] == [OPENING, *LINES]
    assert turns[0]["team"] is None
    assert [turn["team"] for turn in turns[1:]] == [
        {
            "language": "pt",
            "language_probability": 0.9 + number / 100,
            "take_ms": 5000 + number,
            "mother_tongue": False,
            "interrupted_at_s": None,
            "guide_heard": words,
        }
        for number, words in enumerate(WORDS)
    ]
    for turn in turns:
        assert turn["voice"]["outcome"] == "validated"
        assert turn["voice"]["boundary"] is False
        assert turn["voice"]["attempts"] == 1
        assert turn["voice"]["audio_url"]


async def test_a_turn_where_the_team_cut_the_voice_off_at_4_s_reads_as_interrupted_at_4_seconds_and_what_the_guide_received_starts_with_the_apps_note(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, LINES[0]]
    await _opens(client, room)
    script.heard = _heard(WORDS[0])
    await _says(
        client,
        room,
        "cortou",
        interrupted="1",
        interrupted_at_ms="4000",
        interrupted_of_ms="9000",
    )

    (_opening, cut) = await _read(client, room)

    assert cut["team"]["interrupted_at_s"] == 4
    assert cut["team"]["guide_heard"].startswith("[A equipe interrompeu")
    assert cut["team"]["guide_heard"] != WORDS[0]
    assert cut["team"]["guide_heard"].endswith(WORDS[0])


async def test_a_mother_tongue_take_reads_as_mother_tongue_with_the_note_instead_of_words(
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, LINES[0]]
    await _opens(client, room)
    script.heard = _heard(
        "maka nanu ipuxova", language_code="sw", language_probability=0.99, take_ms=12000
    )
    await _says(client, room, "lingua-materna")

    (_opening, rehearsal) = await _read(client, room)

    assert rehearsal["team"]["mother_tongue"] is True
    assert rehearsal["team"]["language"] == "sw"
    assert rehearsal["team"]["guide_heard"]
    assert "maka nanu ipuxova" not in rehearsal["team"]["guide_heard"]


async def test_a_short_take_with_no_words_reads_as_nothing_reaching_the_guide_a_fail_safe_turn(
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING]
    await _opens(client, room)
    script.heard = _heard("", take_ms=3000)
    await _says(client, room, "nada")

    (_opening, missed) = await _read(client, room)

    assert missed["team"]["guide_heard"] == ""
    assert missed["voice"]["outcome"] == "fail_safe"


async def test_a_turn_the_validator_corrected_after_two_attempts_reads_corrected_2_attempts_and_the_voiced_text_is_the_corrected_one(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, "Rascunho um", "Rascunho dois"]
    await _opens(client, room)
    script.verdicts = [
        REGENERATE,
        {"verdict": "correct", "issues": [], "corrected_response": "Texto corrigido."},
    ]
    script.heard = _heard(WORDS[0])
    await _says(client, room, "corrigido")

    (_opening, corrected) = await _read(client, room)

    assert corrected["voice"]["outcome"] == "corrected"
    assert corrected["voice"]["attempts"] == 2
    assert corrected["voice"]["text"] == "Texto corrigido."


async def test_a_fail_safe_turn_reads_fail_safe_a_boundary_turn_with_its_own_clip(
    client, db_session, room_app, script, elevenlabs, bucket, monkeypatch
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING]
    await _opens(client, room)
    script.verdicts = [REGENERATE, REGENERATE, REGENERATE]
    script.heard = _heard(WORDS[0])
    answered = await _says(client, room, "falhou")
    line = await client.get(
        f"{PREFIX}/fixed-lines/{answered['fixed_line']}",
        params={"language": "pt"},
        headers=team_headers(room.credential),
    )
    assert line.status_code == 200, line.text[:300]
    heard = await _what_the_tablet_heard(client, room, line.json()["audio_url"])
    spoken = list(elevenlabs.spoken)
    monkeypatch.setattr(get_settings(), "internalization_room_voice_id", NEXT_VOICE)

    (_opening, fail_safe) = await _read(client, room)
    played = await _play(client, room, fail_safe)

    assert fail_safe["voice"]["outcome"] == "fail_safe"
    assert fail_safe["voice"]["boundary"] is True
    assert bucket.objects[played] == heard
    assert elevenlabs.spoken == spoken


async def test_a_guide_line_that_hands_the_team_off_reads_as_a_boundary_turn_an_ordinary_line_does_not_the_opening_never_does(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [
        "Eu sou o Facilitador Digital. Se precisarem, falem com o seu facilitador.",
        "Isso a história não conta. Perguntem ao seu facilitador.",
        "Quem estava com elas na estrada?",
        "Eu sou o seu Facilitador Digital. O que vem depois?",
        "The passage does not tell us that.",
    ]
    await _opens(client, room)
    for number in range(4):
        script.heard = _heard(WORDS[number])
        await _says(client, room, f"turno-{number}")

    turns = await _read(client, room)

    assert [turn["voice"]["boundary"] for turn in turns] == [False, True, False, False, True]


async def test_the_model_is_the_rung_that_answered_after_a_fallback(
    client, db_session, room_app, script, monkeypatch
) -> None:
    rungs = llm.voice_ladder(get_settings())
    provider = Anthropic([OPENING, LINES[0]], refuses=rungs[0])
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=provider)
    )
    the_room_agent_is(monkeypatch, turn=llm.call_agent)
    room = await _a_room(db_session, room_app)
    await _opens(client, room)
    script.heard = _heard(WORDS[0])
    await _says(client, room, "degrau")
    script.heard = _heard("", take_ms=3000)
    await _says(client, room, "nada")

    (opening, answered, missed) = await _read(client, room)

    assert opening["voice"]["model"] == rungs[1]
    assert answered["voice"]["model"] == rungs[1]
    assert missed["voice"]["model"] is None


async def test_recognition_and_reply_times_are_kept_no_synthesis_time_is_invented(
    client, db_session, room_app, script, monkeypatch
) -> None:
    provider = Anthropic([OPENING, LINES[0]], takes_s=0.15)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=provider)
    )
    the_room_agent_is(monkeypatch, turn=llm.call_agent)

    async def slow_hearing(*_: Any, **__: Any) -> HeardSpeech:
        await asyncio.sleep(0.5)
        return _heard(WORDS[0])

    monkeypatch.setattr(sessions_api, "heard_speech", slow_hearing)
    room = await _a_room(db_session, room_app)
    await _opens(client, room)
    await _says(client, room, "cronometrado")

    (opening, timed) = await _read(client, room)

    assert opening["voice"]["recognition_ms"] is None
    assert 500 <= timed["voice"]["recognition_ms"] < 800
    assert 300 <= timed["voice"]["reply_ms"] < 500
    assert timed["voice"]["synthesis_ms"] is None


async def test_playing_a_turn_whose_clip_was_stored_returns_that_same_clip_and_synthesizes_nothing(
    client, db_session, room_app, script, elevenlabs, bucket, monkeypatch
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, LINES[0]]
    await _opens(client, room)
    script.heard = _heard(WORDS[0])
    answered = await _says(client, room, "ouvir")
    heard = await _what_the_tablet_heard(client, room, answered["audio_url"])
    spoken = list(elevenlabs.spoken)
    monkeypatch.setattr(get_settings(), "internalization_room_voice_id", NEXT_VOICE)

    (_opening, turn) = await _read(client, room)
    played = await _play(client, room, turn)

    assert bucket.objects[played] == heard
    assert elevenlabs.spoken == spoken


async def _a_turn_stored_before_this_change(db: AsyncSession, room_app) -> Room:
    room = await _a_room(db, room_app)
    session = await db.get(IRSession, room.session_id)
    assert session is not None
    session.messages = [
        {"role": "guide", "text": "Abertura antiga.", "at": "2026-09-01T12:00:00+00:00"},
        {"role": "team", "text": "resposta antiga", "at": "2026-09-01T12:01:00+00:00"},
        {
            "role": "guide",
            "text": "Linha antiga.",
            "at": "2026-09-01T12:01:00+00:00",
            "outcome": "pass",
            "redrafts": 0,
        },
    ]
    await db.commit()
    return room


async def test_playing_a_turn_stored_before_this_change_synthesizes_it_once_in_the_current_voice_and_the_second_play_returns_the_same_clip_without_synthesizing_again(  # noqa: E501
    client, db_session, room_app, elevenlabs, bucket
) -> None:
    room = await _a_turn_stored_before_this_change(db_session, room_app)
    (_opening, old) = await _read(client, room)

    first = await _play(client, room, old)
    second = await _play(client, room, old)

    assert elevenlabs.spoken == ["Linha antiga."]
    assert elevenlabs.voices == [get_settings().internalization_room_voice_id]
    assert second == first
    assert first in bucket.objects


async def test_reading_a_live_sessions_turns_and_playing_one_leaves_the_session_unchanged(
    client, db_session, room_app, script, per_request
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, LINES[0]]
    await _opens(client, room)
    script.heard = _heard(WORDS[0])
    await _says(client, room, "ao-vivo")
    before = await _row(per_request, room.session_id)

    turns = await _read(client, room)
    await _play(client, room, turns[1])

    assert await _row(per_request, room.session_id) == before


async def test_reading_the_turns_without_the_facilitators_credential_is_refused(
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    theirs, _other = await a_claimed_device(db_session, email="estranha@example.com")
    stranger, _them = await at_the_desk(db_session, room_app, theirs)
    script.drafts = [OPENING]
    await _opens(client, room)
    turns = _turns_of(room.session_id)
    (opening,) = await _read(client, room)
    audio = opening["voice"]["audio_url"]

    for address in (turns, audio):
        unsigned = client.build_request("GET", address)
        del unsigned.headers[DEVICE_CREDENTIAL_HEADER]
        anonymous = await client.send(unsigned)
        tablet = await client.get(address, headers=team_headers(room.credential))
        other_team = await client.get(address, headers=stranger)

        assert anonymous.status_code == 401, anonymous.text[:300]
        assert tablet.status_code == 401, tablet.text[:300]
        assert other_team.status_code == 404, other_team.text[:300]


async def test_a_first_take_the_room_missed_reads_as_the_teams_turn_not_the_opening(
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.heard = _heard("", take_ms=3000)
    await _says(client, room, "primeira-sem-palavras")

    (missed,) = await _read(client, room)

    assert missed["team"] is not None
    assert missed["team"]["take_ms"] == 3000


async def test_a_session_with_no_turns_reads_as_an_empty_list(client, db_session, room_app) -> None:
    room = await _a_room(db_session, room_app)

    assert await _read(client, room) == []


async def test_a_turn_stored_before_this_change_reads_its_missing_facts_as_null(
    client, db_session, room_app
) -> None:
    room = await _a_turn_stored_before_this_change(db_session, room_app)

    (opening, old) = await _read(client, room)

    assert opening["team"] is None
    assert opening["voice"]["outcome"] == "no_record"
    assert old["team"] == {
        "language": None,
        "language_probability": None,
        "take_ms": None,
        "mother_tongue": None,
        "interrupted_at_s": None,
        "guide_heard": None,
    }
    assert {key: old["voice"][key] for key in old["voice"] if key != "audio_url"} == {
        "outcome": "validated",
        "boundary": False,
        "attempts": 0,
        "recognition_ms": None,
        "reply_ms": None,
        "synthesis_ms": None,
        "model": None,
        "text": "Linha antiga.",
    }


async def test_an_archived_sessions_turns_are_read_by_its_id(
    client, db_session, room_app, script
) -> None:
    room = await _a_room(db_session, room_app)
    script.drafts = [OPENING, LINES[0]]
    await _opens(client, room)
    script.heard = _heard(WORDS[0])
    await _says(client, room, "antes-do-zerar")
    zerar = await client.post(
        f"{PREFIX}/facilitator/projects/{room.team}/passages/{P}/archive", headers=room.desk
    )
    assert zerar.status_code == 200, zerar.text[:300]

    turns = await _read(client, room)

    assert [turn["voice"]["text"] for turn in turns] == [OPENING, LINES[0]]
