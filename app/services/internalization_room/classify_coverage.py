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
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Coverage classifier returned unparseable JSON: %s", raw[:300])
        return {"engaged": [], "surfaced": []}
    if not isinstance(parsed, dict):
        return {"engaged": [], "surfaced": []}
    engaged = [k for k in parsed.get("engaged", []) if isinstance(k, str)]
    surfaced = [k for k in parsed.get("surfaced", []) if isinstance(k, str)]
    return {"engaged": engaged, "surfaced": surfaced}


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
        engaged=verdict["engaged"],
    )
