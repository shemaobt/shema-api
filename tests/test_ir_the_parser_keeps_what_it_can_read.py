"""The parser keeps what it can read, and writes down what it could not.

On 2026-09-02 the analyst answered a real session (P02, pt) with valid JSON, two findings
with valid kinds and non-empty notes — and the room told the team three times that the
analysis "could not be done right now". The service had not failed. The reply carried
`evidence_sufficient: true` beside an `insufficient_evidence` finding, the parser read
that as a contradiction and returned None without a word, and the route called None an
upstream failure. A good `addition` finding went out with it.

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

from app.api.internalization_room import back_translation as bt_api
from app.core.config import Settings
from app.core.exceptions import ERROR_CODE_UPSTREAM
from app.db.models.internalization_room import IRPromptKey, IRSegment, IRTakeKind
from app.services.internalization_room import sessions as room
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import FindingKind, analyse_telling_back
from app.services.internalization_room.voice_handles import clip_url
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
    """Case 1, at the parser. The finding on the third stretch exists after the read.

    The reply that cost ENG-719 a whole round is now read for what the room still has a
    word for: the `addition` on the third stretch. What it says about thin evidence is no
    finding under Marcia's rule, so it leaves — and the finding beside it stays.
    """
    analysis = await _read(CAPTURED_REPLY, patch_analyst)

    assert analysis is not None, "uma resposta bem formada nunca é descartada inteira"
    assert [f.kind for f in analysis.findings] == [FindingKind.ADDITION]
    assert analysis.findings[0].segment_id == "segmento-3"


@pytest.mark.asyncio
async def test_what_the_analyst_said_is_written_down_with_what_was_dropped(
    patch_analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """A finding the room drops on its own is a decision, and nobody may learn it from silence."""
    with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
        await _read(CAPTURED_REPLY, patch_analyst)

    assert "casa dos 'tios'" in caplog.text, "o log mostra o que o analista disse"
    assert "insufficient_evidence" in _besides_the_reply(caplog, CAPTURED_REPLY)


@pytest.mark.parametrize(
    ("reply", "refused_field"),
    [
        pytest.param(
            json.dumps({"session": MARK, "evidence_sufficient": True, "findings": "nada"}),
            "findings",
            id="findings-is-not-a-list",
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
    assert body["findings_remaining"] == 1
    assert body["finding_kind"] == FindingKind.ADDITION.value
    assert body["checked"] is False, "há achado aberto; a passagem não é dada por conferida"

    resumed = await _resumed(client, session_id)
    assert resumed["finding_kind"] == FindingKind.ADDITION.value, (
        "e o achado está no estado que o tablet retoma, não só na resposta"
    )
    assert resumed["finding_segment_id"] == resumed["segments"][2]["segment_id"]
    assert resumed["checked"] is False


@pytest.mark.asyncio
async def test_a_reply_the_room_cannot_read_is_not_a_provider_that_is_down(
    client: httpx.AsyncClient,
    analyst: Analyst,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 3. The analyst answered; the room could not read it. Say that, not the other thing.

    Marcia's second case, and the only round with no verdict once the evidence flag is gone:
    the Speaker is never asked to say anything, nothing is saved, and the next press asks
    the analyst again rather than serving a verdict nobody reached.
    """
    verdicts: list[str] = []
    voiced = bt_api.room.run_verdict_turn

    async def counting(*args: Any, **kwargs: Any) -> Any:
        verdicts.append(kwargs.get("closing", ""))
        return await voiced(*args, **kwargs)

    monkeypatch.setattr(bt_api.room, "run_verdict_turn", counting)
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
    assert verdicts == [], "sem leitura não há veredito: a voz não é chamada"

    resumed = await _resumed(client, session_id)
    assert resumed["checked"] is False
    assert resumed["finding_kind"] is None, "e nada foi guardado no estado que o tablet retoma"

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


def _a_state_stored_before_the_taxonomy_shrank(segment_id: str) -> dict[str, Any]:
    """The row a session in flight has, written when the retired kinds were still emitted."""
    return {
        "scope": PASSAGE,
        "findings": [
            {
                "kind": "meaning_change",
                "note": "contaram que Noemi voltou alegre",
                "segment_id": segment_id,
            }
        ],
        "evidence_sufficient": True,
        "checked": False,
        "superseded": [
            {
                "findings": [
                    {"kind": "wrong_relation", "note": "trocaram quem pediu", "segment_id": None}
                ],
                "evidence_sufficient": True,
                "played_ranges": [],
                "clip_duration_ms": None,
            }
        ],
        "played_ranges": [],
        "clip_duration_ms": None,
    }


