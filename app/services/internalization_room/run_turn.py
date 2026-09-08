from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.bridge_language import strays_from
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.prompt_blocks import (
    coverage_status_block,
    meaning_map_block,
)
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import (
    ALREADY_MET_INSTRUCTION,
    NOT_THIS_TURN,
    OPENING_INSTRUCTION,
    OPENING_MOVEMENT_INSTRUCTION,
    OPENING_MOVEMENT_MARK,
    VALIDATOR_USER_MESSAGE,
    _nobody_spoke_this_turn,
    split_opening_movements,
)

__all__ = ["OPENING_MOVEMENT_MARK"]

logger = logging.getLogger(__name__)

MAX_REDRAFTS = 2
_RECENT_TURNS = 6

_PEER_CUE_PHRASES = (
    "entre vocês",
    "entre voces",
    "conversem",
    "ensaiem",
    "ensaie",
    "na língua de vocês",
    "na lingua de voces",
    "among yourselves",
    "talk it over",
    "rehearse",
    "in your own language",
    "entre ustedes",
    "conversen",
    "ensayen",
    "ensaye",
    "en su lengua",
    "en su propia lengua",
)


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
    needs_person: bool = False


def detects_peer_cue(speech: str) -> bool:
    """Whether the turn hands the talking to the team rather than back to the app.

    Read off the validated speech because the Guide returns prose, not a flag. It is a
    heuristic: a cleaner design would have the Guide mark the cue explicitly.
    """
    lowered = speech.casefold()
    return any(phrase in lowered for phrase in _PEER_CUE_PHRASES)


