from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.coverage import merge, remaining
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)


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
            verdict[new_status].append(element_id)
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
    session_language: str = "Portuguese",
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
    return merge(
        coverage_state,
        pericope_num=pericope_num,
        surfaced=verdict["surfaced"],
        partially_engaged=verdict["partially_engaged"],
        engaged=verdict["engaged"],
    )
