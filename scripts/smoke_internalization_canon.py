from __future__ import annotations

import json
import re
import sys

from app.core.served_books import SERVED_BOOKS
from app.services.internalization_room.canon.book_material import pericope_digest
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import VENDOR, load_book
from app.services.internalization_room.canon.titles import portuguese_titles, scene_title
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.passage_lines import offered

MANIFEST = VENDOR / "VENDOR_MANIFEST.json"
RAW_CODE = re.compile(r"(B|PL|O|TM|S|CB|FIG)[0-9]+")
REFERENCE_LINE = re.compile(r"\*\*[^*\s][^*]*\*\*.*")
HER_TITLES = {
    ("P10", 2): 'Com a sogra: a pergunta, o relato e "fique quieta"',
    ("P13", 1): "O casamento, a gravidez, o nascimento",
    ("P13", 2): "As palavras das mulheres a Noemi",
}


def _wrong_with(label: str) -> str | None:
    if not label.strip():
        return "is empty"
    if "[[" in label:
        return "leaks a link"
    if RAW_CODE.fullmatch(label.strip()):
        return "is a bare code"
    return None


def problems() -> list[str]:
    found = []
    recorded = len(json.loads(MANIFEST.read_text())["passages"])
    for spoken in ROOM_LANGUAGES:
        menu = sum(len(offered(book, spoken)) for book in sorted(SERVED_BOOKS))
        if menu != recorded:
            found.append(
                f"the menu offers {menu} passages in {spoken} but the record holds {recorded}"
            )
    for book in sorted(SERVED_BOOKS):
        for meaning_map in load_book(book):
            tag = meaning_map.pericope_num
            for element in labelled_elements(tag, book=book):
                if wrong := _wrong_with(element.label_en):
                    found.append(
                        f"{tag}: the coverage label of {element.key} {wrong}: {element.label_en!r}"
                    )
            found.extend(
                f"{tag}: scene {scene.number} has no title"
                for scene in meaning_map.scenes
                if not scene.title.strip()
            )
            keyed = sorted(portuguese_titles().get(tag, {}), key=lambda key: int(key[1:]))
            scenes = [f"S{scene.number}" for scene in meaning_map.scenes]
            if keyed != scenes:
                found.append(
                    f"{tag}: her Portuguese titles name {', '.join(keyed)}, "
                    f"but the map's scenes are {', '.join(scenes)}"
                )
            reference, arc, *_ = pericope_digest(meaning_map).split("\n")
            if not REFERENCE_LINE.fullmatch(reference):
                found.append(f"{tag}: the digest has no reference line")
            if not arc.strip():
                found.append(f"{tag}: the digest has no arc")
    for (tag, number), hers in HER_TITLES.items():
        if (titled := scene_title(tag, number, "", "pt")) != hers:
            found.append(f"{tag}: scene {number} is titled {titled!r}, not her approved {hers!r}")
    return found


def main() -> int:
    found = problems()
    if found:
        print("canon smoke failed:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("canon smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
