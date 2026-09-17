"""Three placeholders reach the model in the session's own language, not always Portuguese.

The bug (ENG-729): each of the three stands in for "the team has not spoken yet" and was
hardcoded Portuguese, so an `en` or `es` session shipped a Portuguese fragment inside an
otherwise correctly-languaged prompt. Sibling of ENG-714, which did the same for the redraft
note — and, like ENG-714's own test file, every site here is exercised over the full
`ROOM_LANGUAGES` tuple: a claimed language with no text written for it would otherwise fall
to the English floor with nothing here going red.

Every case observes only what the model would receive — the rendered system prompt captured
at the `call_agent` boundary — never a dict, a constant name, or a helper's return value. The
expected sentences below come from the Linear issue (already decided by João), not from the
production dicts they happen to match.
"""

import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import analyse_telling_back
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.languages import LANGUAGE_NAMES, ROOM_LANGUAGES
from app.services.internalization_room.run_turn import run_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
P = "P03"

_EXPECTED_VALIDATOR_OPENING = {
    "pt": "(a equipe ainda não falou — abertura da sessão)",
    "en": "(the team has not spoken yet — session opening)",
    "es": "(el equipo aún no ha hablado — apertura de la sesión)",
}

_EXPECTED_CLASSIFIER_NO_UTTERANCE = {
    "pt": "(a equipe ainda não falou)",
    "en": "(the team has not spoken yet)",
    "es": "(el equipo aún no ha hablado)",
}

_EXPECTED_NOTHING_TOLD_BACK = {
    "pt": "(a equipe ainda não contou nada de volta)",
    "en": "(the team has not told anything back yet)",
    "es": "(el equipo aún no ha contado nada de vuelta)",
}


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _patch_validator_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Let the Guide draft through, then record the system prompt the Validator is judged by."""
    module = sys.modules["app.services.internalization_room.run_turn"]
    captured: dict[str, str] = {}

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            captured["system"] = system_prompt
            return json.dumps({"verdict": "pass", "issues": []})
        return "fala"

    monkeypatch.setattr(module, "call_agent", agent)
    return captured


def _patch_classifier_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    module = sys.modules["app.services.internalization_room.classify_coverage"]
    captured: dict[str, str] = {}

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        captured["system"] = system_prompt
        return json.dumps({"decisions": []})

    monkeypatch.setattr(module, "call_agent", agent)
    return captured


def _patch_analyst_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    module = sys.modules["app.services.internalization_room.back_translation"]
    captured: dict[str, str] = {}

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        captured["system"] = system_prompt
        return json.dumps({"findings": []})

    monkeypatch.setattr(module, "call_agent", agent)
    return captured


@pytest.mark.asyncio
@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
async def test_the_validator_opens_the_session_in_its_own_language(
    monkeypatch: pytest.MonkeyPatch, language_code: str
) -> None:
    """The negative check names the other two languages' exact sentences, not the substring
    "ainda não": with `messages=[]` the Validator also renders `recent_conversation_block`'s
    own Portuguese fallback ("(início da sessão — ainda não houve troca)"), which is a
    separate, out-of-scope placeholder (run_turn.py:190) this ticket does not touch.
    """
    captured = _patch_validator_capture(monkeypatch)

    await run_turn(
        session_language=LANGUAGE_NAMES[language_code],
        language_code=language_code,
        transcript="",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        opening=True,
        settings=_settings(),
    )

    system = captured["system"]
    assert _EXPECTED_VALIDATOR_OPENING[language_code] in system
    for other, sentence in _EXPECTED_VALIDATOR_OPENING.items():
        if other != language_code:
            assert sentence not in system


@pytest.mark.asyncio
@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
async def test_the_classifier_sees_the_no_utterance_placeholder_in_the_sessions_own_language(
    monkeypatch: pytest.MonkeyPatch, language_code: str
) -> None:
    captured = _patch_classifier_capture(monkeypatch)

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="",
        guide_response="o Guia perguntou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        session_language=LANGUAGE_NAMES[language_code],
        language_code=language_code,
        settings=_settings(),
    )

    system = captured["system"]
    assert _EXPECTED_CLASSIFIER_NO_UTTERANCE[language_code] in system
    for other, sentence in _EXPECTED_CLASSIFIER_NO_UTTERANCE.items():
        if other != language_code:
            assert sentence not in system


@pytest.mark.asyncio
@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
async def test_the_analyst_sees_the_nothing_told_back_placeholder_in_the_sessions_own_language(
    monkeypatch: pytest.MonkeyPatch, language_code: str
) -> None:
    captured = _patch_analyst_capture(monkeypatch)

    await analyse_telling_back(
        segments=[],
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        session_language=LANGUAGE_NAMES[language_code],
        language_code=language_code,
        settings=_settings(),
    )

    system = captured["system"]
    assert _EXPECTED_NOTHING_TOLD_BACK[language_code] in system
    for other, sentence in _EXPECTED_NOTHING_TOLD_BACK.items():
        if other != language_code:
            assert sentence not in system


@pytest.mark.asyncio
async def test_a_language_the_room_does_not_claim_gets_the_english_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_analyst_capture(monkeypatch)

    await analyse_telling_back(
        segments=[],
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        session_language="French",
        language_code="fr",
        settings=_settings(),
    )

    system = captured["system"]
    assert _EXPECTED_NOTHING_TOLD_BACK["en"] in system
    assert _EXPECTED_NOTHING_TOLD_BACK["pt"] not in system
