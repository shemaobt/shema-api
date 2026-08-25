from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError

VENDOR = Path(__file__).parent / "vendor"
MAPS_DIR = VENDOR / "meaning-map"

ROOM_BOOK = "Ruth"

CONSUMABLE_STATUS = "complete"
SUPPORTED_GENRE_GROUPS = frozenset({"NARRATIVE"})

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_H1 = re.compile(r"^# (\S+) — (.+)$", re.M)
_ARC = re.compile(
    r"^### 2\.1 [^\n]*\n(.*?)(?=^### 2\.2 )",
    re.M | re.S,
)
_SCENE = re.compile(r"^### Scene (\d+) — (.+?) \(([^)]*)\)\s*$", re.M)
# 3C is written two ways across the corpus — "Objects and Elements" in half the maps and
# "Objects and Concepts" in the other half. Matching one would drop the other in silence.
_BLOCK = re.compile(r"^\*\*3([A-F]) — [^*]+\*\*\s*$", re.M)
_ABSENCE = re.compile(r"^\*\*Significant Absence\*\*\s*$", re.M)
_WIKILINK = re.compile(r"\[\[([A-Za-z]+[0-9_][^\]|]*)\]\]")
_PROPOSITION = re.compile(r"^### Proposition (\d+) — (.+?) \[Scene (\d+)\]\s*$", re.M)
_ATOM = re.compile(r"^- \*\*Q:\*\* (.+?) \*\*A:\*\* (.+)$", re.M)


class Entity(BaseModel):
    code: str | None
    label: str

    @property
    def key(self) -> str:
        return self.code or self.label


class Scene(BaseModel):
    number: int
    title: str
    verses: str
    beings: list[Entity] = Field(default_factory=list)
    places: list[Entity] = Field(default_factory=list)
    objects: list[Entity] = Field(default_factory=list)
    times: list[Entity] = Field(default_factory=list)
    what_happens: str = ""
    absence: str | None = None


class Proposition(BaseModel):
    number: int
    ref: str
    scene: int
    atoms: list[tuple[str, str]] = Field(default_factory=list)


class MeaningMap(BaseModel):
    pericope_num: str
    title: str
    reference: str
    bcv: str
    genre_group: str
    genre: str
    status: str
    arc_prose: str
    scenes: list[Scene]
    propositions: list[Proposition]
    body: str
    """The authored document verbatim, minus frontmatter.

    What gets injected as `{{MEANING_MAP}}` is this, not a re-rendering of the parsed parts:
    the prose was ruled by the project's exegete, and rebuilding it from fields could quietly
    drop something the map says.
    """

    @property
    def book(self) -> str:
        """Derived from the reference (`Ruth 1:15-18`) rather than stored, so the session
        table needs no second column that could disagree with canon."""
        return self.reference.split(" ", 1)[0]


def _entities(block: str) -> list[Entity]:
    """Entity lines are `[[B3-Naomi]] — נָעֳמִי / Naomi`, but 24 of the corpus's 350 carry
    no wikilink (implied places like `הַדֶּרֶךְ / the road`). Both are real entities."""
    found: list[Entity] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("- "):
            continue
        link = _WIKILINK.search(line)
        if link:
            code = link.group(1).split("-", 1)[0]
            found.append(Entity(code=code, label=line))
        elif "/" in line:
            found.append(Entity(code=None, label=line))
    return found


def _scene_blocks(body: str) -> dict[str, str]:
    """Split one scene's body into its 3A to 3F blocks plus its Significant Absence.

    Blocks are found by their letter alone, never by their title: 3C is written
    "Objects and Elements" in half the corpus and "Objects and Concepts" in the other
    half, and matching either title would drop the other half's objects in silence.
    """
    marks = [(m.group(1), m.start(), m.end()) for m in _BLOCK.finditer(body)]
    absence = _ABSENCE.search(body)
    blocks: dict[str, str] = {}
    for index, (letter, _start, end) in enumerate(marks):
        stop = marks[index + 1][1] if index + 1 < len(marks) else len(body)
        if absence and end < absence.start() < stop:
            stop = absence.start()
        blocks[letter] = body[end:stop].strip()
    if absence:
        blocks["ABSENCE"] = body[absence.end() :].strip()
    return blocks


