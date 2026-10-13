"""ENG-1510 — one process reads one passage under two canons and each read gets its own canon.

A session keeps the canon it opened with, so a server holds the served canon and the kept one at
once. A cache keyed only by the passage answers the second canon with whatever the first one
left in it. Each case reads in the order that lets a stale cache hand the wrong canon back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.internalization_room.canon import kept
from app.services.internalization_room.canon.elements import scene_of
from app.services.internalization_room.canon.kept import reading_the_canon_of
from tests.canon_harness import the_canon_moves_on

NEW_PIN = "a" * 40
FIRST_SCENE_HEADING = "### Scene 1 —"
SECOND_SCENE_HEADING = "### Scene 2 —"


def _the_kept_p02_has_no_first_scene(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P02-*.md")
    told = page.read_text(encoding="utf-8")
    first = told.index(FIRST_SCENE_HEADING)
    page.write_text(told[:first] + told[told.index(SECOND_SCENE_HEADING) :], encoding="utf-8")


def test_a_passage_read_under_two_canons_answers_each_canons_scenes_not_the_first_one_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_pin = kept.deployed_pin()
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p02_has_no_first_scene)

    with reading_the_canon_of(NEW_PIN):
        served = scene_of("P02")
    with reading_the_canon_of(old_pin):
        kept_scenes = scene_of("P02")

    assert served.get("scene:S1") == 1
    assert "scene:S1" not in kept_scenes, (
        "o canon guardado respondeu as cenas do canon servido, lidas primeiro no mesmo processo"
    )
    assert kept_scenes.get("scene:S2") == 2
