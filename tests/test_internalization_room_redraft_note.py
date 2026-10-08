import dataclasses
import re

import pytest

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import TurnOutcome, _redraft_note, run_turn
from tests.turn_harness import (
    GUIDE,
    VALIDATOR,
    FakeAgent,
    P,
    settings,
    the_agent_answers,
    the_room_agent_is,
)


def test_a_send_back_with_no_issue_named_carries_ungrounded_content() -> None:
    assert _redraft_note([]) == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: ungrounded content. Redraft the same answer, as fully as the team's "
        "request deserves, using only what the map contains.)"
    )


_FIVE_ISSUES = [
    {
        "problem": "invented_detail",
        "claim": "Noemi chorava na estrada",
        "explanation": "The map records no tears on the road.",
    },
    {
        "problem": "imported_knowledge",
        "claim": "Moabe ficava além do Jordão",
        "explanation": "The map gives no geography beyond Moab.",
    },
    {
        "problem": "softened_absence",
        "claim": "ninguém sabe por que ela voltou",
        "explanation": "The map marks the reason as deliberately absent.",
    },
    {
        "problem": "overstated_certainty",
        "claim": "Rute decidiu na mesma hora",
        "explanation": "The map leaves the moment of decision open.",
    },
    {
        "problem": "scrambled_structure",
        "claim": "primeiro a colheita, depois a despedida",
        "explanation": "The map orders the farewell before the harvest.",
    },
]

_HER_NOTE_FOR_FIVE_ISSUES = (
    "(internal redraft note — the previous draft carried something the map does not "
    "support: invented_detail: Noemi chorava na estrada — The map records no tears on the "
    "road.; imported_knowledge: Moabe ficava além do Jordão — The map gives no geography "
    "beyond Moab.; softened_absence: ninguém sabe por que ela voltou — The map marks the "
    "reason as deliberately absent.; overstated_certainty: Rute decidiu na mesma hora — The "
    "map leaves the moment of decision open.; scrambled_structure: primeiro a colheita, "
    "depois a despedida — The map orders the farewell before the harvest.. Redraft the same "
    "answer, as fully as the team's request deserves, using only what the map contains.)"
)


def test_a_draft_sent_back_with_five_issues_lists_all_five_with_their_reasons() -> None:
    assert _redraft_note(_FIVE_ISSUES) == _HER_NOTE_FOR_FIVE_ISSUES


def test_an_issue_with_no_explanation_lists_as_its_problem_and_claim_alone() -> None:
    issues = [
        {
            "claim": "vocês acrescentaram que ele deu a sandália pro Boaz",
            "problem": "invented_absence",
            "explanation": (
                "R5 accepts the team's telling 'deu pro Boaz': it is correct, not an addition."
            ),
        },
        {"claim": "segunda frase", "problem": "overstated_certainty"},
    ]

    assert _redraft_note(issues) == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: invented_absence: vocês acrescentaram que ele deu a sandália pro Boaz — R5 "
        "accepts the team's telling 'deu pro Boaz': it is correct, not an addition.; "
        "overstated_certainty: segunda frase. Redraft the same answer, as fully as the "
        "team's request deserves, using only what the map contains.)"
    )


_UNNAMED_PROBLEM_ISSUE = [{"claim": "Rute era moabita"}]


def test_an_issue_with_no_claim_lists_as_its_problem_alone() -> None:
    assert _redraft_note([{"problem": "invented_detail"}]) == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: invented_detail. Redraft the same answer, as fully as the team's request "
        "deserves, using only what the map contains.)"
    )


def test_an_issue_missing_its_problem_key_falls_back_to_the_english_word() -> None:
    note = _redraft_note(_UNNAMED_PROBLEM_ISSUE)

    assert "problem: Rute era moabita" in note


def test_a_row_the_validator_wrote_with_nulls_is_listed_and_never_raises() -> None:
    issues = [
        {"problem": None, "claim": "Rute era moabita", "explanation": None},
        {"problem": "invented_detail", "claim": None, "explanation": None},
    ]

    assert _redraft_note(issues) == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: problem: Rute era moabita; invented_detail. Redraft the same answer, as "
        "fully as the team's request deserves, using only what the map contains.)"
    )


_SAY_LESS = re.compile(r"say less|saying less|dizendo menos|diga menos", re.I)


@pytest.mark.parametrize("issues", [[], _FIVE_ISSUES])
def test_no_redraft_note_asks_the_guide_to_say_less(issues: list[dict[str, str]]) -> None:
    assert not _SAY_LESS.search(_redraft_note(issues))


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    def _install(agent: FakeAgent) -> FakeAgent:
        return the_agent_answers(monkeypatch, agent)

    return _install


async def _portuguese_turn() -> TurnOutcome:
    return await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="pergunta",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings(),
    )


async def test_a_portuguese_session_sent_back_reads_her_english_note(patch_agent) -> None:
    agent = patch_agent(
        FakeAgent(
            verdicts=[
                {
                    "verdict": "regenerate",
                    "issues": [
                        {
                            "problem": "imported_knowledge",
                            "claim": "Rute era moabita",
                            "explanation": "The map never names her people.",
                        }
                    ],
                },
                {"verdict": "pass", "issues": []},
            ]
        )
    )

    await _portuguese_turn()

    assert agent.guide_inputs[1] == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: imported_knowledge: Rute era moabita — The map never names her people.. "
        "Redraft the same answer, as fully as the team's request deserves, using only what "
        "the map contains.)"
    )


async def test_a_draft_blanked_for_leaving_the_language_gets_no_note_about_the_language(
    monkeypatch: pytest.MonkeyPatch, patch_agent
) -> None:
    agent = patch_agent(
        FakeAgent(verdicts=[{"verdict": "pass", "issues": []}, {"verdict": "pass", "issues": []}])
    )
    strays = iter([True, False])
    the_room_agent_is(monkeypatch, strays_from=lambda speech, language_code: next(strays))

    await _portuguese_turn()

    assert agent.guide_inputs[1] == (
        "(internal redraft note — the previous draft carried something the map does not "
        "support: off_bridge_language. Redraft the same answer, as fully as the team's "
        "request deserves, using only what the map contains.)"
    )


_SENT_BACK = {
    "verdict": "regenerate",
    "issues": [
        {
            "problem": "imported_knowledge",
            "claim": "Rute era moabita",
            "explanation": "The map never names her people.",
        }
    ],
}


@pytest.mark.parametrize(
    "verdicts",
    [[_SENT_BACK, {"verdict": "pass", "issues": []}], [_SENT_BACK, _SENT_BACK, _SENT_BACK]],
    ids=["redrafted-and-voiced", "sent-back-until-the-fail-safe"],
)
async def test_nothing_the_turn_keeps_carries_a_word_of_the_redraft_note(
    patch_agent, verdicts: list[dict[str, object]]
) -> None:
    agent = patch_agent(FakeAgent(verdicts=verdicts))

    outcome = await _portuguese_turn()

    assert "internal redraft note" in agent.guide_inputs[1]
    kept = str(dataclasses.asdict(outcome))
    assert "internal redraft note" not in kept
    assert "Redraft the same answer" not in kept
