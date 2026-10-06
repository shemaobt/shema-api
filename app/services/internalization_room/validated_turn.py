from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.services.internalization_room.fail_safe import validation_ladder
from app.services.internalization_room.llm import TruncatedReply, Turn, cache_break_before
from app.services.internalization_room.peer_cue import detects_peer_cue
from app.services.internalization_room.redraft_note import _redraft_note
from app.services.internalization_room.render import render
from app.services.internalization_room.room_agent import room_agent
from app.services.internalization_room.turn_instructions import (
    EARLIER_PASSAGES_HEADING,
    OPENING_MOVEMENT_INSTRUCTION,
    SPEAK_THIS_TURN,
    TEAM_EVIDENCE_HEADING,
    VALIDATOR_USER_MESSAGE,
    her_block,
    split_opening_movements,
)
from app.services.internalization_room.usage import (
    Spend,
    close_ledger,
    open_ledger,
    report_session,
)
from app.services.internalization_room.validator_reply import _issues_as_dicts, _parse_verdict
from app.services.platform.tts import warm_connection_in_background

logger = logging.getLogger(__name__)

MAX_REDRAFTS = 2

#: How many times one draft is put to the Validator before its reply is given up on.
READINGS_OF_ONE_DRAFT = 2


@dataclass
class TurnOutcome:
    speech: str
    transcript: str
    peer_cue: bool = False
    used_fail_safe: bool = False
    degraded: bool = False
    redrafts: int = 0
    issues: list[dict[str, Any]] = field(default_factory=list)
    #: Which pre-approved line was spoken, when one was. The app ships these as audio, so a
    #: fail-safe is named rather than synthesized — no TTS bill, no network, no waiting.
    fixed_line: str = ""
    #: The opening's two movements — the whole passage, then the scene and its invitation —
    #: when the Guide marked the boundary itself. Empty on every other turn and whenever the
    #: mark was not exactly where it was asked for; `speech` always stays the whole text.
    movements: list[str] = field(default_factory=list)
    #: The last words the Guide drafted and the last verdict the Validator gave on them, as
    #: it wrote it — empty when no draft was asked for, or when no reply could be read.
    #: They are what the record keeps of a firing, so a fail-safe can be read back later.
    draft: str = ""
    verdict: str = ""
    room_note: str = ""
    #: The turn the Guide was handed in the team's place: their words behind any room note,
    #: or the instruction it spoke on. Empty when no Guide was asked.
    guide_heard: str = ""


def _conversation_turns(messages: list[dict[str, Any]]) -> list[Turn]:
    """The session as the two speakers a model knows, oldest first and all of it.

    The room stores three: the team, its own notes, and the Guide. Which of the three is the
    assistant is the only thing being decided here — a room note collapses onto the team's
    side the same as the team's own words do, because the API knows only two roles, and
    nothing is left out — a session grows for as long as it runs, and what pays for the
    length is the cache, not a window.
    """
    return [
        Turn(
            role="assistant" if message.get("role") == "guide" else "user",
            text=str(message.get("text", "")),
        )
        for message in messages
    ]


def _refused(condition: str, raw: str, session_id: str, attempt: int) -> None:
    """Every refused Validator reply leaves itself behind, whole, with what refused it.

    Same idea as `back_translation._refused` on the Analyst side (ENG-719, a sibling change
    not yet on `main` as of this writing): the night of 2026-09-01 the room fell to the
    family-A fail-safe and nothing here said what the Validator had actually answered. The
    reply is logged whole rather than cut short — a truncated reply is exactly what could
    not be diagnosed — and it is the Validator's own output, not the team's speech, so the
    policy that keeps the team's words off this logger does not apply to it.
    """
    logger.warning(
        "Validator reply refused (%s) for session %s, attempt %s: %s",
        condition,
        session_id,
        attempt,
        raw,
        extra={"session_id": session_id, "attempt": attempt, "condition": condition},
    )


def _draft_rejected(condition: str, session_id: str, attempt: int, detail: str) -> None:
    """The room's own gate rejecting spoken text: the condition and a number, never the words.

    The rejected text is the Guide's draft on a `pass` verdict, or the Validator's own
    ``corrected_response`` on a `correct` one — either way ``detail`` may never be that text
    itself, because both can echo the team's own turn back at them, which is exactly what
    `test_a_failed_turn_logs_its_cause_and_never_what_the_team_said` forbids of the log.
    """
    logger.warning(
        "Guide draft rejected (%s) for session %s, attempt %s: %s",
        condition,
        session_id,
        attempt,
        detail,
        extra={"session_id": session_id, "attempt": attempt, "condition": condition},
    )


