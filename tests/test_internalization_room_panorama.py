import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.coverage import counts
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.run_turn import TurnOutcome, run_panorama_turn
from app.services.internalization_room.sessions import (
    book_of,
    create_session,
    get_session,
    is_panorama,
    resolve_pericope,
)
from app.services.platform.tts import SynthesizedSpeech

PANORAMA = default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
OV = "OV-Ruth"
PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
NOTE_PT = (
    "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à mesa, "
    "pronta para conversar. Fale primeiro.]"
)
VENDOR = Path(__file__).parents[1] / "app/services/internalization_room/prompts/vendor"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The turn endpoint as the tablet reaches it, in a panorama session.

    `run_panorama_turn` is patched per test at `sessions_api.room`, the same seam
    `test_internalization_room_api.py` uses — the endpoint reads it off the `room` module,
    not by name, so a bare-function monkeypatch there is what the route actually calls.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/v/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _no_prepared_opening(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "prepare_opening", _no_prepared_opening)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _open_panorama(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV", "language": "pt"}
    )
    session_id: str = created.json()["session_id"]
    await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})
    return session_id


async def _speak(client: httpx.AsyncClient, session_id: str, filename: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": (filename, b"audio", "audio/m4a")},
    )


class FakeAgent:
    def __init__(self, verdict: dict[str, Any], draft: str = "Vamos conhecer o livro."):
        self.verdict = verdict
        self.draft = draft
        self.systems: list[str] = []
        self.asked: list[str] = []
        self.histories: list[list[dict[str, str]]] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.systems.append(system_prompt)
        self.asked.append(user_content)
        if "corrected_response" in system_prompt:
            return json.dumps(self.verdict)
        self.histories.append([dict(turn) for turn in kwargs["conversation"]])
        return self.draft


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(agent: FakeAgent) -> FakeAgent:
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_a_book_id_is_recognised_as_a_panorama() -> None:
    assert is_panorama(OV)
    assert book_of(OV) == "Ruth"
    assert not is_panorama("P03")
    assert book_of("P03") == "Ruth"


def test_the_bare_alias_resolves_to_the_book_the_room_serves() -> None:
    """A client asks for `OV` and never learns which book it is — the canon stays here."""
    assert resolve_pericope("OV") == OV
    assert resolve_pericope("P03") == "P03"


def test_the_wheels_own_panorama_id_also_resolves_to_the_book_the_room_serves() -> None:
    """The passage wheel hands a team `"panorama"`, not `"OV"` — a session opened with the
    id the wheel just gave out must reach the panorama, not a refusal from a pericope
    nobody vendored."""
    assert resolve_pericope("panorama") == OV


async def test_the_alias_opens_a_real_panorama_session(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope="OV")

    assert session.pericope == OV
    assert is_panorama(session.pericope)


async def test_a_panorama_session_has_no_coverage_spine(db_session: AsyncSession) -> None:
    """It prepares the team to enter the book; it asks no retelling and never completes."""
    session = await create_session(db_session, pericope=OV)

    assert session.coverage_state == {}
    assert counts(session.coverage_state) == {"engaged": 0, "surfaced": 0, "total": 0}
    assert session.status is IRSessionStatus.IN_PROGRESS


async def test_the_panorama_is_grounded_on_the_book_material(patch_agent) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    material = build_book_material("Ruth")

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=material,
        opening=True,
        settings=_settings(),
    )

    assert outcome.speech == "Vamos conhecer o livro."
    speaker_system = agent.systems[0]
    assert "THE BOOK OF RUTH" in speaker_system
    assert "PRESERVATION NOTES" in speaker_system


async def test_the_panorama_speaks_from_her_body_whole_not_from_a_copy_missing_her_opening(
    patch_agent,
) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    material = build_book_material("Ruth")
    lines = (VENDOR / "book_overview_system_prompt.md").read_text(encoding="utf-8").splitlines()
    begin = lines.index("`=== BEGIN SYSTEM PROMPT ===`")
    end = lines.index("`=== END SYSTEM PROMPT ===`")
    hers = "\n".join(lines[begin + 1 : end]).strip()

    await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="o que é esse livro?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=material,
        settings=_settings(),
    )

    speaker_system = agent.systems[0].replace(CACHE_BREAK, "")
    assert speaker_system == (
        hers.replace("{{BOOK_NAME}}", "Ruth")
        .replace("{{SESSION_LANGUAGE}}", "Portuguese")
        .replace("{{BOOK_MATERIAL}}", material)
    ), "o panorama falava de uma cópia nossa, sem a seção de abertura dela"
    assert (
        "quando\nquiserem falar comigo, toquem no círculo; toquem de novo quando terminarem"
        in speaker_system
    ), "a frase do círculo (K1) saía do corpo dela"
    assert "**Written for a voice, not a page.**" in speaker_system


