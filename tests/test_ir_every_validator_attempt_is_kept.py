"""ENG-1200 — a Guide turn keeps every attempt the Validator saw, whatever became of the turn.

The consultant reads a turn back to see what the Guide drafted, what the Validator made of
each draft, and what the room added. The cases script the Guide's drafts and the Validator's
replies, take a real turn through the room's own door, and read the stored session back.
"""

import json
from typing import Any
from unittest.mock import ANY

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.back_translation import closing_block, findings_block
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.part_names import Addresses
from app.services.internalization_room.prepare_opening import hand_over, prepare_opening
from app.services.internalization_room.run_turn import TurnOutcome, run_verdict_turn
from app.services.internalization_room.sessions import append_exchange, create_session, get_session
from app.services.internalization_room.validated_turn import MAX_REDRAFTS
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client
from tests.room_route_audit_harness import models_in, room_app_routes
from tests.turn_harness import SPEAKER, VALIDATOR, settings, the_room_agent_is, the_speaker_answers

TEAM = "a fome chegou"
ATTEMPT_FIELDS = {"attempts", "draft", "verdict", "corrected", "corrected_response"}


def _verdict(verdict: str, issues: list[dict[str, str]] | None = None, **rest: str) -> str:
    return json.dumps({"verdict": verdict, "issues": issues or [], **rest})


def _issue(problem: str, claim: str) -> dict[str, str]:
    return {"problem": problem, "claim": claim, "explanation": f"porque {claim}"}


class _Model:
    """A Guide that drafts the lines it was given, and a Validator that answers as scripted."""

    def __init__(self, drafts: list[str], replies: list[str]) -> None:
        self.drafts = drafts
        self.replies = replies
        self.drafted = 0
        self.judged = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" not in system_prompt:
            self.drafted += 1
            return self.drafts[self.drafted - 1]
        self.judged += 1
        return self.replies[self.judged - 1]


async def _heard(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text=TEAM)


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/t.mp3"
    )
    return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