def recent_conversation_block(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "(início da sessão — ainda não houve troca)"
    lines = []
    for message in messages[-_RECENT_TURNS:]:
        who = "EQUIPE" if message.get("role") == "team" else "FACILITADOR"
        lines.append(f"{who}: {message.get('text', '')}")
    return "\n".join(lines)


_UNPARSEABLE_VERDICT: dict[str, Any] = {
    "verdict": "regenerate",
    "issues": [{"problem": "unparseable_verdict"}],
}


def _parse_verdict(raw: str) -> tuple[dict[str, Any], str | None]:
    """The Validator's reply as a verdict, and the condition that refused it when one did.

    A parse failure still returns a usable ``regenerate`` verdict — the loop above asks for
    another draft either way — but the second element names *why* this reply could not be
    trusted, so the caller can leave the trace `_refused` exists for instead of the silence
    that used to sit here for two of these three exits.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _UNPARSEABLE_VERDICT, "not JSON"
    if not isinstance(parsed, dict):
        return _UNPARSEABLE_VERDICT, "verdict reply is not a JSON object"
    if "verdict" not in parsed:
        return _UNPARSEABLE_VERDICT, "verdict reply has no 'verdict' key"
    return parsed, None


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
    `test_a_failed_call_is_logged_without_repeating_what_the_team_said` forbids on this
    logger.
    """
    logger.warning(
        "Guide draft rejected (%s) for session %s, attempt %s: %s",
        condition,
        session_id,
        attempt,
        detail,
        extra={"session_id": session_id, "attempt": attempt, "condition": condition},
    )


def _issues_as_dicts(raw: Any) -> list[dict[str, Any]]:
    """The Validator's ``issues`` in the shape every reader of them assumes.

    The field comes straight from a model, so its rows are whatever the model wrote and a
    list of strings is as likely as a list of objects. Every reader asks each row for
    ``problem``, and a bare string there raises in the middle of the generative path, where
    the cost is the whole turn instead of one rejected draft.
    """
    if not isinstance(raw, list):
        return []
    return [row if isinstance(row, dict) else {"problem": str(row)} for row in raw]


async def _draft(
    *,
    guide_prompt: str,
    conversation: str,
    utterance: str,
    redraft_note: str,
    settings: Settings,
    opening_instruction: str = "",
    ask_for_movements: bool = False,
) -> str:
    """Assemble the Speaker's user turn.

    An empty `opening_instruction` is a turn that opens nothing: the verdict Speaker has no
    team utterance to answer and no session to open either, so it is told neither.
    """
    if utterance:
        user_content = (
            f"## A conversa até aqui\n\n{conversation}\n\n"
            f"## O que a equipe acabou de dizer\n\n{utterance}\n"
        )
    elif opening_instruction:
        opening = opening_instruction
        if ask_for_movements:
            opening = f"{opening} {OPENING_MOVEMENT_INSTRUCTION}"
        user_content = f"## A conversa até aqui\n\n{conversation}\n\n{opening}\n"
    else:
        user_content = f"## A conversa até aqui\n\n{conversation}\n"
    if redraft_note:
        user_content += f"\n## Nota de reescrita\n\n{redraft_note}\n"
    return (
        await call_agent(
            system_prompt=guide_prompt,
            user_content=user_content,
            temperature=0.6,
            max_output_tokens=1200,
            settings=settings,
        )
    ).strip()


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
    validator_context: str = "",
    opening_instruction: str = "",
    ask_for_movements: bool = False,
    telling_back: str = "",
    finding: str = "",
    ordered_closing: str = "",
) -> TurnOutcome:
    """Draft, gate, and only then voice — the rule that governs every session type.

    The Panorama runs through this too, with the book material standing where a passage
    session puts its map: containment is enforced twice either way.

    `telling_back`, `finding` and `ordered_closing` are the verdict turn's own context — what
    the team told back outside the conversation, what the analyst found, and the ending the
    Speaker was ordered to write. Every other turn leaves them empty, and the Validator is told
    in words that an empty block is a block that does not apply to this turn rather than
    evidence being withheld, so nothing about a conversation turn changes.

    The movement mark is cut from the draft and never from the validated speech: the Validator
    must judge exactly the words the team will hear, and it is told to write plain speakable
    text, so a mark left in front of it comes back either flagged or silently dropped. When the
    Validator returns a correction instead, the boundary the Guide drew no longer describes the
    speech, and one clip is the honest answer.

    This is the boundary with the model, so it is where a model or transport failure stops:
    a timeout, a quota, a dead socket, or a reply shaped in a way no reader here expected
    comes out as the same fail-safe turn an exhausted redraft already produces. Letting it
    rise instead reaches the endpoint as a 500, and a tablet reads a 500 as the room itself
    being broken — which stops a session over an outage that lasted seconds.

    The ``try`` holds only the two calls and the reading of their replies. Everything the
    room decides for itself afterwards — the bridge-language check, the peer cue, the
    redraft note — sits outside it on purpose: a defect in one of those is ours,
    and answering it with an outage line would spend the team's turn hiding it in a log
    instead of surfacing it. ``Exception`` and not ``BaseException`` for the same kind of
    reason: a cancelled or interrupted turn has no team left to answer, and dressing
    shutdown up as an outage would keep the turn running past the point the runtime asked
    it to stop.
    """
    conversation = recent_conversation_block(messages)
    redraft_note = ""
    issues: list[dict[str, Any]] = []

    model_failed = False
    for attempt in range(MAX_REDRAFTS + 1):
        try:
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
                validator_prompt,
                SESSION_LANGUAGE=session_language,
                MEANING_MAP=standard_of_truth,
                RECENT_CONVERSATION=conversation,
                TEAM_UTTERANCE=transcript or _nobody_spoke_this_turn(telling_back, language_code),
                DRAFTED_RESPONSE=draft,
                TELLING_BACK=telling_back or NOT_THIS_TURN,
                FINDING=finding or NOT_THIS_TURN,
                ORDERED_CLOSING=ordered_closing or NOT_THIS_TURN,
            )
            if validator_context:
                validator_system = f"{validator_system}\n\n{validator_context}"
            raw_verdict = await call_agent(
                system_prompt=validator_system,
                user_content=VALIDATOR_USER_MESSAGE,
                temperature=0.0,
                max_output_tokens=2000,
                settings=settings,
            )
            verdict, refusal = _parse_verdict(raw_verdict)
            issues = _issues_as_dicts(verdict.get("issues"))

            speech = ""
            if refusal is None:
                if verdict.get("verdict") == "pass":
                    speech = draft
                elif verdict.get("verdict") == "correct":
                    speech = (verdict.get("corrected_response") or "").strip()
                    movements = []
                    if not speech:
                        refusal = "correct verdict has an empty corrected_response"
                else:
                    refusal = f"verdict is {verdict.get('verdict')!r}"
            if refusal is not None:
                _refused(refusal, raw_verdict, session_id, attempt + 1)
        except Exception:
            logger.exception(
                "Guide or Validator call failed; the turn degrades to a fail-safe",
                extra={"session_id": session_id, "attempt": attempt + 1},
            )
            model_failed = True
            break

        if speech and strays_from(speech, language_code):
            issues = [*issues, {"problem": "off_bridge_language"}]
            _draft_rejected(
                "off_bridge_language", session_id, attempt + 1, f"{len(speech)} characters"
            )
            speech = ""

        if speech:
            return TurnOutcome(
                speech=speech,
                transcript=transcript,
                peer_cue=detects_peer_cue(speech),
                redrafts=attempt,
                issues=issues,
                movements=movements,
            )

        redraft_note = _redraft_note(issues, language_code)
    else:
        logger.warning("Fail-safe fired after %s redrafts: issues=%s", MAX_REDRAFTS, issues)

    off_language = not model_failed and any(
        issue.get("problem") == "off_bridge_language" for issue in issues
    )
    speech, line = choose(
        FailSafe.OFF_BRIDGE_LANGUAGE if off_language else FailSafe.UNREPAIRABLE,
        language_code,
        turn=len(messages),
    )
    return TurnOutcome(
        speech=speech,
        transcript=transcript,
        used_fail_safe=True,
        degraded=True,
        redrafts=MAX_REDRAFTS,
        issues=issues,
        fixed_line=line,
    )


