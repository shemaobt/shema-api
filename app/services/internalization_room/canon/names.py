from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

from app.services.internalization_room.canon.parse_map import VENDOR, MeaningMap, Scene

logger = logging.getLogger(__name__)

REGISTRY_DIR = VENDOR / "registry"
COORDINATES_DIR = VENDOR / "meaning-coordinates"

UNRESOLVED_LABEL = "(unresolved — needs grounded wording)"
WITHHELD_BEING_LABEL = "someone the text leaves unnamed here"

_STRIPPED = "STRIPPED_TO_"
_SPOKEN = {"STRIPPED_TO_HA_ISHAH": "the woman"}
_PASSAGE_LABEL = {("P10", "O13"): "The Cloak"}
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


@lru_cache(maxsize=64)
def _beings_by_scene(pericope_num: str) -> dict[int, list[dict]]:
    path = next(COORDINATES_DIR.glob(f"{pericope_num}-*-MEANING-COORDINATES.md"))
    fenced = path.read_text(encoding="utf-8").split("```json\n", 1)[1].split("\n```", 1)[0]
    coordinates = json.loads(fenced)
    return {
        int(scene["scene_id"].removeprefix("S")): scene["beings_in_scene"]["entries"]
        for scene in coordinates["level_2_scenes"]
    }


@lru_cache(maxsize=32)
def _glosses(body: str) -> dict[str, str]:
    glosses: dict[str, str] = {}
    for code, rest in _DEFINITION.findall(body):
        gloss = _NAMED_LINK.sub("", rest.strip().rsplit("/", 1)[-1].strip())
        if gloss and "[[" not in gloss and not _FLAG_NOTE.match(gloss):
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
    gloss = _glosses(meaning_map.body).get(code)
    if gloss:
        return gloss
    logger.warning(
        "%s %s has no name in the names list and no gloss in the map",
        meaning_map.pericope_num,
        code,
    )
    return UNRESOLVED_LABEL


def thing_name(meaning_map: MeaningMap, code: str) -> str:
    return _PASSAGE_LABEL.get((meaning_map.pericope_num, code)) or name_of(meaning_map, code)


def being_names(meaning_map: MeaningMap, scene: Scene) -> list[str]:
    entries = _beings_by_scene(meaning_map.pericope_num).get(scene.number, [])
    names: list[str] = []
    for being in scene.beings:
        if being.code is None:
            names.append(WITHHELD_BEING_LABEL)
            continue
        form = next(
            (entry.get("referential_form") for entry in entries if entry["being_id"] == being.code),
            None,
        )
        name = name_of(meaning_map, being.code)
        names.append(_SPOKEN[form] if form and form.startswith(_STRIPPED) else name)
    return names
