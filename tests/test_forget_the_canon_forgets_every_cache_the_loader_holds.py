"""ENG-1469 — the helper that puts the canon back leaves nothing of a made-up book behind.

Four copies of it existed and they disagreed: one cleared three caches, three cleared four,
and none cleared the caches the passages are built from. A made-up book left in any of them
stays cached for the rest of the worker's run.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.internalization_room import passage_lines
from app.services.internalization_room.canon import kept
from tests.canon_harness import forget_the_canon, the_caches_the_loader_holds


def test_the_discovery_finds_the_caches_the_ticket_names() -> None:
    found = {name for name, _ in the_caches_the_loader_holds()}

    assert {
        "significant_absences",
        "_names_list",
        "_passage_labels",
        "_beings_by_scene",
        "_portuguese",
        "checkpoints_for",
    } <= found


def test_a_canon_cache_declared_outside_the_canon_package_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planted = kept.per_canon(maxsize=1)(lambda: 0)
    monkeypatch.setattr(passage_lines, "_a_planted_cache", planted, raising=False)

    found = [cache for _, cache in the_caches_the_loader_holds()]

    assert any(cache is planted for cache in found)


def test_the_caches_of_the_rest_of_the_room_are_not_the_canons_to_forget() -> None:
    found = {name for name, _ in the_caches_the_loader_holds()}

    assert found.isdisjoint({"_sections", "load_prompt", "fail_safe_utterances"})


@pytest.mark.parametrize("held", the_caches_the_loader_holds(), ids=lambda held: held[0])
def test_forgetting_the_canon_empties_every_cache_the_loader_holds(
    held: tuple[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    name, cache = held
    emptied: list[str] = []
    empty_it = cache.cache_clear

    def empty_and_note() -> None:
        emptied.append(name)
        empty_it()

    monkeypatch.setattr(cache, "cache_clear", empty_and_note)

    forget_the_canon()

    assert emptied == [name]
