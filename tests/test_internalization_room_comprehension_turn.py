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
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.practice import (
    mother_tongue_practice_prompt,
)
from app.services.internalization_room.comprehension.probe import ProbePurpose
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.comprehension.stt_recovery import (
    stt_recovery_reduce_burden_line,
)
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.rehearsal_readiness import (
    RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
    rehearsal_consent_declined_line,
    rehearsal_consent_question,
    rehearsal_readiness_cue,
)
from app.services.internalization_room.run_turn import OPENING_MOVEMENT_MARK, detects_peer_cue
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    comprehension_of,
    create_session,
    save_comprehension,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


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
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="adaptive")

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
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="adaptive")
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
    """A Guide whose first movement runs past even the panorama's wider ceiling."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return f"{'palavra ' * 200}.\n[[CENA]]\nE agora a cena."


@pytest.mark.asyncio
async def test_even_the_panorama_has_a_ceiling(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongPanoramaAgent())
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="adaptive")

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.used_fail_safe
    assert turn.outcome.movements == []


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
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="adaptive")

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
async def test_a_turn_after_the_opening_still_answers_to_the_budget(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", LongWindedAgent())
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="adaptive")
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(transcript="a fome chegou", is_substantial=True),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.used_fail_safe
    assert turn.outcome.fixed_line


@pytest.mark.asyncio
async def test_the_opening_turn_belongs_to_the_guide(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The session's first line opens the passage; it is never an app-owned prompt.

    The Terena field test heard 'ensaiem juntos esta cena' as the very first utterance of
    a passage nobody had opened yet — instant, unframed, and with no thinking. Frame
    first, elicit second: the opening always goes through the Guide.
    """
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
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

    assert turn.bridge_mode == "guided_microchecks"
    assert turn.outcome.speech == "Vamos começar pela primeira cena. O que vocês acham?"
    assert turn.outcome.speech != mother_tongue_practice_prompt("pt")
    assert not turn.outcome.used_fail_safe
    assert turn.state.active_probe is None


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_room_hands_the_talking_over_in_every_language_it_claims(spoken: str) -> None:
    """A linha cujo propósito inteiro é passar a palavra para a equipe.

    `peer_cue` é detectado relendo a frase que o próprio app escreveu, então cada idioma
    precisa das suas expressões. Faltando as do espanhol, `peer_cue` voltava falso em todo
    turno de uma sessão em espanhol — e o teste ao lado abre com `language="pt"`, então a
    suíte seguia verde por cima disso.
    """
    assert detects_peer_cue(mother_tongue_practice_prompt(spoken)), (
        f"a sala convida a equipe a ensaiar entre si em {spoken!r} e não marca o convite, "
        "então a tela não entra em modo de conversa e a equipe fica olhando o círculo"
    )


