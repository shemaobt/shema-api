from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.bridge_language import strays_from
from app.services.internalization_room.canon.book_material import story_so_far
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import remaining
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)

MAX_REDRAFTS = 2
_RECENT_TURNS = 6

MAX_SPOKEN_TURN_WORDS = 45
MAX_SPOKEN_TURN_SENTENCES = 3


def spoken_turn_fits_budget(text: str) -> bool:
    words = len(text.split())
    sentences = len([part for part in re.split(r"[.!?…]+", text) if part.strip()])
    return words <= MAX_SPOKEN_TURN_WORDS and sentences <= MAX_SPOKEN_TURN_SENTENCES


_PEER_CUE_PHRASES = (
    "entre vocês",
    "entre voces",
    "conversem",
    "ensaiem",
    "ensaie",
    "na língua de vocês",
    "na lingua de voces",
)


@dataclass
class TurnOutcome:
    speech: str
    transcript: str
    peer_cue: bool = False
    used_fail_safe: bool = False
    redrafts: int = 0
    issues: list[dict[str, Any]] = field(default_factory=list)
    #: Which pre-approved line was spoken, when one was. The app ships these as audio, so a
    #: fail-safe is named rather than synthesized — no TTS bill, no network, no waiting.
    fixed_line: str = ""


def detects_peer_cue(speech: str) -> bool:
    """Whether the turn hands the talking to the team rather than back to the app.

    Read off the validated speech because the Guide returns prose, not a flag. It is a
    heuristic: a cleaner design would have the Guide mark the cue explicitly.
    """
    lowered = speech.casefold()
    return any(phrase in lowered for phrase in _PEER_CUE_PHRASES)


def coverage_status_block(coverage_state: dict[str, str], pericope_num: str) -> str:
    left = remaining(coverage_state, pericope_num)
    if not left:
        return "REMAINING: (nada — todos os elementos foram trabalhados pela equipe)"
    lines = ["REMAINING (ainda não trabalhados pela equipe, nas palavras deles):"]
    lines.extend(f"- [{element.key}] {element.label}" for element in left)
    return "\n".join(lines)


def meaning_map_block(pericope_num: str, book: str) -> str:
    """The passage's map verbatim, plus the digests of strictly earlier passages.

    The design document calls the Guide's standard of truth "MEANING MAP + story-so-far", and
    the earlier-only scoping is what keeps a later disclosure from reaching this session.
    """
    passage = load_map(pericope_num).body
    earlier = story_so_far(book, pericope_num)
    return f"{passage}\n\n{earlier}" if earlier else passage


