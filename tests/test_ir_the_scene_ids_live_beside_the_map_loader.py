"""ENG-1575 — the scene ids of a passage are read where its map is parsed.

`comprehension/` was left holding one function after the probe machinery went, and the
function only reads the map. It lives beside `load_map` now, and the package that held it
is gone.
"""

import importlib

import pytest

from app.services.internalization_room.canon.scene_ids import scene_ids_for


def test_a_passage_names_the_scenes_her_map_gives_it() -> None:
    assert scene_ids_for("P03") == ["S1", "S2", "S3"], "a P03 de Rute 1:15-18 tem três cenas"


def test_the_package_that_held_only_this_function_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.services.internalization_room.comprehension")
