"""The parser keeps what it can read, and writes down what it could not.

On 2026-09-02 the analyst answered a real session (P02, pt) with valid JSON, two findings
with valid kinds and non-empty notes — and the room told the team three times that the
analysis "could not be done right now". The service had not failed. The reply carried
`evidence_sufficient: true` beside an `insufficient_evidence` finding, the parser read
that as a contradiction and returned None without a word, and the route called None an
upstream failure. A good `meaning_change` finding went out with it.

Three things are pinned here. A well-formed reply is never discarded whole. Every refusal
the parser makes says which condition refused and shows what the analyst sent. And a
reply the room could not read is not a provider that is down: the two are told apart in
the exception, in the error code, and in the log, so the next investigation starts at
the right place.

The reply below is the one captured in ENG-719, verbatim, and the stretches under it are
four because it points at the third and the fourth.
"""

from __future__ import annotations

import base64
import importlib
import json
import logging
import sys
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ERROR_CODE_UPSTREAM
from app.db.models.internalization_room import IRPromptKey, IRSegment, IRTakeKind
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import FindingKind, analyse_telling_back
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P02"
ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
PARSER_LOGGER = "app.services.internalization_room.back_translation"

#: What the analyst answered in session 5fd9839e on 2026-09-02, as captured in ENG-719.
CAPTURED_REPLY = """{
  "evidence_sufficient": true,
  "findings": [
    { "kind": "meaning_change", "chunk": 3, "note": "…casa dos 'tios', mas o mapa especifica a casa da 'mãe'" },
    { "kind": "insufficient_evidence", "chunk": 4, "note": "o relato termina no versículo 8; falta todo o conteúdo de 1:9 a 1:14 (…)" }
  ]
}"""  # noqa: E501

#: A token planted in each malformed reply, so "the log shows what was received" can be
#: checked without asserting on the shape of the log line itself.
MARK = "MARCA-7f3e"

#: What the upstream handler writes. Case 5 is the positive control for case 3's negative:
#: if the wording moves, case 5 fails loudly and case 3 does not go quietly vacuous.
UPSTREAM_LOG_LINE = "Upstream service failure"


