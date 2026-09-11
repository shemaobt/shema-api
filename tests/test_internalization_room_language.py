"""The room answers in the language the app asked for, and keeps answering in it.

Every spoken thing a team hears is made on this side — the wheel's names, the Guide's turns,
the back-translation prose, the synthesis — so the language was the server's to decide and it
decided once, at deploy time, for everybody. The tablet knows which language the people in
front of it set it to, so the tablet names it and this side obeys.

It is named on the session and not on each request. A per-request language would move under a
team because somebody opened the phone settings mid-passage, and half a passage in each
language is worse than the whole of it in either.
"""

import json
import re
import sys
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES, floor, normalize
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"

#: A letter no English sentence in this codebase has ever needed. Most of the original
#: Portuguese literals this branch removed carried at least one, so this catches a
#: reintroduced literal without having to name it in advance — but not all of them did
#: ("Julgue a resposta rascunhada.", "Fale este turno.", "Classifique esta troca." have none),
#: so the exact-value tests below carry those three; this class is one layer, not the whole
#: guard. It does not, and must not, run against `prompts/*.md`: those carry Portuguese on
#: purpose, reviewed by Marcia, not by a grep (ENG-822, item 7).
_PORTUGUESE_MARKER = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")


@pytest.fixture()
async def spoken() -> list[dict[str, Any]]:
    return []


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, spoken: list[dict[str, Any]]
):
    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _panorama(**kwargs: Any) -> TurnOutcome:
        spoken.append(kwargs)
        return TurnOutcome(speech="Bem-vindos.", transcript="")

    async def _speech(text: str, **kwargs: Any) -> tuple[SynthesizedSpeech, bool]:
        spoken.append({"synthesized": text, **kwargs})
        return SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/{get_settings().internalization_room_voice_id}/m/f/{abs(hash(text))}.mp3",
        ), False

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(voice_api, "synthesize_facilitator_speech", _speech)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


async def _open(client: httpx.AsyncClient, **body: Any) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV", **body}
    )


async def test_a_session_opened_naming_a_language_answers_in_it(
    client: httpx.AsyncClient, spoken: list[dict[str, Any]]
) -> None:
    created = await _open(client, language="pt")
    assert created.status_code == 200, created.text[:200]

    await client.post(
        f"{PREFIX}/sessions/{created.json()['session_id']}/turns", headers={"X-Room-Key": KEY}
    )

    turn = next(call for call in spoken if "session_language" in call)
    assert turn["language_code"] == "pt"
    assert turn["session_language"] == "Brazilian Portuguese"


async def test_a_session_that_names_no_language_gets_english(
    client: httpx.AsyncClient, spoken: list[dict[str, Any]]
) -> None:
    """O piso é o inglês: um chamador que não nomeia idioma não pode cair no português."""
    created = await _open(client)

    await client.post(
        f"{PREFIX}/sessions/{created.json()['session_id']}/turns", headers={"X-Room-Key": KEY}
    )

    turn = next(call for call in spoken if "session_language" in call)
    assert turn["language_code"] == FLOOR
    assert turn["session_language"] == "English"


async def test_the_language_is_fixed_at_the_open_and_no_later_request_moves_it(
    client: httpx.AsyncClient, spoken: list[dict[str, Any]]
) -> None:
    """Uma equipe ouvindo metade da passagem numa língua e metade noutra é pior que qualquer
    uma das duas — por isso a escolha vive na sessão e não no pedido."""
    created = await _open(client, language="pt")
    session_id = created.json()["session_id"]

    await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY, "Accept-Language": "en", "X-Room-Language": "en"},
    )
    standing = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})

    assert standing.json()["language"] == "pt"
    assert all(call["language_code"] == "pt" for call in spoken if "language_code" in call), (
        "um cabeçalho de idioma mudou o turno de uma sessão que já tinha escolhido"
    )


async def test_the_session_says_back_which_language_it_is_being_run_in(
    client: httpx.AsyncClient,
) -> None:
    assert (await _open(client, language="pt")).json()["language"] == "pt"
    assert (await _open(client)).json()["language"] == FLOOR


async def test_a_regional_tag_finds_its_own_language(client: httpx.AsyncClient) -> None:
    assert (await _open(client, language="pt-BR")).json()["language"] == "pt"
    assert (await _open(client, language="PT-br")).json()["language"] == "pt"


async def test_a_language_the_room_does_not_speak_is_refused_rather_than_answered(
    client: httpx.AsyncClient,
) -> None:
    """Responder em inglês a quem pediu francês é uma resposta errada que ninguém detecta."""
    refused = await _open(client, language="fr")

    assert refused.status_code == 400, refused.text[:200]


