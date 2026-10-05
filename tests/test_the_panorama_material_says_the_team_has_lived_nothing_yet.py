from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.internalization_room.canon import book_material, parse_map

HER_SENTENCE = (
    "The team has not yet lived any passage: every one of these still lies ahead of them. "
    "The panorama must honor each — never state, pair, name, or attribute what a passage "
    "withholds until its moment."
)


def test_the_ruth_notes_open_with_her_sentence_that_the_team_has_lived_nothing() -> None:
    material = book_material.build_book_material("Ruth")

    assert HER_SENTENCE in material
    assert material.index("## PRESERVATION NOTES") < material.index(HER_SENTENCE)


@pytest.fixture
def a_book_whose_logs_record_no_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-1-2.md").write_text(
        (parse_map.MAPS_DIR / "P03-Ruth-1-15-18.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    for cached in (
        parse_map.load_map,
        parse_map.load_book,
        book_material.preservation_rules,
        book_material._register_complete,
    ):
        cached.cache_clear()
    yield "Fable"
    for cached in (
        parse_map.load_map,
        parse_map.load_book,
        book_material.preservation_rules,
        book_material._register_complete,
    ):
        cached.cache_clear()


def test_a_book_with_no_recorded_rule_gets_none_recorded_instead_of_failing(
    a_book_whose_logs_record_no_rule: str,
) -> None:
    material = book_material.build_book_material(a_book_whose_logs_record_no_rule)

    assert material.endswith(f"{HER_SENTENCE}\n\n- (none recorded)\n")
