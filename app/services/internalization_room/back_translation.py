from __future__ import annotations

import enum
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.render import render

logger = logging.getLogger(__name__)


class FindingKind(enum.StrEnum):
    MISSING = "missing"
    ADDITION = "addition"
    UNCLEAR = "unclear"


class Finding(BaseModel):
    kind: FindingKind
    note: str


class Chunk(BaseModel):
    index: int
    text: str
    pass_number: int = 1


class BackTranslationState(BaseModel):
    scope: str = ""
    chunks: list[Chunk] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    checked: bool = False
    pass_number: int = 1

    @property
    def current_finding(self) -> Finding | None:
        """The one finding the Speaker is allowed to voice this turn."""
        return self.findings[0] if self.findings else None


def segments_block(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(a equipe ainda não contou nada de volta)"
    return "\n".join(f"{chunk.index}. {chunk.text}" for chunk in chunks)


def _parse_findings(raw: str) -> list[Finding]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("BT analyst returned unparseable JSON: %s", raw[:300])
        return []
    if not isinstance(parsed, dict):
        return []

    findings: list[Finding] = []
    for entry in parsed.get("findings", []):
        if not isinstance(entry, dict):
            continue
        try:
            findings.append(
                Finding(
                    kind=FindingKind(str(entry.get("kind", ""))),
                    note=str(entry.get("note", "")),
                )
            )
        except ValueError:
            logger.warning("BT analyst returned an unknown finding kind: %s", entry)
    return findings


async def analyse_telling_back(
    *,
    chunks: list[Chunk],
    scope: str,
    pericope_num: str,
    analyst_prompt: str,
    session_language: str = "Portuguese",
    settings: Settings | None = None,
) -> list[Finding]:
    """Compare the bridge-language telling-back against the map. Never voiced.

    The system never hears the mother-tongue recording; it only ever sees what the team told
    back. A failure here returns no findings, which reads as "nothing to raise" rather than
    inventing one — the analyst under-reports by design.
    """
    cfg = settings or get_settings()
    system = render(
        analyst_prompt,
        SESSION_LANGUAGE=session_language,
        SCOPE=scope,
        MEANING_MAP=load_map(pericope_num).body,
        SEGMENTS=segments_block(chunks),
    )
    try:
        raw = await call_agent(
            system_prompt=system,
            user_content="Compare o contado de volta com o mapa.",
            temperature=0.0,
            max_output_tokens=2000,
            settings=cfg,
        )
    except Exception:
        logger.exception("BT analysis failed for %s", pericope_num)
        return []
    return _parse_findings(raw)


def findings_block(finding: Finding | None) -> str:
    """Exactly one finding reaches the Speaker; the rest wait for the next round."""
    if finding is None:
        return "(nenhum achado — o contado de volta está completo)"
    return f"- {finding.kind}: {finding.note}"
