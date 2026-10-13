from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.progression import resolve
from tests.canon_harness import (
    A_FABLE_LOG_WITH_A_COMPLETE_REGISTER,
    a_fable_map,
    forget_the_canon,
)


@pytest.fixture
def a_book_whose_first_map_is_marked_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-1-2.md").write_text(a_fable_map(1, status="pending"), encoding="utf-8")
    (maps / "Q02-Fable-1-2-3.md").write_text(a_fable_map(2), encoding="utf-8")
    for stem in ("Q01-Fable-1-1-2", "Q02-Fable-1-2-3"):
        (logs / f"{stem}-COMPILATION-LOG.md").write_text(
            A_FABLE_LOG_WITH_A_COMPLETE_REGISTER, encoding="utf-8"
        )
    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Fable"}))
    forget_the_canon()
    yield "Fable"
    forget_the_canon()


def test_a_map_marked_pending_is_read_into_the_story_so_far_of_the_passage_after_it(
    a_book_whose_first_map_is_marked_pending: str,
) -> None:
    told = book_material.story_so_far(a_book_whose_first_map_is_marked_pending, "Q02")

    assert "**Fable 1:1-2**" in told


def test_a_pending_status_alone_does_not_close_its_passage(
    a_book_whose_first_map_is_marked_pending: str,
) -> None:
    assert book_material.unwalkable(parse_map.load_map("Q01")) is None
    assert resolve(set(), book=a_book_whose_first_map_is_marked_pending) == "Q01"
