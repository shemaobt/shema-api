from __future__ import annotations

import json
import re

from pydantic import BaseModel

from app.core.canon_pin import pinned_commit
from app.core.exceptions import ValidationError
from app.core.served_books import SERVED_BOOKS
from app.services.internalization_room.canon.kept import canon_path, per_canon
from app.services.internalization_room.canon.parse_map import (
    _PERICOPE,
    VENDOR,
    MeaningMap,
    code_only_links,
    load_book,
    not_served,
)

LOGS_DIR = VENDOR / "compilation-log"
COORDINATES_DIR = VENDOR / "meaning-coordinates"

_AUDIT_BLOCK = re.compile(r'"high_risk_register_audit"\s*:\s*(\[)', re.S)
_JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.S)


class PreservationRule(BaseModel):
    pericope: str
    rule_id: str
    kind: str
    note: str

    def render(self, *, tagged: bool = True) -> str:
        tag = f"[{self.pericope}] " if tagged else ""
        return f"- {tag}{self.rule_id} ({self.kind}): {self.note}"

    def folds_into(self, absence_text: str) -> bool:
        """Whether this rule is about the silence one scene's absence describes.

        A structural-absence rule and a scene absence about the *same* silence are one thing
        for the team to work, not two. Matched against this scene's own silence only: a
        multi-scene rule's own wording would make every absence appear related merely because
        the rule mentions its theme globally.
        """
        if not self.kind.startswith("STRUCTURAL_ABSENCE_"):
            return False
        text = absence_text.lower()
        if "DIVINE_AGENCY" in self.kind:
            return bool(re.search(r"\bgod\b|yhwh|divine|cause|causation|sent|agent", text))
        if re.search(r"GRIEF|MOURNING|FUNERAL", self.kind):
            return bool(re.search(r"grief|grieving|mourn|mourning|funeral|lament|wept|weep", text))
        if re.search(r"OFFSPRING|CHILD", self.kind):
            return bool(re.search(r"child|children|offspring|heir|born|birth", text))
        return False


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


@per_canon(maxsize=8)
def preservation_rules(book: str) -> tuple[PreservationRule, ...]:
    """The book's withholdings: audit entries the project marked `do_not_decide`.

    Entries flagged only `required_in_audit` are deliberately excluded — they are preferences,
    not constraints, and the project's own rendered material leaves them out.
    """
    rules: list[PreservationRule] = []
    for path in sorted(canon_path(LOGS_DIR).glob(f"*-{book}-*-COMPILATION-LOG.md")):
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


class SceneAbsence(BaseModel):
    scene_id: str
    verse_range: str
    text: str


@per_canon(maxsize=64)
def significant_absences(pericope_num: str) -> tuple[SceneAbsence, ...]:
    matches = (
        sorted(canon_path(COORDINATES_DIR).glob(f"{pericope_num}-*-MEANING-COORDINATES.md"))
        if _PERICOPE.match(pericope_num)
        else []
    )
    if not matches:
        raise ValidationError(f"no vendored Meaning Coordinates for {pericope_num}")
    path = matches[0]
    block = _JSON_BLOCK.search(path.read_text(encoding="utf-8"))
    if block is None:
        raise ValidationError(f"{path.name}: no json block")
    coordinates = json.loads(block.group(1))
    return tuple(
        SceneAbsence(
            scene_id=scene["scene_id"],
            verse_range=scene["verse_range"],
            text=scene["significant_absence"],
        )
        for scene in coordinates["level_2_scenes"]
        if scene.get("significant_absence")
    )


def unwalkable(meaning_map: MeaningMap) -> str | None:
    """Why this passage must not be walked, or ``None`` when it may be.

    The same refusal, asked rather than raised, so the wheel, the progression and the open
    describe the same book.
    """
    book = meaning_map.book
    if book not in SERVED_BOOKS:
        return f"{meaning_map.pericope_num}: {not_served(book)}"
    return None


def require_walkable(meaning_map: MeaningMap) -> None:
    """Refuse a passage of a book the room does not serve; every other passage walks (ADR 0066)."""
    reason = unwalkable(meaning_map)
    if reason is not None:
        raise ValidationError(reason)


