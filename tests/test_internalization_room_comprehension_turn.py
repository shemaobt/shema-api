"""The comprehension-aware turn as a whole: probes persist only when voiced, practice is
spoken as fixed process speech, and mother-tongue speech meets the fixed boundary."""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys, elements_for
from app.services.internalization_room.comprehension.checkpoints import (
    scene_ids_for,
)
from app.services.internalization_room.comprehension.practice import (
    guide_invited_mother_tongue_practice,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.run_turn import OPENING_MOVEMENT_MARK, detects_peer_cue
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    comprehension_of,
    create_session,
    save_comprehension,
    session_is_done,
)

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
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", ApprovingAgent())


class InvitingAgent:
    """A Guide that opens the scene and closes with the invitation its contract asks for."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
            "Rehearse this scene together in your own language; when you have finished, "
            "come back and tell me in English what you understood."
        )


@pytest.fixture
def guide_invites(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", InvitingAgent())


class InvitingAgentPT:
    """The same Guide, in the language the room is actually speaking."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "Uma fome chega, e uma família sai de Belém para os campos de Moabe. "
            "Agora ensaiem esta cena juntos na língua de vocês; quando terminarem, "
            "venham me contar em português o que vocês entenderam."
        )


@pytest.fixture
def guide_invites_pt(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", InvitingAgentPT())


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


@pytest.mark.asyncio
async def test_the_opening_is_cut_where_the_guide_marked_it(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two movements, so the room can hand the scene back on its own and the necklace can
    wait for it — and so each half answers to its own ceiling instead of the turn becoming
    one long breath."""
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", TwoMovementAgent())
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

    assert len(turn.outcome.movements) == 2
    assert turn.outcome.movements[0].startswith("Olá, eu sou o Facilitador Digital.")
    assert turn.outcome.movements[1].startswith("Vamos ficar no começo.")
    assert OPENING_MOVEMENT_MARK not in turn.outcome.speech
    assert "[[" not in turn.outcome.speech


@pytest.mark.asyncio
async def test_a_session_that_already_spoke_is_not_opened_twice(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file-less POST on a live session is a re-open, not a first line.

    Letting it ask for the two movements again would say the whole passage a second time and
    pull the necklace apart under a team already working.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", TwoMovementAgent())
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

    assert turn.outcome.movements == []
    assert OPENING_MOVEMENT_MARK not in turn.outcome.speech


class LongPanoramaAgent:
    """A Guide whose first movement runs past what the panorama used to be allowed."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return f"{'palavra ' * 200}.\n[[CENA]]\nE agora a cena."


@pytest.mark.asyncio
async def test_a_long_opening_is_spoken_in_its_two_movements(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mark the Guide drew is what divides the opening, and length no longer undoes it.

    An opening whose whole ran past the panorama's ceiling was refused, redrafted and then
    replaced by a fixed line, and a fail-safe carries no movements — so the two clips the
    team was supposed to hear collapsed into one canned sentence on the exact turn the room
    had the most to say.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongPanoramaAgent())
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

    assert not turn.outcome.used_fail_safe
    assert len(turn.outcome.movements) == 2
    assert OPENING_MOVEMENT_MARK not in turn.outcome.speech


@pytest.mark.asyncio
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
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongWindedAgent())
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

    assert not turn.outcome.used_fail_safe
    assert turn.outcome.speech.startswith("Olá, eu sou o Facilitador Digital.")
    assert len(turn.outcome.speech.split()) > 45


@pytest.mark.asyncio
async def test_a_turn_that_runs_long_is_spoken_as_it_is(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Length is prompt style, never a reject — and an ordinary turn answers to no ceiling.

    Sixty words on a turn measured at forty-five were redrafted twice and then thrown away
    for a fixed line, so a team that had just told something back heard the room say nothing
    about it. Brevity is asked for in the Guide's own prompt now, and nowhere else.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongWindedAgent())
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

    assert not turn.outcome.used_fail_safe
    assert not turn.outcome.fixed_line
    assert len(turn.outcome.speech.split()) > 45


@pytest.mark.asyncio
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

    assert turn.outcome.speech == "Vamos começar pela primeira cena. O que vocês acham?"
    assert turn.outcome.speech != FIXED_PRACTICE_INVITATION
    assert not turn.outcome.used_fail_safe
    assert turn.state.active_probe is None


#: A despedida do Guia, que é o convite ao ensaio desde o ENG-777 — a em português é a
#: frase da Marcia; a em inglês é a mesma despedida na língua da sala.
SEND_OFF = {
    "pt": "Agora gravem o ensaio de vocês, na língua de vocês.",
    "en": "Now record your rehearsal, in your own language.",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_room_hands_the_talking_over_in_every_language_it_claims(spoken: str) -> None:
    """A frase cujo propósito inteiro é passar a palavra para a equipe.

    `peer_cue` é detectado relendo a frase dita, então cada idioma precisa das suas
    expressões. Faltando as do espanhol, `peer_cue` voltava falso em todo turno de uma
    sessão em espanhol — e o teste ao lado abre com `language="pt"`, então a suíte seguia
    verde por cima disso.

    A frase lida aqui era a deixa fixa do app, que o ENG-777 apagou junto com a pergunta de
    gravação. Quem convida agora é a despedida do Guia, e é ela que precisa marcar o convite:
    é o mesmo turno, com o mesmo trabalho a fazer na tela.
    """
    assert detects_peer_cue(SEND_OFF[spoken]), (
        f"a sala manda a equipe ensaiar e gravar em {spoken!r} e não marca o convite, "
        "então a tela não entra em modo de conversa e a equipe fica olhando o círculo"
    )


@pytest.mark.asyncio
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

    await save_comprehension(db_session, session, turn.state)
    await append_exchange(
        db_session, session, team_utterance="podemos começar", guide_response=turn.outcome.speech
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

    spoken = [turn.outcome.speech, recovery.outcome.speech]
    assert FIXED_PRACTICE_INVITATION not in spoken
    assert not any("ensaiem juntos" in line for line in spoken), spoken
    assert not recovery.outcome.used_fail_safe


@pytest.mark.asyncio
async def test_mother_tongue_speech_meets_the_fixed_boundary_and_keeps_the_probe(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )
    seeded = ComprehensionState.model_validate(
        {"active_probe": {"id": "consent-1", "purpose": "recording_handoff_consent"}}
    )
    session = await save_comprehension(db_session, session, seeded)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(
            text="koeti yoko vitukeovo enepone itukovo",
            language_code="und",
            language_probability=0.99,
        ),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.used_fail_safe
    assert not turn.outcome.degraded
    assert turn.outcome.fixed_line.startswith("G")
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.id == "consent-1"
    assert all(event.kind != "evidence" for event in turn.state.ledger)


@pytest.mark.asyncio
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
            speech=HeardSpeech(text="mmm ne", transcript_confidence=0.2),
            opening=False,
            guide_prompt=GUIDE,
            validator_prompt=VALIDATOR,
            settings=_settings(),
        )
        session = await save_comprehension(db_session, session, turn.state)
        spoken.append(turn.outcome)

    inaudible = utterances(FailSafe.INAUDIBLE, "pt")
    assert all(outcome.speech in inaudible for outcome in spoken), [o.speech for o in spoken]
    assert not any("Refine" in outcome.speech for outcome in spoken)
    assert all(outcome.used_fail_safe and outcome.degraded for outcome in spoken)


@pytest.mark.asyncio
async def test_a_turn_without_a_prior_probe_mints_no_evidence(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="Noemi voltou para Belém com Rute"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.state.ledger == []
    assert comprehension_of(session).ledger == []


async def _session_at_the_recording_handoff(
    db_session: AsyncSession, *, practice_reported: bool = True
) -> IRSession:
    """Everything the passage asks for is done except the recording: the coverage floor is
    met and every scene was rehearsed, so the app is about to offer its own question.

    The ledger is empty and stays empty. Nothing writes to it any more, and the gate no
    longer asks it anything — what has to be true is the floor, the rehearsals and the
    team's consent.

    `practice_reported=False` is the same room with nobody having said the closing word:
    every bead is engaged while the practice record stays empty."""
    session = await create_session(db_session, language="pt", pericope=P)
    session = await save_comprehension(
        db_session,
        session,
        ComprehensionState(practiced_scene_ids=scene_ids_for(P) if practice_reported else []),
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


_UNUSABLE_SPEECH = (
    HeardSpeech(
        text="koeti yoko vitukeovo enepone itukovo",
        language_code="und",
        language_probability=0.99,
    ),
    HeardSpeech(text="mmm ne", transcript_confidence=0.2),
    HeardSpeech(),
)


@pytest.mark.asyncio
async def test_a_scene_the_team_worked_to_the_last_bead_needs_no_closing_word(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A necklace fully engaged is the practice, whether or not anyone announced it.

    The report was only ever recorded when the team said the closing word out loud, so a
    room that told every scene in its own language and simply moved on stayed one scene
    short forever: the readiness gate kept the passage in rehearsal and the room answered
    the team's own "we are finished" with yet another invitation to retell."""
    session = await _session_at_the_recording_handoff(db_session, practice_reported=False)

    await _say(db_session, session, "acho que já falamos de tudo")

    assert session_is_done(session)


class InvitingAgentAskingForTheWord:
    """A Guide that invites the rehearsal and names the one word it wants back."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
            "Rehearse this scene together in your own language; when you have finished, "
            "just say: done."
        )


@pytest.fixture
def guide_asks_for_the_word(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", InvitingAgentAskingForTheWord())


@pytest.mark.asyncio
async def test_the_closing_word_the_guide_asked_for_closes_the_scene(
    db_session: AsyncSession, guide_asks_for_the_word: None
) -> None:
    """The one word the room asked for was heard while the app owned the invitation.

    The reader for it hung off the practice probe, and the probe went with the contract, so
    a team that rehearsed and came back with exactly the word it was told to say would have
    had that word land on nothing. The invitation moved to the Guide; what answers it did
    not change.
    """
    session = await create_session(db_session, language="en", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="opening"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    invitation = await _say(db_session, session, "we can start")
    assert guide_invited_mother_tongue_practice(invitation)

    await _say(db_session, session, "done")

    assert comprehension_of(session).practiced_scene_ids == [scene_ids_for(P)[0]]


@pytest.mark.asyncio
async def test_the_guide_invites_the_rehearsal_and_the_retelling_finishes_it(
    db_session: AsyncSession, guide_invites: None
) -> None:
    """Session 735b5eda: the opening carried no invitation, so the fixed line arrived after.

    The Guide closed the scene with a passage question and the app said its own sentence a
    turn later, asking for the same rehearsal under a different contract. The invitation
    belongs at the end of the opening, in the Guide's voice, and it asks the team to come
    back telling in the bridge language what it understood — so that telling is what
    finishes the practice, and the fixed line has nothing left to add."""
    session = await create_session(db_session, language="en", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="opening"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    opening = await _say(db_session, session, "we can start")
    assert opening != FIXED_PRACTICE_INVITATION
    assert guide_invited_mother_tongue_practice(opening)

    answer = await _say(
        db_session, session, "A famine came and a family left Bethlehem to live in Moab"
    )
    assert answer != FIXED_PRACTICE_INVITATION
    assert comprehension_of(session).practiced_scene_ids == [scene_ids_for(P)[0]]


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


@pytest.mark.asyncio
async def test_the_telling_that_answers_the_invitation_lands_before_any_probe_exists(
    db_session: AsyncSession, guide_invites: None
) -> None:
    """Session 23520187: the team did exactly what it was asked and it counted for nothing.

    The invitation is said at the end of the opening, a turn before the planner has any
    reason to raise a practice probe for that scene. A team that obeys answers on the very
    next turn — so requiring a standing probe threw away the one reply the invitation had
    asked for. The scene stayed unpractised, the probe was raised afterwards, and the room
    went back to asking for the rehearsal the team had already told, until the validator
    started refusing the Guide's drafts for not honouring a contract nobody could satisfy.
    """
    session = await create_session(db_session, language="en", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="opening"
    )

    invitation = await _say(db_session, session, "we can start")
    assert guide_invited_mother_tongue_practice(invitation)
    assert comprehension_of(session).active_probe is None

    await _say(
        db_session,
        session,
        "A famine came, and Elimelech took Naomi and their two sons from Bethlehem to Moab",
    )

    assert comprehension_of(session).practiced_scene_ids == [scene_ids_for(P)[0]]
    assert comprehension_of(session).active_probe is None


@pytest.mark.asyncio
async def test_the_second_scene_is_opened_by_the_guide_before_it_is_probed(
    db_session: AsyncSession, guide_invites_pt: None
) -> None:
    """The first scene is opened by the passage opening; nothing opened the second.

    With the first scene worked through, the planner walked straight into a checkpoint
    question about a scene the room had never told, and the app's fixed line — which may
    carry no passage content — could not have opened it either. The Guide opens it and
    invites the rehearsal in the same turn, and the telling that comes back closes it.
    """
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    session.coverage_state = {
        **(session.coverage_state or {}),
        **{e.key: "engaged" for e in elements_for(P) if e.scene == 1},
    }
    await db_session.commit()

    opening = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="entendemos a primeira cena"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert opening.state.active_probe is None
    assert opening.outcome.speech != FIXED_PRACTICE_INVITATION
    assert guide_invited_mother_tongue_practice(opening.outcome.speech)

    await save_comprehension(db_session, session, opening.state)
    session = await append_exchange(
        db_session,
        session,
        team_utterance="entendemos a primeira cena",
        guide_response=opening.outcome.speech,
    )

    told_back = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="ensaiamos e entendemos que a família volta para Belém"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert "S2" in told_back.state.practiced_scene_ids