@pytest.mark.parametrize("unspoken", ["fr", "es", "es-419"])
async def test_a_language_the_room_does_not_speak_is_refused_at_the_wheel(
    client: httpx.AsyncClient, unspoken: str
) -> None:
    refused = await client.get(
        f"{PREFIX}/books/Ruth/passages?language={unspoken}", headers={"X-Room-Key": KEY}
    )

    assert refused.status_code == 400, refused.text[:200]


async def test_the_service_refuses_a_language_the_room_does_not_speak(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValidationError):
        await create_session(db_session, pericope="OV", language="ja")


async def test_the_floor_setting_reaches_the_session_and_the_wheel_and_not_only_the_voice(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Segurar uma frota em português enquanto o app que nomeia idioma ainda não saiu é a
    razão de o piso ser ajustável. Um piso que só o sintetizador honrasse deixaria as sessões
    e a roda respondendo inglês por baixo dele — exatamente a falha que ele existe para evitar.
    """
    monkeypatch.setattr(
        get_settings(), "internalization_room_default_language", "pt", raising=False
    )

    opened = await create_session(db_session, pericope="OV")

    assert opened.language == "pt"
    assert floor() == "pt"


def test_a_floor_the_room_cannot_speak_falls_back_instead_of_reaching_a_team() -> None:
    """Um erro de digitação num ambiente não pode reivindicar um idioma que a sala não fala."""
    settings = get_settings()
    original = settings.internalization_room_default_language
    try:
        object.__setattr__(settings, "internalization_room_default_language", "kl")
        assert floor() == FLOOR
    finally:
        object.__setattr__(settings, "internalization_room_default_language", original)


async def test_the_voice_route_reads_a_regional_tag_the_way_the_session_does(
    client: httpx.AsyncClient, spoken: list[dict[str, Any]]
) -> None:
    """Três portas recebem idioma; esta era a única que pulava o módulo escrito para isso.

    A afirmação é sobre a tag que chega embaixo, não sobre o status: as vozes são indexadas
    por idioma primário, então `pt-BR` cru não acha voz nenhuma e a rota respondia 400 — vindo
    do mesmo locale de tablet que `POST /sessions` aceita e guarda como `pt`.
    """
    said = await client.post(
        f"{PREFIX}/voice/speak",
        headers={"X-Room-Key": KEY},
        json={"text": "Bem-vindos.", "language": "pt-BR"},
    )

    assert said.status_code == 200, said.text[:200]
    assert [call["language"] for call in spoken if "synthesized" in call] == ["pt"]


async def test_the_voice_route_refuses_a_language_the_room_does_not_speak(
    client: httpx.AsyncClient,
) -> None:
    refused = await client.post(
        f"{PREFIX}/voice/speak",
        headers={"X-Room-Key": KEY},
        json={"text": "Bem-vindos.", "language": "fr"},
    )

    assert refused.status_code == 400, refused.text[:200]


def test_a_locale_the_room_does_not_speak_is_not_quietly_narrowed_to_one_it_does() -> None:
    assert normalize("pt-BR") == "pt"
    assert normalize("PT") == "pt"
    assert normalize("es-419") is None
    assert normalize("ja") is None
    assert normalize("fr-CA") is None
    assert normalize(None) is None


def test_the_injected_language_name_carries_marcias_grain_and_no_third_entry() -> None:
    """Spanish is dead (ticket ENG-822, question 10) — a pilot that only speaks pt/en must
    never find a third name to inject, and the Portuguese one must carry the grain her
    rebuilt prompts already use, not the bare autonym."""
    assert LANGUAGE_NAMES == {"en": "English", "pt": "Brazilian Portuguese"}


def test_no_portuguese_reaches_the_opening_and_validator_instructions() -> None:
    """These four are sent to the model on every session, in every language — unlike the
    prompt files, nothing here is templated per {{SESSION_LANGUAGE}}, so a Portuguese literal
    in any of them is Portuguese an English session hears too (ENG-822, item 3)."""
    from app.services.internalization_room.turn_instructions import (
        NOT_THIS_TURN,
        OPENING_INSTRUCTION,
        OPENING_MOVEMENT_INSTRUCTION,
        VALIDATOR_USER_MESSAGE,
    )

    for value in (
        OPENING_INSTRUCTION,
        OPENING_MOVEMENT_INSTRUCTION,
        NOT_THIS_TURN,
        VALIDATOR_USER_MESSAGE,
    ):
        assert not _PORTUGUESE_MARKER.search(value), value


def test_speak_this_turn_is_english_on_every_session() -> None:
    """SPEAK_THIS_TURN is the filler user message a verdict turn sends when it has neither an
    opening nor a team utterance to answer — a backend-composed instruction exactly like
    OPENING_INSTRUCTION above, just missed by the sweep that translated its siblings in this
    same file. A `pt` session must not see "Fale este turno."."""
    from app.services.internalization_room.turn_instructions import SPEAK_THIS_TURN

    assert SPEAK_THIS_TURN == "Speak this turn."


def test_the_validator_user_message_matches_the_model_marcia_authored() -> None:
    from app.services.internalization_room.turn_instructions import VALIDATOR_USER_MESSAGE

    assert (
        VALIDATOR_USER_MESSAGE == "Validate the drafted response now. Return only the JSON object."
    )


async def test_the_redraft_note_heading_the_guide_reads_is_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_draft` appends the redraft note under its own heading — a section title exactly like
    the EQUIPE/FACILITADOR labels item 3 targets, just added back the same day (c3ee0e2) it
    removed those. Never Portuguese, whatever the session speaks (ENG-822, item 3)."""
    from app.services.internalization_room.validated_turn import _draft

    module = sys.modules["app.services.internalization_room.run_turn"]
    captured: dict[str, str] = {}

    async def agent(*, user_content: str, **kwargs: Any) -> str:
        captured["user_content"] = user_content
        return "fala"

    monkeypatch.setattr(module, "call_agent", agent)

    await _draft(
        guide_prompt="system",
        conversation=[],
        utterance="algo",
        redraft_note="Redo it.",
        settings=get_settings(),
    )

    assert "## Rewrite note" in captured["user_content"]
    assert "## Nota de reescrita" not in captured["user_content"]


async def test_the_classifier_composes_english_when_nobody_has_spoken_and_nothing_is_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """classify_coverage.py builds three backend-composed strings that used to be Portuguese
    regardless of session language: the no-utterance placeholder, the "nothing pending" block,
    and its own user message. ENG-822, item 4 — the classifier's version of item 3's treatment.
    """
    from app.services.internalization_room.classify_coverage import classify_coverage
    from app.services.internalization_room.coverage import initial_state, merge
    from app.services.internalization_room.render import render as real_render

    P = "P01"
    fully_engaged = merge(initial_state(P), pericope_num=P, engaged=list(initial_state(P).keys()))
    assert fully_engaged  # a real pericope, or COVERAGE_ELEMENTS below proves nothing

    module = sys.modules["app.services.internalization_room.classify_coverage"]
    captured: dict[str, str] = {}

    def capturing_render(template: str, **values: str) -> str:
        captured.update(values)
        return real_render(template, **values)

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        captured["user_content"] = user_content
        return json.dumps({"decisions": []})

    monkeypatch.setattr(module, "render", capturing_render)
    monkeypatch.setattr(module, "call_agent", agent)

    await classify_coverage(
        coverage_state=fully_engaged,
        team_utterance="",
        guide_response="the Guide asked",
        classifier_prompt=(
            "{{SESSION_LANGUAGE}} {{SCENES}} {{COVERAGE_ELEMENTS}} {{TEAM_UTTERANCE}} "
            "{{GUIDE_RESPONSE}}"
        ),
        pericope_num=P,
        session_language="English",
    )

    assert captured["TEAM_UTTERANCE"] == "(the team has not spoken yet)"
    assert captured["COVERAGE_ELEMENTS"] == "(no elements pending)"
    assert captured["user_content"] == "Classify this exchange now. Return only the JSON object."


def test_the_guides_coverage_status_block_is_english_in_both_branches() -> None:
    """coverage_status_block feeds the Guide's COVERAGE_STATUS slot directly — a heading and a
    "nothing left" placeholder, neither threaded through the session's language at all
    (ENG-822, item 3/4's "same treatment", the run_turn.py successor of the old status block)."""
    from app.services.internalization_room.coverage import initial_state, merge
    from app.services.internalization_room.prompt_blocks import coverage_status_block

    P = "P01"
    fully_engaged = merge(initial_state(P), pericope_num=P, engaged=list(initial_state(P).keys()))

    assert coverage_status_block(fully_engaged, P) == (
        "REMAINING: (none — every element has been worked by the team)"
    )
    assert coverage_status_block(initial_state(P), P).startswith(
        "REMAINING (not yet worked by the team, in their own words):"
    )
