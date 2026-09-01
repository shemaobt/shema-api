from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
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

#: What an app-owned block says when the turn has none. The Validator is shared with every
#: conversation turn, where there is no finding, no ordered closing and no telling-back, and
#: an empty heading there reads as evidence withheld rather than as a block that does not
#: apply. The prompt says so in words; this is the same sentence in the slot itself.
NOT_THIS_TURN = "(não se aplica a este turno)"

#: What the Validator is told when nobody spoke this turn. On the verdict path the team has
#: spoken — outside the conversation, into the telling-back — and the opening line said the
#: opposite, which is the sentence the Validator quoted back when it refused the verdict.
_NO_UTTERANCE_YET = "(a equipe ainda não falou — abertura da sessão)"
_TOLD_BACK_INSTEAD = (
    "(a equipe não falou nesta conversa; o que ela contou de volta está no bloco abaixo)"
)


def _nobody_spoke_this_turn(telling_back: str) -> str:
    """What stands where the team's utterance would, on a turn that had none."""
    return _TOLD_BACK_INSTEAD if telling_back else _NO_UTTERANCE_YET


MAX_SPOKEN_TURN_WORDS = 45
MAX_SPOKEN_TURN_SENTENCES = 3

MAX_SPOKEN_PANORAMA_WORDS = 90
MAX_SPOKEN_PANORAMA_SENTENCES = 6


@dataclass(frozen=True)
class SpeechBudget:
    """How much a single spoken movement may be.

    A ceiling per movement rather than one for the whole turn: the panorama that opens a
    passage has to carry the shape of the story and cannot say it in three sentences, while
    the scene that follows it — and every turn after — must stay short enough that a team
    hearing it once can hold it. Removing the ceiling from the opening altogether produced a
    ninety-second monologue, which is the thing the Guide's own prompt forbids.
    """

    words: int
    sentences: int

    def fits(self, text: str) -> bool:
        words = len(text.split())
        sentences = len([part for part in re.split(r"[.!?…]+", text) if part.strip()])
        return words <= self.words and sentences <= self.sentences


TURN_BUDGET = SpeechBudget(MAX_SPOKEN_TURN_WORDS, MAX_SPOKEN_TURN_SENTENCES)
PANORAMA_BUDGET = SpeechBudget(MAX_SPOKEN_PANORAMA_WORDS, MAX_SPOKEN_PANORAMA_SENTENCES)
OPENING_BUDGET = SpeechBudget(
    MAX_SPOKEN_PANORAMA_WORDS + MAX_SPOKEN_TURN_WORDS,
    MAX_SPOKEN_PANORAMA_SENTENCES + MAX_SPOKEN_TURN_SENTENCES,
)

OPENING_MOVEMENT_MARK = "[[CENA]]"
_MOVEMENT_MARK = re.compile(r"^[ \t]*\[\[CENA\]\][ \t]*$", re.M)


def spoken_turn_fits_budget(text: str) -> bool:
    return TURN_BUDGET.fits(text)


def split_opening_movements(draft: str) -> tuple[str, list[str]]:
    """The draft with the mark taken out, and its two movements when the mark is exact.

    The text comes back mark-free whatever happens: a marker read aloud by the synthesiser
    is the one outcome nothing downstream recovers from. The movements come back empty
    unless the mark stands exactly once, alone on its own line, with speech on both sides —
    a half-offered structure has to be indistinguishable from no structure at all, because
    an opening told in one breath is what the room already does well.
    """
    parts = _MOVEMENT_MARK.split(draft)
    clean = _MOVEMENT_MARK.sub("", draft).replace(OPENING_MOVEMENT_MARK, " ")
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if len(parts) != 2:
        return clean, []
    whole, scene = (part.strip() for part in parts)
    if not whole or not scene:
        return clean, []
    return clean, [whole, scene]


def _broken_ceiling(speech: str, movements: list[str], budget: SpeechBudget) -> SpeechBudget | None:
    """The ceiling the speech went over, or None when it fits."""
    if movements:
        for text, ceiling in zip(movements, (PANORAMA_BUDGET, TURN_BUDGET), strict=True):
            if not ceiling.fits(text):
                return ceiling
        return None
    return None if budget.fits(speech) else budget


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

OPENING_MOVEMENT_INSTRUCTION = (
    "Escreva esta abertura em dois movimentos, separados por uma linha contendo "
    f"apenas {OPENING_MOVEMENT_MARK} e nada mais. Antes da linha: o todo da "
    "passagem, o arco e o tom. Depois da linha: abra a primeira cena e convide. "
    "Não escreva a marca em nenhum outro lugar e não a comente."
)


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
    validator_context: str = "",
    budget: SpeechBudget | None = None,
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
    room decides for itself afterwards — the ceiling, the bridge-language check, the peer
    cue, the redraft note — sits outside it on purpose: a defect in one of those is ours,
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
                TEAM_UTTERANCE=transcript or _nobody_spoke_this_turn(telling_back),
                DRAFTED_RESPONSE=draft,
                TELLING_BACK=telling_back or NOT_THIS_TURN,
                FINDING=finding or NOT_THIS_TURN,
                ORDERED_CLOSING=ordered_closing or NOT_THIS_TURN,
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
            issues = _issues_as_dicts(verdict.get("issues"))

            speech = ""
            if verdict.get("verdict") == "pass":
                speech = draft
            elif verdict.get("verdict") == "correct":
                speech = (verdict.get("corrected_response") or "").strip()
                movements = []
        except Exception:
            logger.exception("Guide or Validator call failed; the turn degrades to a fail-safe")
            model_failed = True
            break

        broken = _broken_ceiling(speech, movements, budget) if speech and budget else None
        if broken is not None:
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
                movements=movements,
            )

        redraft_note = _redraft_note(issues, session_language, ceiling=broken)
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
    session_language: str = "Portuguese",
    language_code: str = "pt",
    opening: bool = False,
    already_met: bool = False,
    settings: Settings | None = None,
    app_context: str = "",
    validator_context: str = "",
    budget: SpeechBudget | None = None,
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
        validator_context=validator_context,
        budget=budget,
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
    session_language: str = "Portuguese",
    language_code: str = "pt",
    opening: bool = False,
    settings: Settings | None = None,
    validator_context: str = "",
    budget: SpeechBudget | None = None,
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
        validator_context=validator_context,
        budget=budget,
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
    session_language: str = "Portuguese",
    language_code: str = "pt",
    settings: Settings | None = None,
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

    A missing slot is refused rather than rendered around, on both sides. `get_prompt_text`
    prefers the stored row, a row written before a slot existed does not have it, and `render`
    drops a value whose placeholder is absent without a word — so the closing would never reach
    the Speaker and the turn would ask for a spoken answer while the screen waits for a tap, or
    the context would never reach the Validator and the verdict would fall to a fail-safe line
    in front of a team. Nothing anywhere would say so.
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
        telling_back=telling_back,
        finding=findings_text,
        ordered_closing=spoken_closing,
    )


def _redraft_note(
    issues: list[dict[str, Any]],
    session_language: str = "português",
    ceiling: SpeechBudget | None = None,
) -> str:
    """What to tell a Guide whose draft did not pass, written in the session's own language.

    The ceiling quoted back is the one that actually broke, not the smallest one there is:
    telling a Guide that busted the panorama to redraft in three sentences asks for the wrong
    turn.
    """
    if any(issue.get("problem") == "over_speech_budget" for issue in issues):
        held = ceiling or TURN_BUDGET
        return (
            "A resposta anterior era longa demais para uma sala oral. Refaça com no "
            f"máximo {held.sentences} frases curtas e {held.words} palavras."
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
