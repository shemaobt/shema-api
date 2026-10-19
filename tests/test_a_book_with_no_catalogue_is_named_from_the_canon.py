"""ENG-1248 — a book nobody has translated is named from the canon, with her Portuguese titles.

Only Ruth has a label catalogue. Esther's and Jonah's beads are named as her app names them:
a scene by her Portuguese title (`ui-labels.pt.json`, generated from her pin), every other
bead by the canon's English with no Portuguese. The titles and names below are copied from
her list and her `esther.aliases.json`.
"""

from __future__ import annotations

import pytest

from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.canon.titles import portuguese_titles

THE_PIN = (
    [f"E{number:02d}" for number in range(1, 19)]
    + [f"J{number:02d}" for number in range(1, 6)]
    + [f"P{number:02d}" for number in range(1, 15)]
)


def test_an_esther_passage_names_its_beads_from_the_canon_with_her_portuguese_scene_titles() -> (
    None
):
    beads = {bead.key: bead for bead in labelled_elements("E01")}
    king = beads["being:S1:B4"]
    ruth = labelled_elements("P01")

    assert beads["scene:S1"].label_pt == "O império e o trono"
    assert king.label_en == "Ahasuerus"
    assert king.label_pt is None
    assert all(bead.label_pt for bead in ruth)


@pytest.mark.parametrize("pericope", THE_PIN)
def test_every_scene_of_every_served_passage_has_her_portuguese_title(pericope: str) -> None:
    scenes = {f"S{scene.number}" for scene in load_map(pericope).scenes}

    assert set(portuguese_titles()[pericope]) == scenes


def test_jonah_1_1_3_opens_with_the_word_of_the_lord_in_her_portuguese() -> None:
    assert portuguese_titles()["J01"]["S1"] == "A palavra do SENHOR vem a Jonas"