@pytest.mark.parametrize(
    ("language_code", "session_language", "note"),
    [
        (
            "pt",
            "Portuguese",
            "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à "
            "mesa, pronta para conversar. Fale primeiro.]",
        ),
        (
            "en",
            "English",
            "[The session has just begun. The team opened the Book Panorama of Ruth and is at "
            "the table, ready to talk. Speak first.]",
        ),
        (
            "es",
            "Spanish",
            "[The session has just begun. The team opened the Book Panorama of Ruth and is at "
            "the table, ready to talk. Speak first.]",
        ),
    ],
)
async def test_the_panorama_opens_on_her_note_not_on_an_instruction_written_for_passages(
    patch_agent, language_code: str, session_language: str, note: str
) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    await run_panorama_turn(
        session_language=session_language,
        language_code=language_code,
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        opening=True,
        settings=_settings(),
    )

    assert agent.asked[0] == note, (
        "a abertura do panorama mandava ao Facilitador a nossa instrução em inglês, "
        "escrita para passagens"
    )


async def test_the_validator_judges_against_the_same_material(patch_agent) -> None:
    """Containment is enforced twice in a panorama too, with the book as the standard."""
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="o que é esse livro?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    validator_system = agent.systems[1]
    assert "THE BOOK OF RUTH" in validator_system
    assert "{{" not in validator_system


async def test_a_panorama_that_could_not_hear_the_team_is_a_degraded_turn(patch_agent) -> None:
    """The book session counts toward a facilitator the same way a passage does.

    Its fail-safe is a second copy of the one in `run_turn`, and a room that cannot hear the
    team is a room that is not working whichever session it is standing in."""
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="   ",
        messages=[{"role": "guide", "text": "vamos conhecer o livro"}],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.speech in utterances(FailSafe.INAUDIBLE, "pt")
    assert outcome.used_fail_safe is True
    assert outcome.degraded is True
    assert agent.systems == []


async def test_a_panorama_missing_the_team_again_still_gets_the_first_d_line(
    patch_agent,
) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    one_miss = [
        {"role": "guide", "text": "vamos conhecer o livro", "outcome": "pass"},
        {"role": "guide", "text": "…", "outcome": "fail_safe", "category": "D"},
    ]

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="   ",
        messages=one_miss,
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.fixed_line == "D0", "duas mensagens guardadas davam D1 pela paridade"
    assert agent.systems == []


