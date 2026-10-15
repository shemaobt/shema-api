from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

import regex

from app.services.internalization_room.canon.book_material import (
    _JSON_BLOCK,
    COORDINATES_DIR,
    LOGS_DIR,
    _extract_audit,
)
from app.services.internalization_room.canon.kept import canon_path, per_canon

ACCEPTED_READINGS_HEADER = (
    "ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS (a note from the app, in English like "
    "its other notes; never read aloud, never repeated to the team): the passage's rulings on how "
    "a team's telling of this scene is heard. A line counts only when the team's telling does "
    "what the line describes, and it accepts only what it names; the rest of the telling is "
    "checked as usual. When the telling does not do what a line describes, say nothing about "
    "that line. When the telling does what a line accepts, let that part pass in silence: do not "
    "name it, repeat it, praise it, explain it, compare it with the text's words or say that it "
    "is correct or allowed, and do not send it back for it. A line that calls it a nuance: name "
    "it once \N{EM DASH} in the words the line gives, when it gives them \N{EM DASH} as a plain "
    "remark, adding nothing to it (no instruction to keep or change it, and no word about naming "
    "it or letting it pass), and do not send it back for it. A line that says a telling is "
    "offered back: offer back only the text's own words for that part, with no other reason, and "
    "do not say the team's words are wrong. Nothing from these lines goes into anything else you "
    "say on this turn: not an invitation to tell the scene again, not the opening of the next "
    "scene, not the send-off."
)

ACCEPT_MARK = re.compile(
    r"\baccepted without comment\b|\baccept( it| them| both| these forms)? without comment\b"
    r"|\bcorrect without comment\b|\b(is|are)( all| both| also)? correct\b"
    r"|\bkeeps? (the|most of the) meaning\b|\bnot an addition\b|\bthe voice accepts\b"
    r"|^So does a telling\b",
    re.I | re.A,
)
NUANCE_MARK = re.compile(r"\bnuance\b", re.I | re.A)
OFFER_BACK_MARK = re.compile(r"\boffer(ed)? (it |them )?back\b", re.I | re.A)
NEVER_MARK = re.compile(
    r"For the voice only|never to be said|\bnever\b|\bdo not\b|\bdoes not teach\b|\bmust not\b",
    re.I | re.A,
)
SILENCE_MARK = re.compile(
    r"\bdoes not (say|tell|name|give|use)\b|\b(is|are) not (said|named|told|given)\b"
    r"|\bnot said\b|\bthe text does not\b|\bsilences?\b|\bno one says\b",
    re.I | re.A,
)
FACT_MARK = re.compile(
    r"\bHebrew\b|\bwritten\b|\bketiv\b|\bqere\b|\bmanuscripts?\b|\bsome Bibles\b|\bvariants?\b",
    re.I | re.A,
)
CODE_MARK = re.compile(r"\b(FIG|CB)_\d|\bSC-\d|\bitem \d|\bMarcia\b|\bO\d+:|\bP\d\d R\d", re.A)
_PROVENANCE = re.compile(r"\s*\((item \d+|Marcia[^)]*|SC-\d+[^)]*|P\d\d R\d+[^)]*)\)", re.A)
_ENUMERATOR = re.compile(r"^\(\d+\)\s+", re.A)
_CLOSER = re.compile(r"^(All of these|Accept (both|these forms))\b", re.A)
_ABBREVIATION = re.compile(r"\b(e\.g|i\.e|cf|vs|v|vv|ch)\.(?=\s)", re.A)
_SENTENCE_GAP = regex.compile(r"(?<=[.!?][)'\"»”\u2019]*)\s+(?=[A-Z«\"'“\u2018]|\(\d+\))")
_QUOTED = (
    (re.compile(r'"[^"]*"'), '""'),
    (re.compile(r"«[^»]*»"), "«»"),
    (re.compile(r"“[^”]*”"), "“”"),
    (re.compile(r"(^|[\s(\[—/])'[^']*?'(?=[\s,.;:)!?—/]|$)"), r"\1''"),
)
_CLAUSE = re.compile(r";\s+")
_DASH_CLAUSE = re.compile(r"\s*—\s+")

CUTS: dict[str, list[str]] = {
    "P08 R4.1": ["Keep the same rest-word as at 1:9 where the language allows; "],
    "P08 R8.1": ["The Hebrew reads 'all that you say to me' ('to me' is read, not written); "],
    "P08 R9.3": [" where the text does not"],
    "P08 R11.1": ["the written Hebrew has 'your garment' (one), read 'your garments'; "],
    "P10 R8.3": ["O13: the word here is mitpachat, not the simlah of 3:3; "],
    "P11 R11.1": ["OPTIONAL (FIG_0167): ", "; the voice may explain the idiom"],
    "P11 R13.1": [" (the Hebrew verb allows both)"],
    "P12 R2.4": [" (at 4:4 Boaz speaks of buying and of redeeming together)"],
    "P12 R11.1": [" \N{EM DASH} the Hebrew says 'from among his brothers', meaning his kin"],
    "P14 R9.1": [" (toledot)", ", and the voice may explain the word"],
    "P14 R9.2": [" (holid)"],
}
DROPS: dict[str, str] = {
    "P08 R9.4": "the same acceptance as R9.3 once its silence is cut",
    "P10 R11.3": "the acceptance cannot stand without its qere fact",
    "P11 R13.2": "the acceptance cannot stand without its Hebrew-variant fact",
    "P12 R7.1": "glued to a silence (in the blessing she is not named); canon edit C1 proposed",
    "P12 R11.3": "a Hebrew word note; R8.1 carries the same acceptance",
    "P14 R8.2": "'either form' needs the spelling fact; R9.3 carries the acceptance",
}
SCOPES: dict[str, list[str]] = {
    "P08 R10.1": ["S1"],
    "P10 R8.3": ["S1"],
    "P11 R13.3": ["S2"],
    "P12 R8.1": ["S2"],
}