def _besides_the_reply(caplog: pytest.LogCaptureFixture, reply: str) -> str:
    """The log with the echoed reply cut out.

    The reply itself names every field in the contract, so a log that only echoed it would
    satisfy "names the condition" without naming anything. What is left has to.
    """
    return caplog.text.replace(reply, "")


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _segment(number: int, text: str) -> IRSegment:
    return IRSegment(
        id=f"segmento-{number}",
        session_id="sessao-1",
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


def _four_told() -> list[IRSegment]:
    return [
        _segment(1, "Noemi ouviu que Deus tinha visitado o povo dele."),
        _segment(2, "Ela saiu com as noras para voltar para Judá."),
        _segment(3, "Noemi disse para cada uma voltar para a casa dos tios."),
        _segment(4, "Elas choraram."),
    ]


@pytest.fixture
def patch_analyst(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules[PARSER_LOGGER]

    def _install(reply: str) -> None:
        async def agent(*, system_prompt: str, user_content: str, **_: Any) -> str:
            return reply

        monkeypatch.setattr(module, "call_agent", agent)

    return _install


async def _read(reply: str, patch_analyst):
    patch_analyst(reply)
    return await analyse_telling_back(
        segments=_four_told(),
        scope=PASSAGE,
        pericope_num=PASSAGE,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )


@pytest.mark.asyncio
async def test_a_well_formed_reply_is_never_thrown_away_whole(patch_analyst) -> None:
    """Case 1, at the parser. The `meaning_change` on the third stretch exists after the read.

    The specific finding wins over the general flag: an `insufficient_evidence` finding
    *is* the statement that evidence is insufficient, with content — which stretch, why —
    and the flag is its summary with no information of its own. So both findings stay and
    the flag follows the finding, which is also what keeps `checked` from blessing a passage
    the analyst itself said stops at verse 8.
    """
    analysis = await _read(CAPTURED_REPLY, patch_analyst)

    assert analysis is not None, "uma resposta bem formada nunca é descartada inteira"
    assert [f.kind for f in analysis.findings] == [
        FindingKind.MEANING_CHANGE,
        FindingKind.INSUFFICIENT_EVIDENCE,
    ]
    assert analysis.findings[0].segment_id == "segmento-3"
    assert analysis.evidence_sufficient is False, (
        "o achado sobre um trecho é mais informativo que o flag sobre o conjunto"
    )


@pytest.mark.asyncio
async def test_the_contradiction_is_written_down_with_what_the_analyst_said(
    patch_analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """The analyst broke the contract its own prompt writes; nobody may learn that from silence."""
    with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
        await _read(CAPTURED_REPLY, patch_analyst)

    assert "casa dos 'tios'" in caplog.text, "o log mostra o que o analista disse"
    assert "evidence_sufficient" in _besides_the_reply(caplog, CAPTURED_REPLY)


@pytest.mark.parametrize(
    ("reply", "refused_field"),
    [
        pytest.param(
            json.dumps({"session": MARK, "evidence_sufficient": True, "findings": "nada"}),
            "findings",
            id="findings-is-not-a-list",
        ),
        pytest.param(
            json.dumps({"session": MARK, "evidence_sufficient": "sim", "findings": []}),
            "evidence_sufficient",
            id="evidence_sufficient-is-not-a-boolean",
        ),
        pytest.param(
            json.dumps({"session": MARK, "evidence_sufficient": True, "findings": ["texto"]}),
            "findings",
            id="a-finding-is-not-an-object",
        ),
        pytest.param(
            json.dumps(
                {
                    "session": MARK,
                    "evidence_sufficient": True,
                    "findings": [{"kind": "missing", "chunk": 1, "note": "   "}],
                }
            ),
            "note",
            id="a-note-is-empty",
        ),
        pytest.param(
            json.dumps({"session": MARK, "evidence_sufficient": False, "findings": []}),
            "evidence_sufficient",
            id="insufficient-without-a-finding-naming-the-limit",
        ),
        pytest.param(
            json.dumps(
                {
                    "session": MARK,
                    "evidence_sufficient": True,
                    "findings": [{"kind": "inventado", "chunk": 1, "note": "algo"}],
                }
            ),
            "kind",
            id="a-kind-is-not-in-the-taxonomy",
        ),
        pytest.param(
            json.dumps([MARK]),
            "findings",
            id="the-reply-is-not-an-object",
        ),
    ],
)
@pytest.mark.asyncio
async def test_every_refusal_says_which_condition_and_shows_the_reply(
    reply: str, refused_field: str, patch_analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """Case 2. Every way to return None, none of them silent.

    The field named is the one from the analyst's own output contract, so the check does
    not depend on the wording of the log line. The last two already spoke, one of them
    without the reply; they are here so the list is every exit and not most of them.
    """
    with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
        analysis = await _read(reply, patch_analyst)

    assert analysis is None
    assert MARK in caplog.text, "o log mostra o texto recebido"
    assert refused_field in _besides_the_reply(caplog, reply), "e diz qual condição recusou"


@pytest.mark.asyncio
async def test_invalid_json_is_still_refused_and_still_written_down(
    patch_analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """Case 4. The one exit that already spoke keeps speaking."""
    with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
        analysis = await _read(f"desculpe, não consigo {MARK}", patch_analyst)

    assert analysis is None
    assert MARK in caplog.text


class MemoryStore:
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


class Analyst:
    """The analyst as the route sees it: what it answers, or the way it fails, and a count.

    The count is how "nothing was saved" is observed: a verdict nobody reached must not be
    served on the next press, so the next press has to ask the analyst again.
    """

    def __init__(self) -> None:
        self.reply = '{"evidence_sufficient": true, "findings": []}'
        self.failure: Exception | None = None
        self.readings = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.readings += 1
        if self.failure is not None:
            raise self.failure
        return self.reply


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    reader = Analyst()
    monkeypatch.setattr(sys.modules[PARSER_LOGGER], "call_agent", reader)
    return reader


@pytest.fixture()
def spoken(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The verdict speaker and the voice, so a read reply can be answered end to end."""
    spoken: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(text: str, *_: Any, **__: Any):
        spoken.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(spoken)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return spoken


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    bucket: MemoryStore,
    spoken: list[str],
    monkeypatch: pytest.MonkeyPatch,
):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


async def _open_session(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PASSAGE, "language": "pt"},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell_back(
    client: httpx.AsyncClient, session_id: str, *, take_id: str, position: int
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={
            "take_id": take_id,
            "starts_ms": str((position - 1) * 9000),
            "ends_ms": str(position * 9000),
        },
        files={"file": (f"trecho-{position}.m4a", f"trecho {position}".encode(), "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _finish(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers={"X-Room-Key": KEY}
    )


async def _four_stretches_told(client: httpx.AsyncClient) -> str:
    session_id = await _open_session(client)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.said.extend(segment.transcript for segment in _four_told())  # type: ignore[attr-defined]
    for position in range(1, 5):
        await _tell_back(client, session_id, take_id=take_id, position=position)
    return session_id


async def _resumed(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    standing = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert standing.status_code == 200, standing.text
    return dict(standing.json()["back_translation"])


@pytest.mark.asyncio
async def test_the_valid_finding_reaches_the_session(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Case 1, at the route. The team hears about 'tios', and the passage is not blessed."""
    analyst.reply = CAPTURED_REPLY
    session_id = await _four_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["findings_remaining"] == 2
    assert body["finding_kind"] == FindingKind.MEANING_CHANGE.value
    assert body["checked"] is False, "há achado aberto; a passagem não é dada por conferida"

    resumed = await _resumed(client, session_id)
    assert resumed["finding_kind"] == FindingKind.MEANING_CHANGE.value, (
        "e o achado está no estado que o tablet retoma, não só na resposta"
    )
    assert resumed["finding_segment_id"] == resumed["segments"][2]["segment_id"]
    assert resumed["checked"] is False


@pytest.mark.asyncio
async def test_a_reply_the_room_cannot_read_is_not_a_provider_that_is_down(
    client: httpx.AsyncClient, analyst: Analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """Case 3. The analyst answered; the room could not read it. Say that, not the other thing.

    Nothing is saved either way, so the next press asks the analyst again rather than
    serving a verdict nobody reached.
    """
    analyst.reply = json.dumps({"evidence_sufficient": True, "findings": "nada"})
    session_id = await _four_stretches_told(client)

    with caplog.at_level(logging.WARNING):
        answered = await _finish(client, session_id)

    assert answered.status_code == 502, answered.text
    body = answered.json()
    assert body["code"] == "UNREADABLE_REPLY"
    assert UPSTREAM_LOG_LINE not in caplog.text, (
        "o serviço externo respondeu; chamar isso de queda custou uma investigação inteira"
    )

    await _finish(client, session_id)
    assert analyst.readings == 2, "nada foi salvo: o próximo terminei pergunta de novo"


@pytest.mark.asyncio
async def test_a_provider_that_is_down_is_still_an_upstream_failure(
    client: httpx.AsyncClient, analyst: Analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """Case 5. The other side of case 3, and what keeps it from being a loosening."""
    analyst.failure = RuntimeError("gemini fora do ar")
    session_id = await _four_stretches_told(client)

    with caplog.at_level(logging.WARNING):
        answered = await _finish(client, session_id)

    assert answered.status_code == 502, answered.text
    assert answered.json()["code"] == ERROR_CODE_UPSTREAM
    assert UPSTREAM_LOG_LINE in caplog.text
