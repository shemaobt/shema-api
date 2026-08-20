"""What a facilitator reads on a bead, in the three languages the Desk offers.

Every test here drives the public loader and asserts on the text itself. None asserts on
where the catalogue lives, on the shape of the file behind it, or on how the join is made.
"""

from __future__ import annotations

import json
import re

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.canon.labels import (
    LANGUAGES,
    PENDING_COVERAGE_STATUS,
    TRANSLATED_PERICOPES,
    labelled_elements,
    legend,
)
from app.services.internalization_room.coverage import CoverageStatus

PILOT = ("P01", "P02", "P05", "P14")

#: An ALL_CAPS run is how a technical identifier reaches the screen —
#: `STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY`. YHWH is a name a facilitator says out loud.
_SHOUTED = re.compile(r"[A-Z][A-Z0-9_]{4,}")


def _every_label(pericope_num: str) -> list[tuple[str, str, str]]:
    return [
        (element.key, language, getattr(element, f"label_{language}"))
        for element in labelled_elements(pericope_num)
        for language in LANGUAGES
    ]


@pytest.mark.parametrize("pericope_num", PILOT)
def test_every_element_of_a_pilot_pericope_is_named_in_every_language(pericope_num):
    named = {element.key: element for element in labelled_elements(pericope_num)}

    assert set(named) == {element.key for element in elements_for(pericope_num)}
    for key, language, text in _every_label(pericope_num):
        assert text.strip(), f"{pericope_num} {key} has no {language} label"


@pytest.mark.parametrize("pericope_num", PILOT)
def test_no_label_shows_the_facilitator_a_technical_identifier(pericope_num):
    for key, language, text in _every_label(pericope_num):
        assert not _SHOUTED.search(text.replace("YHWH", "")), (
            f"{pericope_num} {key} {language} shows an identifier: {text}"
        )
        assert "[[" not in text and "]]" not in text, (
            f"{pericope_num} {key} {language} shows wiki syntax: {text}"
        )


def test_every_coverage_state_and_element_kind_is_named_in_every_language():
    """Driven by the enums, so a state added elsewhere cannot ship without a name.

    ENG-441 adds a fourth `CoverageStatus`. Walking a written list of three would have gone
    green over the hole and put a raw value in front of a facilitator.
    """
    named = legend()

    assert set(named.coverage_status) == {status.value for status in CoverageStatus}
    assert set(named.element_kind) == {kind.value for kind in ElementKind}
    for group in (named.coverage_status, named.element_kind):
        for value, texts in group.items():
            for language in LANGUAGES:
                assert texts[language].strip(), f"{value} has no {language} name"


def test_the_same_key_in_two_pericopes_carries_its_own_label():
    """`scene:1` is a different scene in every pericope; so is `absence:1` and `preserved:R3`."""
    first = {e.key: e.label_pt for e in labelled_elements("P01")}
    last = {e.key: e.label_pt for e in labelled_elements("P14")}

    assert first["scene:1"] != last["scene:1"]
    assert first["absence:1"] != last["absence:1"]


def test_a_hole_in_the_catalogue_is_refused_rather_than_filled_in(tmp_path):
    complete = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    holed = {p: {k: dict(v) for k, v in keys.items()} for p, keys in complete.items()}
    holed["P01"]["scene:1"]["es"] = ""
    (tmp_path / "ruth.json").write_text(json.dumps(holed), encoding="utf-8")
    (tmp_path / "legend.json").write_text(
        (_shipped() / "legend.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as refused:
        labelled_elements("P01", catalogue_dir=tmp_path)

    said = str(refused.value)
    assert "P01" in said and "scene:1" in said and "es" in said


def test_a_pericope_nobody_has_translated_is_refused_rather_than_answered_in_english():
    untranslated = next(
        f"P{n:02d}" for n in range(1, 15) if f"P{n:02d}" not in TRANSLATED_PERICOPES
    )

    with pytest.raises(ValidationError) as refused:
        labelled_elements(untranslated)

    assert untranslated in str(refused.value)


def _shipped():
    from app.services.internalization_room.canon.labels import LABELS_DIR

    return LABELS_DIR


def test_a_label_hung_on_a_key_the_canon_no_longer_has_is_refused(tmp_path):
    """`P02 / being:B2` is the live case: fixing the canon's parsing would change that key.

    A label left hanging on a key nobody serves any more is invisible from the screen — the
    pericope is still complete — so the loader has to be the thing that notices.
    """
    complete = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    orphaned = {p: dict(keys) for p, keys in complete.items()}
    orphaned["P01"]["being:B99"] = {"pt": "Alguém", "en": "Someone", "es": "Alguien"}
    (tmp_path / "ruth.json").write_text(json.dumps(orphaned), encoding="utf-8")
    (tmp_path / "legend.json").write_text(
        (_shipped() / "legend.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as refused:
        labelled_elements("P01", catalogue_dir=tmp_path)

    assert "being:B99" in str(refused.value)


def test_a_state_named_before_it_exists_is_declared_rather_than_merely_tolerated():
    """ENG-441 brings `partially_engaged`, and its label is written here before it lands.

    The declaration is what stops the set rotting: once the value is in `CoverageStatus` it
    is no longer pending, and a name left in the set would be a promise about an enum that
    has moved on.
    """
    live = {status.value for status in CoverageStatus}

    assert PENDING_COVERAGE_STATUS.isdisjoint(live), (
        f"{PENDING_COVERAGE_STATUS & live} is in CoverageStatus now; drop it from the set"
    )
    assert set(legend().coverage_status) == live


def test_a_name_for_something_that_is_not_a_state_at_all_is_refused(tmp_path):
    named = json.loads((_shipped() / "legend.json").read_text(encoding="utf-8"))
    named["coverage_status"]["nearly_there"] = {"pt": "Quase", "en": "Nearly", "es": "Casi"}
    (tmp_path / "legend.json").write_text(json.dumps(named), encoding="utf-8")

    with pytest.raises(ValidationError) as refused:
        legend(catalogue_dir=tmp_path)

    assert "nearly_there" in str(refused.value)
