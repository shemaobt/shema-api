"""What a facilitator reads on a bead, in the three languages the Desk offers.

Every test here drives the public loader and asserts on the text itself. None asserts on
where the catalogue lives, on the shape of the file behind it, or on how the join is made.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError, register_exception_handlers
from app.models.internalization_room import LabelledElement
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.canon.labels import (
    LANGUAGES,
    PENDING_COVERAGE_STATUS,
    TRANSLATED_PERICOPES,
    ElementLabelsBroken,
    labelled_elements,
    legend,
)
from app.services.internalization_room.coverage import CoverageStatus

PILOT = ("P01", "P02", "P05", "P14")


@pytest.fixture
def holed_catalogue(tmp_path):
    """A copy of the shipped catalogue with one language emptied out of one element."""
    complete = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    holed = {p: {k: dict(v) for k, v in keys.items()} for p, keys in complete.items()}
    holed["P01"]["scene:1"]["es"] = ""
    (tmp_path / "ruth.json").write_text(json.dumps(holed), encoding="utf-8")
    (tmp_path / "legend.json").write_text(
        (_shipped() / "legend.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


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

    with pytest.raises(ElementLabelsBroken) as refused:
        labelled_elements("P01", catalogue_dir=tmp_path)

    said = str(refused.value)
    assert "P01" in said and "scene:1" in said and "es" in said


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

    with pytest.raises(ElementLabelsBroken) as refused:
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

    with pytest.raises(ElementLabelsBroken) as refused:
        legend(catalogue_dir=tmp_path)

    assert "nearly_there" in str(refused.value)


def test_a_catalogue_that_is_not_a_catalogue_at_all_is_refused(tmp_path):
    """A file that parses as JSON but is not an object of entries.

    Without this the shape is never checked and the first thing to go wrong is a confusing
    failure far from the file that caused it.
    """
    (tmp_path / "ruth.json").write_text('["P01"]', encoding="utf-8")

    with pytest.raises(ElementLabelsBroken) as refused:
        labelled_elements("P01", catalogue_dir=tmp_path)

    assert "ruth.json" in str(refused.value)


@pytest.mark.parametrize("pericope_num", PILOT)
def test_two_beads_on_one_screen_never_read_the_same(pericope_num):
    """A necklace is read across, so a repeated label is two beads a facilitator cannot tell apart.

    P14 shipped four of these: the canon separates `CB_0047-Obed-Name` from the man, and the
    first translation flattened both onto "Obed". Nothing else in the slice can see it — the
    key is present either way and every label is a real sentence.
    """
    for language in LANGUAGES:
        said: dict[str, str] = {}
        for element in labelled_elements(pericope_num):
            text = getattr(element, f"label_{language}")
            clash = said.get(text)
            assert clash is None, (
                f"{pericope_num} {language}: {clash} and {element.key} both read {text!r}"
            )
            said[text] = element.key


def test_a_language_nobody_added_a_field_for_is_refused_rather_than_dropped():
    """`LANGUAGES` growing without the model growing is a label required and then discarded.

    Pydantic ignores an unknown keyword by default, so the loader would demand the new label,
    raise if it were missing, and then throw it away — a hole in the one module whose whole
    posture is that a hole is refused.
    """
    with pytest.raises(PydanticValidationError):
        LabelledElement(
            key="scene:1",
            kind=ElementKind.SCENE,
            scene=1,
            label_pt="a",
            label_en="b",
            label_es="c",
            label_fr="d",
        )


def test_the_kind_on_the_wire_is_the_closed_set_and_not_any_string():
    with pytest.raises(PydanticValidationError):
        LabelledElement(
            key="scene:1",
            kind="scenery",
            scene=1,
            label_pt="a",
            label_en="b",
            label_es="c",
        )


def test_the_two_refusals_do_not_answer_the_same_thing_on_the_wire(tmp_path, holed_catalogue):
    """The status code is the behaviour here, so the status code is what is measured.

    Asserting on the class hierarchy would go green if `ElementLabelsBroken` were ever made
    a `ValidationError` again — which is precisely the defect, and it is invisible from
    inside the service. Measured before the split: both answered `400 BAD_REQUEST` with the
    same code, and ours put `P01 scene:1` in the caller's error body.
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/ours-is-broken")
    def ours_is_broken():
        return labelled_elements("P01", catalogue_dir=holed_catalogue)

    @app.get("/they-asked-for-p03")
    def they_asked_for_p03():
        return labelled_elements("P03")

    client = TestClient(app, raise_server_exceptions=False)

    broken = client.get("/ours-is-broken")
    assert broken.status_code == 500
    assert "scene:1" not in broken.text

    asked = client.get("/they-asked-for-p03")
    assert asked.status_code == 400


def test_our_own_catalogue_being_broken_does_not_read_as_the_caller_s_mistake(tmp_path):
    """A shipped file with a hole in it is our failure and has to sound like one.

    `ValidationError` is answered 400 with its message in the body, so a broken catalogue
    reached whoever called the coverage route as if their request were malformed — and put
    `P01 scene:1` in front of them to debug. Measured before this: both this case and an
    untranslated pericope answered `400 BAD_REQUEST`, indistinguishably.
    """
    complete = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    holed = {p: {k: dict(v) for k, v in keys.items()} for p, keys in complete.items()}
    holed["P01"]["scene:1"]["es"] = ""
    (tmp_path / "ruth.json").write_text(json.dumps(holed), encoding="utf-8")
    (tmp_path / "legend.json").write_text(
        (_shipped() / "legend.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ElementLabelsBroken):
        labelled_elements("P01", catalogue_dir=tmp_path)


def test_a_pericope_nobody_translated_is_still_about_what_was_asked_for():
    """The one refusal that is genuinely about the request keeps being told apart from ours."""
    untranslated = next(
        f"P{n:02d}" for n in range(1, 15) if f"P{n:02d}" not in TRANSLATED_PERICOPES
    )

    with pytest.raises(ValidationError) as refused:
        labelled_elements(untranslated)

    assert not isinstance(refused.value, ElementLabelsBroken)
