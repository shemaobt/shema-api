from __future__ import annotations

import re
import sys

from app.core.served_books import SERVED_BOOKS
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import load_book

RAW_CODE = re.compile(r"(B|PL|O|TM|S|CB|FIG)[0-9]+")


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
