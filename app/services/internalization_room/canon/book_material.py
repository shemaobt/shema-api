from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon.parse_map import (
    SURVEYED_STATUS,
    VENDOR,
    MeaningMap,
    load_book,
)

LOGS_DIR = VENDOR / "compilation-log"

_AUDIT_BLOCK = re.compile(r'"high_risk_register_audit"\s*:\s*(\[)', re.S)


class PreservationRule(BaseModel):
    pericope: str
    rule_id: str
    kind: str
    note: str

    def render(self) -> str:
        return f"- [{self.pericope}] {self.rule_id} ({self.kind}): {self.note}"


def _extract_audit(text: str) -> list[dict]:
    """Pull the high_risk_register_audit array out of a Compilation Log.

    The logs embed JSON inside Markdown, so the array is located by key and then scanned
    bracket by bracket rather than by regex — a note containing `]` would end a lazy match
    early and silently drop the rest of the book's constraints.
    """
    found = _AUDIT_BLOCK.search(text)
    if not found:
        return []
    start = found.start(1)
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                entries: list[dict] = json.loads(text[start : index + 1])
                return entries
    return []


@lru_cache(maxsize=8)
def preservation_rules(book: str) -> tuple[PreservationRule, ...]:
    """The book's withholdings: audit entries the project marked `do_not_decide`.

    Entries flagged only `required_in_audit` are deliberately excluded — they are preferences,
    not constraints, and the project's own rendered material leaves them out.
    """
    rules: list[PreservationRule] = []
    for path in sorted(LOGS_DIR.glob(f"*-{book}-*-COMPILATION-LOG.md")):
        pericope = path.name.split("-", 1)[0]
        for entry in _extract_audit(path.read_text(encoding="utf-8")):
            if not entry.get("do_not_decide"):
                continue
            rules.append(
                PreservationRule(
                    pericope=pericope,
                    rule_id=str(entry.get("id", "")),
                    kind=str(entry.get("kind", "")),
                    note=str(entry.get("note", "")),
                )
            )
    return tuple(rules)


def require_walkable(meaning_map: MeaningMap) -> None:
    """Refuse a passage no team should be walked through, and name which layer is missing.

    The completion floor is every concrete element of the map engaged — each scene, being,
    place, object, time, significant absence, *and preserved element*. A passage with no
    withholdings recorded gets a coverage spine with no `preserved:` beads and a
    comprehension pack with no `preserved_element` checkpoints, meets that shortened floor,
    and hands Refine a package asserting a floor nobody verified. Refusing costs the team a
    passage; running costs Refine a false assurance, which is the more expensive of the two.

    The two signals are read separately on purpose. Ruth's last eight passages happen to
    carry both — no preservation layer *and* a pending survey — but agreement is not either
    one being read, and a layer written before the survey closes would otherwise walk.
    """
    pericope = meaning_map.pericope_num
    book = meaning_map.book
    if not any(rule.pericope == pericope for rule in preservation_rules(book)):
        raise ValidationError(
            f"{pericope}: no preservation layer in the {book} canon — the passage's "
            "withholdings were never written, so its completion floor cannot be met"
        )
    if meaning_map.sta_status != SURVEYED_STATUS:
        raise ValidationError(
            f"{pericope}: the map's survey is {meaning_map.sta_status!r}, not "
            f"{SURVEYED_STATUS!r} — the project has not signed this passage off as canon"
        )


def pericope_digest(meaning_map: MeaningMap) -> str:
    """One passage, verbatim from its map — reference, title, arc prose, scene titles.

    Nothing here is freshly written. If a digest needs a line the map does not supply, that is
    a map problem for the project, not a gap for this app to fill.
    """
    scenes = "; ".join(scene.title for scene in meaning_map.scenes)
    return (
        f"**{meaning_map.reference}** — {meaning_map.title}\n"
        f"{meaning_map.arc_prose}\n"
        f"Scenes: {scenes}."
    )


def build_book_material(book: str) -> str:
    """The Book Panorama's entire standard of truth, derived from vendored canon."""
    maps = load_book(book)
    rules = preservation_rules(book)
    if not rules:
        raise ValidationError(f"no preservation rules found for {book!r}")

    header = (
        f"# THE BOOK OF {book.upper()} — passage digests "
        f"(map-authored; {len(maps)} passages, in story order)"
    )
    digests = "\n\n".join(pericope_digest(m) for m in maps)
    notes = "\n".join(rule.render() for rule in rules)
    return (
        f"{header}\n\n{digests}\n\n"
        "## PRESERVATION NOTES — the book's withholdings "
        "(HARD CONSTRAINTS, union of all passages)\n"
        f"{notes}\n"
    )


def story_so_far(book: str, current_pericope: str) -> str:
    """Digests of strictly earlier passages only.

    The cut happens at the source, not in the prompt, so a later disclosure (who married whom
    in Ruth is withheld until 4:10) is structurally unable to reach an earlier session, rather
    than merely unlikely to.
    """
    earlier = [m for m in load_book(book) if m.pericope_num < current_pericope]
    if not earlier:
        return ""
    digests = "\n\n".join(pericope_digest(m) for m in earlier)
    return f"# THE STORY SO FAR — {book}, passages before {current_pericope}\n\n{digests}\n"


def vendor_pin() -> str:
    pin = Path(VENDOR / "VENDOR_PIN")
    return pin.read_text(encoding="utf-8").strip() if pin.exists() else "unpinned"
