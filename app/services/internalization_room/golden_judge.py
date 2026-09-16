"""Her judge, reading a whole golden session and saying whether the Guide kept the doctrine.

The rubric and the pass rule are hers — `prompts/vendor/golden_judge_system_prompt.md`, "the
acceptance test that guards the app's behaviour across model and prompt changes" — and this
module applies them as she wrote them: the prompt body between her markers, the Validator's
map in the map slot, the session language in its slot, and her one-line request in front of
the transcript block. It never reaches the team; `scripts/golden_runner.py` calls it once per
session played.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.llm import cache_break_at_end, call_agent, voice_ladder
from app.services.internalization_room.prompt_blocks import validator_map_block
from app.services.internalization_room.render import render
from app.services.internalization_room.sessions import book_of

HER_PROMPT = Path(__file__).parent / "prompts/vendor/golden_judge_system_prompt.md"

#: Her request, verbatim (`src/golden/run.ts:132`): the transcript block follows two newlines on.
JUDGE_NOW = "Judge this session now. Return only the JSON object."

_MARKER = re.compile(r"^`?=== (BEGIN|END) SYSTEM PROMPT ===`?\s*$", re.M)

_SCORE = {"type": "integer", "minimum": 0, "maximum": 4}
_DIMENSIONS = (
    "understands_team",
    "answers_requests_to_understand",
    "frames_before_eliciting",
    "rehearsal_and_honest_checking",
    "silences_as_content",
    "containment",
    "register",
    "adaptivity",
)

#: The JSON object her prompt asks for, and nothing beside it: the eight dimensions scored 0 to 4,
#: every incident with its turn, severity, kind, quote and why, her own pass, her summary.
_VERDICT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": dict.fromkeys(_DIMENSIONS, _SCORE),
            "required": list(_DIMENSIONS),
            "additionalProperties": False,
        },
        "incidents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                    "kind": {"type": "string"},
                    "quote": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["turn", "severity", "kind", "quote", "why"],
                "additionalProperties": False,
            },
        },
        "pass": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["scores", "incidents", "pass", "summary"],
    "additionalProperties": False,
}


def _prompt_body(text: str) -> str:
    """What sits between her standalone marker lines; the notes outside them are for a reader.

    The markers are matched as whole lines, the way her `extractPromptBody` matches them,
    because the notes above the body mention the markers inline.
    """
    begin, end = _MARKER.finditer(text)
    return text[begin.end() : end.start()].strip()


async def judge_session(
    *, pericope: str, language: str, transcript: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Her judge on one session: the Validator's map, her budget, her effort, the voice ladder.

    Frontier on purpose. Her 5/5 of 2026-09-03 priced Guide, Validator and judge together on
    Fable 5.1, and a judge on a cheaper rung would be the one place in this system where a
    weaker model is nobody's build failure — so the ladder is the voice's, and the row this
    call takes in `docs/doctrine/MODEL_SEAM` is what stops it being moved quietly. The
    budget and the effort are the ones her `run.ts` gives it.
    """
    cfg = settings or get_settings()
    system = cache_break_at_end(
        render(
            _prompt_body(HER_PROMPT.read_text(encoding="utf-8")),
            MEANING_MAP=validator_map_block(pericope, book_of(pericope)),
            SESSION_LANGUAGE=language,
        )
    )
    raw = await call_agent(
        role="judge",
        system_prompt=system,
        user_content=f"{JUDGE_NOW}\n\n{transcript}",
        ladder=voice_ladder(cfg),
        max_output_tokens=4000,
        effort="high",
        thinks=True,
        schema=_VERDICT,
        settings=cfg,
    )
    parsed: dict[str, Any] = json.loads(raw)
    return parsed
