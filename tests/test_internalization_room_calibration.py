"""The one-shot oral calibration and the explicit-only mode switch.

The parser recognizes only clear task-shaped preferences; anything unclear falls to the
modest adaptive track at the one-shot boundary and the Voice never re-offers the menu.
"""

import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.calibration import (
    BridgeMode,
    bridge_calibration_acknowledgement,
    bridge_calibration_question,
    is_selected_bridge_mode,
    resolve_bridge_mode_for_turn,
    resolve_initial_calibration,
    resolve_one_shot_calibration,
)
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
PANORAMA = "OV"
THE_TEAM_ANSWERS = "Uma pergunta curta de cada vez."
PASSAGE = "P03"
#: The label the Validator reads to tell app-owned state from what the team said.
APP_OWNED = "[APP-OWNED SESSION STATE — not team speech]"

#: The method question as the ticket quotes it, in the three languages the room claims.
#: Read from the ticket rather than from `bridge_calibration_question`, which this branch
#: deletes: an expectation taken from the code under test agrees with it by construction.
THE_METHOD_QUESTION = {
    "pt": (
        "Quando trabalharmos as passagens, qual jeito fica melhor para vocês: "
        "contar naturalmente em português ou receber uma pergunta curta de cada vez?"
    ),
    "en": (
        "When we work through the passages, which suits you better: "
        "telling it back in your own words, or one short question at a time?"
    ),
    "es": (
        "Cuando trabajemos los pasajes, ¿qué les queda mejor: "
        "contarlo con sus propias palabras, o recibir una pregunta corta a la vez?"
    ),
}

GUIDE_OPENING = "Bem-vindos. Vamos conhecer o livro inteiro antes de entrar nele."
GUIDE_REPLY = "O livro começa numa fome, e uma família sai de casa por causa dela."


