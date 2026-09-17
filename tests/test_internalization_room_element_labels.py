"""What a facilitator reads on a bead, in the three languages the Desk offers.

Every test here drives the public loader and asserts on the text itself. None asserts on
where the catalogue lives, on the shape of the file behind it, or on how the join is made.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError, register_exception_handlers
from app.models.internalization_room import LabelledElement
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.canon.labels import (
    LABELS_DIR,
    LANGUAGES,
    PENDING_COVERAGE_STATUS,
    ElementLabelsBroken,
    labelled_elements,
    legend,
)
from app.services.internalization_room.coverage import CoverageStatus

PILOT = ("P01", "P02", "P05", "P14")

#: A passage of no book. The refusal that is genuinely about the request.
NOT_A_PASSAGE = "P99"


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

    @app.get("/they-asked-for-a-passage-that-is-not-one")
    def they_asked_for_a_passage_that_is_not_one():
        return labelled_elements(NOT_A_PASSAGE)

    client = TestClient(app, raise_server_exceptions=False)

    broken = client.get("/ours-is-broken")
    assert broken.status_code == 500
    assert "scene:1" not in broken.text

    asked = client.get("/they-asked-for-a-passage-that-is-not-one")
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


def test_a_passage_this_book_does_not_have_is_still_about_what_was_asked_for():
    """The one refusal that is genuinely about the request keeps being told apart from ours.

    ENG-451 moved which request that is. It used to be a passage nobody had translated,
    which turned out to be ten of Ruth's fourteen and to be reachable by any team that
    walks the book — a whole history refused because one conversation happened in P07. A
    passage the canon does not have at all is the refusal that is really about the ask.
    """
    with pytest.raises(ValidationError) as refused:
        labelled_elements(NOT_A_PASSAGE)

    assert not isinstance(refused.value, ElementLabelsBroken)


# ENG-451 — outside the pilot a bead is still named, and says what it does not have.


@pytest.mark.parametrize(
    "pericope_num",
    [p for p in (f"P{n:02d}" for n in range(1, 15)) if p not in PILOT],
)
def test_a_passage_outside_the_pilot_is_named_rather_than_refused(pericope_num):
    """Ten of the fourteen, and D-03 walks every team through all of them on its own.

    This was a refusal until ENG-451, which is a whole session history 400ing because one
    conversation happened in a passage nobody has translated yet.
    """
    named = labelled_elements(pericope_num)

    assert {element.key for element in named} == {
        element.key for element in elements_for(pericope_num)
    }
    assert all(element.label_en.strip() for element in named)


@pytest.mark.parametrize(
    "pericope_num",
    [p for p in (f"P{n:02d}" for n in range(1, 15)) if p not in PILOT],
)
def test_outside_the_pilot_portuguese_and_spanish_are_absent_and_not_english(pericope_num):
    """The promise `LabelledElement` cites: pt and es arrive missing, never machine-filled.

    English comes almost free from the canon and the other two are translation work — so
    the honest answer for an untranslated passage is nothing at all, and the Desk's own
    `CoverageLabels` is `{ pt: string | null, en: string, es: string | null }` for exactly
    this. Filling them with the English would put a sentence a facilitator does not read in
    front of them and call it their language.
    """
    for element in labelled_elements(pericope_num):
        assert element.label_pt is None
        assert element.label_es is None


def test_inside_the_pilot_nothing_moved():
    """The four translated passages still carry all three, or the fallback ate them."""
    for element in labelled_elements("P01"):
        assert element.label_pt and element.label_en and element.label_es


def test_a_passage_the_catalogue_does_not_have_still_falls_back_to_the_canon(tmp_path):
    """The declared limit closed, and the path it described did not.

    This case asserted that P03's preservation rules arrive as the canon's own ALL_CAPS text —
    the gap ENG-442 declared rather than hid, promising it would close "when a translator
    reaches those ten passages". A translator reached them, so the assertion is now false of
    the shipped catalogue and would be a lie about the product.

    What has to stay is the mechanism, because it is what serves a book nobody has written a
    catalogue for at all. So the same property is asserted where it is still true: against a
    catalogue with the passage taken out.
    """
    catalogue = tmp_path / "element-labels"
    catalogue.mkdir()
    shutil.copy(_shipped() / "legend.json", catalogue / "legend.json")
    written = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    del written["P03"]
    (catalogue / "ruth.json").write_text(json.dumps(written), encoding="utf-8")

    named = labelled_elements("P03", catalogue_dir=catalogue)
    from_the_canon = {element.key: element.label for element in elements_for("P03")}

    assert all(element.label_pt is None and element.label_es is None for element in named)
    assert all(element.label_en == from_the_canon[element.key] for element in named)


def test_a_passage_translated_into_the_catalogue_is_read_from_it_without_a_second_edit(
    tmp_path,
):
    """The catalogue is the only record of which passages are translated.

    A hand-kept list of them beside it is the same fact written twice, and it can only drift
    in the dangerous direction: the day somebody writes P03 into `ruth.json` and does not
    touch the list, the passage goes on being answered from the canon with `label_pt=None`
    and the translation sitting right there unread. That is the silent fallback this module
    exists to prevent, and nothing anywhere would go red.

    So the catalogue is asked directly. This takes a passage back out of a copy of it, puts it
    in again with three languages, and requires that the loader find it with no other change.

    It used to pick a passage the shipped catalogue did not have. **There is no longer one** —
    all fourteen are in it since the ten were written — so the passage is removed first. That
    is not a weakening: what the case is about is the loader consulting the catalogue rather
    than a list, and removing and re-adding exercises exactly that, on data the case controls.
    """
    catalogue = tmp_path / "element-labels"
    catalogue.mkdir()
    shutil.copy(LABELS_DIR / "legend.json", catalogue / "legend.json")
    written = json.loads((LABELS_DIR / "ruth.json").read_text(encoding="utf-8"))
    newly = "P03"
    del written[newly]
    assert newly not in written
    written[newly] = {
        element.key: {
            "pt": f"pt {element.key}",
            "en": f"en {element.key}",
            "es": f"es {element.key}",
        }
        for element in elements_for(newly)
    }
    (catalogue / "ruth.json").write_text(json.dumps(written), encoding="utf-8")

    named = labelled_elements(newly, catalogue_dir=catalogue)

    assert all(element.label_pt and element.label_es for element in named), (
        "the catalogue has this passage and the loader answered from the canon anyway"
    )


# ------------------------------- the ten passages nobody had translated, and what let them in


TEN = [p for p in (f"P{n:02d}" for n in range(1, 15)) if p not in PILOT]


def _with(pericope_num: str, entry: dict, tmp_path):
    """A copy of the shipped catalogue with one passage's entry replaced."""
    catalogue = tmp_path / "element-labels"
    catalogue.mkdir(exist_ok=True)
    shutil.copy(_shipped() / "legend.json", catalogue / "legend.json")
    written = json.loads((_shipped() / "ruth.json").read_text(encoding="utf-8"))
    written[pericope_num] = entry
    (catalogue / "ruth.json").write_text(json.dumps(written), encoding="utf-8")
    return catalogue