async def run_turn(
    *,
    transcript: str,
    coverage_state: dict[str, str],
    messages: list[dict[str, Any]],
    guide_prompt: str,
    validator_prompt: str,
    pericope_num: str,
    book: str = "Ruth",
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    opening: bool = False,
    already_met: bool = False,
    settings: Settings | None = None,
    session_id: str = "?",
    app_context: str = "",
    validator_context: str = "",
    ask_for_movements: bool = False,
) -> TurnOutcome:
    """One exchange of a passage session: the Guide drafts, the Validator gates.

    `opening` is the session's first turn, where the Guide speaks before the team has.
    `app_context` rides inside the Guide's COVERAGE_STATUS slot and `validator_context`
    is appended to the Validator's system — both are app-owned state (bridge mode,
    comprehension evidence, the active probe contract), never team speech.
    """
    cfg = settings or get_settings()

    if not opening and not transcript.strip():
        speech, line = choose(FailSafe.INAUDIBLE, language_code, turn=len(messages))
        return TurnOutcome(
            speech=speech,
            transcript="",
            used_fail_safe=True,
            degraded=True,
            fixed_line=line,
        )

    map_block = meaning_map_block(pericope_num, book)
    coverage_status = coverage_status_block(coverage_state, pericope_num)
    if app_context:
        coverage_status = f"{coverage_status}\n\n{app_context}"
    return await _voiced_after_validation(
        speaker_system=render(
            guide_prompt,
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=map_block,
            COVERAGE_STATUS=coverage_status,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=map_block,
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=(ALREADY_MET_INSTRUCTION if already_met else OPENING_INSTRUCTION),
        settings=cfg,
        session_id=session_id,
        validator_context=validator_context,
        ask_for_movements=ask_for_movements,
    )


async def run_panorama_turn(
    *,
    transcript: str,
    messages: list[dict[str, Any]],
    panorama_prompt: str,
    validator_prompt: str,
    book: str,
    book_material: str,
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    opening: bool = False,
    settings: Settings | None = None,
    session_id: str = "?",
    validator_context: str = "",
    ask_for_movements: bool = False,
) -> TurnOutcome:
    """One exchange of a Book Panorama — the session before a book's first passage.

    No coverage spine: a panorama never completes. The team has not lived any passage yet,
    so every one of the book's withholdings is still ahead of them.
    """
    cfg = settings or get_settings()

    if not opening and not transcript.strip():
        speech, line = choose(FailSafe.INAUDIBLE, language_code, turn=len(messages))
        return TurnOutcome(
            speech=speech,
            transcript="",
            used_fail_safe=True,
            degraded=True,
            fixed_line=line,
        )

    return await _voiced_after_validation(
        speaker_system=render(
            panorama_prompt,
            BOOK_NAME=book,
            SESSION_LANGUAGE=session_language,
            BOOK_MATERIAL=book_material,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=book_material,
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=OPENING_INSTRUCTION,
        settings=cfg,
        session_id=session_id,
        validator_context=validator_context,
        ask_for_movements=ask_for_movements,
    )


#: The slot a stored prompt row must carry for the closing to reach the Speaker.
CLOSING_SLOT = "{{CLOSING}}"

#: The slots a stored Validator row must carry for the verdict's own context to reach it.
#: Their absence is how this failed the first time: `render` drops a value whose placeholder
#: is not in the template without a word, so the Validator went on judging a verdict it could
#: not see the evidence for, and the team heard a fail-safe line with nothing to say why.
VALIDATOR_CONTEXT_SLOTS = ("{{TELLING_BACK}}", "{{FINDING}}", "{{ORDERED_CLOSING}}")


async def run_verdict_turn(
    *,
    findings_text: str,
    closing: str,
    scope: str,
    pericope_num: str,
    messages: list[dict[str, Any]],
    speaker_prompt: str,
    validator_prompt: str,
    telling_back: str = "",
    book: str = "Ruth",
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    settings: Settings | None = None,
    session_id: str = "?",
) -> TurnOutcome:
    """Voice the back-translation verdict — one finding, then stop.

    The Speaker never sees the recording, only what the team told back, so its judgment is
    always about the telling-back. Runs through the Validator like every other voiced turn.

    The Validator is handed the same three things the Speaker was: the finding, the telling-back
    and the closing it was ordered to end with. Without them it judged a draft that spoke of a
    telling-back against evidence saying nobody had spoken, and refused it — correctly, on what
    it had. This is stricter than what it replaced, not looser: a claim about the telling-back
    now has a record to be measured against, and a navigation instruction is legitimate only as
    far as the closing block goes.

    A missing slot is refused rather than rendered around, on both sides. A speaker prompt file
    saved before a slot existed would not carry it, and `render` drops a value whose placeholder
    is absent without a word — so the closing would never reach the Speaker and the turn would
    ask for a spoken answer while the screen waits for a tap, or the context would never reach
    the Validator and the verdict would fall to a fail-safe line in front of a team. Nothing
    anywhere would say so.
    """
    cfg = settings or get_settings()
    map_block = meaning_map_block(pericope_num, book)
    if CLOSING_SLOT not in speaker_prompt:
        raise ValidationError(
            f"The verdict speaker prompt has no {CLOSING_SLOT}: the closing would be dropped "
            "and the turn would ask for an answer the screen no longer collects"
        )
    absent = [slot for slot in VALIDATOR_CONTEXT_SLOTS if slot not in validator_prompt]
    if absent:
        raise ValidationError(
            f"The validator prompt has no {', '.join(absent)}: the verdict would be judged "
            "without the telling-back, the finding or the closing that was ordered, and a "
            "team would hear a fail-safe line instead of what was found"
        )

    spoken_closing = closing.format(session_language=session_language)

    return await _voiced_after_validation(
        speaker_system=render(
            speaker_prompt,
            SESSION_LANGUAGE=session_language,
            SCOPE=scope,
            MEANING_MAP=map_block,
            FINDINGS=findings_text,
            CLOSING=spoken_closing,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=map_block,
        transcript="",
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=True,
        settings=cfg,
        session_id=session_id,
        telling_back=telling_back,
        finding=findings_text,
        ordered_closing=spoken_closing,
    )


_OFF_BRIDGE_LANGUAGE_NOTE: dict[str, str] = {
    "pt": (
        "A resposta anterior saiu do idioma da sessão e por isso não pôde ser falada. "
        "Refaça o turno inteiro em {language}, sem nenhuma frase em outro idioma. O "
        "mapa está em inglês: carregue o sentido dele para o idioma da sessão em vez de "
        "citá-lo."
    ),
    "en": (
        "The previous response left the session's language and could not be spoken. "
        "Redo the whole turn in {language}, with no sentence in another language. The "
        "map is in English: carry its meaning into the session's language instead of "
        "quoting it."
    ),
    "es": (
        "La respuesta anterior salió del idioma de la sesión y por eso no pudo hablarse. "
        "Rehaz el turno completo en {language}, sin ninguna frase en otro idioma. El "
        "mapa está en inglés: lleva su sentido al idioma de la sesión en lugar de "
        "citarlo."
    ),
}

_LANGUAGE_AUTONYMS: dict[str, str] = {"en": "English", "es": "español", "pt": "português"}

_NO_ISSUES_NOTE: dict[str, str] = {
    "pt": "A resposta anterior não passou na conferência. Refaça.",
    "en": "The previous response did not pass review. Redo it.",
    "es": "La respuesta anterior no pasó la revisión. Rehazla.",
}

_DESCRIBED_ISSUES_NOTE: dict[str, str] = {
    "pt": (
        "A resposta anterior foi rejeitada na conferência contra o mapa. Problemas "
        "apontados — {described}. Refaça o turno sem essas afirmações."
    ),
    "en": (
        "The previous response was rejected against the map. Issues raised — "
        "{described}. Redo the turn without those claims."
    ),
    "es": (
        "La respuesta anterior fue rechazada frente al mapa. Problemas señalados — "
        "{described}. Rehaz el turno sin esas afirmaciones."
    ),
}


def _redraft_note(issues: list[dict[str, Any]], language_code: str = FLOOR) -> str:
    """What to tell a Guide whose draft did not pass, written in the session's own language."""
    if any(issue.get("problem") == "off_bridge_language" for issue in issues):
        template = _OFF_BRIDGE_LANGUAGE_NOTE.get(language_code, _OFF_BRIDGE_LANGUAGE_NOTE[FLOOR])
        autonym = _LANGUAGE_AUTONYMS.get(language_code, _LANGUAGE_AUTONYMS[FLOOR])
        return template.format(language=autonym)
    if not issues:
        return _NO_ISSUES_NOTE.get(language_code, _NO_ISSUES_NOTE[FLOOR])
    described = "; ".join(
        f"{issue.get('problem', 'problema')}: {issue.get('claim', '')}".strip(": ")
        for issue in issues[:3]
    )
    template = _DESCRIBED_ISSUES_NOTE.get(language_code, _DESCRIBED_ISSUES_NOTE[FLOOR])
    return template.format(described=described)