def _the_guides_turn(utterance: str, opening_instruction: str, ask_for_movements: bool) -> str:
    """The Speaker's last user turn, behind everything already said.

    What the team just said is that turn, on its own: the exchange it answers is the
    conversation, not a heading inside the question. The instructions that ride per turn —
    the opening, the two-movement mark — stay in that last message, which is where an
    instruction is read as this turn's and not as something said earlier.

    A turn with neither — the back-translation verdict — asks for its speech in the session's
    own language rather than sending nothing: the API refuses an empty user message, and that
    400 would reach the team as a fail-safe line.
    """
    if utterance:
        return utterance
    instruction = opening_instruction or SPEAK_THIS_TURN
    if ask_for_movements:
        return f"{instruction} {OPENING_MOVEMENT_INSTRUCTION}"
    return instruction


async def _draft(
    *,
    guide_prompt: str,
    conversation: list[Turn],
    turn: str,
    redraft_note: str,
    settings: Settings,
) -> str:
    """Ask the Speaker for this turn, with the rewrite note behind it when there is one."""
    user_content = turn
    if redraft_note:
        user_content += f"\n\n## Rewrite note\n\n{redraft_note}\n"
    draft: str = await room_agent().turn.call_agent(
        role="guide",
        system_prompt=guide_prompt,
        user_content=user_content,
        conversation=conversation,
        max_output_tokens=4096,
        settings=settings,
    )
    return draft.strip()


def _timed(
    outcome: TurnOutcome,
    started: float,
    session_id: str,
    spend: Spend,
    prepared_pericope: str | None = None,
) -> TurnOutcome:
    """Say how long the turn took, how it ended, and what it asked of the models.

    Both exits pass through here rather than each logging for itself, because the numbers only
    mean anything next to each other: a turn is allowed to take 56 seconds, and the way to tell
    that apart from a turn that gave up is whether it was voiced or fell to a line — and a turn
    that cost ten times the usual is a different thing again depending on whether it redrafted
    twice or read a 896-thousand-token map that stopped coming from cache.

    `spend` is the turn's own ledger and not a running total: what a redraft costs is only
    visible against turns that did not redraft. Every number it contributes is spelled
    `turn_*`, as `turn_ms` already was — a reader filtering the log for the per-call lines
    picks them out by the fields only a call has, and a summary that answered to the same
    names would be counted as a third call of every turn.

    `prepared_pericope`, when a `prepare_opening` run passed one down, is the one thing this
    line cannot say from `session_id` alone: that run shares the panorama's own id with
    whatever the panorama itself is doing, so two `[llm-turn]` lines under the same id used to
    read as the same turn firing twice (ENG-968, ENG-1107) when the second was a different
    pericope entirely.
    """
    elapsed_ms = round((time.monotonic() - started) * 1000)
    logger.info(
        "[llm-turn] session %s answered in %s ms after %s redrafts, %s calls, US$ %s: "
        "in=%s cache_read=%s cache_write=%s out=%s%s%s%s",
        session_id,
        elapsed_ms,
        outcome.redrafts,
        spend.calls,
        spend.cost_usd,
        spend.input_tokens,
        spend.cache_read_tokens,
        spend.cache_write_tokens,
        spend.output_tokens,
        f" — answered on rung {spend.rung_number}, {spend.rung_fell_because}"
        if spend.rung_number > 1
        else "",
        f" — {spend.unpriced_calls} unpriced, so the total is short"
        if spend.unpriced_calls
        else "",
        f" — prepared={prepared_pericope}" if prepared_pericope else "",
        extra={
            "session_id": session_id,
            "turn_ms": elapsed_ms,
            "redrafts": outcome.redrafts,
            "used_fail_safe": outcome.used_fail_safe,
            "prepared_pericope": prepared_pericope,
            "turn_calls": spend.calls,
            "turn_cost_usd": spend.cost_usd,
            "turn_unpriced_calls": spend.unpriced_calls,
            "turn_input_tokens": spend.input_tokens,
            "turn_output_tokens": spend.output_tokens,
            "turn_cache_read_tokens": spend.cache_read_tokens,
            "turn_cache_write_tokens": spend.cache_write_tokens,
            "turn_model_ms": spend.model_ms,
            "turn_rung_number": spend.rung_number,
            "turn_rung_fell_because": spend.rung_fell_because,
        },
    )
    report_session(session_id, spend)
    close_ledger()
    return outcome


