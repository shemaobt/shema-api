from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.elements import Element, element_keys
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import CoverageStatus, merge, remaining
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_before, classifier_ladder
from app.services.internalization_room.render import render
from app.services.internalization_room.room_agent import room_agent

logger = logging.getLogger(__name__)

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

#: How many beads one reading of the exchange is shown. The doctrine fixes the reading's
#: output ceiling and its thinking spends out of the same ceiling, so a whole passage offered
#: at once came back cut mid-list; a reading this size finishes under it, and one that still
#: does not is read again in halves.
_BEADS_PER_READING = 11


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

    `_report_unknown_elements` makes an id the passage does not hold visible. A key the
    stored ledger still carries but the passage no longer holds is never offered, and
    `merge` would promote it like any other, so the model could move a bead it was never
    asked about. It is dropped as well as said.
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


def _unresolved_block(coverage_state: dict[str, str], offered: list[Element]) -> str:
    if not offered:
        return "[]"
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


def _parse(raw: str) -> dict[str, list[str]] | None:
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

    A reply that is not a decisions object at all — most often one cut off mid-list when the
    reading ran out of room — answers `None` rather than empty buckets: it says nothing about
    the beads it was shown, and reading it as "nothing moved" is what left a whole telling
    at 0 of 44. No prefix is salvaged from it.
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
        return None
    if not isinstance(parsed, dict):
        return None
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        logger.warning("Coverage classifier returned no decisions list: %s", raw[:300])
        return None
    for entry in decisions:
        element_id = entry.get("element_id") if isinstance(entry, dict) else None
        new_status = entry.get("new_status") if isinstance(entry, dict) else None
        if isinstance(element_id, str) and isinstance(new_status, str) and new_status in verdict:
            verdict[new_status].append(element_id.strip())
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
    session_language: str = LANGUAGE_NAMES[FLOOR],
    settings: Settings | None = None,
) -> dict[str, str]:
    """Advance the tracker from one exchange. Never runs on the voice path.

    Any failure leaves coverage untouched: under-counting delays a session, while
    over-counting lets one complete hollow.

    It is offered every bead still short of `engaged`, whatever scene the Scene pointer
    names. Narrowing the offer to the pointer's scene let one bead left at `surfaced` hold
    every later scene off the list for the rest of the session (ADR 0034).

    The offer is read in readings of `_BEADS_PER_READING`, each shown the same exchange and
    only its own beads, and merged once when every reading has landed. A reading that does
    not land is read again in halves, down to a single bead; one that still does not leaves
    the tracker untouched, because a classification applied in part lights beads by which
    reading happened to finish rather than by what the team told.
    """
    cfg = settings or get_settings()

    offered = remaining(coverage_state, pericope_num)
    readings = [
        offered[start : start + _BEADS_PER_READING]
        for start in range(0, max(len(offered), 1), _BEADS_PER_READING)
    ]
    gathered: dict[str, list[str]] = {"surfaced": [], "engaged": []}
    while readings:
        beads = readings.pop(0)
        system = render(
            cache_break_before(classifier_prompt, "{{COVERAGE_ELEMENTS}}"),
            SESSION_LANGUAGE=session_language,
            SCENES=_scenes_block(pericope_num),
            COVERAGE_ELEMENTS=_unresolved_block(coverage_state, beads),
            TEAM_UTTERANCE=team_utterance or _NO_TEAM_UTTERANCE_YET,
            GUIDE_RESPONSE=guide_response,
        )
        try:
            raw = await room_agent().classifier.call_agent(
                role="classifier",
                system_prompt=system,
                user_content="Classify this exchange now. Return only the JSON object.",
                ladder=classifier_ladder(cfg),
                max_output_tokens=6000,
                thinks=True,
                schema=_DECISIONS,
                settings=cfg,
            )
        except Exception:
            logger.exception("Coverage classification failed; leaving the tracker untouched")
            return coverage_state

        verdict = _parse(raw)
        if verdict is None:
            if len(beads) <= 1:
                logger.warning(
                    "Coverage reading of %s never landed; leaving the tracker untouched",
                    [element.key for element in beads],
                )
                return coverage_state
            half = len(beads) // 2
            logger.warning(
                "Coverage reading of %d beads did not land; read again in two halves",
                len(beads),
            )
            readings[:0] = [beads[:half], beads[half:]]
            continue
        _report_unknown_elements(verdict, pericope_num)
        for status, keys in _only_offered(verdict, beads).items():
            gathered[status].extend(keys)

    return merge(
        coverage_state,
        pericope_num=pericope_num,
        surfaced=gathered["surfaced"],
        engaged=gathered["engaged"],
    )


_WORD = re.compile(r"[a-z]{4,}")


def _words(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return set(_WORD.findall(plain))


async def classify_coverage_by_keywords(
    *,
    coverage_state: dict[str, str],
    team_utterance: str,
    guide_response: str,
    pericope_num: str,
    **_: object,
) -> dict[str, str]:
    """The classifier with no model in it: her keyword heuristic over the labels.

    A word of the team's that touches a bead's label engages it; a word of the Guide's
    surfaces it. It is offered exactly what the model would be — the same list, the same
    label with the map's prose — and it reads the words alone, so it is wrong in the ways
    a keyword match is wrong and never in a way that costs a call. It stands in for
    `classify_coverage` wherever a whole room has to run without a provider; the extra
    keywords the settle passes the real one are taken and ignored.
    """
    offered = remaining(coverage_state, pericope_num)
    team, guide = _words(team_utterance), _words(guide_response)
    engaged = [e.key for e in offered if _words(_shown_label(e)) & team]
    surfaced = [e.key for e in offered if e.key not in engaged and _words(_shown_label(e)) & guide]
    return merge(coverage_state, pericope_num=pericope_num, surfaced=surfaced, engaged=engaged)
