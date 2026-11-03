from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.services.internalization_room.canon import book_material, parse_map
from tests.canon_harness import HER_CANON, forget_the_canon


@pytest.fixture
def jonah_is_served(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(parse_map, "MAPS_DIR", HER_CANON / "meaning-map")
    monkeypatch.setattr(book_material, "LOGS_DIR", HER_CANON / "compilation-log")
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Jonah"}))
    forget_the_canon()
    yield "Jonah"
    forget_the_canon()


def test_jonahs_prayer_from_the_deep_opens_on_its_four_scenes_in_map_order(
    jonah_is_served: str,
) -> None:
    prayer = parse_map.load_map("J03")

    assert prayer.reference == "Jonah 2:2\u20139"
    assert [scene.title for scene in prayer.scenes] == [
        "The call answered: the cry from Sheol's belly",
        "Hurled into the deep — banished, yet turning to the temple",
        "The bottom and the lift: down to the roots, up from the pit",
        "The vow: thanksgiving, payment, and the thesis",
    ]


def test_the_jonah_panorama_builds_with_the_prayer_and_no_rule_recorded(
    jonah_is_served: str,
) -> None:
    material = book_material.build_book_material(jonah_is_served)

    assert "5 passages, in story order" in material
    assert "**Jonah 2:2\u20139**" in material
    assert "- (none recorded)" in material


@pytest.mark.parametrize("pericope", ["J04", "J05"])
def test_the_story_so_far_after_the_prayer_builds_and_tells_it(
    jonah_is_served: str, pericope: str
) -> None:
    told = book_material.story_so_far(jonah_is_served, pericope)

    assert "**Jonah 2:2\u20139**" in told