def _parse_scenes(body: str) -> list[Scene]:
    level2 = body.split("## 3. Level 2", 1)
    if len(level2) < 2:
        return []
    region = level2[1].split("## 4. Level 3", 1)[0]

    heads = list(_SCENE.finditer(region))
    scenes: list[Scene] = []
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(region)
        blocks = _scene_blocks(region[head.end() : stop])
        scenes.append(
            Scene(
                number=int(head.group(1)),
                title=head.group(2).strip(),
                verses=head.group(3).strip(),
                beings=_entities(blocks.get("A", "")),
                places=_entities(blocks.get("B", "")),
                objects=_entities(blocks.get("C", "")),
                times=_entities(blocks.get("D", "")),
                what_happens=blocks.get("E", ""),
                absence=blocks.get("ABSENCE") or None,
            )
        )
    return scenes


def _parse_propositions(body: str) -> list[Proposition]:
    if "## 4. Level 3" not in body:
        return []
    region = body.split("## 4. Level 3", 1)[1].split("## 5. Flags", 1)[0]
    heads = list(_PROPOSITION.finditer(region))
    out: list[Proposition] = []
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(region)
        out.append(
            Proposition(
                number=int(head.group(1)),
                ref=head.group(2).strip(),
                scene=int(head.group(3)),
                atoms=_ATOM.findall(region[head.end() : stop]),
            )
        )
    return out


def parse_map(text: str, *, source: str = "<memory>") -> MeaningMap:
    """Parse one Meaning Map. Refuses anything the project has not approved.

    The section grammar is load-bearing: a heading that stops matching means the canon moved,
    and raising is the point — a half-parsed map would ground the Guide on a partial passage
    without anyone noticing.
    """
    front = _FRONTMATTER.search(text)
    if not front:
        raise ValidationError(f"{source}: no YAML frontmatter")
    meta = yaml.safe_load(front.group(1)) or {}

    status = str(meta.get("status", ""))
    if status != CONSUMABLE_STATUS:
        raise ValidationError(
            f"{source}: status is {status!r}, not {CONSUMABLE_STATUS!r} — not approved canon"
        )

    genre_group = str(meta.get("genre-group", ""))
    if genre_group not in SUPPORTED_GENRE_GROUPS:
        raise ValidationError(
            f"{source}: genre-group {genre_group!r} is not enabled. Poetry maps keep the "
            "psalm's own wording in Level 3, so treating them as narrative would coach teams "
            "to reproduce phrasing. Coordinate with the project before enabling."
        )

    body = text[front.end() :]
    h1 = _H1.search(body)
    if not h1:
        raise ValidationError(f"{source}: no '# <pericope> — <reference>' title line")

    arc = _ARC.search(body)
    if not arc:
        raise ValidationError(f"{source}: §2.1 arc prose not found")

    scenes = _parse_scenes(body)
    if not scenes:
        raise ValidationError(f"{source}: no scenes parsed from Level 2")

    return MeaningMap(
        pericope_num=str(meta.get("pericope-num", h1.group(1))),
        title=str(meta.get("pericope-title", "")),
        reference=h1.group(2).strip(),
        bcv=str(meta.get("bcv", "")),
        genre_group=genre_group,
        genre=str(meta.get("genre", "")),
        status=status,
        arc_prose=arc.group(1).strip(),
        scenes=scenes,
        propositions=_parse_propositions(body),
        body=body.strip(),
    )


#: A passage is `P01`; a book is a word. Both arrive from the client — the pericope in a
#: request body, the book in a path segment — and both were spliced straight into a glob,
#: where `*`, `?` and `[…]` are patterns rather than characters. `pericope="*"` matched
#: every vendored map and `sorted()[0]` quietly picked the first, so a session could claim
#: to be one passage and be grounded in another, with the wrong name then written into
#: every take and question it produced.
_PERICOPE = re.compile(r"^[A-Za-z]{1,4}\d{1,3}$")
_BOOK = re.compile(r"^[A-Za-z][A-Za-z0-9 '-]{0,60}$")


@lru_cache(maxsize=64)
def load_map(pericope_num: str) -> MeaningMap:
    if not _PERICOPE.match(pericope_num):
        raise ValidationError(f"no vendored Meaning Map for {pericope_num}")
    matches = sorted(MAPS_DIR.glob(f"{pericope_num}-*.md"))
    if not matches:
        raise ValidationError(f"no vendored Meaning Map for {pericope_num}")
    path = matches[0]
    return parse_map(path.read_text(encoding="utf-8"), source=path.name)


@lru_cache(maxsize=8)
def load_book(book: str) -> tuple[MeaningMap, ...]:
    """Every vendored map of one book, in story order."""
    if not _BOOK.match(book):
        raise ValidationError(f"no vendored Meaning Maps for book {book!r}")
    paths = sorted(MAPS_DIR.glob(f"*-{book}-*.md"))
    if not paths:
        raise ValidationError(f"no vendored Meaning Maps for book {book!r}")
    return tuple(parse_map(path.read_text(encoding="utf-8"), source=path.name) for path in paths)
