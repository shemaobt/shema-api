"""The assessor's fail-closed parser: every evidence row must quote the team exactly and
survive negation, polarity, and duplicate guards.

The second half reads the same guard from the live turn: what the team hears when the
assessor call itself fails, and where a room goes when it keeps failing.
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.comprehension.assessor import (
    TurnAssessment,
    excerpt_drops_nearby_negation,
    is_bare_polar_answer,
    is_exact_excerpt,
    is_semantically_empty_answer,
    parse_turn_assessor_decision,
    semantic_excerpt_has_unresolved_polarity,
)
from app.services.internalization_room.comprehension.checkpoints import checkpoints_for
from app.services.internalization_room.comprehension.evidence import EvidenceMethod
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import (
    ComprehensionTurn,
    _assessor_failures_after,
    run_comprehension_turn,
)
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
    set_bridge_mode,
)

ALLOWED = ["proposition:P03:P1"]

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
P = "P03"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"


def _raw(rows: list[dict], **extra) -> str:
    return json.dumps({"observations": rows, **extra})


def _row(**overrides) -> dict:
    row = {
        "checkpoint_id": ALLOWED[0],
        "result": "demonstrated",
        "evidence_excerpt": "Noemi voltou",
        "rationale": "names the return",
    }
    row.update(overrides)
    return row


def test_a_grounded_row_with_an_exact_quote_survives() -> None:
    parsed = parse_turn_assessor_decision(_raw([_row()]), "Noemi voltou para Belém", ALLOWED)
    assert parsed is not None
    observations, _ = parsed
    assert len(observations) == 1
    assert observations[0].result == "demonstrated"


def test_a_row_quoting_words_the_team_never_said_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Rute ficou no campo")]), "Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_a_quote_that_drops_a_nearby_negation_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]), "não foi que Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_a_proposition_inside_uncertainty_is_not_positive_evidence() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]),
        "não tenho certeza se Noemi voltou",
        ALLOWED,
    )
    assert parsed is not None and parsed[0] == []


def test_a_question_then_denial_is_not_an_assertion() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(evidence_excerpt="Noemi voltou")]), "Noemi voltou? Não.", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_an_unknown_checkpoint_id_is_dropped() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(checkpoint_id="proposition:P03:P99")]), "Noemi voltou", ALLOWED
    )
    assert parsed is not None and parsed[0] == []


def test_the_model_cannot_return_carry_or_stt_results() -> None:
    for result in ("carry_to_refine", "stt_uncertain", "no_evidence"):
        parsed = parse_turn_assessor_decision(_raw([_row(result=result)]), "Noemi voltou", ALLOWED)
        assert parsed is not None and parsed[0] == []


def test_two_competing_rows_for_one_checkpoint_cancel_each_other() -> None:
    parsed = parse_turn_assessor_decision(
        _raw([_row(), _row(result="conflict", evidence_excerpt="Noemi voltou")]),
        "Noemi voltou",
        ALLOWED,
    )
    assert parsed is not None and parsed[0] == []


def test_extra_keys_on_a_row_fail_that_row_closed() -> None:
    parsed = parse_turn_assessor_decision(_raw([_row(extra_field="x")]), "Noemi voltou", ALLOWED)
    assert parsed is not None and parsed[0] == []


def test_unparseable_output_fails_the_whole_envelope() -> None:
    assert parse_turn_assessor_decision("nada de json", "Noemi voltou", ALLOWED) is None


def test_practice_needs_an_exact_quote_and_an_explicit_report() -> None:
    utterance = "já ensaiamos esta cena na nossa língua"
    parsed = parse_turn_assessor_decision(
        _raw(
            [],
            mother_tongue_practice_reported=True,
            practice_evidence_excerpt=utterance,
        ),
        utterance,
        ALLOWED,
    )
    assert parsed is not None and parsed[1] is True

    parsed = parse_turn_assessor_decision(
        _raw(
            [],
            mother_tongue_practice_reported=True,
            practice_evidence_excerpt="falamos terena",
        ),
        "falamos terena",
        ALLOWED,
    )
    assert parsed is not None and parsed[1] is False


def test_bare_polar_answers_are_semantically_empty() -> None:
    for text in ("sim", "não", "isso mesmo", "aham", "ok"):
        assert is_bare_polar_answer(text)
        assert is_semantically_empty_answer(text)
    assert not is_bare_polar_answer("Noemi voltou")
    assert is_semantically_empty_answer("não sei")
    assert not is_semantically_empty_answer("sim, Noemi voltou para Belém")


def test_excerpt_matching_ignores_case_and_spacing_but_not_content() -> None:
    assert is_exact_excerpt("NOEMI  voltou", "noemi voltou para belém")
    assert not is_exact_excerpt("noemi partiu", "noemi voltou")


def test_polarity_guard_accepts_a_plainly_asserted_quote() -> None:
    assert not semantic_excerpt_has_unresolved_polarity(
        "Noemi voltou", "Noemi voltou para Belém", positive_result=True
    )


def test_negation_dropping_guard_sees_nearby_negators() -> None:
    assert excerpt_drops_nearby_negation("voltou", "ela não voltou")
    assert not excerpt_drops_nearby_negation("não voltou", "ela não voltou")


def test_negation_dropping_guard_ignores_ordinary_portuguese_function_words() -> None:
    assert not excerpt_drops_nearby_negation("campo de Boaz", "Rute foi trabalhar no campo de Boaz")
    assert not excerpt_drops_nearby_negation(
        "tempo da colheita", "Noemi voltou para Belém no tempo da colheita"
    )
    assert not excerpt_drops_nearby_negation("para Belém", "Noemi voltou, né, para Belém")


class _ApprovingGuide:
    """A Guide that drafts one short line and a Validator that passes it."""

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


class _ScriptedAssessor:
    """The assessor call answering as this test's script says, one entry per call.

    ``raise`` breaks the transport, ``unreadable`` returns a reply no parser can use, and
    ``no_evidence`` returns a well-formed report that simply found nothing to quote. Once
    the script runs out the assessor works: a call a test did not plan for can only make
    the room healthier, never manufacture the failure the test is looking for.
    """

    def __init__(self, script: list[str]) -> None:
        self._script = list(script)

    async def __call__(self, **kwargs: Any) -> str:
        behaviour = self._script.pop(0) if self._script else "no_evidence"
        if behaviour == "raise":
            raise RuntimeError("assessor transport is down")
        if behaviour == "unreadable":
            return "desculpa, não consegui"
        return json.dumps(
            {
                "observations": [],
                "mother_tongue_practice_reported": False,
                "practice_evidence_excerpt": "",
            }
        )


@pytest.fixture
def guide_that_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", _ApprovingGuide())


def _assessor_answers(monkeypatch: pytest.MonkeyPatch, *script: str) -> None:
    module = sys.modules["app.services.internalization_room.comprehension.assessor"]
    monkeypatch.setattr(module, "call_agent", _ScriptedAssessor(list(script)))


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


async def _a_room_waiting_on_an_answer(db: AsyncSession) -> IRSession:
    session = await create_session(db, language="pt", pericope=P, bridge_mode="guided_microchecks")
    session = await append_exchange(
        db, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )
    target = next(checkpoint for checkpoint in checkpoints_for(P) if checkpoint.critical)
    state = comprehension_of(session)
    state.active_probe = ActiveProbe(
        id="probe-1",
        checkpoint_ids=[target.id],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )
    return await save_comprehension(db, session, state)


async def _the_team_answers(
    db: AsyncSession, session: IRSession, text: str = TEAM_ANSWER
) -> tuple[ComprehensionTurn, IRSession]:
    """One whole turn as the endpoint runs it, so what one turn leaves the next one reads."""
    turn = await run_comprehension_turn(
        db,
        session,
        speech=HeardSpeech(text=text),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    session = await set_bridge_mode(db, session, turn.bridge_mode)
    session = await save_comprehension(db, session, turn.state)
    session = await append_exchange(
        db, session, team_utterance=turn.outcome.transcript, guide_response=turn.outcome.speech
    )
    return turn, session


@pytest.mark.asyncio
async def test_an_assessor_that_cannot_be_reached_degrades_the_turn(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken assessor call is not an answer the room understood and found empty.

    Voicing an ordinary re-ask there tells the team their answer landed and was found
    wanting, and leaves the room free to ask the same question forever.
    """
    _assessor_answers(monkeypatch, "raise")
    session = await _a_room_waiting_on_an_answer(db_session)

    turn, _ = await _the_team_answers(db_session, session)

    assert turn.outcome.used_fail_safe
    assert turn.outcome.degraded
    assert turn.outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")


