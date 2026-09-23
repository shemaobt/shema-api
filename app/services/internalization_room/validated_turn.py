"""The draft-gate-voice engine every session type funnels through.

`call_agent`, `strays_from`, `MAX_REDRAFTS` and the logger are read off `run_turn` at call
time instead of being imported here. Thirty-four sites across twenty-three test files install
their fake model by writing over `run_turn.call_agent`, one writes over `run_turn.strays_from`,
and `tests/test_internalization_room_model_failure.py` asserts on records whose `record.name`
is exactly `app.services.internalization_room.run_turn`. A monkeypatch reaches a function only
through the globals of the module the function was defined in, so an ordinary
`from ... import call_agent` at the top of this file would leave every one of those fakes
unconsulted while the assertions went on passing — the suite would quietly start calling the
real model. The lookup sits inside the functions and never at module level: `run_turn` imports
this module, so a module-level import back would be a cycle that resolves only in the order the
first importer happens to use.

It goes through `importlib` rather than `import ... as` because the package's `__init__` binds
the *function* `run_turn` over the submodule of the same name, so `import
app.services.internalization_room.run_turn as shim` hands back the function and every attribute
read off it raises. The tests reach the same module the same way.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.services.internalization_room.fail_safe import validation_ladder
from app.services.internalization_room.llm import Turn, cache_break_before
from app.services.internalization_room.peer_cue import detects_peer_cue
from app.services.internalization_room.redraft_note import _redraft_note
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import (
    NOT_THIS_TURN,
    OPENING_MOVEMENT_INSTRUCTION,
    SPEAK_THIS_TURN,
    VALIDATOR_USER_MESSAGE,
    _nobody_spoke_this_turn,
    split_opening_movements,
)
from app.services.internalization_room.usage import (
    Spend,
    close_ledger,
    open_ledger,
    report_session,
)
from app.services.internalization_room.validator_reply import _issues_as_dicts, _parse_verdict

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


#: How each stored role is quoted back into the Validator's evidence block. Anything else
#: (the team's own words) falls through to "Team" below.
_EVIDENCE_LABELS = {"guide": "Guide", "room": "Room"}


def _conversation_as_evidence(messages: list[dict[str, Any]]) -> str:
    """The whole session, quoted, for the Validator to check a recollection against.

    The Guide hears every turn (no window), so it may say what the team told it three
    scenes ago. The Validator's evidence rule refuses any such sentence it cannot find in a
    record, and with the slot reading "not this turn" nothing could be found: a true
    recollection of the team's own words died as an "epistemic" violation and the team heard
    the pause line for asking what it had said. This is quoted evidence, never a window — it
    is all of it, oldest first, and the doctrine forbids the window, not the record.

    Takes the raw stored messages, not `Turn`s: a room note is stored as its own role
    (`sessions.append_exchange`), and the API's two-role `Turn` has already folded it onto
    the team's side by the time `_conversation_turns` is done with it. Quoting it back as
    `Team:` would credit the team with words it never said in the session language — this
    labels it `Room:` instead, the one thing the Guide's own prompt already knows to do with
    a bracketed note but the Validator's prompt is never told.
    """
    if not messages:
        return NOT_THIS_TURN
    return "\n".join(
        f"{_EVIDENCE_LABELS.get(str(message.get('role')), 'Team')}: {message.get('text', '')}"
        for message in messages
    )


def _refused(condition: str, raw: str, session_id: str, attempt: int) -> None:
    """Every refused Validator reply leaves itself behind, whole, with what refused it.

    Same idea as `back_translation._refused` on the Analyst side (ENG-719, a sibling change
    not yet on `main` as of this writing): the night of 2026-09-01 the room fell to the
    family-A fail-safe and nothing here said what the Validator had actually answered. The
    reply is logged whole rather than cut short — a truncated reply is exactly what could
    not be diagnosed — and it is the Validator's own output, not the team's speech, so the
    policy that keeps the team's words off this logger does not apply to it.
    """
    shim = importlib.import_module("app.services.internalization_room.run_turn")

    shim.logger.warning(
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
    shim = importlib.import_module("app.services.internalization_room.run_turn")

    shim.logger.warning(
        "Guide draft rejected (%s) for session %s, attempt %s: %s",
        condition,
        session_id,
        attempt,
        detail,
        extra={"session_id": session_id, "attempt": attempt, "condition": condition},
    )


async def _draft(
    *,
    guide_prompt: str,
    conversation: list[Turn],
    utterance: str,
    redraft_note: str,
    settings: Settings,
    opening_instruction: str = "",
    ask_for_movements: bool = False,
) -> str:
    """Assemble the Speaker's last user turn, behind everything already said.

    What the team just said is that turn, on its own: the exchange it answers is the
    conversation, not a heading inside the question. The instructions that ride per turn —
    the opening, the two-movement mark, the rewrite note — stay here, in the last message,
    which is where an instruction is read as this turn's and not as something said earlier.

    A turn with neither — the back-translation verdict — asks for its speech in the session's
    own language rather than sending nothing: the API refuses an empty user message, and that
    400 would reach the team as a fail-safe line. The fallback sits here and not at the call
    site, because this is where the message is built.
    """
    shim = importlib.import_module("app.services.internalization_room.run_turn")

    if utterance:
        user_content = utterance
    else:
        user_content = opening_instruction or SPEAK_THIS_TURN
        if ask_for_movements:
            user_content = f"{user_content} {OPENING_MOVEMENT_INSTRUCTION}"
    if redraft_note:
        user_content += f"\n\n## Rewrite note\n\n{redraft_note}\n"
    draft: str = await shim.call_agent(
        role="guide",
        system_prompt=guide_prompt,
        user_content=user_content,
        conversation=conversation,
        max_output_tokens=4096,
        settings=settings,
    )
    return draft.strip()


def _timed(outcome: TurnOutcome, started: float, session_id: str, spend: Spend) -> TurnOutcome:
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
    """
    shim = importlib.import_module("app.services.internalization_room.run_turn")

    elapsed_ms = round((time.monotonic() - started) * 1000)
    shim.logger.info(
        "[llm-turn] session %s answered in %s ms after %s redrafts, %s calls, US$ %s: "
        "in=%s cache_read=%s cache_write=%s out=%s%s%s",
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
        extra={
            "session_id": session_id,
            "turn_ms": elapsed_ms,
            "redrafts": outcome.redrafts,
            "used_fail_safe": outcome.used_fail_safe,
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
    finding: str = "",
    ordered_closing: str = "",
    mother_tongue: bool = False,
) -> TurnOutcome:
    """Draft, gate, and only then voice — the rule that governs every session type.

    The Panorama runs through this too, with the book material standing where a passage
    session puts its map: containment is enforced twice either way.

    `telling_back`, `finding` and `ordered_closing` are the verdict turn's own context — what
    the team told back outside the conversation, what the analyst found, and the ending the
    Speaker was ordered to write. Every other turn leaves them empty, and the Validator is told
    in words that an empty block is a block that does not apply to this turn rather than
    evidence being withheld, so nothing about a conversation turn changes.

    `mother_tongue` is the one case where `transcript` is not the team's own words in the
    session language — `turn.speech.speak_back` puts the app's own note there instead, so the
    Guide has something to draft against. The Validator's `{{TEAM_UTTERANCE}}` is quoted
    evidence of what the team *said*, under a heading no prompt tells it to read as a fact
    about the room rather than speech; this turn's note has not reached `messages` yet
    either, so nothing in `RECENT_CONVERSATION` catches it. Left alone, the slot would credit
    the team with a sentence in the session language it never spoke.

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
    shim = importlib.import_module("app.services.internalization_room.run_turn")

    started = time.monotonic()
    spend = open_ledger()
    conversation = _conversation_turns(messages)
    redraft_note = ""
    issues: list[dict[str, Any]] = []

    for attempt in range(shim.MAX_REDRAFTS + 1):
        draft, movements = split_opening_movements(
            await _draft(
                guide_prompt=speaker_system,
                conversation=conversation,
                utterance="" if opening else transcript,
                redraft_note=redraft_note,
                settings=settings,
                opening_instruction=opening_instruction,
                ask_for_movements=ask_for_movements,
            )
        )
        if not ask_for_movements:
            movements = []

        validator_system = render(
            cache_break_before(validator_prompt, "{{RECENT_CONVERSATION}}"),
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=standard_of_truth,
            RECENT_CONVERSATION=_conversation_as_evidence(messages),
            TEAM_UTTERANCE=(
                NOT_THIS_TURN
                if mother_tongue
                else transcript or _nobody_spoke_this_turn(telling_back)
            ),
            DRAFTED_RESPONSE=draft,
            TELLING_BACK=telling_back or NOT_THIS_TURN,
            FINDING=finding or NOT_THIS_TURN,
            ORDERED_CLOSING=ordered_closing or NOT_THIS_TURN,
        )
        for _reading in range(READINGS_OF_ONE_DRAFT):
            raw_verdict = await shim.call_agent(
                role="validator",
                system_prompt=validator_system,
                user_content=VALIDATOR_USER_MESSAGE,
                max_output_tokens=4096,
                settings=settings,
            )
            verdict, refusal = _parse_verdict(raw_verdict)
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

        if speech and await asyncio.to_thread(shim.strays_from, speech, language_code):
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
                ),
                started,
                session_id,
                spend,
            )

        redraft_note = _redraft_note(issues, language_code)
    shim.logger.warning("Fail-safe fired after %s redrafts: issues=%s", attempt, issues)

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
        ),
        started,
        session_id,
        spend,
    )