async def test_the_practice_invitation_is_fixed_speech_with_a_peer_cue(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
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

    assert turn.outcome.speech == mother_tongue_practice_prompt("pt")
    assert turn.outcome.peer_cue
    assert not turn.outcome.used_fail_safe


@pytest.mark.asyncio
async def test_practice_is_not_invited_before_the_voice_opens_the_scene(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="podemos começar"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert turn.outcome.speech != mother_tongue_practice_prompt("pt")
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE


@pytest.mark.asyncio
async def test_pronto_after_the_practice_prompt_marks_the_scene(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=mother_tongue_practice_prompt("pt")
    )
    seeded = ComprehensionState.model_validate(
        {
            "active_probe": {
                "id": "practice-1",
                "checkpoint_ids": [],
                "method": "micro_tellback",
                "purpose": "mother_tongue_practice",
                "practice_scene_ids": ["S1"],
            }
        }
    )
    session = await save_comprehension(db_session, session, seeded)

    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="pronto"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert "S1" in turn.state.practiced_scene_ids
    assert turn.state.active_probe is not None
    assert turn.state.active_probe.purpose is ProbePurpose.INITIAL_CHECK


@pytest.mark.asyncio
async def test_a_retelling_during_the_practice_reaches_the_guide_not_the_invitation_again(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A team that answered the invitation by telling the scene back heard it again.

    The room voiced the identical fixed sentence on the next turn, so the Guide never saw
    the retelling and the team was told to rehearse a scene it had just rehearsed.
    """
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    assert await _say(db_session, session, "podemos começar") == (
        mother_tongue_practice_prompt("pt")
    )

    assert (
        await _say(db_session, session, "uma família saiu de Belém e foi morar em Moabe")
        == "Vamos começar pela primeira cena. O que vocês acham?"
    )


@pytest.mark.asyncio
async def test_a_question_during_the_practice_is_answered_not_met_with_the_instruction_again(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A team that asked something while rehearsing got the rehearsal order back.

    The question went nowhere: the app owned the turn, so nobody answered it and the room
    kept saying the one sentence the team had already followed.
    """
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="abertura"
    )
    first_scene_element = next(e for e in elements_for(P) if e.scene == 1)
    session.coverage_state = {
        **(session.coverage_state or {}),
        first_scene_element.key: "surfaced",
    }
    await db_session.commit()

    assert await _say(db_session, session, "podemos começar") == (
        mother_tongue_practice_prompt("pt")
    )

    assert (
        await _say(db_session, session, "podemos contar essa parte com as nossas palavras?")
        == "Vamos começar pela primeira cena. O que vocês acham?"
    )


@pytest.mark.asyncio
async def test_mother_tongue_speech_meets_the_fixed_boundary_and_keeps_the_probe(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )
    from app.services.internalization_room.comprehension.checkpoints import checkpoints_for

    target = next(c for c in checkpoints_for(P) if c.critical)
    seeded = ComprehensionState.model_validate(
        {
            "active_probe": {
                "id": "semantic-1",
                "checkpoint_ids": [target.id],
                "method": "micro_tellback",
                "purpose": "initial_check",
                "practice_scene_ids": [],
            }
        }
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
    assert turn.state.active_probe.id == "semantic-1"
    assert all(event.kind != "evidence" for event in turn.state.ledger)


@pytest.mark.asyncio
async def test_speech_the_room_could_not_hear_degrades_on_both_rungs_of_the_recovery(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A room that cannot hear the team is a room that is not working, on either rung.

    The recovery alternates — the first uncertainty asks them to repeat, the second offers a
    smaller question — so counting only the first would leave a team whose microphone is not
    reaching them answered by the same two lines forever, with nothing adding up."""
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="quem aparece nesta parte?"
    )
    target = next(c for c in checkpoints_for(P) if c.critical)
    session = await save_comprehension(
        db_session,
        session,
        ComprehensionState.model_validate(
            {
                "active_probe": {
                    "id": "semantic-1",
                    "checkpoint_ids": [target.id],
                    "method": "micro_tellback",
                    "purpose": "initial_check",
                    "practice_scene_ids": [],
                }
            }
        ),
    )

    spoken = []
    for _ in range(2):
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

    assert spoken[0].speech in utterances(FailSafe.INAUDIBLE, "pt")
    assert spoken[1].speech == stt_recovery_reduce_burden_line("pt")
    assert all(outcome.used_fail_safe and outcome.degraded for outcome in spoken)


@pytest.mark.asyncio
async def test_a_turn_without_a_prior_probe_mints_no_evidence(
    db_session: AsyncSession, approve_all: None
) -> None:
    session = await create_session(db_session, language="pt", pericope=P, bridge_mode="full_retell")
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
    met and every checkpoint is demonstrated, so the app is about to offer its own
    question.

    `practice_reported=False` is the same room with nobody having said the closing word:
    every bead is engaged while the practice record stays empty."""
    session = await create_session(
        db_session, language="pt", pericope=P, bridge_mode="guided_microchecks"
    )
    session = await save_comprehension(
        db_session,
        session,
        ComprehensionState(
            ledger=[
                EvidenceObservation(
                    id=f"ev-{index}",
                    unit_id=checkpoint.id,
                    probe_id=f"probe-{index}",
                    method=EvidenceMethod.MICRO_TELLBACK,
                    result=EvidenceResult.DEMONSTRATED,
                )
                for index, checkpoint in enumerate(checkpoints_for(P))
            ],
            practiced_scene_ids=scene_ids_for(P) if practice_reported else [],
        ),
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
async def test_a_declined_recording_handoff_is_offered_again(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The app's own question offers two words and the team may say either one.

    Answering "não" used to latch the handoff shut for the rest of the session: the only
    way back was one of seven exact sentences, and the Guide is forbidden from teaching
    them. The room promised "vocês decidem quando estiverem prontos" and then made that
    impossible, so the passage ended with no rehearsal audio and the release refused it.
    """
    session = await _session_at_the_recording_handoff(db_session)

    assert await _say(db_session, session, "acho que já falamos de tudo") == (
        rehearsal_consent_question("pt")
    )
    assert await _say(db_session, session, "não") == rehearsal_consent_declined_line("pt")
    assert comprehension_of(session).recording_handoff_paused

    for _ in range(RECORDING_HANDOFF_REOFFER_AFTER_TURNS):
        assert await _say(db_session, session, "estamos conversando sobre a última cena") != (
            rehearsal_consent_question("pt")
        )

    assert await _say(db_session, session, "essa parte ficou boa do jeito que contamos") == (
        rehearsal_consent_question("pt")
    )
    assert await _say(db_session, session, "sim") == rehearsal_readiness_cue("pt")
    assert comprehension_of(session).recording_consent_given
    assert not comprehension_of(session).recording_handoff_paused


@pytest.mark.asyncio
async def test_declining_twice_defers_twice_instead_of_latching(
    db_session: AsyncSession, approve_all: None
) -> None:
    """A second "não" restarts the wait rather than ending the conversation about it."""
    session = await _session_at_the_recording_handoff(db_session)
    await _say(db_session, session, "acho que já falamos de tudo")
    await _say(db_session, session, "não")
    for _ in range(RECORDING_HANDOFF_REOFFER_AFTER_TURNS):
        await _say(db_session, session, "estamos conversando sobre a última cena")

    assert await _say(db_session, session, "ainda estamos comentando entre nós") == (
        rehearsal_consent_question("pt")
    )
    assert await _say(db_session, session, "não") == rehearsal_consent_declined_line("pt")
    assert comprehension_of(session).recording_handoff_paused_turns == 0

    for _ in range(RECORDING_HANDOFF_REOFFER_AFTER_TURNS):
        assert await _say(db_session, session, "estamos conversando sobre a última cena") != (
            rehearsal_consent_question("pt")
        )

    assert await _say(db_session, session, "essa parte ficou boa do jeito que contamos") == (
        rehearsal_consent_question("pt")
    )


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
async def test_a_paused_handoff_does_not_count_speech_the_room_could_not_use(
    db_session: AsyncSession, approve_all: None
) -> None:
    """The wait is measured in turns the room actually heard.

    A team that spends the pause rehearsing in its own language, or in a corner of the
    house the microphone cannot reach, has not been given the room the wait is for — and
    a transcription that came back empty is the room asking them to repeat, not the room
    standing back."""
    session = await _session_at_the_recording_handoff(db_session)
    await _say(db_session, session, "acho que já falamos de tudo")
    await _say(db_session, session, "não")

    for index in range(3 * (RECORDING_HANDOFF_REOFFER_AFTER_TURNS + 1)):
        turn = await run_comprehension_turn(
            db_session,
            session,
            speech=_UNUSABLE_SPEECH[index % len(_UNUSABLE_SPEECH)],
            opening=False,
            guide_prompt=GUIDE,
            validator_prompt=VALIDATOR,
            settings=_settings(),
        )
        await save_comprehension(db_session, session, turn.state)
        assert turn.outcome.speech != rehearsal_consent_question("pt")

    assert comprehension_of(session).recording_handoff_paused_turns == 0


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

    assert await _say(db_session, session, "acho que já falamos de tudo") == (
        rehearsal_consent_question("pt")
    )