@pytest.mark.asyncio
async def test_an_assessor_reply_nobody_can_read_degrades_the_same_turn(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed JSON and a dead socket cost the room the same thing: the answer."""
    _assessor_answers(monkeypatch, "unreadable")
    session = await _a_room_waiting_on_an_answer(db_session)

    turn, _ = await _the_team_answers(db_session, session)

    assert turn.outcome.used_fail_safe
    assert turn.outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")


@pytest.mark.asyncio
async def test_an_on_topic_answer_with_no_evidence_is_still_an_ordinary_re_ask(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assessor read the answer and found nothing to quote — that is not a failure.

    This is the pair that keeps the fix from marking every empty-handed turn as broken.
    """
    _assessor_answers(monkeypatch, "no_evidence")
    session = await _a_room_waiting_on_an_answer(db_session)

    turn, _ = await _the_team_answers(db_session, session)

    assert not turn.outcome.used_fail_safe
    assert turn.outcome.speech == GUIDE_LINE


@pytest.mark.asyncio
async def test_three_assessor_failures_running_reach_the_hard_stop(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ladder the fail-safe policy promises: repeated failure stops looping and calls a
    person, instead of asking the same question a fourth time as though it were the first.

    Five turns to spend three failed calls: a fail-safe clears the active probe, so the turn
    after one never reaches the assessor at all.
    """
    _assessor_answers(monkeypatch, "raise", "raise", "raise")
    session = await _a_room_waiting_on_an_answer(db_session)

    spoken = []
    for _ in range(5):
        turn, session = await _the_team_answers(db_session, session)
        spoken.append(turn.outcome.speech)

    assert spoken[-1] in utterances(FailSafe.HARD_STOP, "pt")
    assert turn.outcome.used_fail_safe
    assert turn.outcome.degraded
    assert turn.outcome.needs_person


@pytest.mark.asyncio
async def test_a_reply_that_comes_back_clears_what_the_failures_owed(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hiccups spread over a working room never add up to a facilitator handoff.

    The room reaches a carry-to-refine offer before a third call is ever placed, which is
    the no-usable-report ladder doing its own job. What is pinned here is the whole path
    staying out of category E; the clearing rule itself is pinned on
    ``_assessor_failures_after``, where no other ladder can divert it.
    """
    _assessor_answers(monkeypatch, "raise", "no_evidence", "raise", "no_evidence", "raise")
    session = await _a_room_waiting_on_an_answer(db_session)

    spoken = []
    for _ in range(7):
        turn, session = await _the_team_answers(db_session, session)
        spoken.append(turn.outcome.speech)

    hard_stop = utterances(FailSafe.HARD_STOP, "pt")
    assert not any(line in hard_stop for line in spoken)


def test_only_a_reply_clears_what_the_failures_owed() -> None:
    """The three things a turn can learn about the assessor, and what each does to the count.

    Behaviour cannot reach this cleanly: the no-usable-report ladder offers carry-to-refine
    before a third call is placed, so an interleaved room never spends its failures.
    """
    assert _assessor_failures_after(2, TurnAssessment(observations=[], failed=True)) == 3

    replied = TurnAssessment(observations=[], assessment_completed=True, replied=True)
    assert _assessor_failures_after(2, replied) == 0

    never_asked = TurnAssessment(observations=[])
    assert _assessor_failures_after(2, never_asked) == 2

    settled_locally = TurnAssessment(
        observations=[], assessment_completed=True, no_usable_report=True
    )
    assert _assessor_failures_after(2, settled_locally) == 2


@pytest.mark.asyncio
async def test_a_shrug_mid_outage_does_not_clear_the_ladder(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "Não sei" is settled without asking anyone, so it is no proof the assessor is back.

    The room decides a semantically empty answer locally and never places the call. Counting
    that as a healthy reply would let one shrug during an outage zero the ladder, and a team
    that keeps shrugging at a room that keeps breaking would never reach a person.
    """
    _assessor_answers(monkeypatch, "raise", "raise", "raise")
    session = await _a_room_waiting_on_an_answer(db_session)

    turn, session = await _the_team_answers(db_session, session)
    turn, session = await _the_team_answers(db_session, session)
    turn, session = await _the_team_answers(db_session, session, text="não sei")
    for _ in range(3):
        turn, session = await _the_team_answers(db_session, session)

    assert turn.outcome.speech in utterances(FailSafe.HARD_STOP, "pt")
    assert turn.outcome.needs_person


@pytest.mark.asyncio
async def test_the_handoff_spends_the_count_it_was_owed(
    db_session: AsyncSession, guide_that_approves: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling a person is the escalation, so the next failure starts the ladder again.

    Otherwise every later failure of the same outage answers with the identical category-E
    sentence and asks for a person who is already standing there — which is the looping the
    policy asks the hard stop to end.
    """
    _assessor_answers(monkeypatch, "raise", "raise", "raise", "raise")
    session = await _a_room_waiting_on_an_answer(db_session)

    for _ in range(5):
        turn, session = await _the_team_answers(db_session, session)
    assert turn.outcome.needs_person

    for _ in range(2):
        turn, session = await _the_team_answers(db_session, session)

    assert turn.outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert not turn.outcome.needs_person