async def test_a_rejected_panorama_turn_is_never_voiced(patch_agent) -> None:
    patch_agent(
        FakeAgent(
            {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
            draft="Rute se casa com Boaz no fim.",
        )
    )

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="como termina?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True
    assert "Boaz" not in outcome.speech


async def test_a_panorama_past_its_opening_takes_a_second_and_a_third_utterance(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A panorama does not stop after the opening — the team keeps talking, turn after turn."""
    from app.api.internalization_room import sessions as sessions_api

    heard = ["pergunta dois", "pergunta três"]
    routed: list[str] = []

    async def _panorama(*, transcript: str, **_: Any) -> TurnOutcome:
        routed.append(transcript)
        return TurnOutcome(speech=f"resposta {len(routed)}.", transcript=transcript)

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=heard.pop(0))

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    session_id = await _open_panorama(client)
    second = await _speak(client, session_id, "q2.m4a")
    third = await _speak(client, session_id, "q3.m4a")

    assert second.status_code == 200
    assert third.status_code == 200
    assert routed == ["", "pergunta dois", "pergunta três"], (
        "as duas falas seguintes à abertura têm de chegar ao motor do panorama"
    )
    for turn in (second, third):
        body = turn.json()
        assert body["audio_url"].startswith(f"{PREFIX}/voice/")
        assert body["transcript"]


async def test_the_panorama_opening_is_kept_as_her_note_then_the_line_it_opened_with(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    patch_agent,
) -> None:
    patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    session_id = await _open_panorama(client)

    session = await get_session(db_session, session_id)
    assert [(m["role"], m["text"]) for m in session.messages] == [
        ("room", NOTE_PT),
        ("guide", "Vamos conhecer o livro."),
    ], "a abertura ficava guardada sem a nota que o Facilitador leu antes de falar"


async def test_a_panorama_opening_that_falls_to_a_fixed_line_still_keeps_her_note(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    patch_agent,
) -> None:
    patch_agent(FakeAgent({"verdict": "regenerate", "issues": [{"problem": "spoiler"}]}))

    session_id = await _open_panorama(client)

    session = await get_session(db_session, session_id)
    assert [m["role"] for m in session.messages] == ["room", "guide"]
    assert session.messages[0]["text"] == NOTE_PT, (
        "uma abertura que caía na fala fixa perdia a nota e o próximo turno começava sem ela"
    )
    assert session.messages[1]["outcome"] == "fail_safe"


async def test_the_third_turn_still_carries_the_sessions_first_exchange(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, patch_agent
) -> None:
    """Every call gets the whole conversation — no window drops the session's opening.

    A six-turn window would still hold this session's first exchange by the third turn, so
    it is asserted directly rather than merely counted: her note and the opening's own line
    have to be the oldest entries the third call sees, word for word.
    """
    from app.api.internalization_room import sessions as sessions_api

    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    heard = ["pergunta dois", "pergunta três"]

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=heard.pop(0))

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    session_id = await _open_panorama(client)
    await _speak(client, session_id, "q2.m4a")
    await _speak(client, session_id, "q3.m4a")

    assert agent.histories[0] == [], "a abertura não tem conversa nenhuma atrás dela"
    assert agent.histories[2] == [
        {"role": "user", "text": NOTE_PT},
        {"role": "assistant", "text": "Vamos conhecer o livro."},
        {"role": "user", "text": "pergunta dois"},
        {"role": "assistant", "text": "Vamos conhecer o livro."},
    ], "o terceiro turno perdeu a primeira troca da sessão — isso é o que uma janela faria"


async def test_a_slow_panorama_turn_is_not_cut_short(patch_agent) -> None:
    """No prazo por chamada: a room speaking to a slow model still gets its answer.

    Nothing in the panorama's call path wraps the Guide or the Validator in a deadline
    of its own — the doctrine's own numbers (10-56 s, median 27 s per turn) only make
    sense with none. Each of the two real calls is made to take real time here; a
    regression that wrapped either in a short `asyncio.wait_for` would cut this turn
    to a fail-safe well before both had run.
    """
    import asyncio
    import time

    class _SlowAgent(FakeAgent):
        async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            await asyncio.sleep(0.3)
            return await super().__call__(
                system_prompt=system_prompt, user_content=user_content, **kwargs
            )

    agent = patch_agent(_SlowAgent({"verdict": "pass", "issues": []}))

    started = time.monotonic()
    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="me contem mais",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )
    elapsed = time.monotonic() - started

    assert elapsed >= 0.6, (
        "as duas chamadas (Guia e Validador) têm de esperar de verdade, sem atalho"
    )
    assert outcome.used_fail_safe is False
    assert outcome.speech == agent.draft


@pytest.mark.parametrize("workflow", ["deploy.yml", "deploy-staging.yml"])
def test_the_only_ceiling_on_a_panorama_turn_is_the_routes_own_300_seconds(workflow: str) -> None:
    """The doctrine's 300 s is Cloud Run's, not this app's — pinned where it actually lives.

    Nothing in the turn's own code imposes a deadline (the sibling test above pins that);
    the route accepts up to what the deployed service is told to accept. That number is
    `--timeout=300` on the `gcloud run deploy` command each workflow runs, and a change to
    either is exactly what would move this ceiling without a line of `app/` ever noticing.
    """
    import yaml

    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / workflow
    steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    deploy_step = next(step for step in steps if step["name"] == "Deploy Backend")

    assert "--timeout=300" in deploy_step["run"].split()


async def test_a_panorama_never_reports_the_session_done_no_matter_how_many_turns(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A panorama never 'completes' — not at the opening, not five turns in."""
    from app.api.internalization_room import sessions as sessions_api

    async def _panorama(*, transcript: str, **_: Any) -> TurnOutcome:
        return TurnOutcome(speech="resposta.", transcript=transcript)

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text="mais uma pergunta")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV", "language": "pt"}
    )
    session_id = created.json()["session_id"]
    opening = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY}
    )

    turns = [opening] + [await _speak(client, session_id, f"q{n}.m4a") for n in range(2, 6)]

    assert [turn.json()["done"] for turn in turns] == [False] * 5, (
        "nenhum turno do panorama pode dizer que a sessão terminou, em turno nenhum"
    )


