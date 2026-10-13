"""ENG-1510 — one process reads one passage under two canons and each read gets its own canon.

A session keeps the canon it opened with, so a server holds the served canon and the kept one at
once. A cache keyed only by the passage answers the second canon with whatever the first one
left in it. Each case reads in the order that lets a stale cache hand the wrong canon back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.internalization_room.canon import kept
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.elements import scene_of
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.labels import label_index
from app.services.internalization_room.canon.parse_map import load_map
from tests.canon_harness import the_canon_moves_on

NEW_PIN = "a" * 40
FIRST_SCENE_HEADING = "### Scene 1 —"
SECOND_SCENE_HEADING = "### Scene 2 —"
REGISTER_COMPLETE = '"high_risk_register_complete": true'
REGISTER_INCOMPLETE = '"high_risk_register_complete": false'


def _the_kept_p02_has_no_first_scene(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P02-*.md")
    told = page.read_text(encoding="utf-8")
    first = told.index(FIRST_SCENE_HEADING)
    page.write_text(told[:first] + told[told.index(SECOND_SCENE_HEADING) :], encoding="utf-8")


def _the_kept_canon_has_no_p03(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob("P03-*.md")
    page.unlink()


def _the_kept_p02_register_is_incomplete(tree: Path) -> None:
    (log,) = (tree / "vendor" / "compilation-log").glob("P02-*.md")
    log.write_text(
        log.read_text(encoding="utf-8").replace(REGISTER_COMPLETE, REGISTER_INCOMPLETE),
        encoding="utf-8",
    )


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


def test_the_passages_a_canon_has_are_its_own_and_not_those_of_the_canon_read_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_pin = kept.deployed_pin()
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_canon_has_no_p03)

    with reading_the_canon_of(old_pin):
        kept_index = label_index({"P03"})
    with reading_the_canon_of(NEW_PIN):
        served_index = label_index({"P03"})

    assert kept_index == {}
    assert ("P03", "scene:S1") in served_index, (
        "o canon servido herdou do canon guardado, lido primeiro, a falta da P03"
    )


def test_a_kept_canon_whose_register_is_incomplete_refuses_a_passage_the_served_canon_opens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_pin = kept.deployed_pin()
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p02_register_is_incomplete)

    with reading_the_canon_of(NEW_PIN):
        served = unwalkable(load_map("P02"))
    with reading_the_canon_of(old_pin):
        kept_refusal = unwalkable(load_map("P02"))

    assert served is None
    assert kept_refusal is not None and "the register and the survey disagree" in kept_refusal, (
        "o canon guardado leu a lista de verificação do canon servido"
    )