def test_a_label_with_no_portuguese_is_served_absent_rather_than_refused(tmp_path):
    """The loader stopped contradicting the model it fills.

    `LabelledElement` types `label_pt` and `label_es` as `str | None` — ENG-442 established
    that the two are translation work and may be missing. `_text` went on raising for any
    empty language, which was the right rule **before** that and stopped being it after: a
    catalogue entry written in English alone is not a holed file, it is an untranslated
    passage that somebody finally named.

    Measured before the fix: dropping the ten passages' English into `ruth.json` turned ten
    passages that answered from the canon into `ElementLabelsBroken`, which carries no handler
    and is a 500.
    """
    only_english = {
        element.key: {"pt": None, "en": f"en {element.key}", "es": None}
        for element in elements_for("P03")
    }

    named = labelled_elements("P03", catalogue_dir=_with("P03", only_english, tmp_path))

    assert {element.key for element in named} == {e.key for e in elements_for("P03")}
    assert all(element.label_en.startswith("en ") for element in named)
    assert all(element.label_pt is None and element.label_es is None for element in named)


def test_the_permission_does_not_reach_english(tmp_path):
    """The half that must not move with it: `label_en` is still required.

    Without this the fix reads as "empty labels are fine now", and a catalogue entry with no
    English at all would serve a bead with nothing on it — which is the ALL_CAPS identifier
    problem again, one step worse, because there would not even be an identifier.
    """
    no_english = {
        element.key: {"pt": "algo", "en": None, "es": "algo"} for element in elements_for("P03")
    }

    with pytest.raises(ElementLabelsBroken) as refused:
        labelled_elements("P03", catalogue_dir=_with("P03", no_english, tmp_path))

    assert "en" in str(refused.value)