def recent_conversation_block(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "(início da sessão — ainda não houve troca)"
    lines = []
    for message in messages[-_RECENT_TURNS:]:
        who = "EQUIPE" if message.get("role") == "team" else "FACILITADOR"
        lines.append(f"{who}: {message.get('text', '')}")
    return "\n".join(lines)


def _parse_verdict(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Validator returned unparseable JSON: %s", raw[:300])
        return {"verdict": "regenerate", "issues": [{"problem": "unparseable_verdict"}]}
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        return {"verdict": "regenerate", "issues": [{"problem": "unparseable_verdict"}]}
    return parsed


OPENING_INSTRUCTION = (
    "A sessão está começando agora e a equipe ainda não falou. Abra a sessão: "
    "apresente-se brevemente, dê à equipe o todo antes das partes, e convide."
)

ALREADY_MET_INSTRUCTION = (
    "A sessão desta passagem está começando agora e a equipe ainda não falou. "
    "Vocês acabaram de percorrer juntos o panorama do livro, então a equipe já "
    "conhece você: NÃO se apresente de novo nem diga seu nome. Entre direto na "
    "passagem: dê à equipe o todo antes das partes, e convide."
)


async def _draft(
    *,
    guide_prompt: str,
    conversation: str,
    utterance: str,
    redraft_note: str,
    settings: Settings,
    already_met: bool = False,
) -> str:
    if utterance:
        user_content = (
            f"## A conversa até aqui\n\n{conversation}\n\n"
            f"## O que a equipe acabou de dizer\n\n{utterance}\n"
        )
    else:
        opening = ALREADY_MET_INSTRUCTION if already_met else OPENING_INSTRUCTION
        user_content = f"## A conversa até aqui\n\n{conversation}\n\n{opening}\n"
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
    already_met: bool = False,
    validator_context: str = "",
    enforce_speech_budget: bool = False,
) -> TurnOutcome:
    """Draft, gate, and only then voice — the rule that governs every session type.

    The Panorama runs through this too, with the book material standing where a passage
    session puts its map: containment is enforced twice either way.
    """
    conversation = recent_conversation_block(messages)
    redraft_note = ""
    issues: list[dict[str, Any]] = []

    for attempt in range(MAX_REDRAFTS + 1):
        draft = await _draft(
            guide_prompt=speaker_system,
            conversation=conversation,
            utterance="" if opening else transcript,
            redraft_note=redraft_note,
            settings=settings,
            already_met=already_met,
        )

        validator_system = render(
            validator_prompt,
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=standard_of_truth,
            RECENT_CONVERSATION=conversation,
            TEAM_UTTERANCE=transcript or "(a equipe ainda não falou — abertura da sessão)",
            DRAFTED_RESPONSE=draft,
        )
        if validator_context:
            validator_system = f"{validator_system}\n\n{validator_context}"
        verdict = _parse_verdict(
            await call_agent(
                system_prompt=validator_system,
                user_content="Julgue a resposta rascunhada.",
                temperature=0.0,
                max_output_tokens=2000,
                settings=settings,
            )
        )
        issues = verdict.get("issues") or []

        speech = ""
        if verdict.get("verdict") == "pass":
            speech = draft
        elif verdict.get("verdict") == "correct":
            speech = (verdict.get("corrected_response") or "").strip()

        if speech and enforce_speech_budget and not spoken_turn_fits_budget(speech):
            issues = [*issues, {"problem": "over_speech_budget"}]
            speech = ""
        elif speech and strays_from(speech, language_code):
            issues = [*issues, {"problem": "off_bridge_language"}]
            speech = ""

        if speech:
            return TurnOutcome(
                speech=speech,
                transcript=transcript,
                peer_cue=detects_peer_cue(speech),
                redrafts=attempt,
                issues=issues,
            )

        redraft_note = _redraft_note(issues, session_language)

    off_language = any(i.get("problem") == "off_bridge_language" for i in issues)
    logger.warning("Fail-safe fired after %s redrafts: issues=%s", MAX_REDRAFTS, issues)
    speech, line = choose(
        FailSafe.OFF_BRIDGE_LANGUAGE if off_language else FailSafe.UNREPAIRABLE,
        language_code,
        turn=len(messages),
    )
    return TurnOutcome(
        speech=speech,
        transcript=transcript,
        used_fail_safe=True,
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
    session_language: str = "Portuguese",
    language_code: str = "pt",
    opening: bool = False,
    already_met: bool = False,
    settings: Settings | None = None,
    app_context: str = "",
    validator_context: str = "",
    enforce_speech_budget: bool = False,
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
        already_met=already_met,
        settings=cfg,
        validator_context=validator_context,
        enforce_speech_budget=enforce_speech_budget,
    )


async def run_panorama_turn(
    *,
    transcript: str,
    messages: list[dict[str, Any]],
    panorama_prompt: str,
    validator_prompt: str,
    book: str,
    book_material: str,
    session_language: str = "Portuguese",
    language_code: str = "pt",
    opening: bool = False,
    settings: Settings | None = None,
    validator_context: str = "",
    enforce_speech_budget: bool = False,
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
        settings=cfg,
        validator_context=validator_context,
        enforce_speech_budget=enforce_speech_budget,
    )


async def run_verdict_turn(
    *,
    findings_text: str,
    scope: str,
    pericope_num: str,
    messages: list[dict[str, Any]],
    speaker_prompt: str,
    validator_prompt: str,
    book: str = "Ruth",
    session_language: str = "Portuguese",
    language_code: str = "pt",
    settings: Settings | None = None,
) -> TurnOutcome:
    """Voice the back-translation verdict — one finding, then stop.

    The Speaker never sees the recording, only what the team told back, so its judgment is
    always about the telling-back. Runs through the Validator like every other voiced turn.
    """
    cfg = settings or get_settings()
    map_block = meaning_map_block(pericope_num, book)

    return await _voiced_after_validation(
        speaker_system=render(
            speaker_prompt,
            SESSION_LANGUAGE=session_language,
            SCOPE=scope,
            MEANING_MAP=map_block,
            FINDINGS=findings_text,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=map_block,
        transcript="",
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=True,
        settings=cfg,
    )


def _redraft_note(issues: list[dict[str, Any]], session_language: str = "português") -> str:
    if any(issue.get("problem") == "over_speech_budget" for issue in issues):
        return (
            "A resposta anterior era longa demais para uma sala oral. Refaça com no "
            f"máximo {MAX_SPOKEN_TURN_SENTENCES} frases curtas e "
            f"{MAX_SPOKEN_TURN_WORDS} palavras, um único movimento conversacional."
        )
    if any(issue.get("problem") == "off_bridge_language" for issue in issues):
        return (
            "A resposta anterior saiu do idioma da sessão e por isso não pôde ser "
            f"falada. Refaça o turno inteiro em {session_language}, sem nenhuma frase "
            "em outro idioma. O mapa está em inglês: carregue o sentido dele para o "
            "idioma da sessão em vez de citá-lo."
        )
    if not issues:
        return "A resposta anterior não passou na conferência. Refaça, dizendo menos."
    described = "; ".join(
        f"{issue.get('problem', 'problema')}: {issue.get('claim', '')}".strip(": ")
        for issue in issues[:3]
    )
    return (
        "A resposta anterior foi rejeitada na conferência contra o mapa. "
        f"Problemas apontados — {described}. "
        "Refaça o turno sem essas afirmações, dizendo menos."
    )
