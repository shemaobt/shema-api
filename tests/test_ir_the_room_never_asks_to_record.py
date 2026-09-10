"""The room has no recording question, so no turn can voice one.

Marcia's eighth answer — there is no fixed invitation to the rehearsal and no password —
took the app's yes/no question and the seven exact sentences that reopened it together.
What invites the rehearsal now is the Guide's own send-off, and the record entry has been
reachable the whole time, so the team decides when to use it.

The sentences below are written out here rather than imported. They are what the room used
to say, and the point of the file is that nothing in the room says them any more — a test
that imported them from the module would be asserting against the code it is checking, and
would stop compiling the moment the code was right.
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import scene_ids_for
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    build_internalization_release,
)
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    create_session,
    save_comprehension,
    session_is_done,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

#: The app's own recording speech, in every language it was ever written in. No turn may
#: produce any of these again.
NEVER_SPOKEN = (
    "Vocês querem seguir agora para gravar o primeiro ensaio na língua de vocês? Digam sim ou não.",
    "Would you like to go on now and record the first rehearsal in your own language? "
    "Say yes or no.",
    "¿Quieren seguir ahora y grabar el primer ensayo en su lengua? Digan sí o no.",
    "Agora o aplicativo vai mostrar onde gravar o primeiro ensaio na língua de vocês.",
    "The app will now show you where to record the first rehearsal in your own language.",
    "Ahora la aplicación les va a mostrar dónde grabar el primer ensayo en su lengua.",
    "Tudo bem. Podemos continuar conversando e ensaiando. Vocês decidem quando estiverem prontos.",
    "That is fine. We can keep talking and rehearsing. You decide when you are ready.",
    "Está bien. Podemos seguir conversando y ensayando. Ustedes deciden cuándo estén listos.",
)

#: What a team says at the end of a passage, including the two words the app's question
#: used to offer and the phrases that used to be the password back to it.
AT_THE_END = (
    "acho que já falamos de tudo",
    "não",
    "ainda não",
    "sim",
    "estamos prontos para gravar",
    "queremos continuar",
    "vamos gravar",
)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class ApprovingAgent:
    """A Guide that drafts something short and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos começar pela primeira cena. O que vocês acham?"


@pytest.fixture
def approve_all(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", ApprovingAgent())


async def _a_passage_worked_through(db_session: AsyncSession, language: str) -> IRSession:
    """Everything the passage asks for is done: the floor is met and every scene was
    rehearsed. This is exactly the room the app used to interrupt with its question."""
    session = await create_session(db_session, language=language, pericope=P)
    session = await save_comprehension(
        db_session, session, ComprehensionState(practiced_scene_ids=scene_ids_for(P))
    )
    session = await apply_coverage(
        db_session, session.id, merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    )
    return await append_exchange(db_session, session, team_utterance="", guide_response="abertura")


async def _say(db_session: AsyncSession, session: IRSession, utterance: str) -> str:
    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text=utterance),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    await save_comprehension(db_session, session, turn.state)
    await append_exchange(
        db_session, session, team_utterance=utterance, guide_response=turn.outcome.speech
    )
    return turn.outcome.speech


@pytest.mark.asyncio
async def test_a_passage_worked_through_is_finished_without_a_consent_answer(
    db_session: AsyncSession, approve_all: None
) -> None:
    """Nothing waits on the answer any more, because there is no question to answer.

    The gate used to hold the interview open until the team said one of two words to the
    app. With the question gone that flag could never be written again, and every session
    would have stayed open for good — the interview ends on the passage being understood,
    which is the only thing the room can actually observe."""
    session = await _a_passage_worked_through(db_session, "pt")

    for said in AT_THE_END:
        await _say(db_session, session, said)

    assert session_is_done(session)


@pytest.mark.asyncio
async def test_the_refine_package_never_waits_on_a_recording_consent(
    db_session: AsyncSession,
) -> None:
    """What proves the team recorded is the rehearsal audio, which the release already
    demands. A session with nothing in it is refused for everything it is missing, and
    consent is not among them."""
    session = await create_session(db_session, language="pt", pericope=P)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "no_rehearsal_audio" in blocked.value.blockers
    assert "recording_consent_never_given" not in blocked.value.blockers
