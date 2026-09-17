from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.elements import Element, element_keys
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import (
    CoverageStatus,
    merge,
    remaining,
    remaining_in_scene,
)
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import call_agent, classifier_ladder
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)

_BRACKETED_KEY = re.compile(r"^-?\s*\[([^\]]+)\]")

#: The shape the classifier is bound to answer in, and the same one `_parse` reads. The two
#: statuses are named here rather than left to the prompt's prose because a third word coming
#: back is a bead that quietly does not move: `_parse` has no bucket for it, and the session it
#: stalls looks from outside like a team that simply never covered the passage.
_DECISIONS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "string"},
                    "new_status": {
                        "type": "string",
                        "enum": ["surfaced", "engaged"],
                    },
                },
                "required": ["element_id", "new_status"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}

#: What the classifier's TEAM_UTTERANCE slot carries when nobody has spoken this turn.
#: Composed in English like every other backend instruction (ENG-822) — only
#: {{SESSION_LANGUAGE}} carries what language the team speaks.
_NO_TEAM_UTTERANCE_YET = "(the team has not spoken yet)"


def _element_id(named: str) -> str:
    """The element's key, whether the model sent it bare or as the list prints it.

    The unresolved set reaches the model as `- [being:B3] נָעֳמִי / Naomi`, and the output
    contract asks for "the id from the provided list". Read against that list, the id is the
    whole line, and that is what comes back. The key is its bracketed head; `merge` drops
    every other spelling as an element the passage does not hold.

    The list marker is admitted with it. Production echoes the line without the dash, so
    nothing today turns on this — but what is being fixed here is a spelling nobody thought
    to accept, and the dash is how the line is printed.
    """
    bracketed = _BRACKETED_KEY.match(named.strip())
    return bracketed.group(1).strip() if bracketed else named.strip()


def _report_unknown_elements(verdict: dict[str, list[str]], pericope_num: str) -> None:
    """Say when a decision names an element this passage does not hold.

    `merge` drops an unplaceable id on purpose — a key nobody can resolve is not evidence of
    anything — but it dropped it in silence, and a classifier answering entirely in ids the
    spine has never heard of is indistinguishable from one that found nothing to move. That
    is the gap this failure class keeps coming back through, three times now, and the log
    line is what makes the next one visible on the first turn rather than after two releases.
    """
    named = {key for bucket in verdict.values() for key in bucket}
    unknown = sorted(named - set(element_keys(pericope_num)))
    if unknown:
        logger.warning(
            "Coverage classifier named %d of %d elements %s does not hold: %s",
            len(unknown),
            len(named),
            pericope_num,
            unknown[:5],
        )


def _only_offered(verdict: dict[str, list[str]], offered: list[Element]) -> dict[str, list[str]]:
    """The decisions about beads this turn was shown; the rest are dropped, and said.

    `_report_unknown_elements` makes an id the passage does not hold visible. An id the
    passage holds but this turn did not offer — a bead from a scene nobody has opened, or
    one already engaged — used to pass through `merge` like any other, so the model could
    move a bead it was never asked about. It is inert now as well as visible.
    """
    keys = {element.key for element in offered}
    kept = {status: [key for key in named if key in keys] for status, named in verdict.items()}
    dropped = sorted({key for named in verdict.values() for key in named} - keys)
    if dropped:
        logger.warning(
            "Coverage classifier named %d elements not offered this turn: %s",
            len(dropped),
            dropped[:5],
        )
    return kept


def _shown_label(element: Element) -> str:
    return element.label + (f" — {element.detail}" if element.detail else "")


def _shown_status(coverage_state: dict[str, str], element: Element) -> str:
    """The word the classifier is told a bead stands at, out of the two its prompt names.

    A bead still stored under the retired `partially_engaged` is read below the floor
    exactly as `surfaced` is, so that is the word it is shown under: sending the retired
    word would name a status her prompt does not have, and not sending the bead at all
    would freeze it there for good.
    """
    standing = coverage_state.get(element.key, CoverageStatus.NOT_ENCOUNTERED.value)
    if standing == CoverageStatus.PARTIALLY_ENGAGED.value:
        return CoverageStatus.SURFACED.value
    return standing


def _offered(
    coverage_state: dict[str, str], pericope_num: str, scene_pointer: str | None
) -> list[Element]:
    """The beads this turn may move: the current scene's and the scene-less, or all of them.

    With no pointer there is no scene to narrow to, and the whole unresolved set goes as it
    always did. The pointer is `None` on a session where nobody has spoken and once every
    scene is engaged — the second leaves only the scene-less beads on either reading.
    """
    if scene_pointer is None:
        return remaining(coverage_state, pericope_num)
    return remaining_in_scene(coverage_state, pericope_num, scene_pointer)