def test_a_key_the_catalogue_names_with_nothing_at_all_is_still_our_file_being_wrong(
    tmp_path,
):
    """An entry present and empty in all three is a holed file, not an untranslated passage.

    The difference is the whole point of the permission: *absent Portuguese* is a passage
    waiting for a translator, and *absent everything* is our own file. Only one of the two is
    allowed through.
    """
    nothing = {element.key: {"pt": None, "en": None, "es": None} for element in elements_for("P03")}

    with pytest.raises(ElementLabelsBroken):
        labelled_elements("P03", catalogue_dir=_with("P03", nothing, tmp_path))


@pytest.mark.parametrize("pericope_num", TEN)
def test_the_ten_are_read_from_the_catalogue_and_not_from_the_canon(pericope_num):
    """The case without which this slice changes nothing and still passes.

    "The ten carry labels" is green while the loader is still falling back to the canon —
    that path has always answered `label_en`. What separates the two is *which* English
    arrives, and the difference is exactly what a facilitator sees: the canon's own
    `Element.label` for a preservation rule is `KIND: note` in ALL_CAPS and for a significant
    absence is a paragraph of up to 443 characters.

    So this asserts the label is **not** the canon's, on the beads where the canon is worst.
    """
    from_the_canon = {element.key: element.label for element in elements_for(pericope_num)}
    hardest = [
        element
        for element in labelled_elements(pericope_num)
        if element.kind in (ElementKind.PRESERVED, ElementKind.ABSENCE)
    ]

    assert hardest, f"{pericope_num} has neither a rule nor an absence; pick another"
    for element in hardest:
        assert element.label_en != from_the_canon[element.key], (
            f"{pericope_num} {element.key} is still the canon's own text"
        )


@pytest.mark.parametrize("pericope_num", TEN)
def test_the_ten_keep_the_promises_the_pilot_keeps(pericope_num):
    """Zero Hebrew, no wiki syntax, no shouted identifier, nothing longer than a bead holds.

    The pilot's own cases assert these over the four; the ten arrive under the same rules or
    they arrive as a second class of label that nobody is checking.

    **The wiki assert is here because it was missing and the one defect in the 264 hid that.**
    `The house of [[PL_ISRAEL-Israel]] Israel` was caught by the shouted-identifier rule, which
    made this loop look like it covered wiki syntax when it did not — `[[B3-Naomi]]` carries no
    shouted run and would have gone through both asserts. The pilot's own case checks `[[`, and
    it is parametrized over the four.
    """
    hebrew = re.compile(r"[֐-׿]")

    for element in labelled_elements(pericope_num):
        text = element.label_en
        assert not hebrew.search(text), f"{pericope_num} {element.key} shows Hebrew: {text}"
        assert not _SHOUTED.search(text.replace("YHWH", "")), (
            f"{pericope_num} {element.key} shows an identifier: {text}"
        )
        assert "[[" not in text and "]]" not in text, (
            f"{pericope_num} {element.key} shows wiki syntax: {text}"
        )
        assert len(text) <= 45, f"{pericope_num} {element.key} is {len(text)} chars: {text}"


@pytest.mark.parametrize("pericope_num", TEN)
def test_two_beads_of_the_ten_never_read_the_same_on_one_screen(pericope_num):
    """The defect the writer measured twice and found again on the mechanical pass."""
    seen: dict[str, str] = {}
    for element in labelled_elements(pericope_num):
        clash = seen.get(element.label_en)
        assert clash is None, (
            f"{pericope_num}: {element.key} and {clash} both read {element.label_en!r}"
        )
        seen[element.label_en] = element.key


@pytest.mark.parametrize("pericope_num", TEN)
def test_portuguese_and_spanish_stay_absent_for_the_ten(pericope_num):
    """Naming them in English did not machine-fill the other two, which is the whole refusal."""
    for element in labelled_elements(pericope_num):
        assert element.label_pt is None
        assert element.label_es is None