@pytest.mark.asyncio
async def test_a_session_in_flight_with_a_retired_kind_still_loads_and_still_voices(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """A row written by the older server still opens, in the findings and in the superseded.

    No migration touches the row, so the team that pressed `terminei` yesterday resumes
    today: the retired kind reads as addition on the way out of the row, in the findings and
    in the superseded ones, and the round runs to a verdict instead of failing to load.
    """
    session_id = await _four_stretches_told(client)
    told = await _resumed(client, session_id)
    session = await room.get_session(db_session, session_id)
    session.back_translation = _a_state_stored_before_the_taxonomy_shrank(
        told["segments"][0]["segment_id"]
    )
    await db_session.commit()

    state = room.back_translation_of(await room.get_session(db_session, session_id))
    assert state.findings[0].kind is FindingKind.ADDITION
    assert state.superseded[0].findings[0].kind is FindingKind.ADDITION

    resumed = await _resumed(client, session_id)
    assert resumed["finding_kind"] == FindingKind.ADDITION.value

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["checked"] is True, (
        "uma leitura inteira limpa com evidência suficiente confere a passagem"
    )


@pytest.mark.asyncio
async def test_a_garbled_stretch_is_one_unclear_and_does_not_confer(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Marcia's first case. A frase too garbled to judge is a finding, and the round waits.

    The rule that lets a thin reading of a legible frase confer does not touch this one:
    unclear is a finding, and a reading that returns a finding never checks the passage.
    """
    analyst.reply = json.dumps(
        {"findings": [{"kind": "unclear", "chunk": 2, "note": "não deu para ouvir"}]}
    )
    session_id = await _four_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["finding_kind"] == FindingKind.UNCLEAR.value
    assert body["checked"] is False

    resumed = await _resumed(client, session_id)
    assert resumed["finding_kind"] == FindingKind.UNCLEAR.value
    assert resumed["finding_segment_id"] == resumed["segments"][1]["segment_id"]
    assert resumed["checked"] is False


@pytest.mark.asyncio
async def test_a_thin_but_legible_telling_back_confers(
    client: httpx.AsyncClient, analyst: Analyst
) -> None:
    """Marcia's fourth case, and the cost she accepted, on purpose.

    A reading that says the evidence was thin and names no difference is no finding at all,
    so the passage is checked and leaves the rotation. The cost, accepted on 2026-09-07: a
    thin reading of a good telling-back confers. The one it replaces was worse — the room
    asked for a fuller telling of a frase that was perfectly legible, and nothing the team
    did changed the answer.
    """
    analyst.reply = json.dumps({"evidence_sufficient": False, "findings": []})
    session_id = await _four_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["checked"] is True
    assert body["findings_remaining"] == 0
    assert body["fixed_line"] == "", "o caminho normal fala pela síntese, não por fala fixa"
    assert body["audio_url"], "e o Falante disse o fechamento de passagem conferida"

    resumed = await _resumed(client, session_id)
    assert resumed["checked"] is True


def _a_state_stored_before_the_evidence_flag_went(segment_id: str) -> dict[str, Any]:
    """The row a session in flight has, written while the flag and the kind still existed."""
    return {
        "scope": PASSAGE,
        "findings": [
            {"kind": "insufficient_evidence", "note": "contaram pouco", "segment_id": None},
            {
                "kind": "missing",
                "note": "Orfa não apareceu",
                "segment_id": segment_id,
            },
        ],
        "evidence_sufficient": False,
        "checked": False,
        "superseded": [
            {
                "findings": [
                    {
                        "kind": "insufficient_evidence",
                        "note": "a primeira tentativa contou pouco",
                        "segment_id": None,
                    }
                ],
                "evidence_sufficient": False,
                "played_ranges": [],
                "clip_duration_ms": None,
            }
        ],
        "played_ranges": [],
        "clip_duration_ms": None,
    }


@pytest.mark.asyncio
async def test_a_stored_thin_evidence_finding_reads_as_no_finding_at_all(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """The row of a team that pressed `terminei` yesterday opens today, one finding lighter.

    No migration touches the row. Under Marcia's rule the stored insufficient-evidence
    finding was the thin-evidence case, which is no finding, so it is dropped on the way out
    of the row — in the findings and in the superseded ones — and what the team still has to
    answer stays. The flag stored beside them is a key nobody reads.
    """
    session_id = await _four_stretches_told(client)
    told = await _resumed(client, session_id)
    session = await room.get_session(db_session, session_id)
    session.back_translation = _a_state_stored_before_the_evidence_flag_went(
        told["segments"][0]["segment_id"]
    )
    await db_session.commit()

    state = room.back_translation_of(await room.get_session(db_session, session_id))

    assert [f.kind for f in state.findings] == [FindingKind.MISSING]
    assert state.superseded[0].findings == []
    assert state.checked is False

    resumed = await _resumed(client, session_id)
    assert resumed["finding_kind"] == FindingKind.MISSING.value


#: The clip the Speaker made when the row below was written, about the finding that has
#: since stopped being one.
STALE_CLIP = "clipe-do-veredito-de-ontem"


def _a_row_whose_verdict_was_about_thin_evidence(
    findings: list[dict[str, Any]], analysed: list[str]
) -> dict[str, Any]:
    """The row of a team that pressed `terminei` yesterday and heard "too little to check".

    It carries what makes `terminei` serve an answer without asking the analyst again: the
    stretches it already read, and the verdict it already voiced.
    """
    return {
        "scope": PASSAGE,
        "findings": findings,
        "evidence_sufficient": False,
        "checked": False,
        "analysed_segment_ids": analysed,
        "verdict": {"clip_key": STALE_CLIP, "fixed_line": "", "used_fail_safe": False},
        "superseded": [],
        "played_ranges": [],
        "clip_duration_ms": None,
    }


async def _stored(
    client: httpx.AsyncClient,
    db: AsyncSession,
    session_id: str,
    findings: list[dict[str, Any]],
) -> None:
    told = await _resumed(client, session_id)
    session = await room.get_session(db, session_id)
    session.back_translation = _a_row_whose_verdict_was_about_thin_evidence(
        findings, [one["segment_id"] for one in told["segments"]]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_a_verdict_about_thin_evidence_is_not_served_again(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """The team pressed `terminei` yesterday and heard it. Today the room decides again.

    The stored finding is no finding at all, so the answer it produced cannot stand either:
    serving it back would ask for a fuller telling of a legible frase on every press, which
    is exactly what the rule removed. Nothing was told back since, so the analyst is not
    asked to read again — what it already read is what confers the passage.
    """
    session_id = await _four_stretches_told(client)
    await _stored(
        client,
        db_session,
        session_id,
        [{"kind": "insufficient_evidence", "note": "contaram pouco", "segment_id": None}],
    )

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["checked"] is True
    assert body["findings_remaining"] == 0
    assert analyst.readings == 0, "a leitura que o analista já fez continua valendo"
    assert body["audio_url"] != clip_url(STALE_CLIP), "o clipe de ontem não é a resposta"
    assert body["audio_url"], "e o Falante disse o fechamento de passagem conferida"


@pytest.mark.asyncio
async def test_a_finding_that_survives_the_drop_is_what_the_room_says(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    """The other half: what the team still has to answer is what they hear about.

    Deciding again is not conferring again — the round only closes when nothing is left.
    """
    session_id = await _four_stretches_told(client)
    told = await _resumed(client, session_id)
    await _stored(
        client,
        db_session,
        session_id,
        [
            {"kind": "insufficient_evidence", "note": "contaram pouco", "segment_id": None},
            {
                "kind": "missing",
                "note": "Orfa não apareceu",
                "segment_id": told["segments"][1]["segment_id"],
            },
        ],
    )

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["finding_kind"] == FindingKind.MISSING.value
    assert body["checked"] is False
    assert body["findings_remaining"] == 1
    assert analyst.readings == 0
    assert body["audio_url"] != clip_url(STALE_CLIP), (
        "o que a equipe ouve é sobre a falta, não a fala de ontem sobre pouca evidência"
    )