def _unresolved_block(coverage_state: dict[str, str], offered: list[Element]) -> str:
    if not offered:
        return "(no elements pending)"
    return json.dumps(
        [
            {
                "id": element.key,
                "kind": element.kind.value,
                "label": _shown_label(element),
                "status": _shown_status(coverage_state, element),
            }
            for element in offered
        ],
        ensure_ascii=False,
        indent=2,
    )


def _scenes_block(pericope_num: str) -> str:
    scenes = load_map(pericope_num).scenes
    return json.dumps(
        [{"id": f"S{scene.number}", "title": scene.title} for scene in scenes],
        ensure_ascii=False,
        indent=2,
    )


def _the_object_in(text: str) -> str:
    """Her third fallback: the first brace to the last, when the object came wrapped in prose."""
    opens, closes = text.find("{"), text.rfind("}")
    if opens == -1 or closes < opens:
        return text
    return text[opens : closes + 1]


def _parse(raw: str) -> dict[str, list[str]]:
    """Bucket the classifier's decisions into the two lists `merge` advances.

    The reply's shape belongs to `prompts/classifier_system_prompt.md`, which asks for a
    `decisions` array. Reading two top-level status keys instead left both buckets empty on
    every well-formed reply, so no bead ever moved and no session ever reached done.

    The table carries one slot per status the prompt can send, and it is the same table on
    every exit. A status the prompt no longer names — `partially_engaged`, the band an echo
    used to land in — falls through to the log and moves nothing: a model still answering
    with it is a stale prompt, not a bead the team earned.

    It is built once and every exit answers that one. The caller indexes the result, so an
    exit answering a shorter dict raises `KeyError` out of the one path whose whole job is
    to leave coverage untouched — which is what three hand-written copies of the same
    literal were waiting to do the next time the scale grew.
    """
    verdict: dict[str, list[str]] = {"surfaced": [], "engaged": []}
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(_the_object_in(text))
    except json.JSONDecodeError:
        logger.warning("Coverage classifier returned unparseable JSON: %s", raw[:300])
        return verdict
    if not isinstance(parsed, dict):
        return verdict
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        logger.warning("Coverage classifier returned no decisions list: %s", raw[:300])
        return verdict
    for entry in decisions:
        element_id = entry.get("element_id") if isinstance(entry, dict) else None
        new_status = entry.get("new_status") if isinstance(entry, dict) else None
        if isinstance(element_id, str) and isinstance(new_status, str) and new_status in verdict:
            verdict[new_status].append(_element_id(element_id))
        else:
            logger.warning("Coverage classifier returned an unusable decision: %s", entry)
    return verdict


async def classify_coverage(
    *,
    coverage_state: dict[str, str],
    team_utterance: str,
    guide_response: str,
    classifier_prompt: str,
    pericope_num: str,
    scene_pointer: str | None = None,
    session_language: str = LANGUAGE_NAMES[FLOOR],
    settings: Settings | None = None,
) -> dict[str, str]:
    """Advance the tracker from one exchange. Never runs on the voice path.

    Any failure leaves coverage untouched: under-counting delays a session, while
    over-counting lets one complete hollow.

    The scene pointer is bookkeeping: it narrows what the classifier is shown to the scene
    the team is in, and it goes nowhere else — never to the Guide as a scope on what it may
    say, which DOCTRINE.md §3 forbids.
    """
    cfg = settings or get_settings()

    offered = _offered(coverage_state, pericope_num, scene_pointer)
    system = render(
        classifier_prompt,
        SESSION_LANGUAGE=session_language,
        SCENES=_scenes_block(pericope_num),
        COVERAGE_ELEMENTS=_unresolved_block(coverage_state, offered),
        TEAM_UTTERANCE=team_utterance or _NO_TEAM_UTTERANCE_YET,
        GUIDE_RESPONSE=guide_response,
    )

    try:
        raw = await call_agent(
            role="classifier",
            system_prompt=system,
            user_content="Classify this exchange now. Return only the JSON object.",
            ladder=classifier_ladder(cfg),
            max_output_tokens=4096,
            thinks=False,
            schema=_DECISIONS,
            settings=cfg,
        )
    except Exception:
        logger.exception("Coverage classification failed; leaving the tracker untouched")
        return coverage_state

    verdict = _parse(raw)
    _report_unknown_elements(verdict, pericope_num)
    verdict = _only_offered(verdict, offered)
    return merge(
        coverage_state,
        pericope_num=pericope_num,
        surfaced=verdict["surfaced"],
        engaged=verdict["engaged"],
    )
