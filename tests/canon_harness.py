"""What a case that stands a made-up book in place of the canon needs to put the canon back.

The loader reads Marcia's maps and logs through caches, and the passages built from them are
cached in turn, so a case that points the loader at a directory of its own has to forget
everything the loader has held before it and again after it. One list, here, so that a cache
the loader gains is added in one place. Builders and constants only.
"""

from __future__ import annotations

from app.services.internalization_room.canon import book_material, elements, labels, parse_map
from app.services.internalization_room.comprehension import checkpoints


def forget_the_canon() -> None:
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()
    book_material._register_complete.cache_clear()
    elements.elements_for.cache_clear()
    elements.scene_of.cache_clear()
    labels._known_pericopes.cache_clear()
    checkpoints.checkpoints_for.cache_clear()
