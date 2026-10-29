"""ENG-1213 — a consultant reads every team's work in the Desk and changes none of it.

Five readers sign in against three teams: a facilitator of A, a consultant with no team, a
facilitator of A who also holds `consultant`, a platform admin and a facilitator of B, whose
answers are what "reads like a facilitator" means. Every case drives the real application.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import ProjectRole
from app.db.models.internalization_room import (
    IRExternalCheck,
    IRQuestion,
    IRQuestionStatus,
    IRSceneFrase,
    IRSceneRehearsal,
    IRSession,
    IRSessionStatus,
    IRTake,
    IRTakeKind,
)
from app.services.device import create_device
from app.services.device.needs_person import record_needs_person
from app.services.internalization_room import questions as question_service
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.voice_handles import to_handle
from app.services.oral_collector import gcs_utils
from app.services.platform import tts
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.device_harness import a_linked_tablet
from tests.facilitator_route_audit_harness import (
    facilitator_routes,
    parameters_of,
    template_of,
    those_that_read,
)
from tests.room_harness import the_bucket_is_in_memory
from tests.stream_harness import opening_status

IR = "/api/internalization-room"
DESK = "/api/facilitator"
P = "P03"
AUDIO = {"files": {"file": ("resposta.m4a", b"resposta falada", "audio/mp4")}}
FORCE = {"json": {"force": True}}
#: A visit names the halt count the Desk read (ADR 0091); these sessions never halted.
NEVER_HALTED = {"params": {"halt": 0}}
NO_SUCH_HALT = {"params": {"needs_person_since": "2020-01-01T00:00:00+00:00"}}


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


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> Bucket:
    from app.api.internalization_room import takes as take_routes
    from app.services.internalization_room import session_takes

    store = Bucket()

    async def sign(bucket_name: str, key: str, **_: Any) -> str:
        return f"https://signed.test/{bucket_name}/{key}"

    async def signed_question(key: str, **_: Any) -> question_service.SignedAudio:
        return question_service.SignedAudio(
            url=f"https://signed.test/{key}",
            expires_at=datetime.now(UTC) + timedelta(minutes=question_service.LISTEN_MINUTES),
        )

    async def signed_take(take, **_: Any) -> str:
        return f"https://signed.test/{take.storage_key}"

    monkeypatch.setattr(question_service, "_store", lambda *a, **kw: store)
    monkeypatch.setattr(question_service, "listen_address", signed_question)
    monkeypatch.setattr(take_routes, "listen_url", signed_take)
    monkeypatch.setattr(session_takes, "listen_url", signed_take)
    the_bucket_is_in_memory(monkeypatch)
    monkeypatch.setattr(tts, "_default_store", lambda _: store)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", sign)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", sign)
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "plataforma", raising=False)
    return store


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: Bucket):
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


class Team:
    def __init__(self, project, session, question, take, rehearsal, frase, device: str) -> None:
        self.id = project.id
        self.session = session.id
        self.question = question.id
        self.question_key = question.audio_key
        self.take = take.id
        self.rehearsal = rehearsal.id
        self.rehearsal_key = rehearsal.storage_key
        self.frase = frase.id
        self.frase_key = frase.storage_key
        self.device = device


class Desk:
    def __init__(self) -> None:
        self.teams: dict[str, Team] = {}
        self.readers: dict[str, dict[str, str]] = {}

    def __getitem__(self, tag: str) -> Team:
        return self.teams[tag]


async def _headers(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def _a_team(db: AsyncSession, tag: str, bucket: Bucket) -> Team:
    language = await make_language(db, name=f"Lang {tag}", code=f"l{tag}")
    project = await make_project(db, language.id, name=f"Team {tag}")
    session = IRSession(
        id=f"s-{tag}",
        pericope=P,
        project_id=project.id,
        status=IRSessionStatus.NEEDS_PERSON,
        messages=[{"role": "guide", "text": "Vamos ouvir a história.", "voice_key": f"voz/{tag}"}],
        back_translation={
            "sentences": [
                {
                    "sentence_id": f"frase-{tag}",
                    "segment_id": f"seg-{tag}",
                    "previous_take_id": f"tk-{tag}-antes",
                    "take_id": f"tk-{tag}",
                    "starts_ms": 0,
                    "ends_ms": 1000,
                    "sha256": "0" * 64,
                    "storage_key": f"internalization-room/takes/{tag}/sentence/frase.wav",
                    "heard_before": False,
                }
            ]
        },
    )
    db.add(session)
    await db.flush()
    question = IRQuestion(
        id=f"q-{tag}",
        session_id=session.id,
        device_id=f"t-{tag}",
        project_id=project.id,
        pericope=P,
        status=IRQuestionStatus.OPEN,
        audio_key=f"internalization-room/questions/{tag}.m4a",
    )
    take = IRTake(
        id=f"tk-{tag}",
        session_id=session.id,
        device_id=f"t-{tag}",
        project_id=project.id,
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope="passagem",
        storage_key=f"internalization-room/takes/{tag}.m4a",
        size_bytes=8,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/mp4",
    )
    check = IRExternalCheck(
        release_id=f"r-{tag}", session_id=session.id, version=1, takes=[], frases=[]
    )
    rehearsal = IRSceneRehearsal(
        id=f"sr-{tag}",
        session_id=session.id,
        project_id=project.id,
        pericope=P,
        n=1,
        device_id=f"t-{tag}",
        storage_key=f"internalization-room/scene-rehearsals/{tag}.wav",
        size_bytes=8,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/wav",
    )
    frase = IRSceneFrase(
        id=f"sf-{tag}",
        rehearsal_id=rehearsal.id,
        session_id=session.id,
        starts_ms=0,
        ends_ms=1000,
        storage_key=f"internalization-room/scene-rehearsals/{tag}-frase.wav",
        size_bytes=8,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/wav",
        transcript="a frase",
    )
    db.add_all([question, take, check, rehearsal, frase])
    await db.commit()
    await bucket.put(question.audio_key, b"a equipe perguntou", "audio/mp4")
    await bucket.put(f"voz/{tag}", b"a voz falou", "audio/mpeg")
    tablet = await a_linked_tablet(db, team_id=project.id)
    return Team(project, session, question, take, rehearsal, frase, tablet.device_id)


async def _a_reader(
    db: AsyncSession, email: str, *, roles: tuple[str, ...], facilitates: tuple[Team, ...] = ()
) -> dict[str, str]:
    user = await make_user(db, email=email)
    for role in roles:
        await grant_room_app_role(db, user.id, role)
    for team in facilitates:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    return await _headers(db, user)


@pytest.fixture()
async def desk(db_session: AsyncSession, bucket: Bucket) -> Desk:
    built = Desk()
    for tag in ("a", "b", "c"):
        built.teams[tag] = await _a_team(db_session, tag, bucket)
    a, b = built["a"], built["b"]
    built.readers = {
        "facilitator": await _a_reader(
            db_session, "fac@example.com", roles=("facilitator",), facilitates=(a,)
        ),
        "consultant": await _a_reader(db_session, "con@example.com", roles=("consultant",)),
        "both": await _a_reader(
            db_session, "ambos@example.com", roles=("facilitator", "consultant"), facilitates=(a,)
        ),
        "admin": await _headers(
            db_session,
            await make_user(db_session, email="admin@example.com", is_platform_admin=True),
        ),
        "facilitator_of_b": await _a_reader(
            db_session, "facb@example.com", roles=("facilitator",), facilitates=(b,)
        ),
        "consultant_with_a_leftover_link": await _a_reader(
            db_session, "sobra@example.com", roles=("consultant",), facilitates=(a,)
        ),
    }
    return built


def _writes_on(team: Team, claim_code: str) -> list[tuple[str, str, dict]]:
    return [
        ("POST", f"{IR}/facilitator/questions/{team.question}/reply", AUDIO),
        ("POST", f"{IR}/facilitator/questions/{team.question}/resolve", {}),
        ("POST", f"{IR}/facilitator/sessions/{team.session}/attended", NEVER_HALTED),
        ("DELETE", f"{IR}/facilitator/sessions/{team.session}/attended", NEVER_HALTED),
        ("POST", f"{DESK}/devices/{team.device}/attended", NO_SUCH_HALT),
        ("DELETE", f"{DESK}/devices/{team.device}/attended", NO_SUCH_HALT),
        ("POST", f"{DESK}/devices/claim", {"json": {"code": claim_code, "project_id": team.id}}),
        ("PATCH", f"{DESK}/devices/{team.device}", {"json": {"label": "outro nome"}}),
        ("DELETE", f"{DESK}/devices/{team.device}", {}),
        ("POST", f"{IR}/facilitator/sessions/{team.session}/release", FORCE),
        ("POST", f"{IR}/facilitator/projects/{team.id}/passages/{P}/archive", {}),
    ]


def _answer(response: httpx.Response) -> tuple[int, Any]:
    body = response.json()
    if isinstance(body, dict):
        body.pop("generated_at", None)
        body.pop("exportedAt", None)
        body.pop("expires_at", None)
    return response.status_code, body


def _session_reads() -> set[str]:
    return {
        path for method, path in facilitator_routes() if method == "GET" and "{session_id}" in path
    }


def _reads_that_name_a_team_resource() -> set[str]:
    return {
        path
        for method, path in facilitator_routes()
        if method == "GET" and ("{" in path or "team_id" in parameters_of(method, path))
    }


def _audio_doors() -> set[str]:
    return {
        path
        for method, path in facilitator_routes()
        if method == "GET" and "audio" in path.split("/")
    }


def _reads_of_a_team() -> set[str]:
    return {
        path
        for method, path in facilitator_routes()
        if method == "GET" and "team_id" in parameters_of(method, path)
    }


async def _row(per_request: async_sessionmaker[AsyncSession], table, row_id: str) -> dict:
    async with per_request() as db:
        found = (await db.execute(select(table.__table__).where(table.id == row_id))).one()
    return dict(found._mapping)


async def test_a_consultant_with_no_team_link_lists_teams_a_b_and_c_with_their_sessions_and_questions(  # noqa: E501
    client, desk
) -> None:
    from app.main import app

    reader = desk.readers["consultant"]
    every = {desk[tag].id for tag in "abc"}
    questions = {desk[tag].question for tag in "abc"}
    sessions = {desk[tag].session for tag in "abc"}

    teams = await client.get(f"{DESK}/teams", headers=reader)
    inbox = await client.get(f"{IR}/facilitator/questions", headers=reader)
    across = await client.get(f"{DESK}/sessions", headers=reader)
    waiting = await client.get(f"{IR}/facilitator/sessions", headers=reader)

    assert {row["team_id"] for row in teams.json()["teams"]} == every
    assert {card["question_id"] for card in inbox.json()["questions"]} == questions
    assert {row["session_id"] for row in across.json()["sessions"]} == sessions
    assert {row["session_id"] for row in waiting.json()["sessions"]} == sessions
    for tag in "abc":
        team = desk[tag]
        card = await client.get(f"{DESK}/teams/{team.id}", headers=reader)
        history = await client.get(f"{DESK}/teams/{team.id}/sessions", headers=reader)
        devices = await client.get(f"{DESK}/teams/{team.id}/devices", headers=reader)
        pericopes = await client.get(f"{DESK}/teams/{team.id}/pericopes", headers=reader)
        coverage = await client.get(
            f"{DESK}/teams/{team.id}/coverage", headers=reader, params={"pericope": P}
        )
        hands = await client.get(
            f"{IR}/facilitator/questions", headers=reader, params={"team_id": team.id}
        )
        nudges = await opening_status(app, f"{DESK}/teams/{team.id}/nudges", reader)

        assert card.status_code == 200, card.text[:300]
        assert team.session in {row["session_id"] for row in history.json()}, history.text[:300]
        assert [row["device_id"] for row in devices.json()] == [team.device]
        assert pericopes.status_code == 200
        assert coverage.status_code == 200
        assert [card["question_id"] for card in hands.json()["questions"]] == [team.question]
        assert nudges == 200


async def test_a_consultant_reads_team_bs_conversation_turns_takes_release_and_retroverification_file(  # noqa: E501
    client, desk
) -> None:
    session = desk["b"].session
    reads = [
        f"{IR}/facilitator/sessions/{session}/conversation",
        f"{IR}/facilitator/sessions/{session}/turns",
        f"{IR}/facilitator/sessions/{session}/takes",
        f"{IR}/facilitator/sessions/{session}/release",
        f"{IR}/facilitator/sessions/{session}/releases/1",
        f"{IR}/facilitator/sessions/{session}/scene-rehearsals",
        f"{IR}/facilitator/sessions/{session}/coverage",
        f"{IR}/facilitator/sessions/{session}/boundary-turns",
        f"{IR}/facilitator/sessions/{session}/mother-tongue-takes",
        f"{IR}/facilitator/sessions/{session}/takes/downloads",
        f"{IR}/facilitator/sessions/{session}/external-check/1",
        f"{IR}/facilitator/sessions/{session}/retro",
        f"{IR}/facilitator/sessions/{session}/re-recorded-sentences",
        f"{IR}/facilitator/sessions/{session}/takes/whole",
        f"{IR}/facilitator/sessions/{session}/turns/0/audio",
        f"{IR}/facilitator/sessions/{session}/scene-rehearsals/{desk['b'].rehearsal}/audio",
        f"{IR}/facilitator/sessions/{session}/scene-rehearsals/{desk['b'].rehearsal}"
        f"/frases/{desk['b'].frase}/audio",
    ]

    values = {
        "session_id": session,
        "number": 0,
        "version": 1,
        "sentence_id": "frase-b",
        "rehearsal_id": desk["b"].rehearsal,
        "frase_id": desk["b"].frase,
    }
    answers = {
        path: (
            await client.get(path.format(**values), headers=desk.readers["consultant"])
        ).status_code
        for path in _session_reads()
    }
    mounted = those_that_read(answers)
    listed = {template_of("GET", url) for url in reads}
    assert listed == mounted, (
        f"sem leitura: {sorted(mounted - listed)}; "
        f"leitura sem rota: {sorted(listed - mounted, key=str)}"
    )
    for url in reads:
        theirs = await client.get(url, headers=desk.readers["facilitator_of_b"])
        consultants = await client.get(url, headers=desk.readers["consultant"])
        strangers = await client.get(url, headers=desk.readers["facilitator"])

        assert _answer(consultants) == _answer(theirs), url
        assert _answer(strangers) != _answer(theirs), url
    for url in (
        reads[0],
        reads[1],
        reads[2],
        reads[5],
        reads[8],
        reads[10],
        reads[11],
        reads[12],
        reads[14],
        reads[15],
        reads[16],
    ):
        assert (await client.get(url, headers=desk.readers["consultant"])).status_code == 200, url


async def test_a_consultant_plays_a_questions_audio_a_take_and_a_turn_and_the_session_and_the_question_are_unchanged(  # noqa: E501
    client, desk, per_request, db_session, bucket
) -> None:
    team = desk["b"]
    reader = desk.readers["consultant"]
    answered = await db_session.get(IRQuestion, team.question)
    answered.reply_audio_key = f"internalization-room/questions/{team.question}/resposta-1.m4a"
    answered.status = IRQuestionStatus.ANSWERED
    await db_session.commit()
    await bucket.put(answered.reply_audio_key, b"a facilitadora respondeu", "audio/mp4")
    session_before = await _row(per_request, IRSession, team.session)
    question_before = await _row(per_request, IRQuestion, team.question)

    doors = [
        f"{IR}/facilitator/questions/{team.question}/audio",
        f"{IR}/facilitator/questions/audio/{to_handle(team.question_key)}",
        f"{IR}/facilitator/questions/{team.question}/reply/audio",
        f"{IR}/facilitator/takes/{team.take}/audio",
        f"{IR}/facilitator/sessions/{team.session}/turns/0/audio",
        f"{IR}/facilitator/sessions/{team.session}/re-recorded-sentences/frase-b/audio",
        f"{IR}/facilitator/sessions/{team.session}/scene-rehearsals/{team.rehearsal}/audio",
        f"{IR}/facilitator/sessions/{team.session}/scene-rehearsals/{team.rehearsal}"
        f"/frases/{team.frase}/audio",
    ]
    mounted = _audio_doors()
    covered = {template_of("GET", url) for url in doors}
    assert covered == mounted, (
        f"sem porta: {sorted(mounted - covered)}; "
        f"porta sem rota: {sorted(covered - mounted, key=str)}"
    )

    question, by_handle, reply, take, turn, sentence, scene, scene_frase = [
        await client.get(url, headers=reader) for url in doors
    ]

    assert question.status_code == 200, question.text[:300]
    assert by_handle.content == b"a equipe perguntou"
    assert reply.status_code == 200, reply.text[:300]
    assert bucket.objects[reply.json()["url"].removeprefix("https://signed.test/")] == (
        b"a facilitadora respondeu"
    )
    assert take.status_code == 307, take.text[:300]
    assert turn.status_code == 200, turn.text[:300]
    assert bucket.objects[turn.json()["url"].removeprefix("https://signed.test/plataforma/")] == (
        b"a voz falou"
    )
    assert sentence.status_code == 307, sentence.text[:300]
    assert scene.status_code == 200, scene.text[:300]
    assert scene.json()["url"] == f"https://signed.test/plataforma/{team.rehearsal_key}"
    assert scene_frase.status_code == 200, scene_frase.text[:300]
    assert scene_frase.json()["url"] == f"https://signed.test/plataforma/{team.frase_key}"
    assert await _row(per_request, IRSession, team.session) == session_before
    assert await _row(per_request, IRQuestion, team.question) == question_before


async def test_a_consultant_reads_an_archived_session_by_its_id(client, desk, per_request) -> None:
    team = desk["b"]
    zerar = await client.post(
        f"{IR}/facilitator/projects/{team.id}/passages/{P}/archive", headers=desk.readers["admin"]
    )
    assert zerar.status_code == 200, zerar.text[:300]
    assert (await _row(per_request, IRSession, team.session))["archive_id"] is not None

    conversation = await client.get(
        f"{IR}/facilitator/sessions/{team.session}/conversation", headers=desk.readers["consultant"]
    )

    assert conversation.status_code == 200, conversation.text[:300]
    assert [turn["text"] for turn in conversation.json()["turns"]] == ["Vamos ouvir a história."]


async def test_a_consultant_without_the_facilitator_role_is_refused_at_every_write(
    client, desk, db_session, per_request
) -> None:
    team = desk["b"]
    minted = await create_device(db_session)

    answers = {
        f"{method} {url}": (
            await client.request(method, url, headers=desk.readers["consultant"], **kw)
        ).status_code
        for method, url, kw in _writes_on(team, minted.claim_code)
    }

    assert set(answers.values()) == {403}, answers
    question = await _row(per_request, IRQuestion, team.question)
    assert question["status"] == IRQuestionStatus.OPEN
    assert question["answered_by"] is None


async def test_a_facilitator_of_a_who_holds_consultant_replies_and_marks_attended_on_a_and_reads_b(
    client, desk, db_session
) -> None:
    reader = desk.readers["both"]

    replied = await client.post(
        f"{IR}/facilitator/questions/{desk['a'].question}/reply", headers=reader, **AUDIO
    )
    attended = await client.post(
        f"{IR}/facilitator/sessions/{desk['a'].session}/attended",
        params={"halt": 0},
        headers=reader,
    )
    halt, _ = await record_needs_person(db_session, desk["a"].device)
    device_attended = await client.post(
        f"{DESK}/devices/{desk['a'].device}/attended",
        headers=reader,
        params={"needs_person_since": halt.isoformat()},
    )
    read = await client.get(
        f"{IR}/facilitator/sessions/{desk['b'].session}/conversation", headers=reader
    )

    assert replied.status_code == 200, replied.text[:300]
    assert attended.status_code == 200, attended.text[:300]
    assert device_attended.status_code < 300, device_attended.text[:300]
    assert read.status_code == 200, read.text[:300]


async def test_a_facilitator_of_a_who_holds_consultant_is_told_404_when_writing_on_b(
    client, desk, db_session, per_request
) -> None:
    minted = await create_device(db_session)
    writes = _writes_on(desk["b"], minted.claim_code)
    claim = next(w for w in writes if "claim" in w[1])
    writes.remove(claim)

    answers = {
        f"{method} {url}": (
            await client.request(method, url, headers=desk.readers["both"], **kw)
        ).status_code
        for method, url, kw in writes
    }

    claimed = await client.request(claim[0], claim[1], headers=desk.readers["both"], **claim[2])
    b_devices = await client.get(
        f"{DESK}/teams/{desk['b'].id}/devices", headers=desk.readers["admin"]
    )

    assert set(answers.values()) == {404}, answers
    assert claimed.status_code == 400, claimed.text[:300]
    assert [row["device_id"] for row in b_devices.json()] == [desk["b"].device]
    question = await _row(per_request, IRQuestion, desk["b"].question)
    assert question["status"] == IRQuestionStatus.OPEN
    assert question["answered_by"] is None


async def test_a_facilitator_of_a_without_consultant_cannot_reach_team_b(client, desk) -> None:
    from app.main import app

    team = desk["b"]
    reader = desk.readers["facilitator"]
    reads = [
        (f"{DESK}/teams/{team.id}", {}),
        (f"{DESK}/teams/{team.id}/sessions", {}),
        (f"{DESK}/teams/{team.id}/devices", {}),
        (f"{DESK}/teams/{team.id}/pericopes", {}),
        (f"{DESK}/teams/{team.id}/coverage", {"params": {"pericope": P}}),
        (f"{DESK}/sessions", {"params": {"team_id": team.id}}),
        (f"{IR}/facilitator/questions", {"params": {"team_id": team.id}}),
        (f"{IR}/facilitator/questions/{team.question}/audio", {}),
        (f"{IR}/facilitator/questions/{team.question}/reply/audio", {}),
        (f"{IR}/facilitator/sessions/{team.session}/conversation", {}),
        (f"{IR}/facilitator/sessions/{team.session}/coverage", {}),
        (f"{IR}/facilitator/sessions/{team.session}/boundary-turns", {}),
        (f"{IR}/facilitator/sessions/{team.session}/takes", {}),
        (f"{IR}/facilitator/sessions/{team.session}/mother-tongue-takes", {}),
        (f"{IR}/facilitator/sessions/{team.session}/takes/downloads", {}),
        (f"{IR}/facilitator/sessions/{team.session}/takes/whole", {}),
        (f"{IR}/facilitator/sessions/{team.session}/re-recorded-sentences", {}),
        (f"{IR}/facilitator/sessions/{team.session}/re-recorded-sentences/frase-b/audio", {}),
        (f"{IR}/facilitator/takes/{team.take}/audio", {}),
        (f"{IR}/facilitator/questions/audio/{to_handle(team.question_key)}", {}),
        (f"{IR}/facilitator/sessions/{team.session}/release", {}),
        (f"{IR}/facilitator/sessions/{team.session}/releases/1", {}),
        (f"{IR}/facilitator/sessions/{team.session}/retroverificacao", {}),
        (f"{IR}/facilitator/projects/{team.id}/passages/{P}/retroverificacao", {}),
        (f"{IR}/facilitator/sessions/{team.session}/retro", {}),
        (f"{IR}/facilitator/sessions/{team.session}/external-check/1", {}),
        (f"{IR}/facilitator/sessions/{team.session}/scene-rehearsals", {}),
        (f"{IR}/facilitator/sessions/{team.session}/turns", {}),
        (f"{IR}/facilitator/sessions/{team.session}/turns/0/audio", {}),
        (
            f"{IR}/facilitator/sessions/{team.session}/scene-rehearsals/{team.rehearsal}/audio",
            {},
        ),
        (
            f"{IR}/facilitator/sessions/{team.session}/scene-rehearsals/{team.rehearsal}"
            f"/frases/{team.frase}/audio",
            {},
        ),
    ]
    nudges = f"{DESK}/teams/{team.id}/nudges"

    mounted = _reads_that_name_a_team_resource()
    covered = {template_of("GET", url) for url, _ in reads} | {template_of("GET", nudges)}
    assert covered == mounted, (
        f"sem recusa: {sorted(mounted - covered)}; "
        f"recusa sem rota: {sorted(covered - mounted, key=str)}"
    )
    answers = {url: (await client.get(url, headers=reader, **kw)).status_code for url, kw in reads}
    answers[nudges] = await opening_status(app, nudges, reader)
    listed = await client.get(f"{DESK}/teams", headers=reader)

    assert set(answers.values()) == {404}, answers
    assert [row["team_id"] for row in listed.json()["teams"]] == [desk["a"].id]


async def test_the_team_card_says_whether_the_reader_facilitates_that_team(client, desk) -> None:
    def facilitates(listing: httpx.Response) -> dict[str, bool]:
        names = {desk[tag].id: tag for tag in "abc"}
        return {names[row["team_id"]]: row["facilitates"] for row in listing.json()["teams"]}

    cards = {
        reader: facilitates(await client.get(f"{DESK}/teams", headers=desk.readers[reader]))
        for reader in (
            "facilitator",
            "both",
            "consultant",
            "admin",
            "consultant_with_a_leftover_link",
        )
    }
    one_card = await client.get(f"{DESK}/teams/{desk['b'].id}", headers=desk.readers["both"])

    assert cards == {
        "facilitator": {"a": True},
        "both": {"a": True, "b": False, "c": False},
        "consultant": {"a": False, "b": False, "c": False},
        "admin": {"a": True, "b": True, "c": True},
        "consultant_with_a_leftover_link": {"a": False, "b": False, "c": False},
    }
    assert one_card.json()["facilitates"] is False


async def test_the_open_hands_total_counts_only_the_teams_the_reader_facilitates(
    client, desk
) -> None:
    listed = await client.get(f"{DESK}/teams", headers=desk.readers["both"])

    assert listed.json()["open_hands_total"] == 1


async def test_a_team_that_does_not_exist_is_refused_at_every_read_even_to_a_consultant(
    client, desk
) -> None:
    from app.main import app

    reader = desk.readers["consultant"]
    nowhere = "equipe-que-nao-existe"
    reads = [
        (f"{DESK}/teams/{nowhere}", {}),
        (f"{DESK}/teams/{nowhere}/sessions", {}),
        (f"{DESK}/teams/{nowhere}/devices", {}),
        (f"{DESK}/teams/{nowhere}/pericopes", {}),
        (f"{DESK}/teams/{nowhere}/coverage", {"params": {"pericope": P}}),
        (f"{DESK}/sessions", {"params": {"team_id": nowhere}}),
        (f"{IR}/facilitator/questions", {"params": {"team_id": nowhere}}),
    ]
    nudges_url = f"{DESK}/teams/{nowhere}/nudges"

    mounted = _reads_of_a_team()
    covered = {template_of("GET", url) for url, _ in reads} | {template_of("GET", nudges_url)}
    assert covered == mounted, (
        f"sem recusa: {sorted(mounted - covered)}; "
        f"recusa sem rota: {sorted(covered - mounted, key=str)}"
    )
    answers = {url: (await client.get(url, headers=reader, **kw)).status_code for url, kw in reads}
    nudges = await opening_status(app, nudges_url, reader)

    assert set(answers.values()) == {404}, answers
    assert nudges == 404


async def test_a_consultant_reads_the_retroverification_file_of_team_bs_passage(
    client, desk
) -> None:
    team = desk["b"]
    url = f"{IR}/facilitator/projects/{team.id}/passages/{P}/retroverificacao"

    consultant = await client.get(url, headers=desk.readers["consultant"])
    stranger = await client.get(url, headers=desk.readers["facilitator"])

    assert consultant.status_code == 200, consultant.text[:300]
    assert consultant.json()["pericopeId"] == P
    assert stranger.status_code == 404