def pericope_digest(meaning_map: MeaningMap) -> str:
    """One passage from its map — reference, title, arc prose, scene titles, links as codes alone.

    No word here is freshly written. If a digest needs a line the map does not supply, that is
    a map problem for the project, not a gap for this app to fill.
    """
    scenes = "; ".join(scene.title for scene in meaning_map.scenes)
    return code_only_links(
        f"**{meaning_map.reference}** — {meaning_map.title}\n"
        f"{meaning_map.arc_prose}\n"
        f"Scenes: {scenes}."
    )


def build_book_material(book: str) -> str:
    """The Book Panorama's entire standard of truth, derived from vendored canon."""
    if book not in SERVED_BOOKS:
        raise ValidationError(not_served(book))
    maps = load_book(book)
    rules = preservation_rules(book)

    header = (
        f"# THE BOOK OF {book.upper()} — passage digests "
        f"(map-authored; {len(maps)} passages, in story order)"
    )
    digests = "\n\n".join(pericope_digest(m) for m in maps)
    notes = "\n".join(rule.render() for rule in rules) or "- (none recorded)"
    return (
        f"{header}\n\n{digests}\n\n"
        "## PRESERVATION NOTES — the book's withholdings "
        "(HARD CONSTRAINTS, union of all passages)\n"
        "The team has not yet lived any passage: every one of these still lies ahead of them. "
        "The panorama must honor each — never state, pair, name, or attribute what a "
        f"passage withholds until its moment.\n\n{notes}\n"
    )


NOT_WORKED_NOTICE = (
    "(This team has not worked this passage yet. If you speak of anything below, tell it as "
    "the story's — 'a história conta que…' (English sessions: 'the story tells that…') — only "
    "what is needed, in a few words; never 'lembrem', never 'na última parte'.)"
)


def _with_notice(digest: str) -> str:
    heading, _, rest = digest.partition("\n")
    return f"{heading}\n{NOT_WORKED_NOTICE}\n{rest}"


def story_so_far(book: str, current_pericope: str, not_worked: frozenset[str] = frozenset()) -> str:
    """Digests of strictly earlier passages only.

    The cut happens at the source, not in the prompt, so a later disclosure (who married whom
    in Ruth is withheld until 4:10) is structurally unable to reach an earlier session, rather
    than merely unlikely to.
    """
    earlier = [m for m in load_book(book) if m.pericope_num < current_pericope]
    if not earlier:
        return ""
    digests = "\n\n".join(
        _with_notice(pericope_digest(m)) if m.pericope_num in not_worked else pericope_digest(m)
        for m in earlier
    )
    return (
        "---\n\n# THE STORY SO FAR (earlier passages of this book — map-authored)\n"
        "Digests of this book's earlier passages, extracted verbatim from their own Meaning "
        "Maps. Grounded material: it may be used to answer the team's questions about the story "
        "so far and to situate the current passage in the book. Nothing beyond these "
        f"passages and the current map exists.\n\n{digests}"
    )


def vendor_pin() -> str:
    pin = canon_path(VENDOR) / "VENDOR_PIN"
    return pinned_commit(pin.read_text(encoding="utf-8")) if pin.exists() else "unpinned"


def meaning_map_ref(pericope: str) -> dict[str, str] | None:
    """The vendored **Meaning Map** of this pericope as the sync recorded it, or none.

    Read off the sync's own record rather than hashed again, as hers is: the record is what
    the copy was checked against. Through ``canon_path``, so a session reading a kept canon
    names the pin and the file it read.
    """
    record = canon_path(VENDOR / "VENDOR_MANIFEST.json")
    if not record.exists():
        return None
    manifest = json.loads(record.read_text(encoding="utf-8"))
    prefix = f"meaning-map/{pericope}-"
    for entry in manifest["files"]:
        path = entry["path"]
        if path.startswith(prefix) and path.endswith(".md"):
            return {
                "id": path.removeprefix("meaning-map/").removesuffix(".md"),
                "file": path,
                "pin": manifest["pin_commit"],
                "sha256": entry["sha256"],
            }
    return None
