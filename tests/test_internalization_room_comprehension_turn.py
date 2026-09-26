"""The comprehension-aware turn as a whole: mother-tongue speech is a fact the Guide is
handed."""

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.run_turn import OPENING_MOVEMENT_MARK
from app.services.internalization_room.sessions import (
    append_exchange,
    create_session,
)
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

#: The sentence the app used to say in place of the Guide, kept as the thing no turn may
#: produce any more.
FIXED_PRACTICE_INVITATION = (
    "Agora ensaiem juntos esta cena na língua de vocês. Quando terminarem, digam somente: pronto."
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
    the_room_agent_is(monkeypatch, turn=ApprovingAgent())


class LongWindedAgent:
    """A Guide that opens at length — introduce, give the whole, invite — and is approved."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "Olá, eu sou o Facilitador Digital. Esta história começa nos dias em que os "
            "juízes julgavam, quando falta comida na terra e uma família sai de Belém "
            "para peregrinar em Moabe. Ali ela perde quase tudo ao longo de dez anos, e "
            "é desse começo que vamos falar. Como vocês contariam essa primeira parte?"
        )


class TwoMovementAgent:
    """A Guide that marks the boundary between the whole and the first scene."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "Olá, eu sou o Facilitador Digital. Nesta passagem uma família sai de Belém "
            "por falta de comida e peregrina em Moabe, e ali perde quase tudo.\n"
            "[[CENA]]\n"
            "Vamos ficar no começo. Como vocês contariam essa primeira parte?"
        )


async def test_the_opening_is_cut_where_the_guide_marked_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two movements, so the room can hand the scene back on its own and the necklace can
    wait for it — and so each half answers to its own ceiling instead of the turn becoming
    one long breath."""
    the_room_agent_is(monkeypatch, turn=TwoMovementAgent())
    session = await create_session(db_session, language="pt", pericope=P)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert len(turn.movements) == 2
    assert turn.movements[0].startswith("Olá, eu sou o Facilitador Digital.")
    assert turn.movements[1].startswith("Vamos ficar no começo.")
    assert OPENING_MOVEMENT_MARK not in turn.speech
    assert "[[" not in turn.speech


async def test_a_session_that_already_spoke_is_not_opened_twice(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file-less POST on a live session is a re-open, not a first line.

    Letting it ask for the two movements again would say the whole passage a second time and
    pull the necklace apart under a team already working.
    """
    the_room_agent_is(monkeypatch, turn=TwoMovementAgent())
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.movements == []
    assert OPENING_MOVEMENT_MARK not in turn.speech


class LongPanoramaAgent:
    """A Guide whose first movement runs past what the panorama used to be allowed."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return f"{'palavra ' * 200}.\n[[CENA]]\nE agora a cena."


async def test_a_long_opening_is_spoken_in_its_two_movements(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mark the Guide drew is what divides the opening, and length no longer undoes it.

    An opening whose whole ran past the panorama's ceiling was refused, redrafted and then
    replaced by a fixed line, and a fail-safe carries no movements — so the two clips the
    team was supposed to hear collapsed into one canned sentence on the exact turn the room
    had the most to say.
    """
    the_room_agent_is(monkeypatch, turn=LongPanoramaAgent())
    session = await create_session(db_session, language="pt", pericope=P)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert not turn.used_fail_safe
    assert len(turn.movements) == 2
    assert OPENING_MOVEMENT_MARK not in turn.speech


async def test_the_opening_may_give_the_whole_before_the_parts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The oral pacing budget is for the back-and-forth, never for the opening.

    Enforcing 45 words on the turn that has to introduce the Guide, give the whole before
    the parts and invite meant every passage opening busted the budget, redrafted twice and
    fell back to a canned line — so the room never introduced itself and never walked the
    team into the scenes, and the team waited six model calls for it. The opening answers to
    a wider ceiling now, not to none: lifting it entirely produced a ninety-second monologue.
    """
    the_room_agent_is(monkeypatch, turn=LongWindedAgent())
    session = await create_session(db_session, language="pt", pericope=P)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert not turn.used_fail_safe
    assert turn.speech.startswith("Olá, eu sou o Facilitador Digital.")
    assert len(turn.speech.split()) > 45


async def test_a_turn_that_runs_long_is_spoken_as_it_is(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Length is prompt style, never a reject — and an ordinary turn answers to no ceiling.

    Sixty words on a turn measured at forty-five were redrafted twice and then thrown away
    for a fixed line, so a team that had just told something back heard the room say nothing
    about it. Brevity is asked for in the Guide's own prompt now, and nowhere else.
    """
    the_room_agent_is(monkeypatch, turn=LongWindedAgent())
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="a fome chegou"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert not turn.used_fail_safe
    assert not turn.fixed_line
    assert len(turn.speech.split()) > 45