Klass = Literal["NUANCE", "ACCEPT", "OFFER_BACK"]


@dataclass(frozen=True)
class AcceptedItem:
    key: str
    rid: str
    scenes: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Excluded:
    key: str
    text: str
    why: str


@dataclass(frozen=True)
class AcceptedReadings:
    items: tuple[AcceptedItem, ...]
    excluded: tuple[Excluded, ...]
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class _Span:
    id: str
    lo: int
    hi: int


@dataclass(frozen=True)
class _Scenes:
    spans: tuple[_Span, ...]
    props: dict[str, str]


def split_sentences(note: str) -> list[str]:
    guarded = _ABBREVIATION.sub(lambda m: m.group(0)[:-1] + "\0", note)
    parts = (part.replace("\0", ".").strip() for part in _SENTENCE_GAP.split(guarded))
    return [part for part in parts if part]


def unquote(text: str) -> str:
    for pattern, emptied in _QUOTED:
        text = pattern.sub(emptied, text)
    return text


def _classes_of(text: str) -> list[Klass]:
    bare = unquote(text)
    if NUANCE_MARK.search(bare):
        return ["NUANCE"]
    found: list[Klass] = []
    if ACCEPT_MARK.search(bare):
        found.append("ACCEPT")
    if OFFER_BACK_MARK.search(bare):
        found.append("OFFER_BACK")
    return found


def _has_never(text: str) -> bool:
    return bool(NEVER_MARK.search(unquote(text)))


def _positive(found: list[Klass]) -> bool:
    return "ACCEPT" in found or "NUANCE" in found


def top_split(text: str, separator: re.Pattern[str]) -> list[str]:
    out: list[str] = []
    depth = 0
    quote: str | None = None
    current = ""
    index = 0
    while index < len(text):
        char = text[index]
        prev = text[index - 1] if index > 0 else " "
        following = text[index + 1] if index + 1 < len(text) else " "
        if quote:
            current += char
            closes_single = quote == "'" and char == "'" and not re.match(r"[A-Za-zÀ-ÿ]", following)
            if closes_single or (quote != "'" and char == quote):
                quote = None
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == '"':
            quote = '"'
        elif char == "«":
            quote = "»"
        elif char == "“":
            quote = "”"
        elif char == "'" and re.match(r"[\s(\[—/]", prev):
            quote = "'"
        if depth == 0:
            match = separator.match(text, index)
            if match:
                out.append(current)
                current = ""
                index = match.end()
                continue
        current += char
        index += 1
    out.append(current)
    return [part.strip() for part in out if part.strip()]


def _kept_of_sentence(sentence: str) -> tuple[str, list[Klass]] | None:
    whole = _classes_of(sentence)
    if not whole:
        return None
    if not _has_never(sentence) and (_positive(whole) or "OFFER_BACK" not in whole):
        return sentence, whole
    clauses = top_split(sentence, _CLAUSE)
    if _has_never(sentence):
        clauses = [part for clause in clauses for part in top_split(clause, _DASH_CLAUSE)]
    keep = [
        (clause, found)
        for clause in clauses
        if not _has_never(clause) and (found := _classes_of(clause))
    ]
    if not any(_positive(found) for _, found in keep):
        return None
    text = re.sub(r"[.;,\s]*$", "", "; ".join(clause for clause, _ in keep)) + "."
    return text, list(dict.fromkeys(klass for _, found in keep for klass in found))


def _verse(text: str) -> int | None:
    match = re.match(r"^(\d+):(\d+)", text)
    return int(match.group(1)) * 1000 + int(match.group(2)) if match else None


def _scenes_of(coordinates: dict) -> _Scenes:
    spans: list[_Span] = []
    for scene in coordinates["level_2_scenes"]:
        first, *rest = re.split("[-\N{EN DASH}]", scene["verse_range"])
        lo = _verse(first)
        if lo is None:
            raise ValueError(f"{scene['scene_id']}: no verse in {scene['verse_range']!r}")
        if not rest:
            hi = lo
        elif ":" in rest[0]:
            hi = _verse(rest[0]) or lo
        else:
            hi = lo // 1000 * 1000 + int(rest[0])
        spans.append(_Span(id=scene["scene_id"], lo=lo, hi=hi))
    props = {
        prop["prop_id"]: prop["scene_link"]
        for prop in coordinates.get("level_3_propositions") or []
    }
    return _Scenes(spans=tuple(spans), props=props)


