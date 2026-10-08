"""ENG-1469 — the helper that puts the canon back leaves nothing of a made-up book behind.

Four copies of it existed and they disagreed: one cleared three caches, three cleared four,
and none cleared the caches the passages are built from. A made-up book left in any of them
stays cached for the rest of the worker's run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.services.internalization_room.canon import book_material, elements, labels, parse_map
from app.services.internalization_room.comprehension import checkpoints
from tests.canon_harness import forget_the_canon

_THE_CACHES_THE_LOADER_HOLDS: dict[str, tuple[Any, Callable[[], object]]] = {
    "load_map": (parse_map.load_map, lambda: parse_map.load_map("P01")),
    "load_book": (parse_map.load_book, lambda: parse_map.load_book("Ruth")),
    "preservation_rules": (
        book_material.preservation_rules,
        lambda: book_material.preservation_rules("Ruth"),
    ),
    "_register_complete": (
        book_material._register_complete,
        lambda: book_material._register_complete("Ruth"),
    ),
    "elements_for": (elements.elements_for, lambda: elements.elements_for("P01")),
    "scene_of": (elements.scene_of, lambda: elements.scene_of("P01")),
    "checkpoints_for": (
        checkpoints.checkpoints_for,
        lambda: checkpoints.checkpoints_for("P01"),
    ),
    "_known_pericopes": (labels._known_pericopes, lambda: labels._known_pericopes("Ruth")),
}


@pytest.mark.parametrize("name", sorted(_THE_CACHES_THE_LOADER_HOLDS))
def test_forgetting_the_canon_empties_every_cache_the_loader_holds(name: str) -> None:
    cache, fill = _THE_CACHES_THE_LOADER_HOLDS[name]
    fill()
    assert cache.cache_info().currsize > 0

    forget_the_canon()

    assert cache.cache_info().currsize == 0