async def _voiced_after_validation(
    *,
    speaker_system: str,
    validator_prompt: str,
    standard_of_truth: str,
    transcript: str,
    messages: list[dict[str, Any]],
    session_language: str,
    language_code: str,
    opening: bool,
    settings: Settings,
    session_id: str = "?",
    opening_instruction: str = "",
    ask_for_movements: bool = False,
    telling_back: str = "",
    mother_tongue: bool = False,
    prepared_pericope: str | None = None,
    earlier_passages: str = "",
) -> TurnOutcome:
    """Draft, gate, and only then voice — the rule that governs every session type.

    The Panorama runs through this too, with the book material standing where a passage
    session puts its map: containment is enforced twice either way.

    `mother_tongue` is the one case where `transcript` is not the team's own words in the
    session language — `turn.speech.speak_back` puts the app's own note there instead, so the
    Guide has something to draft against. The Validator's `{{TEAM_EVIDENCE}}` is quoted
    evidence of what the team *said*, under a heading no prompt tells it to read as a fact
    about the room rather than speech. Left alone, the slot would credit the team with a
    sentence in the session language it never spoke.

    The movement mark is cut from the draft and never from the validated speech: the Validator
    must judge exactly the words the team will hear, and it is told to write plain speakable
    text, so a mark left in front of it comes back either flagged or silently dropped. When the
    Validator returns a correction instead, the boundary the Guide drew no longer describes the
    speech, and one clip is the honest answer.

    A model or provider failure — a timeout, a rejected key, credits run out, a 5xx —
    rises out of here as the `UpstreamServiceError` that `call_agent` raises it as, and
    the route answers it with a 502 that names the cause. It used to be caught and spoken
    as the family-A fail-safe: the next tap failed the same way, and the team heard the
    same canned line over and over with nothing to say a person was needed. The only
    fail-safe this engine still speaks is the designed one — a Validator that will not
    settle after `MAX_REDRAFTS`, or one whose reply cannot be read twice over.

    A reply the room cannot read is not a verdict on the draft, so it costs a second
    reading of the same draft and never a redraft: the Guide's words were not judged, and
    sending them back to be rewritten spent the budget that keeps the Guide talking on a
    fault that was the Validator's. Only when the second reading is unreadable too does the
    family-A line answer, and the redrafts it reports are the ones actually spent.
    """
    started = time.monotonic()
    spend = open_ledger()
    conversation = _conversation_turns(messages)
    redraft_note = ""
    issues: list[dict[str, Any]] = []
    warmed_connection = False

    turn = _the_guides_turn("" if opening else transcript, opening_instruction, ask_for_movements)

    for attempt in range(MAX_REDRAFTS + 1):
        draft, movements = split_opening_movements(
            await _draft(
                guide_prompt=speaker_system,
                conversation=conversation,
                turn=turn,
                redraft_note=redraft_note,
                settings=settings,
            )
        )
        if not ask_for_movements:
            movements = []

        validator_system = render(
            cache_break_before(validator_prompt, "{{EARLIER_PASSAGES}}"),
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=standard_of_truth,
            EARLIER_PASSAGES=her_block(EARLIER_PASSAGES_HEADING, earlier_passages),
            TEAM_EVIDENCE=her_block(
                TEAM_EVIDENCE_HEADING, "" if mother_tongue else transcript or telling_back
            ),
            DRAFTED_RESPONSE=draft,
        )
        if not warmed_connection:
            warm_connection_in_background(
                api_key=settings.internalization_room_elevenlabs_api_key
                or settings.elevenlabs_api_key,
                settings=settings,
            )
            warmed_connection = True
        for _reading in range(READINGS_OF_ONE_DRAFT):
            try:
                raw_verdict = await room_agent().turn.call_agent(
                    role="validator",
                    system_prompt=validator_system,
                    user_content=VALIDATOR_USER_MESSAGE,
                    max_output_tokens=8192,
                    effort=None,
                    fails_on_truncation=True,
                    settings=settings,
                )
                verdict, refusal = _parse_verdict(raw_verdict)
            except TruncatedReply as cut:
                verdict, refusal, issues = {}, "reply cut at its ceiling", []
                _refused(refusal, cut.reply, session_id, attempt + 1)
                break
            issues = _issues_as_dicts(verdict.get("issues"))
            if refusal is None:
                break
            _refused(refusal, raw_verdict, session_id, attempt + 1)
        if refusal is not None:
            break

        speech = ""
        if verdict["verdict"] == "pass":
            speech = draft
        elif verdict["verdict"] == "correct":
            speech = str(verdict["corrected_response"]).strip()
            movements = []
        else:
            _refused(f"verdict is {verdict['verdict']!r}", raw_verdict, session_id, attempt + 1)

        if speech and bool(
            await asyncio.to_thread(room_agent().strays_from, speech, language_code)
        ):
            issues = [*issues, {"problem": "off_bridge_language"}]
            _draft_rejected(
                "off_bridge_language", session_id, attempt + 1, f"{len(speech)} characters"
            )
            speech = ""

        if speech:
            return _timed(
                TurnOutcome(
                    speech=speech,
                    transcript=transcript,
                    peer_cue=detects_peer_cue(speech),
                    redrafts=attempt,
                    issues=issues,
                    movements=movements,
                    draft=draft,
                    verdict=str(verdict["verdict"]),
                    guide_heard=turn,
                ),
                started,
                session_id,
                spend,
                prepared_pericope,
            )

        redraft_note = _redraft_note(issues)
    logger.warning("Fail-safe fired after %s redrafts: issues=%s", attempt, issues)

    speech, line = validation_ladder(messages, language_code)
    return _timed(
        TurnOutcome(
            speech=speech,
            transcript=transcript,
            used_fail_safe=True,
            degraded=True,
            redrafts=attempt,
            issues=issues,
            fixed_line=line,
            draft=draft,
            verdict=str(verdict.get("verdict", "")),
            guide_heard=turn,
        ),
        started,
        session_id,
        spend,
        prepared_pericope,
    )