def _scope_of(text: str, scenes: _Scenes) -> list[str]:
    found: set[str] = set()
    found.update("S" + m.group(1) for m in re.finditer(r"\bScene (\d+)", text, re.A))
    found.update("S" + m.group(1) for m in re.finditer(r"\bS(\d+)\b", text, re.A))
    for m in re.finditer(r"\b(\d+):(\d+)(?:[\N{EN DASH}-](?:(\d+):)?(\d+))?", text, re.A):
        lo = int(m.group(1)) * 1000 + int(m.group(2))
        hi = (int(m.group(3) or m.group(1))) * 1000 + int(m.group(4)) if m.group(4) else lo
        found.update(span.id for span in scenes.spans if lo <= span.hi and hi >= span.lo)
    if not found:
        for m in re.finditer(r"\bP([1-9]\d?)\b(?!\s+[RP]\d)", text, re.A):
            linked = scenes.props.get("P" + m.group(1))
            if linked:
                found.add(linked)
    known = {span.id for span in scenes.spans}
    return sorted(scene for scene in found if scene in known)


def _own_scope(raw: str, lead: str | None, applies_to: str, scenes: _Scenes) -> list[str]:
    if lead:
        return _scope_of(lead, scenes)
    for m in re.finditer(r"\b((?:FIG|CB)_\d{4})\b", raw, re.A):
        placed = re.search(m.group(1) + r"[^;]*?\((P[1-9]\d?)[,)]", applies_to, re.A)
        if placed:
            return _scope_of(placed.group(1), scenes)
    return []


def _why_held(text: str) -> str:
    bare = unquote(text)
    if NEVER_MARK.search(bare):
        return "never"
    if SILENCE_MARK.search(bare):
        return "silence"
    if FACT_MARK.search(bare):
        return "fact"
    if CODE_MARK.search(text):
        return "code"
    return ""


def accepted_readings_from(
    pericope_num: str, compilation_log: str, coordinates: str
) -> AcceptedReadings:
    block = _JSON_BLOCK.search(coordinates)
    if block is None:
        raise ValueError(f"{pericope_num}: no json block in its Meaning Coordinates")
    scenes = _scenes_of(json.loads(block.group(1)))
    items: list[AcceptedItem] = []
    excluded: list[Excluded] = []
    candidates: list[str] = []
    for entry in _extract_audit(compilation_log):
        applies_to = entry.get("applies_to") or ""
        entry_scenes = _scope_of(applies_to, scenes)
        for index, sentence in enumerate(split_sentences(entry.get("note") or "")):
            key = f"{pericope_num} {entry['id']}.{index}"
            kept = _kept_of_sentence(sentence)
            if kept is None:
                continue
            candidates.append(key)
            if key in DROPS:
                continue
            text = _PROVENANCE.sub("", kept[0])
            cut_missing = next((cut for cut in CUTS.get(key, []) if text.count(cut) != 1), None)
            if cut_missing is not None:
                why = f"cut not found exactly once: {cut_missing}"
                excluded.append(Excluded(key=key, text=text, why=why))
                continue
            for cut in CUTS.get(key, []):
                text = text.replace(cut, "", 1)
            text = _ENUMERATOR.sub("", text)
            text = text[:1].upper() + text[1:]
            why = _why_held(text)
            if why:
                excluded.append(Excluded(key=key, text=text, why=why))
                continue
            lead = re.match(r"^(\d+:\d+)", text)
            own = _own_scope(sentence, lead.group(1) if lead else None, applies_to, scenes)
            scoped = SCOPES.get(key) or own or entry_scenes
            if _CLOSER.match(text):
                siblings = [s for item in items if item.rid == entry["id"] for s in item.scenes]
                if siblings:
                    scoped = sorted(set(siblings))
            items.append(AcceptedItem(key=key, rid=entry["id"], scenes=tuple(scoped), text=text))
    return AcceptedReadings(
        items=tuple(items), excluded=tuple(excluded), candidates=tuple(candidates)
    )


@per_canon(maxsize=16)
def accepted_readings_of(pericope_num: str) -> AcceptedReadings:
    log = next(canon_path(LOGS_DIR).glob(f"{pericope_num}-*-COMPILATION-LOG.md"))
    coordinates = next(canon_path(COORDINATES_DIR).glob(f"{pericope_num}-*-MEANING-COORDINATES.md"))
    return accepted_readings_from(
        pericope_num, log.read_text(encoding="utf-8"), coordinates.read_text(encoding="utf-8")
    )


def accepted_lines(items: tuple[AcceptedItem, ...], scene: str) -> list[str]:
    by_entry: dict[str, list[str]] = {}
    for item in items:
        if scene in item.scenes:
            by_entry.setdefault(item.rid, []).append(item.text)
    return [f"- {rid}: {' '.join(texts)}" for rid, texts in by_entry.items()]


def accepted_ids_for(items: tuple[AcceptedItem, ...], scene: str) -> list[str]:
    return list(dict.fromkeys(item.rid for item in items if scene in item.scenes))
