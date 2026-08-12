from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon.book_material import (
    build_book_material,
    pericope_digest,
    preservation_rules,
    story_so_far,
)
from app.services.internalization_room.canon.parse_map import (
    MAPS_DIR,
    load_book,
    load_map,
    parse_map,
)

GOLDEN = Path(__file__).parent / "fixtures" / "BOOK-PANORAMA-MATERIAL-RUTH.md"


def test_every_ruth_pericope_parses() -> None:
    maps = load_book("Ruth")

    assert len(maps) == 14
    assert [m.pericope_num for m in maps] == [f"P{i:02d}" for i in range(1, 15)]


def test_the_corpus_shape_is_what_the_canon_says() -> None:
    """Counts cross-checked against the vendored files: 42 scenes, one absence each."""
    maps = load_book("Ruth")

    assert sum(len(m.scenes) for m in maps) == 42
    assert sum(1 for m in maps for s in m.scenes if s.absence) == 42


def test_entities_without_a_wikilink_are_still_entities() -> None:
    """24 of the corpus's 350 entities are unlinked implied places (`the road`)."""
    entities = [
        entity
        for m in load_book("Ruth")
        for s in m.scenes
        for entity in s.beings + s.places + s.objects + s.times
    ]

    assert len(entities) == 350
    assert any(entity.code is None for entity in entities)


def test_an_unapproved_map_is_refused_not_degraded() -> None:
    text = (
        (MAPS_DIR / "P03-Ruth-1-15-18.md")
        .read_text()
        .replace('status: "complete"', 'status: "draft"')
    )

    with pytest.raises(ValidationError, match="not approved canon"):
        parse_map(text, source="P03-draft")


def test_poetry_is_refused_until_the_project_enables_it() -> None:
    text = (
        (MAPS_DIR / "P03-Ruth-1-15-18.md")
        .read_text()
        .replace('genre-group: "NARRATIVE"', 'genre-group: "POETIC_SUNG"')
    )

    with pytest.raises(ValidationError, match="not enabled"):
        parse_map(text, source="T13-like")


def test_a_map_missing_its_arc_section_raises() -> None:
    """A half-parsed map would ground the Guide on a partial passage, unnoticed."""
    text = (MAPS_DIR / "P03-Ruth-1-15-18.md").read_text().replace("### 2.1 ", "### 2.9 ")

    with pytest.raises(ValidationError, match="arc prose"):
        parse_map(text, source="P03-no-arc")


def test_the_arc_section_is_found_by_its_number_not_its_title() -> None:
    """The section number is the stable part of the grammar; the prose title may be reworded
    upstream without that meaning the map lost its arc."""
    text = (
        (MAPS_DIR / "P03-Ruth-1-15-18.md")
        .read_text()
        .replace("### 2.1 Prose Arc / Shape / Argument / Burden / Concern", "### 2.1 Arc")
    )

    assert parse_map(text, source="P03-retitled").arc_prose == load_map("P03").arc_prose


def test_the_digest_is_verbatim_from_the_map() -> None:
    p03 = load_map("P03")
    digest = pericope_digest(p03)

    assert p03.arc_prose in digest
    assert digest.startswith(f"**{p03.reference}** {chr(8212)} {p03.title}")
    assert digest.endswith("Scenes: Naomi's last appeal; Ruth's vow; Naomi's silence.")


def test_only_do_not_decide_rules_reach_the_preservation_set() -> None:
    rules = preservation_rules("Ruth")

    assert len(rules) == 32
    # P01 R1 is `required_in_audit` but not `do_not_decide` — a preference, not a constraint.
    assert not any(r.pericope == "P01" and r.rule_id == "R1" for r in rules)


def test_the_book_material_matches_the_projects_own_rendering() -> None:
    """Byte-for-byte against the file the project generated from canon.

    If this fails, the parser is wrong — not the fixture.
    """
    assert build_book_material("Ruth") == GOLDEN.read_text(encoding="utf-8")


def test_story_so_far_cannot_leak_a_later_disclosure() -> None:
    """References come from canon rather than literals so the test cannot drift from it."""
    by_id = {m.pericope_num: m for m in load_book("Ruth")}
    earlier = story_so_far("Ruth", "P03")

    assert by_id["P01"].reference in earlier
    assert by_id["P02"].reference in earlier
    for later_id in ("P03", "P12", "P13", "P14"):
        assert by_id[later_id].reference not in earlier
        assert by_id[later_id].arc_prose not in earlier
    assert "Obed" not in earlier


def test_the_first_pericope_has_no_story_behind_it() -> None:
    assert story_so_far("Ruth", "P01") == ""