@pytest.fixture()
async def spoken(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """A room whose every synthesized line is kept, so a test can read what was said.

    The method question is appended in the router, after the panorama turn has already
    returned, so no service seam can see it. What reaches the voice is the whole of it.

    `heard` is the other half: what the Guide was handed. A turn the app answers by
    itself never reaches the Guide at all, and an empty `heard` is how that shows.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    said: list[str] = []
    heard: list[str] = []

    async def _panorama(**handed: Any) -> TurnOutcome:
        heard.append(str(handed["transcript"]))
        return TurnOutcome(
            speech=GUIDE_OPENING if handed["opening"] else GUIDE_REPLY,
            transcript=str(handed["transcript"]),
            used_fail_safe=False,
        )

    async def _heard_speech(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=THE_TEAM_ANSWERS, language_code="pt", transcript_confidence=0.99)

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        said.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _nothing(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "prepare_opening", _nothing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _nothing)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard_speech)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, said, heard


async def _open_cold(client: httpx.AsyncClient, *, pericope: str, language: str) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": pericope, "language": language},
    )
    assert created.status_code == 200, created.text[:200]
    return str(created.json()["session_id"])


async def test_the_opening_is_the_guides_own_words_from_first_syllable_to_last(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, said, _ = spoken
    session_id = await _open_cold(client, pericope=PANORAMA, language="pt")

    opened = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:200]
    assert said == [GUIDE_OPENING], (
        "a sala grampeava a pergunta de método no fim da abertura e mandava o texto "
        f"emendado para a voz — a equipe ouvia {said}"
    )


def test_a_clear_full_retell_preference_is_explicit() -> None:
    resolved = resolve_initial_calibration("Conseguimos contar a história em português.")
    assert resolved.mode is BridgeMode.FULL_RETELL
    assert resolved.explicit


def test_a_short_questions_preference_selects_guided() -> None:
    resolved = resolve_initial_calibration("Preferimos perguntas curtas, uma de cada vez.")
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert resolved.explicit


def test_naming_the_second_option_selects_guided() -> None:
    assert resolve_initial_calibration("a segunda").mode is BridgeMode.GUIDED_MICROCHECKS


def test_uncertainty_followed_by_a_trial_selects_adaptive() -> None:
    resolved = resolve_initial_calibration("Não sabemos, vamos tentar.")
    assert resolved.mode is BridgeMode.ADAPTIVE


def test_both_preferences_in_one_answer_are_adaptive() -> None:
    resolved = resolve_initial_calibration(
        "Podemos contar a história inteira, mas também queremos perguntas curtas."
    )
    assert resolved.mode is BridgeMode.ADAPTIVE


def test_a_negated_capability_is_not_the_positive_choice() -> None:
    resolved = resolve_initial_calibration("Não conseguimos contar tudo em português.")
    assert resolved.mode is BridgeMode.CALIBRATION_PENDING


def test_negating_one_option_still_selects_the_other() -> None:
    resolved = resolve_initial_calibration(
        "Não conseguimos contar a história toda; preferimos perguntas curtas."
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS


def test_a_question_back_resolves_nothing() -> None:
    resolved = resolve_initial_calibration("O que acontece se a gente errar?")
    assert resolved.mode is BridgeMode.CALIBRATION_PENDING
    assert not resolved.explicit


def test_the_one_shot_boundary_converts_silence_to_adaptive() -> None:
    resolved = resolve_one_shot_calibration("")
    assert resolved.mode is BridgeMode.ADAPTIVE
    assert not resolved.explicit


def test_the_one_shot_boundary_converts_an_unclear_answer_to_adaptive() -> None:
    assert resolve_one_shot_calibration("hmm, sei lá").mode is BridgeMode.ADAPTIVE


def test_the_one_shot_boundary_keeps_an_explicit_answer() -> None:
    resolved = resolve_one_shot_calibration("queremos contar tudo")
    assert resolved.mode is BridgeMode.FULL_RETELL
    assert resolved.explicit


def test_story_speech_never_switches_an_established_mode() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.GUIDED_MICROCHECKS, "Rute voltou para contar tudo a Noemi"
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert not resolved.explicit


def test_a_bare_sim_never_switches_the_mode() -> None:
    resolved = resolve_bridge_mode_for_turn(BridgeMode.FULL_RETELL, "sim")
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_an_explicit_request_switches_to_guided() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.FULL_RETELL, "preferimos perguntas curtas agora"
    )
    assert resolved.mode is BridgeMode.GUIDED_MICROCHECKS
    assert resolved.explicit


def test_an_explicit_request_switches_back_to_full_retell() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.GUIDED_MICROCHECKS, "queremos contar a história inteira"
    )
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_a_question_about_switching_does_not_switch() -> None:
    resolved = resolve_bridge_mode_for_turn(
        BridgeMode.FULL_RETELL, "Devemos mudar para perguntas curtas?"
    )
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_switching_never_infers_adaptive() -> None:
    resolved = resolve_bridge_mode_for_turn(BridgeMode.FULL_RETELL, "tanto faz, sei lá")
    assert resolved.mode is BridgeMode.FULL_RETELL


def test_only_selected_modes_pass_the_intake_boundary() -> None:
    assert is_selected_bridge_mode("full_retell")
    assert is_selected_bridge_mode("guided_microchecks")
    assert is_selected_bridge_mode("adaptive")
    assert not is_selected_bridge_mode("calibration_pending")
    assert not is_selected_bridge_mode("fluente")
    assert not is_selected_bridge_mode(None)


def test_the_menu_offers_methods_not_ability_labels() -> None:
    lowered = bridge_calibration_question("pt").lower()
    for label in ("nível", "básico", "avançado", "fraco", "fluente"):
        assert label not in lowered


def test_every_acknowledgement_is_fixed_and_moves_to_the_panorama() -> None:
    for mode in (BridgeMode.FULL_RETELL, BridgeMode.GUIDED_MICROCHECKS, BridgeMode.ADAPTIVE):
        line = bridge_calibration_acknowledgement(mode, "pt")
        assert line.startswith("Certo.")
        assert "panorama do livro" in line


def test_the_method_choice_is_asked_and_answered_in_every_language_the_room_claims() -> None:
    asked = {spoken: bridge_calibration_question(spoken) for spoken in ROOM_LANGUAGES}

    assert len(set(asked.values())) == len(ROOM_LANGUAGES), (
        "um idioma reivindicado caiu na pergunta de outro: a equipe escolhe o método "
        f"ouvindo uma frase que não é da língua da sessão — {asked}"
    )
    for spoken in ROOM_LANGUAGES:
        said = {
            bridge_calibration_acknowledgement(mode, spoken)
            for mode in (
                BridgeMode.FULL_RETELL,
                BridgeMode.GUIDED_MICROCHECKS,
                BridgeMode.ADAPTIVE,
            )
        }
        assert len(said) == 3, (
            f"as três respostas caíram para a mesma frase em {spoken!r}: a equipe escolhe "
            "um método e ouve de volta a confirmação de outro"
        )


async def test_the_teams_first_utterance_is_a_turn_like_any_other(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, said, heard = spoken
    session_id = await _open_cold(client, pericope=PANORAMA, language="pt")
    await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text[:200]
    assert heard == ["", THE_TEAM_ANSWERS], (
        "a resposta da equipe era lida por um parser de regex e o Guia nem era chamado — "
        f"chegou nele {heard}"
    )
    assert said[-1] == GUIDE_REPLY, (
        "a sala respondia com uma das nove falas fixas de reconhecimento, escolhida pelo "
        f"modo que o parser tinha acabado de decidir — a equipe ouviu {said[-1]!r}"
    )


async def test_a_mode_named_by_the_tablet_is_taken_in_and_never_said_back(
    spoken: tuple[httpx.AsyncClient, list[str], list[str]],
) -> None:
    client, _, _ = spoken
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PANORAMA, "language": "pt", "bridge_mode": "guided_microchecks"},
    )

    assert created.status_code == 200, (
        "o app do piloto ainda manda o modo no createSession, e recusar a chave deixa a "
        f"equipe sem sessão nenhuma — veio {created.status_code}: {created.text[:200]}"
    )
    session_id = created.json()["session_id"]
    turned = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert "bridge_mode" not in created.json(), (
        "a sala devolvia o modo ao tablet, que o guardava e o mandava de volta na sessão "
        f"seguinte — era assim que um modo atravessava sessões: {created.json()}"
    )
    assert "bridge_mode" not in turned.json(), (
        f"o turno também dizia o modo de volta, a cada turno: {turned.json()}"
    )


class _Recording:
    """A Guide and a Validator that keep the whole of what they were handed."""

    def __init__(self) -> None:
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(f"{system_prompt}\n\n{user_content}")
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos ficar nesta cena. O que vocês contariam?"


async def test_the_validator_still_reads_the_evidence_as_the_apps_and_not_as_the_teams(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.internalization_room.live_turn import run_comprehension_turn
    from app.services.internalization_room.sessions import append_exchange, create_session

    models = _Recording()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", models
    )
    session = await create_session(db_session, language="pt", pericope=PASSAGE)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )

    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="A fome chegou e eles partiram."),
        opening=False,
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        settings=get_settings(),
    )

    handed = models.validator[0]
    assert APP_OWNED in handed, (
        "a etiqueta vinha pendurada na linha do modo e era a única coisa dizendo ao "
        "Validador que aquele bloco é do app; sem ela a evidência de compreensão chega "
        "como se a equipe tivesse falado aquilo"
    )
    assert "BRIDGE MODE" not in handed, (
        f"o modo continuava viajando dentro do estado do app entregue ao Validador: {handed[-400:]}"
    )