async def test_the_opening_turn_belongs_to_the_guide(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The session's first line opens the passage; it is never an app-owned prompt.

    The Terena field test heard 'ensaiem juntos esta cena' as the very first utterance of
    a passage nobody had opened yet — instant, unframed, and with no thinking. Frame
    first, elicit second: the opening always goes through the Guide.
    """
    session = await create_session(db_session, language="pt", pericope=P)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.speech == "Vamos começar pela primeira cena. O que vocês acham?"
    assert turn.speech != FIXED_PRACTICE_INVITATION
    assert not turn.used_fail_safe


async def test_the_rehearsal_invitation_is_never_a_fixed_line_the_app_says(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The Guide invites the rehearsal, every turn, in its own words.

    The fixed sentence was the app taking the turn: a probe stood through a whole turn
    without an invitation being said, and the app said this one instead of the Guide. It
    is written here rather than imported because what the test asks is that nothing in
    the build can produce it.
    """
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    # The team took the scene up ("partially_engaged"): practice is only invited for a
    # scene the team was told, and a bead the Guide merely mentioned ("surfaced") is not.
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "partially_engaged",
    }
    await db_session.commit()

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="podemos começar"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    await append_exchange(
        db_session, session, team_utterance="podemos começar", guide_response=turn.speech
    )

    recovery = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="tudo bem"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    spoken = [turn.speech, recovery.speech]
    assert FIXED_PRACTICE_INVITATION not in spoken
    assert not any("ensaiem juntos" in line for line in spoken), spoken
    assert not recovery.used_fail_safe


async def test_mother_tongue_speech_is_an_ordinary_guide_turn_that_credits_nothing(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(
            text="koeti yoko vitukeovo enepone itukovo",
            language_code="und",
            language_probability=0.99,
            take_ms=12_000,
        ),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert not turn.used_fail_safe, "a sala respondia com a linha fixa G"
    assert turn.fixed_line == ""
    assert turn.transcript == ""
    assert turn.room_note == (
        "[A equipe falou na língua materna por cerca de 12 segundos; sem transcrição — nenhuma "
        "palavra chegou até você.]"
    )


async def test_speech_the_room_could_not_hear_is_answered_the_same_way_every_time(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A room that cannot hear the team is a room that is not working, and it says so.

    The second uncertainty used to offer a choice — one shorter question, or keeping the
    point for Refine — and that offer only existed to feed the probe planner a smaller
    scope. With no planner to feed, the choice would be a process step the team is walked
    through for nothing, and it is the same wrong answer the ticket is named after: a
    problem the room could not hear answered as though the team had a point to defer.
    """
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )
    spoken = []
    for _ in range(3):
        turn = await run_comprehension_turn(
            db_session,
            session,
            speech=HeardSpeech(),
            opening=False,
            guide_prompt=GUIDE,
            validator_prompt=VALIDATOR,
            settings=_settings(),
        )
        spoken.append(turn)

    inaudible = utterances(FailSafe.INAUDIBLE, "pt")
    assert all(outcome.speech in inaudible for outcome in spoken), [o.speech for o in spoken]
    assert not any("Refine" in outcome.speech for outcome in spoken)
    assert all(outcome.used_fail_safe and outcome.degraded for outcome in spoken)


_UNUSABLE_SPEECH = (
    HeardSpeech(
        text="koeti yoko vitukeovo enepone itukovo",
        language_code="und",
        language_probability=0.99,
    ),
    HeardSpeech(),
)


class RecordingInvitingAgent:
    """The inviting Guide, keeping every system prompt it was handed to draft from."""

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.systems.append(system_prompt)
        return (
            "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
            "Rehearse this scene together in your own language; when you have finished, "
            "come back and tell me in English what you understood."
        )
