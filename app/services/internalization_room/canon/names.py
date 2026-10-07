from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from app.services.internalization_room.canon.parse_map import VENDOR, MeaningMap, Scene

logger = logging.getLogger(__name__)

REGISTRY_DIR = VENDOR / "registry"
COORDINATES_DIR = VENDOR / "meaning-coordinates"
PASSAGE_LABELS = Path(__file__).parent / "passage-labels.json"

UNRESOLVED_LABEL = "(unresolved — needs grounded wording)"
WITHHELD_BEING_LABEL = "someone the text leaves unnamed here"

_STRIPPED = "STRIPPED_TO_"
WITHHELD_BEING = "B?"

_SPOKEN = {"STRIPPED_TO_HA_ISHAH": "the woman", "REDEEMER_GOEL": "a redeemer"}
_ROLE_WORD = {"SON": "a son"}
_DEFINITION = re.compile(r"^\[\[([A-Z][A-Z0-9_]*?)-[^\]\n]*\]\][ \t]*—[ \t]*([^\n]+)$", re.M)
_NAMED_LINK = re.compile(r"\[\[[^\]\n]*\]\][ \t]+(?=[^\W\d_])")
_FLAG_NOTE = re.compile(r"^active at\b", re.I)
_RETIRED_OR_RESERVED = re.compile(r"\[(retired|reserved)", re.I)
_RETIRED_KEY = re.compile(r"_RETIRED$", re.I)


@lru_cache(maxsize=8)
def _names_list(book: str) -> dict[str, dict]:
    path = REGISTRY_DIR / f"{book.lower()}.aliases.json"
    entities: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))["entities"]
    return entities


@lru_cache(maxsize=1)
def _passage_labels() -> dict[str, dict[str, dict[str, str]]]:
    labels: dict[str, dict[str, dict[str, str]]] = json.loads(
        PASSAGE_LABELS.read_text(encoding="utf-8")
    )
    return labels


@lru_cache(maxsize=64)
def _beings_by_scene(pericope_num: str) -> dict[int, list[dict]]:
    path = next(COORDINATES_DIR.glob(f"{pericope_num}-*-MEANING-COORDINATES.md"))
    fenced = path.read_text(encoding="utf-8").split("```json\n", 1)[1].split("\n```", 1)[0]
    coordinates = json.loads(fenced)
    return {
        int(scene["scene_id"].removeprefix("S")): scene["beings_in_scene"]["entries"]
        for scene in coordinates["level_2_scenes"]
    }


def _gloss(line: str) -> str | None:
    gloss = _NAMED_LINK.sub("", line.strip().rsplit("/", 1)[-1].strip())
    if gloss and "[[" not in gloss and not _FLAG_NOTE.match(gloss):
        return gloss
    return None


@lru_cache(maxsize=32)
def _glosses(body: str) -> dict[str, str]:
    glosses: dict[str, str] = {}
    for code, rest in _DEFINITION.findall(body):
        gloss = _gloss(rest)
        if gloss:
            glosses.setdefault(code, gloss)
    return glosses


def _retired_or_reserved(code: str, entry: dict) -> bool:
    return bool(
        _RETIRED_OR_RESERVED.search(entry.get("english") or "") or _RETIRED_KEY.search(code)
    )


def name_of(meaning_map: MeaningMap, code: str) -> str:
    entry = _names_list(meaning_map.book).get(code)
    if entry is not None and not _retired_or_reserved(code, entry):
        return str(entry["english"])
    return _grounded(meaning_map, code, _glosses(meaning_map.body).get(code))


def _grounded(meaning_map: MeaningMap, mention: str, gloss: str | None) -> str:
    if gloss:
        return gloss
    logger.warning(
        "%s %s has no name in the names list and no gloss in the map",
        meaning_map.pericope_num,
        mention,
    )
    return UNRESOLVED_LABEL


def thing_name(meaning_map: MeaningMap, code: str) -> str:
    for_passage = _passage_labels().get(meaning_map.book, {}).get(meaning_map.pericope_num, {})
    return for_passage.get(code) or name_of(meaning_map, code)


def _withheld_label(form: str | None, role: str | None) -> str:
    if not form:
        return _ROLE_WORD.get(role or "", WITHHELD_BEING_LABEL)
    if form in _SPOKEN:
        return _SPOKEN[form]
    words = form.lower().replace("_", " ").split()
    if words[-1] == "unnamed":
        return " ".join(words[:-1]) + " (unnamed here)"
    return " ".join(words)


def being_names(meaning_map: MeaningMap, scene: Scene) -> list[str]:
    entries = _beings_by_scene(meaning_map.pericope_num)[scene.number]
    withheld = iter(entry for entry in entries if entry["being_id"] == WITHHELD_BEING)
    names: list[str] = []
    for being in scene.beings:
        if being.code is None:
            entry = next(withheld, None)
            if entry is None:
                names.append(_grounded(meaning_map, being.label, _gloss(being.label)))
            else:
                names.append(
                    _withheld_label(entry.get("referential_form"), entry.get("role_in_scene"))
                )
            continue
        form = next(
            (entry.get("referential_form") for entry in entries if entry["being_id"] == being.code),
            None,
        )
        name = name_of(meaning_map, being.code)
        names.append(_SPOKEN[form] if form and form.startswith(_STRIPPED) else name)
    return names
