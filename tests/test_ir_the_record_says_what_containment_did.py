"""What a session's own messages say about each turn the Guide took.

A guide message used to be a role and a text. Read back later, nothing in it said whether
the Validator passed the draft, mended it, or refused it and a fixed line spoke instead —
a facilitator export had to infer containment from a coverage projection. Her fail-safe
spec asks for more of every firing: the pericope, the scene, the team's words, the Guide's
draft, the Validator's verdict and issues, and which family answered.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import append_exchange, create_session

P = "P03"
TEAM = "a fome chegou"


async def test_a_passing_turn_is_recorded_as_a_pass_with_its_redrafts(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(speech="isso mesmo", transcript=TEAM, draft="isso mesmo", verdict="pass")

    session = await append_exchange(
        db_session, session, team_utterance=TEAM, guide_response="isso mesmo", outcome=outcome
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "isso mesmo",
        "outcome": "pass",
        "redrafts": 0,
    }


async def test_a_mended_turn_is_recorded_as_corrected(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(
        speech="isso mesmo",
        transcript=TEAM,
        redrafts=1,
        issues=[{"problem": "imported_knowledge"}],
        draft="isso mesmo, e Rute casou com Malom",
        verdict="correct",
    )

    session = await append_exchange(
        db_session, session, team_utterance=TEAM, guide_response="isso mesmo", outcome=outcome
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "isso mesmo",
        "outcome": "corrected",
        "redrafts": 1,
    }


async def test_a_fail_safe_is_recorded_with_everything_her_spec_asks_for(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    outcome = TurnOutcome(
        speech="Vamos com calma.",
        transcript=TEAM,
        used_fail_safe=True,
        degraded=True,
        redrafts=2,
        issues=[{"problem": "imported_knowledge", "claim": "Rute casou com Malom"}],
        fixed_line="A1",
        draft="Rute casou com Malom",
        verdict="regenerate",
    )

    session = await append_exchange(
        db_session,
        session,
        team_utterance=TEAM,
        guide_response="Vamos com calma.",
        outcome=outcome,
        scene="S1",
    )

    assert session.messages[-1] == {
        "role": "guide",
        "text": "Vamos com calma.",
        "outcome": "fail_safe",
        "redrafts": 2,
        "category": "A",
        "fixed_line": "A1",
        "pericope": P,
        "scene": "S1",
        "team_utterance": TEAM,
        "draft": "Rute casou com Malom",
        "verdict": "regenerate",
        "issues": [{"problem": "imported_knowledge", "claim": "Rute casou com Malom"}],
    }
