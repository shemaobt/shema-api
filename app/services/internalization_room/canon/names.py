from __future__ import annotations

import json
import re
from functools import lru_cache

from app.services.internalization_room.canon.parse_map import VENDOR, MeaningMap, Scene

REGISTRY_DIR = VENDOR / "registry"
COORDINATES_DIR = VENDOR / "meaning-coordinates"

_STRIPPED = "STRIPPED_TO_"
_SPOKEN = {"STRIPPED_TO_HA_ISHAH": "the woman"}
_DEFINITION = re.compile(r"^\[\[([A-Z][A-Z0-9_]*?)-[^\]\n]*\]\][ \t]*—[ \t]*([^\n]+)$", re.M)
_NAMED_LINK = re.compile(r"\[\[[^\]\n]*\]\][ \t]+(?=[^\W\d_])")
_FLAG_NOTE = re.compile(r"^active at\b", re.I)


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


def name_of(meaning_map: MeaningMap, code: str) -> str | None:
    entry = _names_list(meaning_map.book).get(code)
    if entry is not None:
        return str(entry["english"])
    return _glosses(meaning_map.body).get(code)


def being_names(meaning_map: MeaningMap, scene: Scene) -> list[str | None]:
    entries = _beings_by_scene(meaning_map.pericope_num).get(scene.number, [])
    names: list[str | None] = []
    for being in scene.beings:
        if being.code is None:
            names.append(None)
            continue
        form = next(
            (entry.get("referential_form") for entry in entries if entry["being_id"] == being.code),
            None,
        )
        name = name_of(meaning_map, being.code)
        names.append(_SPOKEN[form] if form and form.startswith(_STRIPPED) else name)
    return names
