from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon import book_material, parse_map
from tests.canon_harness import A_FABLE_LOG_WITH_A_COMPLETE_REGISTER, forget_the_canon


@pytest.fixture
def a_second_book_that_would_walk_in_every_other_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    ruth_map = (parse_map.MAPS_DIR / "P03-Ruth-1-15-18.md").read_text(encoding="utf-8")
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-15-18.md").write_text(
        ruth_map.replace("P03", "Q01").replace("Ruth 1:15", "Fable 1:15"), encoding="utf-8"
    )
    (logs / "Q01-Fable-1-15-18-COMPILATION-LOG.md").write_text(
        A_FABLE_LOG_WITH_A_COMPLETE_REGISTER, encoding="utf-8"
    )
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    forget_the_canon()
    yield "Fable"
    forget_the_canon()


def test_a_book_that_is_not_ruth_is_refused_at_the_gate_even_when_it_is_vendored_whole(
    a_second_book_that_would_walk_in_every_other_way: str,
) -> None:
    meaning_map = parse_map.load_map("Q01")

    reason = book_material.unwalkable(meaning_map)

    assert reason is not None
    assert a_second_book_that_would_walk_in_every_other_way in reason
    assert "not served" in reason


def test_the_same_book_walks_the_day_the_lock_names_it(
    a_second_book_that_would_walk_in_every_other_way: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Fable"}))

    assert book_material.unwalkable(parse_map.load_map("Q01")) is None
    assert "THE BOOK OF FABLE" in book_material.build_book_material("Fable")


def test_the_panorama_of_a_book_that_is_not_ruth_is_refused(
    a_second_book_that_would_walk_in_every_other_way: str,
) -> None:
    with pytest.raises(ValidationError, match="not served"):
        book_material.build_book_material(a_second_book_that_would_walk_in_every_other_way)
