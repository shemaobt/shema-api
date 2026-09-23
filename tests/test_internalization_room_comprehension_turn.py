"""The comprehension-aware turn as a whole: probes persist only when voiced, practice is
spoken as fixed process speech, and mother-tongue speech is a fact the Guide is handed."""

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
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.run_turn import OPENING_MOVEMENT_MARK
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

    assert not turn.outcome.used_fail_safe, "a sala respondia com a linha fixa G"
    assert turn.outcome.fixed_line == ""
    assert turn.outcome.transcript == ""
    assert turn.outcome.room_note == (
        "[A equipe falou na língua materna por cerca de 12 segundos; sem transcrição]"
    )
    assert turn.state.practiced_scene_ids == []
    assert all(event.kind != "evidence" for event in turn.state.ledger)


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


async def test_a_scene_worked_to_its_last_bead_is_not_a_mother_tongue_rehearsal(
    db_session: AsyncSession, approve_all: None
) -> None:
    """Engagement is the ledger painting beads; rehearsal is what the team reports.

    Marcia's answer 8: the ledger informs, it never ends the conversation (DOCTRINE.md §4).
    A necklace can go fully engaged through the bridge language alone, so a scene worked to
    its last bead without the team ever switching into their own language stays a passage
    still owed its first rehearsal — the gate keeps waiting on the report, not the beads."""
    session = await _session_at_the_recording_handoff(db_session, practice_reported=False)

    await _say(db_session, session, "acho que já falamos de tudo")

    assert not session_is_done(session)


_THE_INVITATION_FOR_THE_LAST_TWO_SCENES = (
    "Entendo. E vocês têm razão numa coisa: vocês já entenderam a história inteira. Isso "
    "ficou claro no que me contaram.\n\n"
    "Mas entender é só uma parte. A outra parte é a história viver na boca de vocês, na "
    "língua de vocês. As duas últimas cenas ainda não passaram por aí. Não leva muito tempo.\n\n"
    "Então façam assim. Ensaiem juntos, na língua de vocês, a cena dos casamentos e dos dez "
    "anos, e depois a cena em que Malom e Quiliom morrem e Noemi fica sozinha, sem os dois "
    "filhos e sem o marido. Podem fazer as duas cenas seguidas. Quando terminarem, voltem e "
    "me contem em português, bem curto, o que vocês disseram no ensaio.\n\n"
    "Depois disso, vamos pro próximo passo."
)
_THE_TELLING_OF_BOTH = (
    "A gente ensaiou juntos na nossa língua a cena dos casamentos e dos 10 anos, e depois a "
    "cena em que Malone e Kleon morrer-morreram, e Noemí fica sozinha, sem os filhos e sem o "
    "marido."
)


async def test_a_full_necklace_does_not_let_a_telling_mark_a_scene_it_only_retold(
    db_session: AsyncSession, approve_all: None
) -> None:
    """Session dce19a6b, on the pilot device: every bead engaged, one scene already reported.

    The Guide invited a rehearsal of the two scenes still owed, and the team told both back
    at length instead of reporting a finished rehearsal. The Guide checks a retelling itself,
    item by item against the pinned map (DOCTRINE.md §4) — the app does not, on a full
    necklace or otherwise — so the practice record stays exactly what it was."""
    passage = "P01"
    session = await create_session(db_session, language="pt", pericope=passage)
    session = await save_comprehension(
        db_session, session, ComprehensionState(practiced_scene_ids=["S1"])
    )
    session = await apply_coverage(
        db_session,
        session.id,
        merge(initial_state(passage), pericope_num=passage, engaged=element_keys(passage)),
    )
    session = await append_exchange(
        db_session,
        session,
        team_utterance="Pra ser sincero, eu acho que a gente já cobriu tudo, tá bom?",
        guide_response=_THE_INVITATION_FOR_THE_LAST_TWO_SCENES,
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text=_THE_TELLING_OF_BOTH),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.state.practiced_scene_ids == ["S1"]


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


async def test_the_guide_invites_the_rehearsal_and_a_retelling_alone_does_not_finish_it(
    db_session: AsyncSession, guide_invites: None
) -> None:
    """Session 735b5eda: the opening carried no invitation, so the fixed line arrived after.

    The Guide closed the scene with a passage question and the app said its own sentence a
    turn later, asking for the same rehearsal under a different contract. The invitation
    belongs at the end of the opening, in the Guide's voice — but the telling the team sends
    back is not, on its own, the report that closes the practice: only the team's own word
    that the rehearsal is finished does that (DOCTRINE.md §4)."""
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
    assert comprehension_of(session).practiced_scene_ids == []


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


async def test_the_second_scene_is_opened_by_the_guide_before_it_is_probed(
    db_session: AsyncSession, guide_invites_pt: None
) -> None:
    """The first scene is opened by the passage opening; nothing opened the second.

    With the first scene worked through, the planner walked straight into a checkpoint
    question about a scene the room had never told, and the app's fixed line — which may
    carry no passage content — could not have opened it either. The Guide opens it and
    invites the rehearsal in the same turn — but the telling that comes back is not the
    report, so it does not close the scene on its own.
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
        speech=HeardSpeech(text="entendemos que a família volta para Belém"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert "S2" not in told_back.state.practiced_scene_ids


async def test_a_complete_portuguese_retelling_leaves_the_practice_record_untouched(
    db_session: AsyncSession, guide_invites_pt: None
) -> None:
    """The Guide checks the retelling itself, item by item against the pinned map, with the
    whole conversation in context (DOCTRINE.md §4) — the app never claims to know what a
    mother-tongue rehearsal said. A team that tells the scene back whole and fluently, right
    after a real invitation, has not thereby reported anything: only the team's own word that
    the rehearsal is finished does that.
    """
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="opening"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    invitation = await _say(db_session, session, "podemos começar")
    assert guide_invited_mother_tongue_practice(invitation)

    await _say(
        db_session,
        session,
        # No report in it: a pure telling, so the assertion proves what the name says.
        # ("Ensaiamos …" alone would not count either — the report reader wants "já
        # ensaiamos" / "acabamos de ensaiar" — but that is ENG-987's question, not this one.)
        "Entendemos que uma fome chegou e a família saiu de Belém para Moabe, e lá o marido "
        "de Noemi morreu",
    )

    assert comprehension_of(session).practiced_scene_ids == []
