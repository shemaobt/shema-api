from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import merge, remaining
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)

_BRACKETED_KEY = re.compile(r"^-?\s*\[([^\]]+)\]")


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


def _unresolved_block(coverage_state: dict[str, str], pericope_num: str) -> str:
    left = remaining(coverage_state, pericope_num)
    if not left:
        return "(nenhum elemento pendente)"
    return "\n".join(f"- [{element.key}] {element.label}" for element in left)


def _scenes_block(pericope_num: str) -> str:
    scenes = load_map(pericope_num).scenes
    return "\n".join(
        f"- [scene:{scene.number}] {scene.title} ({scene.verses}): {scene.what_happens}"
        for scene in scenes
    )


def _parse(raw: str) -> dict[str, list[str]]:
    """Bucket the classifier's decisions into the three lists `merge` advances.

    The reply's shape belongs to `prompts/classifier_system_prompt.md`, which asks for a
    `decisions` array. Reading two top-level status keys instead left both buckets empty on
    every well-formed reply, so no bead ever moved and no session ever reached done.

    The table carries one slot per status the prompt can send, and it is the same table on
    every exit. It held two while the prompt sent three, and `partially_engaged` — the one
    status the completion floor was lowered to accept — fell through to the log on its way
    out. A passage the team worked on the Guide's terms could not close, which is most of
    how the preservation rules are worked at all.

    It is built once and every exit answers that one. The caller indexes the result, so an
    exit answering a shorter dict raises `KeyError` out of the one path whose whole job is
    to leave coverage untouched — which is what three hand-written copies of the same
    literal were waiting to do the next time the scale grew.
    """
    verdict: dict[str, list[str]] = {"surfaced": [], "partially_engaged": [], "engaged": []}
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
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
    session_language: str = LANGUAGE_NAMES[FLOOR],
    settings: Settings | None = None,
) -> dict[str, str]:
    """Advance the tracker from one exchange. Never runs on the voice path.

    Any failure leaves coverage untouched: under-counting delays a session, while
    over-counting lets one complete hollow.
    """
    cfg = settings or get_settings()

    system = render(
        classifier_prompt,
        SESSION_LANGUAGE=session_language,
        SCENES=_scenes_block(pericope_num),
        COVERAGE_ELEMENTS=_unresolved_block(coverage_state, pericope_num),
        TEAM_UTTERANCE=team_utterance or "(a equipe ainda não falou)",
        GUIDE_RESPONSE=guide_response,
    )

    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Classifique esta troca.",
            temperature=0.0,
            max_output_tokens=1500,
            settings=cfg,
        )
    except Exception:
        logger.exception("Coverage classification failed; leaving the tracker untouched")
        return coverage_state

    verdict = _parse(raw)
    _report_unknown_elements(verdict, pericope_num)
    return merge(
        coverage_state,
        pericope_num=pericope_num,
        surfaced=verdict["surfaced"],
        partially_engaged=verdict["partially_engaged"],
        engaged=verdict["engaged"],
    )