async def test_a_direct_question_about_who_ruth_marries_is_answered_from_a_prompt_that_defers(
    patch_agent,
) -> None:
    """Not a test of what a model says — of the prompt and material that make deferring the
    only honest answer.

    The panorama's own hard rule ("Keep the book's secrets") and the book's withholdings
    (Ruth's marriage pairing held to 4:10, the famine and the deaths left agentless) are
    both rendered straight into the system prompt every turn is drafted against. Asserting a
    recorded model reply here would test a fixture, not the room; this asserts the ingredients
    a compliant answer has no way around.
    """
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="com quem Rute vai se casar?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    speaker_system = agent.systems[0]
    assert "Keep the book's secrets" in speaker_system
    assert "every withholding is still ahead of them" in speaker_system
    assert "never with a spoiler" in speaker_system
    assert "must not infer the pairing here" in speaker_system, (
        "o par Rute-Malom, só revelado em 4:10, tem de seguir retido no material da fala"
    )
    assert "must not assign divine causation" in speaker_system, (
        "a fome e as mortes não podem ser atribuídas a Deus no material que sustenta a fala"
    )


async def test_a_panorama_take_the_ear_heard_as_the_mother_tongue_reaches_the_guide_as_her_note(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    patch_agent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    note = (
        "[A equipe falou na língua materna por cerca de 116 segundos; sem transcrição — nenhuma "
        "palavra chegou até você.]"
    )

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(bridge_language="pt", wordless_long_take=True, take_ms=116_000)

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    session_id = await _open_panorama(client)
    answered = await _speak(client, session_id, "ensaio.m4a")

    assert agent.asked[-2] == note, "a rota do panorama não passava ao motor o que o ouvido decidiu"
    assert answered.json()["transcript"] == ""
    session = await get_session(db_session, session_id)
    assert (session.messages[-2]["role"], session.messages[-2]["text"]) == ("room", note)


@pytest.mark.parametrize(
    ("heard", "line"),
    [
        (
            HeardSpeech(
                text="Kalivono", bridge_language="pt", language_code="grn", language_probability=0.5
            ),
            "heard=grn p=0.5 decision=mother tongue reason=recognizer heard grn, session speaks pt",
        ),
        (
            HeardSpeech(
                text="Entendemos.",
                bridge_language="pt",
                language_code="por",
                language_probability=0.3,
            ),
            "heard=por p=0.3 decision=mother tongue "
            "reason=recognizer unsure it was pt (p=0.30 < 0.35)",
        ),
        (
            HeardSpeech(bridge_language="pt", wordless_long_take=True, take_ms=115_700),
            "heard=None p=None decision=mother tongue "
            "reason=no words in a long take (116 s >= 20 s)",
        ),
        (
            HeardSpeech(
                text="Entendemos.",
                bridge_language="pt",
                language_code="por",
                language_probability=0.9,
            ),
            "heard=por p=0.9 decision=words reason=",
        ),
        (HeardSpeech(bridge_language="pt"), "heard=None p=None decision=inaudible reason="),
    ],
)
async def test_every_take_leaves_one_line_saying_why_the_ear_decided_as_it_did(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    heard: HeardSpeech,
    line: str,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return heard

    async def _panorama(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech="Vamos conhecer o livro.", transcript="")

    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    session_id = await _open_panorama(client)

    with caplog.at_level("INFO"):
        await _speak(client, session_id, "ensaio.m4a")

    assert [r.getMessage() for r in caplog.records if "[hearing]" in r.getMessage()] == [
        f"[hearing] session={session_id} {line}"
    ], "nada no log dizia por que um turno virou palavras, língua materna ou a linha D"