def the_room_hears(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    def _install(drafts: list[str], replies: list[str], **seams: Any) -> None:
        the_room_agent_is(monkeypatch, turn=_Model(drafts, replies), **seams)

    return _install


async def _a_turn(client, db_session: AsyncSession, session_id: str) -> dict[str, Any]:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert answered.status_code == 200, answered.text[:300]
    return (await get_session(db_session, session_id)).messages[-1]


async def _a_session(db_session: AsyncSession):
    session = await create_session(db_session, language="pt", pericope=P)
    await append_exchange(db_session, session, team_utterance="a fome", guide_response="…")
    return session


async def test_a_turn_passed_on_the_first_attempt_keeps_one_attempt_with_its_draft_and_pass(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(["Vamos ficar nesta cena."], [_verdict("pass")])
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["attempts"] == [
        {"attempt": 1, "draft": "Vamos ficar nesta cena.", "verdict": "pass", "issues": []}
    ]


async def test_a_turn_sent_back_once_then_passed_keeps_two_attempts_the_first_with_every_issue(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    issues = [_issue("imported_knowledge", "Rute casou"), _issue("leading", "diga que sim")]
    the_room_hears(
        ["Rute casou com Malom.", "O que Rute fez?"],
        [_verdict("regenerate", issues), _verdict("pass")],
    )
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["attempts"] == [
        {"attempt": 1, "draft": "Rute casou com Malom.", "verdict": "regenerate", "issues": issues},
        {"attempt": 2, "draft": "O que Rute fez?", "verdict": "pass", "issues": []},
    ]


async def test_a_turn_the_validator_corrected_keeps_the_corrected_text_on_its_attempt(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    issue = _issue("imported_knowledge", "Rute casou")
    the_room_hears(
        ["Rute casou com Malom."],
        [_verdict("correct", [issue], corrected_response="O que Rute fez?")],
    )
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["text"] == "O que Rute fez?"
    assert kept["attempts"] == [
        {
            "attempt": 1,
            "draft": "Rute casou com Malom.",
            "verdict": "correct",
            "issues": [issue],
            "corrected": "O que Rute fez?",
        }
    ]


async def test_a_turn_that_ended_in_a_fail_safe_keeps_all_its_attempts(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    drafts = [f"rascunho {n}" for n in range(1, MAX_REDRAFTS + 2)]
    issues = [[_issue("imported_knowledge", f"afirmacao {n}")] for n in range(len(drafts))]
    the_room_hears(drafts, [_verdict("regenerate", found) for found in issues])
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["outcome"] == "fail_safe"
    assert kept["category"] == "A"
    assert kept["fixed_line"].startswith("A")
    assert kept["draft"] == drafts[-1]
    assert kept["verdict"] == "regenerate"
    assert kept["issues"] == issues[-1]
    assert kept["attempts"] == [
        {"attempt": n, "draft": draft, "verdict": "regenerate", "issues": found}
        for n, (draft, found) in enumerate(zip(drafts, issues, strict=True), start=1)
    ]


async def test_an_attempt_whose_validator_reply_could_not_be_read_keeps_its_draft_and_attempt_note(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    partial = json.dumps({"issues": [_issue("imported_knowledge", "Rute casou")]})
    the_room_hears(["Vamos ficar nesta cena."], [partial, partial])
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["outcome"] == "fail_safe"
    assert kept["attempts"] == [
        {"attempt": 1, "draft": "Vamos ficar nesta cena.", "issues": [], "note": ANY}
    ]
    assert kept["attempts"][0]["note"].strip()


async def test_an_attempt_that_strayed_from_the_bridge_language_keeps_the_attempt_note_and_issue(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(
        ["Let us stay in this scene.", "Vamos ficar nesta cena."],
        [_verdict("pass"), _verdict("pass")],
        strays_from=lambda text, _language: text.startswith("Let us"),
    )
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["attempts"] == [
        {
            "attempt": 1,
            "draft": "Let us stay in this scene.",
            "verdict": "pass",
            "issues": [{"problem": "off_bridge_language"}],
            "note": ANY,
        },
        {"attempt": 2, "draft": "Vamos ficar nesta cena.", "verdict": "pass", "issues": []},
    ]
    assert kept["attempts"][0]["note"].strip()


async def test_a_turn_stored_before_attempts_were_kept_is_read_back_without_invented_attempts(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(["O que Rute fez?"], [_verdict("pass")])
    session = await create_session(db_session, language="pt", pericope=P)
    old = [
        {
            "role": "guide",
            "text": "Vamos com calma.",
            "outcome": "fail_safe",
            "redrafts": 2,
            "fixed_line": "A1",
            "draft": "Rute casou com Malom",
            "verdict": "regenerate",
            "issues": [{"problem": "imported_knowledge"}],
        },
        {"role": "guide", "text": "O que Rute fez?", "outcome": "corrected", "redrafts": 1},
    ]
    session.messages = old
    await db_session.commit()

    await _a_turn(client, db_session, session.id)
    reread = (await get_session(db_session, session.id)).messages

    assert reread[:2] == old
    assert [m["role"] for m in reread[2:]] == ["team", "guide"]
    assert len(reread[-1]["attempts"]) == 1


async def test_what_the_validator_sent_beyond_problem_claim_and_explanation_is_not_kept(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    reply = (
        '{"verdict": "pass", "issues": [{"problem": "p", "claim": "c", "explanation": "e", '
        '"weight": NaN}], "confidence": Infinity}'
    )
    the_room_hears(["O que Rute fez?"], [reply])
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["attempts"][0]["issues"] == [{"problem": "p", "claim": "c", "explanation": "e"}]
    json.dumps((await get_session(db_session, session.id)).messages, allow_nan=False)


async def test_a_fail_safe_turn_whose_validator_reply_carried_a_nan_extra_is_stored_as_plain_json(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    reply = (
        '{"verdict": "regenerate", "issues": [{"problem": "p", "claim": "c", '
        '"explanation": "e", "weight": NaN}]}'
    )
    the_room_hears([f"rascunho {n}" for n in range(MAX_REDRAFTS + 1)], [reply] * (MAX_REDRAFTS + 1))
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["outcome"] == "fail_safe"
    assert kept["issues"] == [{"problem": "p", "claim": "c", "explanation": "e"}]
    json.dumps((await get_session(db_session, session.id)).messages, allow_nan=False)


async def test_a_telling_back_verdict_turn_keeps_its_attempts(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_speaker_answers(monkeypatch, "A passagem foi contada e conferida.")
    outcome = await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block([], Addresses()),
        closing=closing_block(None, checked=True),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )
    session = await create_session(db_session, language="pt", pericope=P)

    session = await append_exchange(
        db_session,
        session,
        team_utterance="",
        guide_response=outcome.speech,
        outcome=outcome,
        told_back="1. Noemi mandou Rute voltar.",
    )

    assert session.messages[-1]["attempts"] == [
        {
            "attempt": 1,
            "draft": "A passagem foi contada e conferida.",
            "verdict": "pass",
            "issues": [],
        }
    ]


async def test_a_prepared_opening_once_taken_is_stored_with_its_attempts(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears([], [])
    attempts = [{"attempt": 1, "draft": "Vamos começar.", "verdict": "pass", "issues": []}]
    session = await create_session(db_session, language="pt", pericope=P)
    session.prepared_speech = "Vamos começar."
    session.prepared_audio_key = "clips/prepared.mp3"
    session.prepared_pericope = P
    session.prepared_attempts = attempts
    await db_session.commit()

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}
    )

    assert answered.status_code == 200, answered.text[:300]
    reread = await get_session(db_session, session.id)
    assert reread.messages[-1]["attempts"] == attempts
    assert reread.prepared_attempts is None


async def test_a_prepared_opening_keeps_its_attempts_while_it_waits_and_on_hand_over(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = [{"attempt": 1, "draft": "Vamos começar.", "verdict": "pass", "issues": []}]

    async def _drafted(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech="Vamos começar.", transcript="", attempts=attempts)

    monkeypatch.setattr(prepare_opening_module, "run_turn", _drafted)
    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", _voice)
    panorama = await create_session(db_session, language="pt", pericope="OV-Ruth")
    passage = await create_session(db_session, language="pt", pericope=P)

    await prepare_opening(panorama.id, pericope=P)
    await db_session.refresh(panorama)
    handed = hand_over(panorama, passage)

    assert handed is True
    assert passage.prepared_attempts == attempts
    assert panorama.prepared_attempts is None


async def test_the_teams_tablet_receives_none_of_the_attempts(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(
        ["SENTINELA-RASCUNHO-REJEITADO", "O que Rute fez?"],
        [
            _verdict("regenerate", [_issue("imported_knowledge", "SENTINELA-AFIRMACAO")]),
            _verdict("pass"),
        ],
    )
    session = await _a_session(db_session)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text[:300]
    assert ATTEMPT_FIELDS.isdisjoint(answered.json())
    assert "SENTINELA" not in answered.text
    reachable = {model for route in room_app_routes() for model in models_in(route.response_model)}
    assert [m.__name__ for m in reachable if "attempts" in m.model_fields] == []


async def test_keeping_attempts_changes_nothing_the_team_hears(
    client, db_session: AsyncSession, the_room_hears
) -> None:
    the_room_hears(
        ["Rute casou com Malom.", "O que Rute fez?"],
        [_verdict("regenerate", [_issue("imported_knowledge", "Rute casou")]), _verdict("pass")],
    )
    session = await _a_session(db_session)

    kept = await _a_turn(client, db_session, session.id)

    assert kept["text"] == "O que Rute fez?"
    assert kept["redrafts"] == 1
    assert kept["outcome"] == "pass"
